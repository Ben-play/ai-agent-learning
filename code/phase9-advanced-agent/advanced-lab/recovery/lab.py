"""Fixed subprocess worker for the Phase 9 cancellation and receipt rehearsal."""

import argparse
from contextlib import closing, contextmanager
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
import runpy
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve()
CODE = HERE.parents[3]
RAG = runpy.run_path(str(CODE / "phase7-data-rag/rag-lab/lab.py"))
HARNESS = runpy.run_path(str(CODE / "phase5-agent-harness/harness-lab/main.py"))
ACTOR = HARNESS["Actor"]("support", "mei")
TERMS = {"schedule": "同步", "retention": "保留", "missing": "未收录的领取规则"}
COMMANDS = ("start", "advance", "approve", "cancel", "recover")
TERMINAL = {"cancelled", "exhausted", "saved", "needs_evidence"}
LOST_REPLY_EXIT = 19
VERSION = "long-task-fixture-v2"


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value):
    return sha256(value.encode("utf-8")).hexdigest()


def binding(job, payload):
    return encode(asdict(HARNESS["Binding"](ACTOR, job, 1, digest(payload))))


def evidence_for(job):
    with RAG["open_demo"]() as db:
        hits = db.search(ACTOR.tenant, ACTOR.name, RAG["Query"]((TERMS[job],)), k=1)
        if not hits:
            return None
        chunk = hits[0].chunk
        return encode([*chunk.key, chunk.text]) if db.source(ACTOR.tenant, ACTOR.name, chunk.key) == chunk else None


def current_evidence(payload):
    doc, version, locator, quote = json.loads(payload)
    with RAG["open_demo"]() as db:
        row = db.source(ACTOR.tenant, ACTOR.name, (doc, version, locator))
        return row is not None and row.text == quote


def step(path, command, job, budget, lose_reply, *, rehearse_volatile_stop=False):
    with closing(sqlite3.connect(path)) as db:
        db.row_factory = sqlite3.Row
        db.executescript("""
            CREATE TABLE IF NOT EXISTS task (
                id TEXT PRIMARY KEY, state TEXT NOT NULL, remaining INTEGER NOT NULL CHECK (remaining >= 0),
                events TEXT NOT NULL, citation TEXT, approval TEXT, receipt TEXT
            );
            CREATE TABLE IF NOT EXISTS effects (
                task_id TEXT PRIMARY KEY, op_id TEXT UNIQUE NOT NULL, citation TEXT NOT NULL
            );
        """)
        with db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM task WHERE id=?", (job,)).fetchone()
            if command == "start":
                if row is not None:
                    raise ValueError("task already started")
                if budget is None or not 0 <= budget <= 12:
                    raise ValueError("invalid fixture budget")
                db.execute("INSERT INTO task VALUES (?, 'ready', ?, '[]', NULL, NULL, NULL)", (job, budget))
                return {"state": "ready", "remaining": budget, "events": [], "receipt": None, "insert_attempts": 0}
            if row is None:
                raise ValueError("task missing")
            state, remaining = row["state"], row["remaining"]
            citation, decision, receipt = row["citation"], row["approval"], row["receipt"]
            events, attempts = json.loads(row["events"]), 0
            cancel_result = None
            if state == "saved":
                persisted = db.execute("SELECT op_id, citation FROM effects WHERE task_id=?", (job,)).fetchone()
                if (persisted is None or tuple(persisted) != (receipt, citation)
                        or receipt != digest(binding(job, citation))):
                    raise RuntimeError("saved task does not match the recorded effect")
            elif state not in TERMINAL:
                if command == "cancel":
                    # Control for the rehearsal only: a local acknowledgement is not durable cancellation.
                    if rehearse_volatile_stop:
                        return {"state": state, "remaining": remaining, "events": events, "receipt": receipt,
                                "insert_attempts": 0, "cancel_result": "not_persisted"}
                    state, decision = "cancelled", None
                    cancel_result = "persisted"
                elif command == "approve" and state == "pending_approval":
                    decision, state = binding(job, citation), "approved"
                elif command == "advance" and state != "pending_approval":
                    if remaining == 0:
                        state, decision = "exhausted", None
                    else:
                        remaining -= 1  # reserve one workflow step before it runs
                        if state == "ready":
                            events.append("retrieve")
                            citation = evidence_for(job)
                            state = "retrieved" if citation else "needs_evidence"
                        elif state == "retrieved":
                            events.append("preview")
                            state = "pending_approval"
                        elif state == "approved":
                            if decision != binding(job, citation) or not current_evidence(citation):
                                raise RuntimeError("approval or evidence no longer matches")
                            receipt = digest(decision)
                            events.append("save")
                            attempts += 1  # immediately before the business INSERT
                            db.execute("INSERT INTO effects VALUES (?, ?, ?)", (job, receipt, citation))
                            state = "saved"
                        else:
                            raise RuntimeError("unexpected task state")
                db.execute("UPDATE task SET state=?, remaining=?, events=?, citation=?, approval=?, receipt=? WHERE id=?",
                           (state, remaining, encode(events), citation, decision, receipt, job))
        if lose_reply and attempts == 1 and state == "saved":
            # This teaching fault occurs after commit: the fresh worker returns no result.
            raise SystemExit(LOST_REPLY_EXIT)
    result = {"state": state, "remaining": remaining, "events": events, "receipt": receipt,
              "insert_attempts": attempts}
    if cancel_result is not None:
        result["cancel_result"] = cancel_result
    return result


