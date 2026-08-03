from __future__ import annotations

from phase2_practices.assessment import _compute_metrics
from phase2_practices.contracts import EvaluationCase, Observation, SemanticPolicy, Usage


def case(case_id: str, repeats: int, expected: str = "holds") -> EvaluationCase:
    return EvaluationCase(
        case_id=case_id,
        task="metric",
        split="holdout",
        prompt="fixture",
        expected_answer=expected,
        should_abstain=expected == "ABSTAIN",
        allowed_evidence_ids=frozenset(),
        required_evidence_ids=frozenset(),
        repeats=repeats,
        policy=SemanticPolicy.create({}, maximum_estimated_input_units=1000),
    )


def observation(
    case_id: str,
    repeat: int,
    answer: str,
    *,
    quality: float = 1.0,
    latency: int = 100,
    estimated: int = 92,
    actual: int = 92,
) -> Observation:
    return Observation(
        observation_id=f"{case_id}-{repeat}",
        provider="Virtual",
        candidate_id="Fixture",
        case_id=case_id,
        split="holdout",
        repeat=repeat,
        estimated_uncached_input_units=estimated,
        estimated_output_units=0,
        answer=answer,
        quality_score=quality,
        factual_errors=0 if answer.strip().casefold().rstrip(".!?") == "holds" else 1,
        facts_checked=1,
        abstained=answer.strip().casefold().rstrip(".!?") == "abstain",
        evidence_ids=(),
        cache_entry_available_before=False,
        cache_origin="none",
        usage=Usage(actual, 0, 0, 0),
        retries=0,
        escalations=0,
        fixed_latency_ms=latency,
    )


def test_pairwise_divergence_has_precise_probability() -> None:
    metric_case = case("divergent", 5)
    items = tuple(
        observation("divergent", index, answer)
        for index, answer in enumerate(("A", "A", "B", "C", "D"), 1)
    )
    assert _compute_metrics((metric_case,), items).divergence_rate == 0.9


def test_narrow_format_normalization_avoids_false_divergence() -> None:
    metric_case = case("formatted", 5)
    items = tuple(
        observation("formatted", index, answer)
        for index, answer in enumerate(("holds", "holds.", "HOLDS", " holds", "holds\n"), 1)
    )
    metrics = _compute_metrics((metric_case,), items)
    assert metrics.divergence_rate == 0.0
    assert metrics.factual_error_rate == 0.0


def test_false_abstentions_on_answerable_case_are_penalized() -> None:
    metric_case = case("answerable", 5)
    items = tuple(observation("answerable", index, "ABSTAIN") for index in range(1, 6))
    metrics = _compute_metrics((metric_case,), items)
    assert metrics.correct_abstention_rate == 0.0
    assert metrics.factual_error_rate == 1.0


def test_per_observation_estimate_error_cannot_cancel() -> None:
    metric_case = case("estimate", 5)
    estimates = (0, 184, 0, 184, 92)
    items = tuple(
        observation("estimate", index, "holds", estimated=estimate, actual=92)
        for index, estimate in enumerate(estimates, 1)
    )
    assert _compute_metrics((metric_case,), items).estimated_vs_actual_usage_delta == 0.6


def test_quality_and_latency_weight_cases_equally_not_repeats() -> None:
    poor = case("poor-five", 5)
    good = case("good-one", 1)
    items = tuple(
        observation("poor-five", index, "holds", quality=0.0, latency=1000)
        for index in range(1, 6)
    ) + (observation("good-one", 1, "holds", quality=1.0, latency=0),)
    metrics = _compute_metrics((poor, good), items)
    assert metrics.quality == 0.5
    assert metrics.mean_fixed_latency_ms == 500.0
