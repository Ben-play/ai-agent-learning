"""Rehearse native Phase 6 checkpoints, not Phase 10's synthetic v1 schema."""

from contextlib import contextmanager
from hashlib import sha256
import json
from pathlib import Path
import runpy
from tempfile import TemporaryDirectory
from typing import TypedDict

from host import (ACTOR, CODE, JOB, SOURCES, THREAD, Binding, DraftStore, Review,
                  binding_fields, connect, finish, open_store, payload, reply, saved_drafts)
from rehearsal import GOLD, clone, hashes, require
from snapshot_history import CHECKPOINT, frontier, graph_probe, invoke_latest, verify_advanced, verify_start

BUNDLE = (CHECKPOINT, "business.sqlite", "reviews.sqlite")
IDENTITY = (ACTOR.tenant, ACTOR.name, JOB)
CONFIG = {"configurable": {"thread_id": THREAD}}


class CandidateState(TypedDict, total=False):
    # Match the original TaskState, including the operation ID channel name.
    revision: int
    digest: str
    status: str
    op_id: str | None
    schema: int
    completion: str


def interpret(values):
    # The trusted host fixes tenant, actor, job and action; these are not parsed from the thread ID.
    revision, digest = values.get("revision"), values.get("digest")
    if type(revision) is not int or type(digest) is not str:
        return None
    return Binding(ACTOR, JOB, revision, digest)


def checkpoint(directory):
    with connect(directory / "business.sqlite") as db:
        return DraftStore(db).checkpoint(ACTOR, JOB)


def decision(directory, binding):
    with connect(directory / "reviews.sqlite") as db:
        row = db.execute("""SELECT decision FROM decisions WHERE tenant=? AND actor=? AND job=?
            AND action=? AND revision=? AND digest=?""", tuple(binding_fields(binding).values())).fetchone()
    return row[0] if row else None


def check_authority(directory, values):
    """Check the fixed host authority before dispatch and before candidate execution."""
    binding, current = interpret(values), checkpoint(directory)
    if current is None or binding != current.binding:
        return "rejected", None, None
    if current.status == "saved":
        digest_key = [binding.action, *IDENTITY, binding.version, binding.digest]
        op_id = sha256(json.dumps(digest_key).encode("utf-8")).hexdigest()
        if values["status"] != "reviewed" or current.op_id != op_id:
            return "inconsistent", None, None
        with connect(directory / "business.sqlite") as db:
            row = db.execute("SELECT payload FROM saved_drafts WHERE op_id=?", (op_id,)).fetchone()
        if row is None or type(row[0]) is not str or sha256(row[0].encode("utf-8")).hexdigest() != binding.digest:
            return "inconsistent", None, None
        expected_rows = ((op_id, *IDENTITY, payload(current.draft)),)
    elif current.status == "pending" and current.op_id is None:
        expected_rows = ()
    else:
        return "inconsistent", None, None
    if saved_drafts(directory / "business.sqlite") != expected_rows:
        return "inconsistent", None, None
    choice = decision(directory, binding)
    if choice is None and values["status"] == "pending":
        return "pending", None, None
    if choice != "approve":
        # This original-snapshot arm exercises approved and no-decision histories only.
        return "rejected", None, None
    # Phase 6 did not persist current sources. This supplemental check uses the trusted
    # synthetic host's fixed current evidence, independently of the Phase 5 draft and digest.
    draft = current.draft
    if (draft.title != "需人工确认：导出保留期" or draft.source_ids != tuple(SOURCES)
            or draft.body != " ".join(SOURCES.values())):
        return ("replay_withheld" if current.status == "saved" else "source_blocked"), None, None
    return None, binding, Review.APPROVE


def preflight(directory, state):
    values = state["values"]
    if state["thread"] != THREAD or values.keys() != {"revision", "digest", "status"}:
        return "migration_refused"
    binding = interpret(values)
    if binding is None:
        return "migration_refused"
    if state["next"] == ["review"]:
        valid = (values["status"] == "pending" and
                 state["interrupts"] == [{"job": JOB, "revision": binding.version}])
    elif state["next"] == ["apply_review"]:
        valid = values["status"] == "reviewed" and not state["interrupts"]
    else:
        valid = False
    if not valid:
        return "migration_refused"
    return check_authority(directory, values)[0]


