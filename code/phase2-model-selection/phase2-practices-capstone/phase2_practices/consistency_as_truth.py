"""Teaching helper for why repeated agreement is not ground truth."""

from __future__ import annotations

from collections.abc import Sequence

from .contracts import Observation


def assert_consistency_is_not_truth(
    observations: Sequence[Observation], expected_answer: str
) -> None:
    """Require an external reference even when all observations agree."""

    if len(observations) != 5:
        raise AssertionError("counterfactual requires exactly five observations")
    if len({item.answer for item in observations}) != 1:
        raise AssertionError("counterfactual requires five consistent answers")
    asserted_truth = observations[0].answer
    if asserted_truth != expected_answer:
        raise AssertionError(
            "consistency-as-truth accepted five consistent unsupported/wrong observations"
        )


__all__ = ["assert_consistency_is_not_truth"]
