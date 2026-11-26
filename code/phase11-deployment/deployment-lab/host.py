"""Sequential synthetic host shared by the offline worker and the optional HTTP adapter."""

from collections import deque
from contextlib import closing, contextmanager
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import re
import runpy
from secrets import token_hex
import sqlite3
from time import monotonic

CODE = Path(__file__).resolve().parents[2]
P5 = runpy.run_path(str(CODE / "phase5-agent-harness/harness-lab/main.py"))
RAG = runpy.run_path(str(CODE / "phase7-data-rag/rag-lab/lab.py"))
CHECKS = runpy.run_path(str(CODE / "phase7-data-rag/rag-lab/assessment/checks.py"))
saved_drafts = runpy.run_path(str(CODE / "phase8-agent-engineering/engineering-lab/observations.py"))["saved_drafts"]
Actor, Binding, Review, LostReply, DraftStore, open_store = (
    P5[key] for key in ("Actor", "Binding", "Review", "LostReply", "DraftStore", "open_store")
)
SCHEMA = 1
ACTION = "save_local_draft"
BINDING_FIELDS = ("tenant", "actor", "job", "action", "revision", "digest")
PROFILES = {"support": ("support", "mei"), "reviewer": ("support", "mei"),
            "lin": ("support", "lin"), "other": ("operations", "mei")}
JOBS = frozenset({"export", "sync", "pre-approve", "pre-deny", "canary-approve", "canary-deny", "lost"})
QUESTIONS = {"export": P5["QUESTION"], "sync": "同步任务几点运行？"}
CITATIONS = {"export": CHECKS["DEMO_POLICY"], "sync": CHECKS["DEMO_SYNC"]}
OPS_POLICY = CHECKS["Citation"]("operations", ("EXPORT-POLICY", 1, "§1"), "运维导出文件保留 30 天。")
# KB-02's legacy draft sentence is not the exact Phase 7 quote. Check both explicitly.
LEGACY = {"KB-01": (CITATIONS["export"].quote, CITATIONS["export"]),
          "KB-02": ("超过保留期需重新发起导出。", CHECKS["DEMO_RENEWAL"]),
          "KB-03": (CITATIONS["sync"].quote, CITATIONS["sync"])}
DRAFTS = {("KB-01", "KB-02"): "需人工确认：导出保留期", ("KB-03",): "需人工确认：同步时间"}
SHAPES = {"ask": {"topic"}, "stage": {"job", "revision", "topic"}, "inspect": {"job"},
          "review": {"binding", "decision"}, "recover": {"binding"},
          "fixture_lost": {"binding"}, "fixture_revoke": {"topic"}}
REVIEW_ONLY = frozenset({"review", "recover", "fixture_lost", "fixture_revoke"})
REVIEW_DDL = """
CREATE TABLE IF NOT EXISTS decisions (
    tenant TEXT, actor TEXT, job TEXT, action TEXT, revision INTEGER, digest TEXT,
    decision TEXT NOT NULL CHECK(decision IN ('approve', 'deny')),
    trace_id TEXT NOT NULL,
    PRIMARY KEY (tenant,actor,job,action,revision,digest)
);
CREATE TABLE IF NOT EXISTS revoked (
    tenant TEXT, actor TEXT, doc_id TEXT, PRIMARY KEY (tenant,actor,doc_id)
);
"""
EXTRA_DDL = """CREATE TABLE IF NOT EXISTS candidate_meta (
    job TEXT, revision INTEGER, PRIMARY KEY(job,revision)
);"""


class IncompatibleSchema(ValueError):
    """The old writer must not open a newer or unknown application layout."""


class SourceBlocked(ValueError):
    """Current scoped evidence does not support the draft."""


@contextmanager
def connect(path, *, readonly=False):
    if readonly:
        target = path.resolve().as_uri() + "?mode=ro"
    else:
        target = path
    with closing(sqlite3.connect(target, uri=readonly)) as db, db:
        yield db


