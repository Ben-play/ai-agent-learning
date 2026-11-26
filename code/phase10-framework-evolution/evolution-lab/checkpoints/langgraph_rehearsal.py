"""Optional original Phase 6 and Phase 10 application rehearsals on the Phase 6 SDK pins."""

import argparse
from contextlib import contextmanager
from importlib.metadata import PackageNotFoundError, version as installed_version
import json
import sys
import tomllib
from typing import TypedDict

from host import CODE, THREAD, Host, LostReply, binding_fields, finish, initial_state, put_review, reply
from native_phase6 import run_native
import rehearsal
from snapshot_history import CHECKPOINT, frontier, graph_probe, invoke_latest, verify_advanced, verify_start, view

CONFIG = {"configurable": {"thread_id": THREAD}}


class StateV1(TypedDict, total=False):
    schema: int
    binding: dict | list
    status: str
    receipt: str | None


class StateV2(StateV1, total=False):
    completion: str


def check_environment():
    pins = CODE / "phase6-langgraph-mcp/graph-lab/pyproject.toml"
    project = tomllib.loads(pins.read_text(encoding="utf-8"))["project"]
    if not (3, 11) <= sys.version_info[:2] < (3, 14):
        raise SystemExit(f"Use Phase 6's Python range: {project['requires-python']}")
    for requirement in project["dependencies"]:
        if "==" in requirement:
            name, expected = requirement.split("==", 1)
            try:
                actual = installed_version(name)
            except PackageNotFoundError:
                actual = None
            if actual != expected:
                raise SystemExit(f"Use the existing Phase 6 environment with {requirement}")


@contextmanager
def graph_at(directory, host, nodes, version, *, lose=False):
    # Public APIs only; no querying or rewriting saver tables.
    from langgraph.checkpoint.sqlite import SqliteSaver
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import interrupt
    from langsmith import tracing_context

    def review(state):
        raw = state["binding"]
        job, revision = (raw["job"], raw["revision"]) if type(raw) is dict else (raw[2], raw[4])
        signal = interrupt({"job": job, "revision": revision})  # Same first interrupt in both versions.
        nodes.append("review")
        stop, _, _ = host.check(state, version)
        if signal != "review_recorded" or stop is not None:
            host.result = reply(stop or "rejected")
            return {"status": host.result["status"]}
        return {"status": "reviewed"}

    def apply_review(state):
        nodes.append("apply_review")
        status = host.apply(state, version, lose=lose)
        return {"status": status, "receipt": host.result["receipt"]}

    def finalize(_):
        nodes.append("finish")
        return finish()

    def inspect_only(_):
        raise RuntimeError("the snapshot observer must never execute a node")

    observing = version is None
    builder = StateGraph(StateV1 if version == 1 else StateV2)
    builder.add_node("review", inspect_only if observing else review)
    builder.add_node("apply_review", inspect_only if observing else apply_review)
    builder.add_edge(START, "review")
    builder.add_conditional_edges("review", lambda s: s["status"] == "reviewed", {True: "apply_review", False: END})
    if version == 1:
        builder.add_edge("apply_review", END)
    else:
        builder.add_node("finish", inspect_only if observing else finalize)
        builder.add_conditional_edges("apply_review", lambda s: s["status"] in {"saved", "replayed"},
                                      {True: "finish", False: END})
        builder.add_edge("finish", END)
    with tracing_context(enabled=False), SqliteSaver.from_conn_string(str(directory / CHECKPOINT)) as saver:
        yield builder.compile(checkpointer=saver)


def inspect(directory):
    # The observer declares the union of channels but never interprets binding or runs nodes.
    with graph_probe(directory) as probe, graph_at(probe, None, [], None) as graph:
        return view(graph.get_state(CONFIG))


def seed(directory, stop, encoding):
    from langgraph.types import Command

    host = Host(directory)
    old, current = host.stage()
    with graph_at(directory, host, [], 1) as graph:
        graph.invoke(initial_state(current, encoding), CONFIG, durability="sync")
    if stop != "pending":
        put_review(directory, binding_fields(current), "approve")
        with graph_at(directory, host, [], 1) as graph:
            before = frontier(graph, CONFIG)
            invoke_latest(graph, CONFIG, Command(resume="review_recorded"), interrupt_before=["apply_review"])
            verify_advanced(graph, CONFIG, before)
    lost = advance(directory, 1, lose=True) if stop == "committed" else None
    return binding_fields(old), lost


def advance(directory, version, *, lose=False):
    from langgraph.types import Command

    host, nodes = Host(directory), []
    # Pick the expected latest identity on an isolated readback before opening the working saver.
    with graph_probe(directory) as probe, graph_at(probe, None, [], None) as observer:
        before = frontier(observer, CONFIG)
    stop = host.preflight(before["state"], version)
    if stop is not None:
        host.result = reply(stop)
    else:
        try:
            with graph_at(directory, host, nodes, version, lose=lose) as graph:
                snapshot = verify_start(graph, CONFIG, before)
                signal = Command(resume="review_recorded") if snapshot.next == ("review",) else None
                invoke_latest(graph, CONFIG, signal)
            with graph_probe(directory) as probe, graph_at(probe, None, [], None) as observer:
                verify_advanced(observer, CONFIG, before)
        except LostReply:
            host.result = reply("reply_lost")  # fault observer, not a delivered business reply
            with graph_probe(directory) as probe, graph_at(probe, None, [], None) as observer:
                after = verify_advanced(observer, CONFIG, before, may_stay=True)
                rehearsal.require("lost reply retains the pending apply step", after["state"], before["state"])
    return {"reply": host.result, "nodes": nodes, "calls": host.calls, "inserts": host.inserts}


def main():
    check_environment()
    if rehearsal.worker():
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-only", action="store_true", help="only rehearse original Phase 6 snapshots")
    args = parser.parse_args()
    report = {"phase6_original_snapshots": run_native()}
    if not args.native_only:
        report["phase10_application_fixtures"] = rehearsal.run(sys.modules[__name__], "stage")
    print(json.dumps(report, ensure_ascii=True, indent=2))
    print("PHASE 6 ORIGINAL SNAPSHOT REHEARSAL PASSED" if args.native_only else
          "P10 LANGGRAPH APPLICATION REHEARSAL PASSED")


if __name__ == "__main__":
    main()
