"""Trusted, sequential fixture host, shared by the two checkpoint runners."""

from contextlib import closing, contextmanager
from hashlib import sha256
import json
from pathlib import Path
import runpy
import sqlite3

HERE = Path(__file__).resolve().parent
CODE = HERE.parents[2]
P5 = runpy.run_path(str(CODE / "phase5-agent-harness/harness-lab/main.py"))
saved_drafts = runpy.run_path(str(CODE / "phase8-agent-engineering/engineering-lab/observations.py"))["saved_drafts"]
Actor, Binding, Review, LostReply, DraftStore, open_store = (
    P5[name] for name in ("Actor", "Binding", "Review", "LostReply", "DraftStore", "open_store")
)
ACTOR, JOB = Actor("training", "reviewer"), "export"
THREAD = "training:reviewer:export"
FIELDS = ("tenant", "actor", "job", "action", "revision", "digest")
# A reviewed bridge from the old draft to explicit current, actor-scoped source records.
SOURCES = {"KB-01": "导出文件生成后保留 7 天。", "KB-02": "超过保留期需重新发起导出。"}


def binding_fields(binding):
    return dict(zip(FIELDS, (binding.actor.tenant, binding.actor.name, binding.job,
                             binding.action, binding.version, binding.digest)))


def initial_state(binding, encoding):
    fields = binding_fields(binding)
    return {"schema": 1, "binding": fields if encoding == "named" else list(fields.values()), "status": "pending"}


def decode(values, version):
    if type(values) is not dict:
        return None
    schema, raw = values.get("schema"), values.get("binding")
    if type(schema) is not int or schema not in ({1} if version == 1 else {1, 2}):
        return None
    if type(raw) is list and version == 1 and len(raw) == len(FIELDS):
        raw = dict(zip(FIELDS, raw))
    if (type(raw) is not dict or raw.keys() != set(FIELDS) or type(raw["revision"]) is not int
            or any(type(raw[key]) is not str for key in FIELDS if key != "revision")):
        return None
    return Binding(Actor(raw["tenant"], raw["actor"]), raw["job"], raw["revision"], raw["digest"], raw["action"])


@contextmanager
def connect(path, *, write=False):
    path = Path(path)
    target = path if write else path.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(target, uri=not write)) as db, db:
        yield db


def reply(status, receipt=None, draft=None):
    return {"status": status, "receipt": receipt, "draft": draft}


def payload(draft):
    return [draft.title, draft.body, list(draft.source_ids)]


def finish():
    return {"schema": 2, "completion": "receipt_checked"}


