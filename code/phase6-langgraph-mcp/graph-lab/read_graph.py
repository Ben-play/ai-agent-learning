"""Migrate the Phase 5 read loop, not its evidence or business rules."""

from pathlib import Path
from typing import TypedDict
import runpy

from langgraph.graph import END, START, StateGraph
from langsmith import tracing_context

CODE = Path(__file__).resolve().parents[2]
P4 = runpy.run_path(str(CODE / "phase4-prompt-context/main.py"))
P5 = runpy.run_path(str(CODE / "phase5-agent-harness/harness-lab/main.py"))
ReadCall, ReadResult, Task = (P5[name] for name in ("ReadCall", "ReadResult", "Task"))
QUESTION, REPHRASE = P5["QUESTION"], P5["REPHRASE"]


class ReadState(TypedDict):
    question: str
    valid: bool
    dynamic: bool
    budget: int
    calls: int
    states: tuple[str, ...]
    status: str
    answer: str | None
    source_ids: tuple[str, ...]


def build_reader(*, lookup=P4["run"], on_dispatch=None):
    """Return a callable with the same input and result contract as Phase 5."""
    def gate(state: ReadState):
        if state["calls"] >= state["budget"]:
            status = "exhausted"
        elif not state["valid"]:
            status = "failed"
        else:
            return {"status": "pending"}
        return {"status": status, "states": (*state["states"], status)}

    def read(state: ReadState):
        question = state["question"]
        if on_dispatch is not None:
            on_dispatch(question)  # Observe dispatch, not the inner adapter.
        evidence = lookup(question)
        update = {"calls": state["calls"] + 1}
        if evidence["status"] == "answered":
            status = "complete"
            update |= {"answer": evidence["answer"], "source_ids": tuple(
                row["source_id"] for row in evidence["citations"]
            )}
        elif state["dynamic"] and evidence["status"] == "needs_evidence" and question == REPHRASE:
            status = "pending"
            update["question"] = QUESTION
        else:
            status = "failed"
        return update | {"status": status, "states": (*state["states"], status)}

    builder = StateGraph(ReadState)
    builder.add_node("gate", gate)
    builder.add_node("read", read)
    builder.add_edge(START, "gate")
    builder.add_conditional_edges("gate", lambda state: state["status"] == "pending",
                                  {True: "read", False: END})
    builder.add_conditional_edges("read", lambda state: state["status"] == "pending",
                                  {True: "gate", False: END})
    graph = builder.compile()

    def run(first, *, dynamic=True, budget=2):
        if type(budget) is not int or not 0 <= budget <= 2:
            raise ValueError("read budget must be an integer from 0 to 2")
        valid = (type(first) is ReadCall and first.task is Task.EVIDENCE_QA
                 and type(first.question) is str and bool(first.question.strip()))
        with tracing_context(enabled=False):
            result = graph.invoke({"question": first.question if valid else "", "valid": valid,
                                   "dynamic": dynamic, "budget": budget, "calls": 0,
                                   "states": ("pending",), "status": "pending",
                                   "answer": None, "source_ids": ()})
        return ReadResult(result["states"], result["calls"], result["answer"], result["source_ids"])

    return run


def read_acceptance():
    observed = []
    graph_read = build_reader(on_dispatch=observed.append)
    first = ReadCall(Task.EVIDENCE_QA, REPHRASE)
    rows = {}
    for case, flags, expected, steps in (
        ("baseline", {"dynamic": False}, ("failed", 1, ()), [REPHRASE]),
        ("dynamic", {}, ("complete", 2, ("KB-01", "KB-02")), [REPHRASE, QUESTION]),
        ("budget", {"budget": 1}, ("exhausted", 1, ()), [REPHRASE]),
    ):
        observed.clear()
        candidate = graph_read(first, **flags)
        original = P5["run_loop"](first, **flags)
        row = (candidate.status, candidate.calls, candidate.source_ids)
        if candidate != original or row != expected or observed != steps:
            raise AssertionError((case, original, candidate, tuple(observed)))
        rows[case] = row
    return rows


if __name__ == "__main__":
    read_acceptance()
    print("P6 GRAPH READ CONTRACT OK")
