"""Compare the original single stub with one read-only delegated call."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import runpy


CHECKS = runpy.run_path(str(Path(__file__).with_name("acceptance.py")))
LAB = CHECKS["LAB"]


def recommend(summary):
    base, candidate = summary["single"], summary["worker"]
    if base.contract_errors:
        return "stop_review"
    if (candidate.contract_errors or candidate.correct_answers < base.correct_answers
            or candidate.total_cost > base.total_cost or candidate.p95_ms > base.p95_ms):
        return "keep_single"
    gain = (candidate.correct_answers > base.correct_answers or candidate.total_cost < base.total_cost
            or candidate.p95_ms < base.p95_ms)
    return "review_candidate" if gain else "keep_single"


def exercise():
    rows, summary = CHECKS["comparison"](("single", "worker"), LAB["WORKER_COHORT"])
    return rows, summary, recommend(summary)


def check_worked():
    rows, summary, decision = exercise()
    observed = {arm: (s.correct_answers, s.tasks, s.total_cost, s.p95_ms, s.dispatches, s.contract_errors)
                for arm, s in summary.items()}
    expected = {"single": (1, 3, 21, 43, 14, ()), "worker": (1, 3, 25, 47, 18, ())}
    if observed != expected or decision != "keep_single":
        raise AssertionError((observed, decision))
    if any(base.outcome != candidate.outcome or base.source_calls != candidate.source_calls
           for base, candidate in zip(rows["single"], rows["worker"], strict=True)):
        raise AssertionError("delegation changed the outcome or the scoped access")


def check_transfer():
    expiry = LAB["WORKER_COHORT"][0]
    budget = LAB["Budget"]()
    probes = (
        ("omit_budget", "c P c b:invalid_handoff h:invalid_handoff", "invalid_handoff"),
        ("wrong_scope", "c P c b:invalid_handoff h:invalid_handoff", "invalid_handoff"),
        ("omit_evidence", "c P c w O m:invalid_worker_result h:invalid_worker_result", "invalid_worker_result"),
        ("wrong_source", "c P c w O m:invalid_worker_result h:invalid_worker_result", "invalid_worker_result"),
        ("wrong_result_scope", "c P c w O m:invalid_worker_result h:invalid_worker_result", "invalid_worker_result"),
        ("repeat_read", "c P c w:read_lease_denied O h:read_lease_denied", "read_lease_denied"),
    )
    for fault, trace, reason in probes:
        row = LAB["run"](expiry, "worker", budget=budget, fault=fault)
        CHECKS["verify"](row, trace, CHECKS["stopped"]("expiry", reason), budget)
    tight = LAB["Budget"](credits=9)
    row = LAB["run"](expiry, "worker", budget=tight)
    CHECKS["verify"](row, "c P c b:budget_exhausted h:budget_exhausted",
                     CHECKS["stopped"]("expiry", "budget_exhausted"), tight)
    for arm, cap in (("single", tight), ("worker", budget)):
        row = LAB["run"](expiry, arm, budget=cap)
        CHECKS["verify"](row, CHECKS["TRACES"]["expiry"][arm], CHECKS["GOLD"]["expiry"], cap)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", choices=("worked", "transfer"))
    args = parser.parse_args()
    if args.check == "worked":
        check_worked()
        print("L89 ACCEPTED")
    elif args.check == "transfer":
        check_transfer()
        print("L89 TRANSFER PASSED")
    else:
        rows, summary, decision = exercise()
        print(json.dumps({"workload": LAB["WORKLOAD"], "decision": decision,
                          "summary": {arm: {**asdict(value), "cost_per_answer": str(value.cost_per_answer)}
                                      for arm, value in summary.items()},
                          "trials": {arm: [asdict(row) for row in trials] for arm, trials in rows.items()}},
                         ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
