"""An interrupt is a pause, not an approval or a business receipt.

This lab uses one trusted demo identity, sequential commands, and temporary files.
The review database is a fixture, not an authentication/approval service.
"""

from contextlib import closing, contextmanager
from pathlib import Path
import runpy
import sqlite3
from typing import TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from langsmith import tracing_context

P5 = runpy.run_path(str(Path(__file__).resolve().parents[2] / "phase5-agent-harness/harness-lab/main.py"))
Actor, Binding, Review, LostReply, open_store = (
    P5[name] for name in ("Actor", "Binding", "Review", "LostReply", "open_store")
)
ACTOR = Actor("training", "reviewer")
JOB = "export"
CONFIG = {"configurable": {"thread_id": "training:reviewer:export"}}


class TaskState(TypedDict, total=False):
    revision: int
    digest: str
    status: str
    op_id: str | None


@contextmanager
def review_db(directory):
    with closing(sqlite3.connect(directory / "reviews.sqlite")) as db, db:
        db.execute("""CREATE TABLE IF NOT EXISTS decisions (
            tenant TEXT NOT NULL, actor TEXT NOT NULL, job TEXT NOT NULL,
            action TEXT NOT NULL, revision INTEGER NOT NULL, digest TEXT NOT NULL,
            decision TEXT NOT NULL,
            PRIMARY KEY (tenant, actor, job, action, revision, digest)
        )""")
        yield db


def keys(binding):
    return (binding.actor.tenant, binding.actor.name, binding.job,
            binding.action, binding.version, binding.digest)


def record_fixture_review(directory, binding, decision):
    """Called by the trusted test driver, not by the model or the resume payload."""
    with review_db(directory) as db:
        db.execute("INSERT OR REPLACE INTO decisions VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (*keys(binding), decision.value))


def current_review(directory, binding):
    with review_db(directory) as db:
        row = db.execute("""SELECT decision FROM decisions WHERE tenant=? AND actor=?
            AND job=? AND action=? AND revision=? AND digest=?""", keys(binding)).fetchone()
    return Review(row[0]) if row else None


def binding_from(values):
    return Binding(ACTOR, JOB, values["revision"], values["digest"])


def stage_revisions(directory, *, on_write=None):
    with open_store(directory / "business.sqlite", on_draft_write_attempt=on_write) as store:
        old = store.stage(ACTOR, JOB, 1, "同步任务几点运行？")
        current = store.stage(ACTOR, JOB, 2, P5["QUESTION"])
    return old, current


def checked_checkpoint(business_path, binding):
    with open_store(business_path) as store:
        checkpoint = store.checkpoint(ACTOR, JOB)
    return checkpoint if checkpoint is not None and checkpoint.binding == binding else None


def draft_fields(draft):
    return {"title": draft.title, "body": draft.body, "source_ids": list(draft.source_ids)}


def pending_preview(business_path, values):
    checkpoint = checked_checkpoint(business_path, binding_from(values))
    if checkpoint is None:
        return None  # Do not show a different revision under the paused graph's reference.
    return {"revision": checkpoint.binding.version, **draft_fields(checkpoint.draft)}


@contextmanager
def open_graph(directory, *, on_write=None, lose_reply=False, on_result=None):
    business_path = directory / "business.sqlite"

    def review_node(state: TaskState):
        binding = binding_from(state)
        if checked_checkpoint(business_path, binding) is None:
            return {"status": "rejected"}
        # The resumed node starts at the top. The persisted interrupt carries only a reference.
        signal = interrupt({"job": JOB, "revision": binding.version})
        if signal != "review_recorded" or current_review(directory, binding) is None:
            return {"status": "rejected"}
        return {"status": "reviewed"}

    def apply_review(state: TaskState):
        binding = binding_from(state)
        review = current_review(directory, binding)
        with open_store(business_path, on_draft_write_attempt=on_write) as store:
            result = store.resume(ACTOR, JOB, binding, review, lose_reply=lose_reply)
        if on_result is not None:
            on_result(result)  # Return the draft to this host call, not to the checkpointer.
        return {"status": result.status, "op_id": result.op_id}

    with SqliteSaver.from_conn_string(str(directory / "graph.sqlite")) as saver:
        builder = StateGraph(TaskState)
        builder.add_node("review", review_node)
        builder.add_node("apply_review", apply_review)
        builder.add_edge(START, "review")
        builder.add_conditional_edges("review", lambda s: s["status"] == "reviewed",
                                      {True: "apply_review", False: END})
        builder.add_edge("apply_review", END)
        yield builder.compile(checkpointer=saver)


def run_step(directory, command, *, on_write=None, lose_reply=False):
    """Only the harness chooses commands and the demo thread; no external inputs."""
    path = directory / "business.sqlite"
    results = []
    with tracing_context(enabled=False), open_graph(directory, on_write=on_write,
                                                    lose_reply=lose_reply, on_result=results.append) as graph:
        snapshot = graph.get_state(CONFIG)
        if command == "stage":
            if snapshot.values:
                raise ValueError("use a new lab directory for another task")
            _, current = stage_revisions(directory, on_write=on_write)
            binding = current.binding
            output = graph.invoke({"revision": binding.version, "digest": binding.digest,
                                   "status": "pending"}, CONFIG, durability="sync")
            return {"status": "pending", "interrupt": output["__interrupt__"][0].value,
                    "preview": pending_preview(path, output)}
        if command == "inspect":
            row = {"status": snapshot.values.get("status"), "next": list(snapshot.next),
                   "revision": snapshot.values.get("revision")}
            if snapshot.next == ("review",):
                row["preview"] = pending_preview(path, snapshot.values)
            return row
        if command == "resume" and snapshot.next == ("review",):
            if current_review(directory, binding_from(snapshot.values)) is None:
                return {"status": "pending"}  # Orchestration state; the save API was not called.
            output = graph.invoke(Command(resume="review_recorded"), CONFIG, durability="sync")
        elif command == "recover" and snapshot.next == ("apply_review",):
            # Replay the saved graph step, not a new task. Business storage de-duplicates.
            output = graph.invoke(None, snapshot.config, durability="sync")
        else:
            return {"status": "not_runnable"}
        draft = results[-1].draft if results else None
        return {"status": output.get("status"), "op_id": output.get("op_id"),
                "draft": draft_fields(draft) if draft is not None else None}


def inspect_business(directory):
    with open_store(directory / "business.sqlite") as store:
        cp = store.checkpoint(ACTOR, JOB)
        return cp, store.saved_count(ACTOR, JOB)
