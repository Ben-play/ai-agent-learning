"""Deliberately fail after ranking cost before applying hard gates."""

from __future__ import annotations

from phase2_practices import build_offline_lab
from phase2_practices.counterfactuals import CounterfactualReached
from phase2_practices.rank_before_gate import assert_ranking_respects_hard_gates



def main() -> None:
    report = build_offline_lab().assess()
    grounded = next(task for task in report.tasks if task.task == "grounded_lookup")
    # Unsafe design: cheapest total cost wins before qualification is considered.
    selected = min(
        (candidate for candidate in grounded.candidates if candidate.costs is not None),
        key=lambda candidate: candidate.costs.total if candidate.costs is not None else 0.0,
    )
    if selected.candidate_id != "Spruce-S":
        raise AssertionError(
            "counterfactual fixtures no longer make the unsafe cheap candidate win"
        )
    try:
        assert_ranking_respects_hard_gates(grounded.candidates, selected.candidate_id)
    except AssertionError as exc:
        raise CounterfactualReached(str(exc)) from exc


if __name__ == "__main__":
    main()