@contextmanager
def open_candidate(directory, *, on_write=None, on_result=None):
    from langgraph.checkpoint.sqlite import SqliteSaver
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import interrupt

    def review(state):
        binding, current = interpret(state), checkpoint(directory)
        if current is None or binding != current.binding:
            return {"status": "rejected"}
        # Preserve the original first interrupt and signal; only the trusted DB can authorize.
        signal = interrupt({"job": JOB, "revision": binding.version})
        stop, _, _ = check_authority(directory, state)
        return {"status": "reviewed" if signal == "review_recorded" and stop is None else "rejected"}

    def apply_review(state):
        stop, binding, review = check_authority(directory, state)
        if stop is not None:
            return {"status": stop}
        with open_store(directory / "business.sqlite", on_draft_write_attempt=on_write) as store:
            result = store.resume(ACTOR, JOB, binding, review)
        if on_result is not None:
            on_result(result)
        return {"status": result.status, "op_id": result.op_id}

    def finalize(_):
        return finish()

    builder = StateGraph(CandidateState)
    builder.add_node("review", review)
    builder.add_node("apply_review", apply_review)
    builder.add_node("finish", finalize)
    builder.add_edge(START, "review")
    builder.add_conditional_edges("review", lambda s: s["status"] == "reviewed", {True: "apply_review", False: END})
    builder.add_conditional_edges("apply_review", lambda s: s["status"] in {"saved", "replayed"},
                                  {True: "finish", False: END})
    builder.add_edge("finish", END)
    with SqliteSaver.from_conn_string(str(directory / CHECKPOINT)) as saver:
        yield builder.compile(checkpointer=saver)


def observe(directory, open_graph):
    with graph_probe(directory) as probe, open_graph(probe) as graph:
        return frontier(graph, CONFIG)


def audit(directory):
    """Read all rows from closed stores, independent of graph state and callbacks."""
    with connect(directory / "business.sqlite") as db:
        checkpoints = [[tenant, actor, job, rev, json.loads(draft), status, op_id]
                       for tenant, actor, job, rev, draft, status, op_id in db.execute(
                           "SELECT * FROM checkpoints ORDER BY tenant, actor, job")]
    with connect(directory / "reviews.sqlite") as db:
        tables = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        require("native Phase 6 approval table, no Phase 10 sources table", tables, ["decisions"])
        reviews = [list(row) for row in db.execute("SELECT * FROM decisions ORDER BY 1, 2, 3, 4, 5, 6")]
    return {"checkpoints": checkpoints, "reviews": reviews,
            "saved": [list(row) for row in saved_drafts(directory / "business.sqlite")]}


def check_ledger(directory, *, approved, saved):
    task, draft = GOLD["task"], GOLD["draft"]
    who = [task["tenant"], task["actor"], task["job"]]
    op_id = GOLD["receipt"] if saved else None
    actual = audit(directory)
    require("native all business and approval rows", actual, {
        "checkpoints": [[*who, task["revision"], draft, "saved" if saved else "pending", op_id]],
        "reviews": [[*(task[key] for key in GOLD["binding_order"]), "approve"]] if approved else [],
        "saved": [[op_id, *who, draft]] if saved else [],
    })
    return actual


def check_seed_state(state, stop):
    task, expected = GOLD["task"], GOLD["seeds"][stop]
    require("native stopped graph", state, {
        "thread": GOLD["thread"],
        "values": {"revision": task["revision"], "digest": task["digest"], "status": expected["status"]},
        "next": expected["next"],
        "interrupts": [{"job": task["job"], "revision": task["revision"]}] if stop == "pending" else [],
    })


