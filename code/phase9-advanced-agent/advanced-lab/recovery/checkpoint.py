"""Compare two cancellation designs on one fixed, synthetic local workflow."""

import json
from pathlib import Path
import runpy

HERE = Path(__file__).resolve().parent
LAB = runpy.run_path(str(HERE / "lab.py"))
CITATION = ["SYNC-POLICY", 1, "§1", "同步任务每天 02:00 运行。"]
BUDGET = 3


def _prepare(task):
    task.call("start", budget=BUDGET)
    task.call("advance")
    task.call("advance")
    task.call("approve")
    record = task.read_checkpoint()
    if ((record["state"], record["remaining"], record["events"], record["citation"]) !=
            ("approved", 1, ["retrieve", "preview"], CITATION)
            or not record["approval"] or task.durable_rows()):
        raise AssertionError("the fixed draft did not reach the expected approved, unsaved input")
    return record


def _cancel_then_restart(open_trial):
    with open_trial() as task:
        before = _prepare(task)
        response = task.call("cancel")
        after_cancel = task.read_checkpoint()
        if response["insert_attempts"] or task.durable_rows():
            raise AssertionError("the cancel command must not save")
        after_restart = task.call("advance")
        committed = task.durable_rows()
    return {"before_cancel": before, "cancel_result": response["cancel_result"],
            "checkpoint_after_cancel": after_cancel, "after_restart": after_restart,
            "committed_rows": len(committed)}, committed


def _lost_reply_control():
    with LAB["trial"]() as task:
        _prepare(task)
        loss = task.lose_reply()
        prior = task.durable_rows()
        first, second = task.call("recover"), task.call("recover")
        if (len(prior) != 1 or prior[0]["citation"] != CITATION or first != second
                or (first["state"], first["remaining"], first["events"], first["insert_attempts"]) !=
                ("saved", 0, ["retrieve", "preview", "save"], 0)
                or not first["receipt"] or first["receipt"] != prior[0]["op_id"]
                or task.durable_rows() != prior):
            raise AssertionError("post-commit recovery did not return the same durable receipt")
    return {"exit_code": loss["exit_code"], "rows": len(prior), "new_insert_attempts": first["insert_attempts"]}


def run():
    original, old_rows = _cancel_then_restart(LAB["volatile_stop_control"])
    candidate, new_rows = _cancel_then_restart(LAB["trial"])
    before = original["before_cancel"]
    if (before != candidate["before_cancel"] or original["checkpoint_after_cancel"] != before
            or candidate["checkpoint_after_cancel"] != {**before, "state": "cancelled", "approval": None}):
        raise AssertionError("the two arms must only differ in whether cancellation persists")
    old, new = original["after_restart"], candidate["after_restart"]
    if (original["cancel_result"], old["state"], old["remaining"], old["events"], old["insert_attempts"]) != (
            "not_persisted", "saved", 0, ["retrieve", "preview", "save"], 1):
        raise AssertionError("the baseline did not reproduce the missing stop state")
    expected_write = {"task_id": "schedule", "op_id": old["receipt"], "citation": CITATION}
    if not old["receipt"] or old_rows != [expected_write]:
        raise AssertionError("the baseline write was not independently verified")
    if (candidate["cancel_result"], new["state"], new["remaining"], new["events"],
            new["insert_attempts"], new["receipt"], new_rows) != (
            "persisted", "cancelled", 1, ["retrieve", "preview"], 0, None, []):
        raise AssertionError("the durable stop crossed the effect boundary")
    return {
        "version": "long-task-adoption-v2",
        "worker_fixture": LAB["VERSION"],
        "input": {"task": "schedule", "budget": BUDGET, "citation": CITATION},
        "prior_reference": "Phase 8 acceptance-v2 covers save/replay; it is not the cancellation baseline",
        "bottleneck": "an approved local draft can proceed when a stop request was not persisted",
        "comparison": {"volatile_stop_baseline": original, "durable_stop_candidate": candidate},
        "benefit": {"subsequent_steps_avoided": len(old["events"]) - len(new["events"]),
                    "inserts_avoided": old["insert_attempts"] - new["insert_attempts"]},
        "lost_reply_control": _lost_reply_control(),
        "decision": "keep a workflow; add a persisted stop state only if the queue needs cancellation",
        "authority": "fixed synthetic subject, evidence binding and host approval; local draft only",
        "maintenance": "new durable states, finite step accounting and restart regression cases",
        "unverified": ["concurrent workers", "in-flight remote cancellation", "production identity", "external effects"],
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, ensure_ascii=False))