@dataclass(frozen=True)
class Trial:
    path: Path
    job: str
    _rehearse_volatile_stop: bool = False

    def _invoke(self, command, *, budget=None, lose_reply=False):
        args = [sys.executable, "-I", "-X", "utf8", str(HERE), str(self.path), self.job, command]
        if budget is not None:
            args += ["--budget", str(budget)]
        if lose_reply:
            args.append("--lose-reply")
        if command == "cancel" and self._rehearse_volatile_stop:
            args.append("--rehearse-volatile-stop")
        return subprocess.run(args, capture_output=True, encoding="utf-8", timeout=10, check=False)

    def call(self, command, *, budget=None):
        proc = self._invoke(command, budget=budget)
        if proc.returncode or proc.stderr:
            raise RuntimeError(proc.stderr.strip() or f"worker exited {proc.returncode}")
        return json.loads(proc.stdout)

    def lose_reply(self):
        proc = self._invoke("advance", lose_reply=True)
        if proc.returncode != LOST_REPLY_EXIT or proc.stdout or proc.stderr:
            raise RuntimeError("expected a committed write with no reply")
        return {"exit_code": proc.returncode, "stdout": proc.stdout}

    def read_checkpoint(self):
        """Independent read of trusted synthetic input and the persisted stop/approval state."""
        with closing(sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
            row = db.execute("SELECT state, remaining, events, citation, approval FROM task WHERE id=?",
                             (self.job,)).fetchone()
        if row is None:
            raise RuntimeError("rehearsal checkpoint missing")
        state, remaining, events, citation, approval = row
        return {"state": state, "remaining": remaining, "events": json.loads(events),
                "citation": json.loads(citation) if citation else None,
                "approval": json.loads(approval) if approval else None}

    def durable_rows(self):
        with closing(sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
            return [{"task_id": task, "op_id": op, "citation": json.loads(payload)}
                    for task, op, payload in db.execute("SELECT task_id, op_id, citation FROM effects ORDER BY task_id")]


@contextmanager
def _fresh_trial(job, *, volatile_stop):
    if job not in TERMS:
        raise ValueError("unknown lab case")
    with TemporaryDirectory(prefix="advanced-task-") as tmp:
        yield Trial(Path(tmp) / "local.sqlite3", job, volatile_stop)


def trial(job="schedule"):
    return _fresh_trial(job, volatile_stop=False)


def volatile_stop_control():
    """Fixed synthetic baseline for a single teaching comparison only."""
    return _fresh_trial("schedule", volatile_stop=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("job", choices=TERMS)
    parser.add_argument("command", choices=COMMANDS)
    parser.add_argument("--budget", type=int)
    parser.add_argument("--lose-reply", action="store_true")
    parser.add_argument("--rehearse-volatile-stop", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if (args.budget is not None and args.command != "start"
            or args.lose_reply and args.command != "advance"
            or args.rehearse_volatile_stop and (args.command != "cancel" or args.job != "schedule")):
        parser.error("invalid worker flags")
    try:
        row = step(args.path, args.command, args.job, args.budget, args.lose_reply,
                   rehearse_volatile_stop=args.rehearse_volatile_stop)
    except (ValueError, RuntimeError) as exc:
        parser.exit(2, f"{exc}\n")
    print(encode(row))


if __name__ == "__main__":
    main()