def present_schema(path):
    with connect(path, readonly=True) as db:
        return db.execute("PRAGMA user_version").fetchone()[0]


def fields(binding):
    return dict(zip(BINDING_FIELDS, (binding.actor.tenant, binding.actor.name, binding.job,
                                   binding.action, binding.version, binding.digest)))


def parse_binding(raw, actor):
    if type(raw) is not dict or raw.keys() != set(BINDING_FIELDS):
        return None
    if ((raw["tenant"], raw["actor"]) != (actor.tenant, actor.name) or raw["action"] != ACTION
            or type(raw["job"]) is not str or raw["job"] not in JOBS
            or type(raw["revision"]) is not int or not 1 <= raw["revision"] < 2**63
            or type(raw["digest"]) is not str or not re.fullmatch(r"[0-9a-f]{64}", raw["digest"])):
        return None
    return Binding(actor, raw["job"], raw["revision"], raw["digest"], ACTION)


def payload(draft):
    return [draft.title, draft.body, list(draft.source_ids)]


def audit(directory):
    """Independent, all-subject readback. For the local examiner, not the HTTP response."""
    business, reviews = directory / "business.sqlite", directory / "review.sqlite"
    with connect(business, readonly=True) as db:
        checkpoints = [[tenant, actor, job, revision, json.loads(body), status, operation]
                       for tenant, actor, job, revision, body, status, operation in db.execute(
                           "SELECT * FROM checkpoints ORDER BY tenant,actor,job")]
    with connect(reviews, readonly=True) as db:
        decisions = db.execute("SELECT tenant,actor,job,action,revision,digest,decision FROM decisions ORDER BY 1,2,3,4,5,6")
        revoked = db.execute("SELECT tenant,actor,doc_id FROM revoked ORDER BY 1,2,3")
        exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='candidate_meta'").fetchone()
        return {"schema": present_schema(business), "checkpoints": checkpoints,
                "reviews": [list(row) for row in decisions], "saved": [list(row) for row in saved_drafts(business)],
                "revocations": [list(row) for row in revoked],
                "extras": [list(row) for row in db.execute("SELECT job,revision FROM candidate_meta ORDER BY 1,2")]
                if exists else []}


class ReadBudget:
    """Observe entry to the real Phase 7 read method, not the returned status."""

    def __init__(self, db):
        self.db, self.calls = db, 0

    def source(self, tenant, actor, key):
        self.calls += 1
        return self.db.source(tenant, actor, key)


def _current_draft(source, scope, draft, budget):
    entries = tuple(LEGACY[key] for key in draft.source_ids) if draft.source_ids in DRAFTS else ()
    if (not entries or draft.title != DRAFTS[draft.source_ids]
            or draft.body != " ".join(text for text, _ in entries)):
        return "source_blocked"
    if len(entries) > budget:
        return "budget_exhausted"  # Reserve the whole required read set before dispatch.
    if not all(CHECKS["exact_source"](source, scope, citation) for _, citation in entries):
        return "source_blocked"
    return None


def _reply(status, **fields):
    return {"status": status, "receipt": None, "draft": None, **fields}


