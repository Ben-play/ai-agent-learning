"""Phase 5: offline read-only loop and local draft workflow."""

import hashlib
import json
import runpy
import sqlite3
from collections.abc import Callable
from contextlib import closing, contextmanager
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from tempfile import TemporaryDirectory

PHASE4_MAIN = Path(__file__).resolve().parents[2] / "phase4-prompt-context" / "main.py"
QUESTION = "导出文件保留多久？"
REPHRASE = "导出文件有效期？"


def _phase4(question, *, intent="answer"):
    return runpy.run_path(str(PHASE4_MAIN))["run"](question, intent=intent)


class Task(Enum):
    EVIDENCE_QA = "evidence_qa"


@dataclass(frozen=True)
class ReadCall:
    task: Task
    question: str


@dataclass(frozen=True)
class ReadResult:
    states: tuple[str, ...]
    calls: int
    answer: str | None = None
    source_ids: tuple[str, ...] = ()

    @property
    def status(self):
        return self.states[-1]


def run_loop(first: ReadCall, *, dynamic=True, budget=2) -> ReadResult:
    """Count Phase 4 dispatches, not its internal fixture adapter calls."""
    if type(budget) is not int or not 0 <= budget <= 2:
        raise ValueError("read budget must be an integer from 0 to 2")
    states, calls, decision = ["pending"], 0, first
    while calls < budget:
        if (type(decision) is not ReadCall or decision.task is not Task.EVIDENCE_QA
                or type(decision.question) is not str or not decision.question.strip()):
            return ReadResult((*states, "failed"), calls)
        calls += 1
        evidence = _phase4(decision.question)
        if evidence["status"] == "answered":
            return ReadResult((*states, "complete"), calls, evidence["answer"],
                              tuple(row["source_id"] for row in evidence["citations"]))
        if not (dynamic and evidence["status"] == "needs_evidence" and decision.question == REPHRASE):
            return ReadResult((*states, "failed"), calls)
        # The scripted policy proposes one known rephrase. The host still checks budget.
        decision = ReadCall(Task.EVIDENCE_QA, QUESTION)
        states.append("pending")
    return ReadResult((*states, "exhausted"), calls)


SAVE_LOCAL = "save_local_draft"


@dataclass(frozen=True)
class Actor:
    tenant: str
    name: str


@dataclass(frozen=True)
class Binding:
    actor: Actor
    job: str
    version: int
    digest: str
    action: str = SAVE_LOCAL


@dataclass(frozen=True)
class Draft:
    title: str
    body: str
    source_ids: tuple[str, ...]


@dataclass(frozen=True)
class Checkpoint:
    binding: Binding
    draft: Draft
    status: str
    op_id: str | None


class Review(Enum):
    APPROVE = "approve"
    DENY = "deny"


@dataclass(frozen=True)
class SaveResult:
    status: str
    op_id: str | None = None
    draft: Draft | None = None


class LostReply(RuntimeError):
    """The transaction committed, but the caller did not receive its result."""


def _digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _key(actor, job):
    if type(actor) is not Actor or any(type(x) is not str or not x.strip()
                                       for x in (actor.tenant, actor.name, job)):
        raise ValueError("tenant, actor and job must be nonempty strings")
    return actor.tenant, actor.name, job


def _draft(payload):
    title, body, source_ids = json.loads(payload)
    return Draft(title, body, tuple(source_ids))


