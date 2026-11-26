"""Run the three L88 arms and record the simplest full-contract choice."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import runpy


CHECKS = runpy.run_path(str(Path(__file__).with_name("acceptance.py")))
LAB = CHECKS["LAB"]
ARMS = ("thin", "workflow", "single")


def recommend(summary):
    eligible = [arm for arm in ARMS if not summary[arm].contract_errors]
    if not eligible:
        return "stop_review"
    # This fixture has no reason to add selection steps if coverage is identical.
    return min(eligible, key=lambda arm: (-summary[arm].correct_answers, summary[arm].total_cost,
                                          summary[arm].p95_ms, ARMS.index(arm)))


def exercise():
    rows, summary = CHECKS["comparison"](ARMS, LAB["CASES"])
    return rows, summary, recommend(summary)


def check_worked():
    rows, summary, decision = exercise()
    intended_gaps = ("expiry:outcome", "expiry-no-grant:outcome", "expiry-timeout:outcome")
    observed = {arm: (s.correct_answers, s.tasks, s.total_cost, s.p95_ms, s.dispatches, s.contract_errors)
                for arm, s in summary.items()}
    expected = {"thin": (2, 6, 13, 13, 8, intended_gaps),
                "workflow": (3, 6, 19, 37, 10, ()), "single": (3, 6, 27, 43, 18, ())}
    if observed != expected or decision != "workflow":
        raise AssertionError((observed, decision))
    if rows["workflow"][4].cost != 6 or rows["workflow"][4].ms != 37:
        raise AssertionError("timeout and review must remain in the measurement")


def check_transfer():
    expiry = LAB["WORKER_COHORT"][0]
    budget = LAB["Budget"](reads=1)
    traces = {"thin": "P h:needs_followup",
              "workflow": "P b:budget_exhausted h:budget_exhausted",
              "single": "c P c b:budget_exhausted h:budget_exhausted"}
    for arm, trace in traces.items():
        reason = "needs_followup" if arm == "thin" else "budget_exhausted"
        row = LAB["run"](expiry, arm, budget=budget)
        CHECKS["verify"](row, trace, CHECKS["stopped"]("expiry", reason), budget)
        # Independent positive control: the unmodified workflow and stub still answer fully.
        if arm != "thin":
            normal = LAB["run"](expiry, arm)
            CHECKS["verify"](normal, CHECKS["TRACES"]["expiry"][arm], CHECKS["GOLD"]["expiry"], LAB["Budget"]())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", choices=("worked", "transfer"))
    args = parser.parse_args()
    if args.check == "worked":
        check_worked()
        print("L88 ACCEPTED")
    elif args.check == "transfer":
        check_transfer()
        print("L88 TRANSFER PASSED")
    else:
        rows, summary, decision = exercise()
        print(json.dumps({"workload": LAB["WORKLOAD"], "decision": decision,
                          "summary": {arm: {**asdict(value), "cost_per_answer": str(value.cost_per_answer)}
                                      for arm, value in summary.items()},
                          "trials": {arm: [asdict(row) for row in trials] for arm, trials in rows.items()}},
                         ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
