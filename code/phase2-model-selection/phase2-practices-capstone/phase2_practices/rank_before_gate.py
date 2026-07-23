"""Teaching helper for why hard gates must precede ranking."""

from __future__ import annotations

from collections.abc import Sequence

from .contracts import CandidateAssessment


def assert_ranking_respects_hard_gates(
    candidates: Sequence[CandidateAssessment], selected_candidate: str
) -> None:
    """Reject a pre-gate ranker that selects a disqualified candidate."""

    selected = next(
        candidate for candidate in candidates if candidate.candidate_id == selected_candidate
    )
    if not selected.qualified:
        raise AssertionError(
            "rank-before-gate selected an unsafe cheap candidate rejected by hard gates"
        )


__all__ = ["assert_ranking_respects_hard_gates"]