@contextmanager
def open_store(path: Path, *, on_draft_write_attempt: Callable[[str], None] | None = None,
               before_stage: Callable[[Draft], None] | None = None):
    """Open a host-owned SQLite store.

    The optional host observer receives the operation ID just before the draft
    INSERT inside the transaction; it does not observe checkpoint writes.
    The optional host validator receives the actual draft before the pending
    transaction and may raise to withhold it; it cannot replace the payload.
    """
    with closing(sqlite3.connect(path)) as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS checkpoints (
                tenant TEXT NOT NULL, actor TEXT NOT NULL, job TEXT NOT NULL,
                version INTEGER NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL, op_id TEXT,
                PRIMARY KEY (tenant, actor, job)
            );
            CREATE TABLE IF NOT EXISTS saved_drafts (
                op_id TEXT PRIMARY KEY NOT NULL,
                tenant TEXT NOT NULL, actor TEXT NOT NULL, job TEXT NOT NULL, payload TEXT NOT NULL
            );
        """)
        yield DraftStore(db, on_draft_write_attempt=on_draft_write_attempt, before_stage=before_stage)


class DraftStore:
    def __init__(self, db, *, on_draft_write_attempt: Callable[[str], None] | None = None,
                 before_stage: Callable[[Draft], None] | None = None):
        self._db = db
        self._on_draft_write_attempt = on_draft_write_attempt
        self._before_stage = before_stage

    def checkpoint(self, actor: Actor, job: str) -> Checkpoint | None:
        row = self._db.execute(
            "SELECT version, payload, status, op_id FROM checkpoints WHERE tenant=? AND actor=? AND job=?",
            _key(actor, job),
        ).fetchone()
        if row is None:
            return None
        version, payload, status, op_id = row
        return Checkpoint(Binding(actor, job, version, _digest(payload)), _draft(payload), status, op_id)

    def stage(self, actor: Actor, job: str, version: int, question: str) -> Checkpoint:
        """Prepare or replace a pending draft without saving it."""
        key = _key(actor, job)
        if type(version) is not int or not 1 <= version < 2**63:
            raise ValueError("invalid draft version")
        proposal = _phase4(question, intent="draft")
        if proposal["status"] != "drafted":
            raise ValueError("no evidence-backed draft")
        fields = proposal["draft"]
        draft = Draft(fields["title"], fields["body"], tuple(fields["source_ids"]))
        if self._before_stage is not None:
            self._before_stage(draft)
        payload = json.dumps([draft.title, draft.body, draft.source_ids], separators=(",", ":"))
        with self._db:
            self._db.execute("BEGIN IMMEDIATE")
            current = self.checkpoint(actor, job)
            if current and (current.status != "pending" or version <= current.binding.version):
                raise ValueError("only a newer version of a pending draft may be staged")
            self._db.execute("""
                INSERT INTO checkpoints VALUES (?, ?, ?, ?, ?, 'pending', NULL)
                ON CONFLICT (tenant, actor, job) DO UPDATE SET version=excluded.version, payload=excluded.payload
            """, (*key, version, payload))
            return self.checkpoint(actor, job)

    def saved_count(self, actor: Actor, job: str) -> int:
        row = self._db.execute(
            "SELECT COUNT(*) FROM saved_drafts WHERE tenant=? AND actor=? AND job=?", _key(actor, job)
        ).fetchone()
        return row[0]

    def _insert_draft(self, op_id: str, key: tuple[str, str, str]) -> None:
        if self._on_draft_write_attempt is not None:
            self._on_draft_write_attempt(op_id)
        self._db.execute("""
            INSERT INTO saved_drafts (op_id, tenant, actor, job, payload)
            SELECT ?, tenant, actor, job, payload FROM checkpoints WHERE tenant=? AND actor=? AND job=?
        """, (op_id, *key))

    def resume(self, actor: Actor, job: str, binding: Binding, review: Review | None, *, lose_reply=False) -> SaveResult:
        key = _key(actor, job)
        with self._db:
            self._db.execute("BEGIN IMMEDIATE")
            current = self.checkpoint(actor, job)
            if (current is None or type(binding) is not Binding or type(binding.version) is not int
                    or binding != current.binding):
                return SaveResult("rejected")
            if current.status == "denied":
                return SaveResult("denied")
            if review is Review.DENY and current.status == "pending":
                self._db.execute("UPDATE checkpoints SET status='denied' WHERE tenant=? AND actor=? AND job=?", key)
                return SaveResult("denied")
            if review is not Review.APPROVE:
                return SaveResult("rejected")
            if current.status == "saved":
                row = self._db.execute(
                    "SELECT payload FROM saved_drafts WHERE op_id=? AND tenant=? AND actor=? AND job=?",
                    (current.op_id, *key),
                ).fetchone()
                if row is None or _digest(row[0]) != current.binding.digest:
                    return SaveResult("inconsistent")  # Stop for inspection; do not retry the write.
                return SaveResult("replayed", current.op_id, _draft(row[0]))
            if current.status != "pending":
                return SaveResult("inconsistent")
            op_id = _digest(json.dumps([SAVE_LOCAL, *key, binding.version, binding.digest]))
            self._insert_draft(op_id, key)
            self._db.execute(
                "UPDATE checkpoints SET status='saved', op_id=? WHERE tenant=? AND actor=? AND job=?", (op_id, *key)
            )
        # Deliberately outside the transaction: the local write and its result are already durable.
        if lose_reply:
            raise LostReply("local save committed; reply lost")
        return SaveResult("saved", op_id, current.draft)


def run_acceptance() -> dict:
    """Run the offline course fixtures quietly and return observed outcomes."""
    first = ReadCall(Task.EVIDENCE_QA, REPHRASE)
    baseline, dynamic, budget = run_loop(first, dynamic=False), run_loop(first), run_loop(first, budget=1)
    actor, other = Actor("demo-tenant", "reviewer"), Actor("other-tenant", "reviewer")
    attempts: list[str] = []
    write_attempts: dict[str, int] = {}

    @contextmanager
    def count_attempts(case: str):
        before = len(attempts)
        try:
            yield
        finally:
            write_attempts[case] = len(attempts) - before

    with TemporaryDirectory() as tmp:
        db = Path(tmp) / "harness.sqlite3"
        with open_store(db, on_draft_write_attempt=attempts.append) as store, count_attempts("pending"):
            old = store.stage(actor, "export", 1, "同步任务几点运行？")
            store.stage(actor, "export", 2, QUESTION)
            store.stage(other, "export", 2, QUESTION)
            denied = store.stage(actor, "denied-example", 1, QUESTION)
        with open_store(db, on_draft_write_attempt=attempts.append) as store:
            pending = store.checkpoint(actor, "export")
            with count_attempts("missing_review"):
                missing_review = store.resume(actor, "export", pending.binding, None)
            with count_attempts("unauthorized"):
                unauthorized = store.resume(other, "export", pending.binding, Review.APPROVE)
            with count_attempts("denied"):
                refused = store.resume(actor, "denied-example", denied.binding, Review.DENY)
            with count_attempts("changed"):
                changed = store.resume(actor, "export", old.binding, Review.APPROVE)
            if (store.saved_count(actor, "export") or store.saved_count(other, "export")
                    or store.saved_count(actor, "denied-example")):
                raise RuntimeError("draft saved before matching approval")
            try:
                with count_attempts("commit"):
                    store.resume(actor, "export", pending.binding, Review.APPROVE, lose_reply=True)
            except LostReply:
                pass
            else:
                raise RuntimeError("expected a lost reply after commit")
        with open_store(db, on_draft_write_attempt=attempts.append) as store:
            commit = store.checkpoint(actor, "export")
            if store.saved_count(actor, "export") != 1:
                raise RuntimeError("expected one saved draft after the lost reply")
            with count_attempts("replay"):
                replay = store.resume(actor, "export", pending.binding, Review.APPROVE)
            if not (commit.op_id and replay.op_id == commit.op_id and replay.draft == pending.draft):
                raise RuntimeError("replay did not return the original operation and draft")
            saved_count = store.saved_count(actor, "export")
    return {
        "baseline": {"status": baseline.status, "calls": baseline.calls},
        "dynamic": {"status": dynamic.status, "calls": dynamic.calls, "source_ids": list(dynamic.source_ids)},
        "budget": {"status": budget.status, "calls": budget.calls},
        "draft": {"pending": pending.status, "missing_review": missing_review.status,
                  "unauthorized": unauthorized.status, "denied": refused.status, "changed": changed.status,
                  "commit": commit.status, "replay": replay.status, "saved_count": saved_count,
                  "write_attempts": write_attempts},
    }


def main():
    result = run_acceptance()
    expected = {
        "baseline": {"status": "failed", "calls": 1},
        "dynamic": {"status": "complete", "calls": 2, "source_ids": ["KB-01", "KB-02"]},
        "budget": {"status": "exhausted", "calls": 1},
        "draft": {
            "pending": "pending", "missing_review": "rejected", "unauthorized": "rejected",
            "denied": "denied", "changed": "rejected", "commit": "saved", "replay": "replayed",
            "saved_count": 1,
            "write_attempts": {"pending": 0, "missing_review": 0, "unauthorized": 0,
                               "denied": 0, "changed": 0, "commit": 1, "replay": 0},
        },
    }
    if result != expected:
        raise SystemExit(f"PHASE5 HARNESS FAILED: {result}")
    print("PHASE5 HARNESS OK baseline=failed/1 dynamic=complete/2 budget=exhausted/1 draft=saved/replayed")


if __name__ == "__main__":
    main()
