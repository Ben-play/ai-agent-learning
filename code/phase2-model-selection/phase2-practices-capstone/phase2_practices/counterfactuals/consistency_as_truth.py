"""Deliberately fail after treating repeated agreement as truth."""

from __future__ import annotations

from phase2_practices import build_offline_lab
from phase2_practices.consistency_as_truth import assert_consistency_is_not_truth
from phase2_practices.contracts import Observation, Usage
from phase2_practices.counterfactuals import CounterfactualReached



def main() -> None:
    # Build the real lab first so subprocess tests also prove package resolution.
    if not build_offline_lab().assess().fixture_integrity_validated:
        raise AssertionError("counterfactual could not validate the real fixture lab")
    observations = tuple(
        Observation(
            observation_id=f"counterfactual-consistency-{repeat}",
            provider="Counterfactual Virtual",
            candidate_id="Unsafe-Consistent",
            case_id="unsupported-field",
            split="holdout",
            repeat=repeat,
            estimated_uncached_input_units=1,
            estimated_output_units=1,
            answer="invented-value",
            quality_score=1.0,
            factual_errors=0,
            facts_checked=0,
            abstained=False,
            evidence_ids=(),
            cache_entry_available_before=False,
            cache_origin="none",
            usage=Usage(1, 0, 0, 1),
            retries=0,
            escalations=0,
            fixed_latency_ms=1,
        )
        for repeat in range(1, 6)
    )
    try:
        assert_consistency_is_not_truth(observations, expected_answer="ABSTAIN")
    except AssertionError as exc:
        raise CounterfactualReached(str(exc)) from exc


if __name__ == "__main__":
    main()