def seed(directory, lab, stop):
    from langgraph.types import Command

    directory.mkdir()
    open_graph = lab["open_graph"]
    attempts, returned = [], []
    staged = lab["run_step"](directory, "stage", on_write=attempts.append)
    task = GOLD["task"]
    title, body, ids = GOLD["draft"]
    require("original Phase 6 stage response", staged, {
        "status": "pending", "interrupt": {"job": task["job"], "revision": task["revision"]},
        "preview": {"revision": task["revision"], "title": title, "body": body, "source_ids": ids},
    })
    pending = observe(directory, open_graph)
    check_seed_state(pending["state"], "pending")
    fault = None
    if stop == "pending":
        with lab["review_db"](directory):
            pass  # Initialize only the original approvals schema; there is no decision.
    else:
        binding = lab["binding_from"](pending["state"]["values"])
        require("original binding before approval", binding_fields(binding), task)
        lab["record_fixture_review"](directory, binding, lab["Review"].APPROVE)
        with open_graph(directory, on_write=attempts.append, on_result=returned.append) as graph:
            verify_start(graph, CONFIG, pending)
            invoke_latest(graph, CONFIG, Command(resume="review_recorded"), interrupt_before=["apply_review"])
        with graph_probe(directory) as probe, open_graph(probe) as graph:
            approved = verify_advanced(graph, CONFIG, pending)
        # Confirm the public breakpoint actually stopped before Phase 5's business operation.
        check_seed_state(approved["state"], "approved")
        check_ledger(directory, approved=True, saved=False)
        require("no draft write at the breakpoint", attempts, [])
        require("no business result at the breakpoint", returned, [])
        if stop == "committed":
            before_fault = observe(directory, open_graph)
            try:
                with open_graph(directory, on_write=attempts.append, on_result=returned.append, lose_reply=True) as graph:
                    verify_start(graph, CONFIG, before_fault)
                    invoke_latest(graph, CONFIG, None)
            except lab["LostReply"]:
                pass  # The original exception is deliberately outside the business transaction.
            else:
                raise AssertionError("Phase 6 did not signal a lost reply after commit")
            with graph_probe(directory) as probe, open_graph(probe) as graph:
                failed = verify_advanced(graph, CONFIG, before_fault, may_stay=True)
            require("failed reply leaves apply_review in flight", failed["state"], before_fault["state"])
            fault = {"reply": reply("reply_lost"), "inserts": attempts, "business_results": len(returned),
                     "checkpoint": failed}
    require("no delivered business results during seeding", returned, [])
    require("native seed INSERT attempts", attempts, [GOLD["receipt"]] if stop == "committed" else [])
    origin = hashes(directory, BUNDLE)
    selected = observe(directory, open_graph)
    check_seed_state(selected["state"], stop)
    ledger = check_ledger(directory, approved=stop != "pending", saved=stop == "committed")
    require("sealed native origin after readback", hashes(directory, origin), origin)
    return {"origin": origin, "checkpoint": selected, "ledger": ledger, "fault_observer": fault}


def advance(directory, open_graph, decode, before):
    origin = hashes(directory, BUNDLE)
    observed = observe(directory, open_graph)
    require("native arm latest and older checkpoints match preparation", observed, before)
    stop = preflight(directory, observed["state"])
    # Runpy creates distinct Phase 5 classes. Compare values, never pass typed objects
    # across the original and candidate stores.
    fields = None
    if stop != "migration_refused":
        fields = binding_fields(decode(observed["state"]["values"]))
        if stop is None:
            require("arm binding at dispatch boundary", fields, GOLD["task"])
    require("native read-only preflight preserved the working bytes", hashes(directory, BUNDLE), origin)
    if stop is not None:
        # Only the probe was opened; the working saver was never opened or invoked.
        return {"reply": reply(stop), "inserts": [], "business_results": 0, "binding": fields,
                "checkpoint": {"id": observed["id"], "state": observed["state"],
                               "parent_path_to_previous_latest": [observed["id"]]}}
    from langgraph.types import Command

    attempts, returned = [], []
    with open_graph(directory, on_write=attempts.append, on_result=returned.append) as graph:
        snapshot = verify_start(graph, CONFIG, before)
        signal = Command(resume="review_recorded") if snapshot.next == ("review",) else None
        invoke_latest(graph, CONFIG, signal)
    with graph_probe(directory) as probe, open_graph(probe) as graph:
        after = verify_advanced(graph, CONFIG, before)
    result, = returned
    return {"reply": reply(result.status, result.op_id, payload(result.draft) if result.draft else None),
            "inserts": attempts, "business_results": len(returned), "binding": fields, "checkpoint": after}