class Host:
    """One serialized fixture writer. Production authentication and concurrency are out of scope."""

    def __init__(self, directory, *, build="v1", outage=False, quota=20, window=60, read_cap=2, clock=monotonic):
        if build not in {"v1", "v2"} or type(quota) is not int or quota < 1 or window <= 0 or read_cap not in {0, 1, 2}:
            raise ValueError("invalid trusted lab config")
        directory.mkdir(parents=True, exist_ok=True)
        self.business, self.reviews = directory / "business.sqlite", directory / "review.sqlite"
        files = (self.business, self.reviews)
        existing = [file for file in files if file.exists()]
        if existing and (len(existing) != len(files) or any(present_schema(file) != SCHEMA for file in existing)):
            raise IncompatibleSchema("incompatible_schema")
        if not existing:
            with open_store(self.business):
                pass
            with connect(self.business) as db:
                db.execute("PRAGMA user_version = 1")
        if not existing or build == "v2":
            with connect(self.reviews) as db:
                if not existing:
                    db.executescript(REVIEW_DDL)
                    db.execute("PRAGMA user_version = 1")
                if build == "v2":
                    db.executescript(EXTRA_DDL)  # Additive, non-authoritative, v1 does not read it.
        self.build, self.outage = build, outage
        self.quota, self.window, self.read_cap, self.clock = quota, window, read_cap, clock
        self._windows = {}
        self.events = deque(maxlen=64)

    def _quota(self, tenant):
        window = int(self.clock() // self.window)
        previous, count = self._windows.get(tenant, (window, 0))
        if window != previous:
            count = 0
        if count == self.quota:
            return False
        self._windows[tenant] = (window, count + 1)
        return True

    def _record(self, operation, trace, result):
        self.events.append({"event": operation, "trace_id": trace, "result": result["status"]})
        return result

    def dispatch(self, profile, operation, request, *, fixtures=False):
        """Profile, fixtures and resource limits are selected by the trusted adapter, never by request JSON."""
        trace = token_hex(12)
        read_calls, inserts = 0, []
        known = type(operation) is str and operation in SHAPES
        event = operation if known else "unknown"
        if not known or (operation.startswith("fixture_") and not fixtures):
            result = _reply("forbidden")
        elif type(profile) is not str or profile not in PROFILES or (operation in REVIEW_ONLY and profile != "reviewer"):
            result = _reply("forbidden")
        elif type(request) is not dict or request.keys() != SHAPES[operation]:
            result = _reply("invalid_request")
        else:
            actor = Actor(*PROFILES[profile])
            if not self._quota(actor.tenant):
                result = _reply("rate_limited")
            else:
                result, trace, read_calls = self._run(operation, request, actor, trace, inserts)
        return self._record(event, trace, {**result, "read_calls": read_calls, "inserts": inserts})

    @contextmanager
    def _sources(self):
        with connect(self.reviews, readonly=True) as db:
            revoked = db.execute("SELECT tenant,actor,doc_id FROM revoked").fetchall()
        with RAG["open_demo"]() as db:
            for tenant, actor, doc_id in revoked:
                db.revoke(tenant, actor, doc_id)
            yield ReadBudget(db)

    def _checkpoint(self, actor, job):
        with connect(self.business, readonly=True) as db:
            return DraftStore(db).checkpoint(actor, job)

    def _run(self, op, req, actor, trace, inserts):
        scope = CHECKS["Scope"](actor.tenant, actor.name)
        if op in {"ask", "stage", "fixture_revoke"}:
            topic = req["topic"]
            if type(topic) is not str or topic not in CITATIONS:
                return _reply("invalid_request"), trace, 0
        if op in {"stage", "inspect"}:
            job = req["job"]
            if type(job) is not str or job not in JOBS:
                return _reply("invalid_request"), trace, 0
        if op == "fixture_revoke":
            with connect(self.reviews) as db:
                db.execute("INSERT OR IGNORE INTO revoked VALUES (?,?,?)", (actor.tenant, actor.name, CITATIONS[topic].key[0]))
            return _reply("revoked"), trace, 0
        if op == "inspect":
            current = self._checkpoint(actor, job)
            return (_reply(current.status, binding=fields(current.binding)) if current else _reply("not_available")), trace, 0
        if op in {"ask", "stage"}:
            if self.outage:
                return _reply("dependency_unavailable"), trace, 0
            with self._sources() as source:
                if op == "ask":
                    if self.read_cap == 0:
                        return _reply("budget_exhausted"), trace, 0
                    citation = OPS_POLICY if actor.tenant == "operations" and topic == "export" else CITATIONS[topic]
                    result = (_reply("answered", evidence=[asdict(citation)])
                              if CHECKS["exact_source"](source, scope, citation) else _reply("source_blocked"))
                else:
                    result = self._stage(actor, scope, req, source)
                return result, trace, source.calls

        binding = parse_binding(req["binding"], actor)
        current = self._checkpoint(actor, binding.job) if binding else None
        if current is None or current.binding != binding:
            return _reply("rejected"), trace, 0
        key = tuple(fields(binding).values())
        if op == "review":
            return self._review(current, key, req["decision"], trace)
        with connect(self.reviews, readonly=True) as db:
            row = db.execute("""SELECT decision,trace_id FROM decisions WHERE tenant=? AND actor=?
                AND job=? AND action=? AND revision=? AND digest=?""", key).fetchone()
        if row is None:
            return _reply("pending" if current.status == "pending" else "inconsistent"), trace, 0
        decision, trace = row
        if op == "fixture_lost" and (decision != "approve" or current.status != "pending"):
            return _reply("not_runnable"), trace, 0
        if not self._receipt_consistent(current):
            return _reply("inconsistent"), trace, 0
        reads = 0
        if decision == "approve":
            if self.outage:
                return _reply("dependency_unavailable"), trace, 0
            with self._sources() as source:
                stop = _current_draft(source, scope, current.draft, self.read_cap)
                reads = source.calls
            if stop:
                status = "replay_withheld" if current.status == "saved" and stop == "source_blocked" else stop
                return _reply(status), trace, reads
        try:
            with open_store(self.business, on_draft_write_attempt=inserts.append) as store:
                saved = store.resume(actor, binding.job, binding, Review(decision), lose_reply=op == "fixture_lost")
        except LostReply:
            return _reply("reply_lost"), trace, reads
        return _reply(saved.status, receipt=saved.op_id, draft=payload(saved.draft) if saved.draft else None), trace, reads

    def _stage(self, actor, scope, req, source):
        def before(draft):
            status = _current_draft(source, scope, draft, self.read_cap)
            if status:
                raise SourceBlocked(status)

        try:
            with open_store(self.business, before_stage=before) as store:
                current = store.stage(actor, req["job"], req["revision"], QUESTIONS[req["topic"]])
        except SourceBlocked as exc:
            return _reply(str(exc))
        except ValueError:
            return _reply("invalid_request")
        if self.build == "v2":
            with connect(self.reviews) as db:
                db.execute("INSERT OR IGNORE INTO candidate_meta VALUES (?,?)", (req["job"], current.binding.version))
        return _reply("pending", binding=fields(current.binding), draft=payload(current.draft))

    def _review(self, current, key, decision, trace):
        if decision not in ("approve", "deny"):
            return _reply("invalid_request"), trace, 0
        with connect(self.reviews) as db:
            existing = db.execute("""SELECT decision,trace_id FROM decisions WHERE tenant=? AND actor=?
                AND job=? AND action=? AND revision=? AND digest=?""", key).fetchone()
            if existing:
                return _reply("review_recorded" if existing[0] == decision else "review_conflict"), existing[1], 0
            if current.status != "pending":
                return _reply("not_runnable"), trace, 0
            db.execute("INSERT INTO decisions VALUES (?,?,?,?,?,?,?,?)", (*key, decision, trace))
        return _reply("review_recorded"), trace, 0

    def _receipt_consistent(self, current):
        bound = current.binding
        key = (bound.actor.tenant, bound.actor.name, bound.job)
        with connect(self.business, readonly=True) as db:
            rows = db.execute("SELECT op_id,payload FROM saved_drafts WHERE tenant=? AND actor=? AND job=?", key).fetchall()
        if current.status in {"pending", "denied"}:
            return current.op_id is None and not rows
        if current.status != "saved":
            return False
        operation = sha256(json.dumps([ACTION, *key, bound.version, bound.digest]).encode("utf-8")).hexdigest()
        return (current.op_id == operation and len(rows) == 1 and rows[0][0] == operation
                and sha256(rows[0][1].encode("utf-8")).hexdigest() == bound.digest)