def put_review(directory, fields, decision):
    """Invoke only from the trusted fixture driver; never decode this from resume data."""
    with connect(directory / "reviews.sqlite", write=True) as db:
        db.execute("INSERT OR REPLACE INTO decisions VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (*(fields[name] for name in FIELDS), decision))


class Host:
    def __init__(self, directory):
        self.directory = directory
        self.business = directory / "business.sqlite"
        self.reviews = directory / "reviews.sqlite"
        self.calls = 0
        self.inserts = []
        self.result = None

    def stage(self):
        with open_store(self.business) as store:
            old = store.stage(ACTOR, JOB, 1, "同步任务几点运行？")
            current = store.stage(ACTOR, JOB, 2, P5["QUESTION"])
        with connect(self.reviews, write=True) as db:
            db.executescript("""
                CREATE TABLE decisions (tenant TEXT, actor TEXT, job TEXT, action TEXT, revision INTEGER,
                    digest TEXT, decision TEXT, PRIMARY KEY (tenant, actor, job, action, revision, digest));
                CREATE TABLE sources (tenant TEXT, actor TEXT, source_id TEXT, revision INTEGER, text TEXT,
                    PRIMARY KEY (tenant, actor, source_id));
            """)
            db.executemany("INSERT INTO sources VALUES (?, ?, ?, 1, ?)",
                           ((ACTOR.tenant, ACTOR.name, key, text) for key, text in SOURCES.items()))
        return old.binding, current.binding

    def preflight(self, snapshot, version):
        """Do not dispatch an unknown continuation or a mismatched lifecycle."""
        if type(snapshot) is not dict:
            return "migration_refused"
        values = snapshot.get("values")
        binding = decode(values, version)
        if binding is None:
            return "migration_refused"
        node, interrupts = snapshot.get("next"), snapshot.get("interrupts")
        if snapshot.get("thread") != THREAD or type(node) is not list or type(interrupts) is not list:
            return "migration_refused"
        if node == [] and interrupts == []:
            return "not_runnable"
        if node == ["review"]:
            valid = (values.get("status") == "pending"
                     and interrupts == [{"job": binding.job, "revision": binding.version}])
        elif node == ["apply_review"]:
            valid = values.get("status") == "reviewed" and interrupts == []
        else:
            valid = False
        if not valid or values["schema"] != 1 or "receipt" in values or "completion" in values:
            return "migration_refused"
        return self.check(values, version)[0]

    def check(self, values, version):
        """Return a stop reason or the exact authority to use, without applying."""
        binding = decode(values, version)
        if binding is None:
            return "migration_refused", None, None
        with connect(self.business) as db:
            current = DraftStore(db).checkpoint(ACTOR, JOB)
        if current is None or binding != current.binding:
            return "rejected", None, None
        if (current.status not in {"pending", "saved"}
                or (current.status == "pending" and current.op_id is not None)
                or (current.status == "saved" and values["status"] != "reviewed")):
            return "inconsistent", None, None
        with connect(self.reviews) as db:
            rows = db.execute("SELECT * FROM decisions").fetchall()
            key = tuple(binding_fields(binding).values())
            matching = next((row[-1] for row in rows if row[:-1] == key), None)
            if matching not in {"approve", "deny"}:
                # This fixture owns a single task per bundle. No row means still waiting.
                return ("rejected" if rows or values["status"] != "pending" else "pending"), None, None
            if matching == "approve":
                actual = dict(db.execute("""SELECT source_id, text FROM sources
                    WHERE tenant=? AND actor=? AND revision=1""", (ACTOR.tenant, ACTOR.name)))
                draft = current.draft
                if (draft.title != "需人工确认：导出保留期" or draft.source_ids != tuple(SOURCES)
                        or any(actual.get(key) != text for key, text in SOURCES.items())
                        or draft.body != " ".join(actual[key] for key in SOURCES)):
                    return ("replay_withheld" if current.status == "saved" else "source_blocked"), None, None
                if current.status == "saved":
                    op_key = [binding.action, binding.actor.tenant, binding.actor.name,
                              binding.job, binding.version, binding.digest]
                    expected_id = sha256(json.dumps(op_key).encode("utf-8")).hexdigest()
                    if current.op_id != expected_id:
                        return "inconsistent", None, None
            elif current.status == "saved":
                return "rejected", None, None  # A denial is not permission to replay a receipt.
        return None, binding, Review(matching)

    def apply(self, values, version, *, lose=False):
        stop, binding, decision = self.check(values, version)
        if stop is not None:
            self.result = reply(stop)
        else:
            with open_store(self.business, on_draft_write_attempt=self.inserts.append) as store:
                self.calls += 1  # The actual boundary call; the separate callback counts INSERT attempts.
                result = store.resume(ACTOR, JOB, binding, decision, lose_reply=lose)
            self.result = reply(result.status, result.op_id, payload(result.draft) if result.draft else None)
        return self.result["status"]


def audit(directory):
    """No runner callbacks or actor filters; observe all committed rows after close."""
    with connect(directory / "business.sqlite") as db:
        checkpoints = [[tenant, actor, job, revision, json.loads(draft), state, receipt]
                       for tenant, actor, job, revision, draft, state, receipt in db.execute(
                           "SELECT * FROM checkpoints ORDER BY tenant, actor, job")]
    with connect(directory / "reviews.sqlite") as db:
        reviews = [list(row) for row in db.execute("SELECT * FROM decisions ORDER BY 1, 2, 3, 4, 5, 6")]
        sources = [list(row) for row in db.execute("SELECT * FROM sources ORDER BY 1, 2, 3")]
    return {"checkpoints": checkpoints, "reviews": reviews, "sources": sources,
            "saved": [list(row) for row in saved_drafts(directory / "business.sqlite")]}