def check_arm(actual, before, expected, candidate):
    releases = expected["releases"]
    op_id = GOLD["receipt"] if releases else None
    require("native binding", actual["binding"], GOLD["task"])
    require("native reply", actual["reply"], reply(expected["status"], op_id, GOLD["draft"] if releases else None))
    require("native INSERT attempts", actual["inserts"], [GOLD["receipt"]] if expected["inserts"] else [])
    require("native delivered Phase 5 results", actual["business_results"], expected["calls"])
    state = before["state"]
    if releases:
        values = dict(state["values"], status=expected["status"], op_id=op_id)
        if candidate:
            values.update(schema=2, completion="receipt_checked")
        state = dict(state, values=values, next=[], interrupts=[])
    require("native graph readback after continuation", actual["checkpoint"]["state"], state)


def compare(root, lab, case, root_of_seeds, seeds):
    expected = GOLD["cases"][case]
    stop = expected["seed"]
    source, sealed = root_of_seeds / stop, seeds[stop]
    before = sealed["checkpoint"]
    root.mkdir()
    prepared = clone(source, root / "prepared", sealed["origin"])
    approved = expected["seed"] != "pending" or case == "approve"
    if case == "approve":
        binding = lab["binding_from"](before["state"]["values"])
        lab["record_fixture_review"](prepared, binding, lab["Review"].APPROVE)
    prepared_hashes = hashes(prepared, BUNDLE)
    require("native prepared checkpoint and history", observe(prepared, lab["open_graph"]), before)
    check_ledger(prepared, approved=approved, saved=expected["seed"] == "committed")
    for name in BUNDLE:
        if name != "reviews.sqlite" or case != "approve":
            require(f"native preparation preserved {name}", prepared_hashes[name], sealed["origin"][name])

    arms = {}
    for name, make_graph in (("original", lab["open_graph"]), ("candidate", open_candidate)):
        working = clone(prepared, root / name, prepared_hashes)
        decode = lab["binding_from"] if name == "original" else interpret
        actual = advance(working, make_graph, decode, before)
        check_arm(actual, before, expected, name == "candidate")
        ledger = check_ledger(working, approved=approved, saved=bool(expected["saved"]))
        if not expected["calls"]:
            require("blocked native arm changed no file", hashes(working, BUNDLE), prepared_hashes)
        arms[name] = {**actual, "ledger": ledger, "from_prepared": prepared_hashes}
    require("both native arms agree on the binding", arms["original"]["binding"], arms["candidate"]["binding"])
    require("both native arms agree on the durable business result", arms["original"]["ledger"], arms["candidate"]["ledger"])
    require("unchanged common preparation", hashes(prepared, BUNDLE), prepared_hashes)
    require("unchanged sealed native origin", hashes(source, BUNDLE), sealed["origin"])
    return arms


def run_native():
    """Run only in the already approved, pinned Phase 6 environment."""
    from langsmith import tracing_context

    lab = runpy.run_path(str(CODE / "phase6-langgraph-mcp/graph-lab/draft_graph.py"))
    require("original and candidate use the same fixed thread", lab["CONFIG"], CONFIG)
    require("original fixed subject and job", (lab["ACTOR"].tenant, lab["ACTOR"].name, lab["JOB"]), IDENTITY)
    with tracing_context(enabled=False), TemporaryDirectory(prefix="p10-native-phase6-") as tmp:
        root = Path(tmp)
        seeds = {stop: seed(root / stop, lab, stop) for stop in ("pending", "approved", "committed")}
        require("three distinct native seed bundles", len({tuple(row["origin"].values()) for row in seeds.values()}), 3)
        cases = {case: compare(root / ("case-" + case), lab, case, root, seeds)
                 for case in ("pending", "approve", "apply_approved", "replay")}
        return {"seeds": seeds, "cases": cases}
