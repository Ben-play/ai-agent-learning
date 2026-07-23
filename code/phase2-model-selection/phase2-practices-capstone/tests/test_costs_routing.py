from __future__ import annotations

from dataclasses import replace

import pytest

from phase2_practices import AssessmentReport, build_offline_lab
from phase2_practices.assessment import _rank_qualified, _recommend_route
from phase2_practices.contracts import (
    CandidateAssessment,
    CostBreakdown,
    QualityMetrics,
    RankingWeights,
    TaskAssessment,
)


def _task(report: AssessmentReport, name: str) -> TaskAssessment:
    return next(task for task in report.tasks if task.task == name)


def _candidate(task: TaskAssessment, candidate_id: str) -> CandidateAssessment:
    return next(
        candidate for candidate in task.candidates if candidate.candidate_id == candidate_id
    )


def simple_cost(value: float) -> CostBreakdown:
    return CostBreakdown(
        uncached_input=value,
        cache_write=0.0,
        cache_read=0.0,
        output=0.0,
        retry=0.0,
        escalation=0.0,
        total=value,
        cache_full_price_baseline=0.0,
        cache_net_savings=0.0,
    )


def test_all_holdout_cost_components_reconcile_to_total() -> None:
    report = build_offline_lab().assess()
    for task in report.tasks:
        for candidate in task.candidates:
            if candidate.costs is None:
                continue
            costs = candidate.costs
            assert costs.total == pytest.approx(
                costs.uncached_input
                + costs.cache_write
                + costs.cache_read
                + costs.output
                + costs.retry
                + costs.escalation
            )


def test_hand_calculated_provider_cost_oracles() -> None:
    grounded = _task(build_offline_lab().assess(), "grounded_lookup")
    spruce = _candidate(grounded, "Spruce-S")
    cedar = _candidate(grounded, "Cedar-S")
    assert spruce.costs is not None
    assert cedar.costs is not None
    assert spruce.costs.uncached_input == pytest.approx(0.080)
    assert spruce.costs.cache_write == pytest.approx(0.072)
    assert spruce.costs.cache_read == pytest.approx(0.048)
    assert spruce.costs.output == pytest.approx(0.144)
    assert spruce.costs.retry == pytest.approx(0.0)
    assert cedar.costs.uncached_input == pytest.approx(0.640)
    assert cedar.costs.output == pytest.approx(0.252)


def test_fixture_observed_escalation_charge_is_positive() -> None:
    hard = _task(build_offline_lab().assess(), "high_stakes_reasoning")
    flint = _candidate(hard, "Flint-E")
    assert flint.costs is not None
    assert flint.costs.escalation == pytest.approx(0.075)
    assert flint.costs.escalation > 0


def test_dev_and_holdout_costs_are_reported_separately() -> None:
    routine = _task(build_offline_lab().assess(), "routine_triage")
    spruce = _candidate(routine, "Spruce-S")
    assert spruce.dev_costs is not None
    assert spruce.costs is not None
    assert spruce.dev_costs.total > spruce.costs.total
    assert spruce.dev_costs.total + spruce.costs.total > spruce.costs.total


def test_low_reuse_cache_write_does_not_pay() -> None:
    routine = _task(build_offline_lab().assess(), "routine_triage")
    cedar_costs = _candidate(routine, "Cedar-S").costs
    assert cedar_costs is not None
    assert cedar_costs.cache_net_savings < 0.0


def test_short_but_hard_case_cannot_be_cheaply_misrouted() -> None:
    hard = _task(build_offline_lab().assess(), "high_stakes_reasoning")
    assert hard.qualified_ranking == ("Flint-E",)
    assert hard.route.primary_candidate == "Flint-E"
    assert hard.route.evaluated_strategies[0].primary_candidate == "Flint-E"
    for candidate_id in ("Spruce-S", "Cedar-S", "Quartz-E"):
        candidate = _candidate(hard, candidate_id)
        assert not candidate.qualified
        assert any("unsupported controls" in failure for failure in candidate.gate_failures)


def test_route_is_separate_minimum_total_expected_cost_optimization() -> None:
    routine = _task(build_offline_lab().assess(), "routine_triage")
    route = routine.route
    assert routine.qualified_ranking  # comparison view remains available
    assert route.reason == "lowest total expected cost among holdout-qualified strategies"
    assert route.primary_candidate == "Spruce-S"
    # Holdout calibration observes no failures for the least-capable supported
    # routine candidate, so probability is zero; all stronger fallbacks tie on
    # expected cost and deterministic candidate ordering selects Cedar-S.
    assert route.escalation_candidate == "Cedar-S"
    assert route.escalation_probability == 0.0
    assert route.escalation_cost == 0.0
    assert route.total_expected_cost == pytest.approx(route.primary_cost + route.escalation_cost)
    assert route.total_expected_cost == pytest.approx(
        min(strategy.total_expected_cost for strategy in route.evaluated_strategies)
    )


def test_optimizer_enumerates_farther_cheaper_stronger_fallback() -> None:
    metrics = QualityMetrics(1.0, 0.0, 0.0, 1.0, 1.0, 0.0, 1.0)

    def candidate(candidate_id: str, cost: float) -> CandidateAssessment:
        return CandidateAssessment(
            task="counterexample",
            candidate_id=candidate_id,
            provider="Virtual",
            expected_observations=1,
            observed_observations=1,
            dev_observations=0,
            holdout_observations=1,
            dev_metrics=None,
            metrics=metrics,
            dev_costs=None,
            costs=simple_cost(cost),
            preflight_rejections=(),
            failed_holdout_runs=(),
            holdout_escalation_probability=0.5,
            qualified=True,
            gate_failures=(),
            normalized_score=1.0,
        )

    candidates = (
        candidate("tier-1", 1.0),
        candidate("tier-2-expensive", 100.0),
        candidate("tier-3-cheap", 2.0),
    )
    route = _recommend_route(
        "counterexample",
        tuple(item.candidate_id for item in candidates),
        candidates,
        {"tier-1": 1, "tier-2-expensive": 2, "tier-3-cheap": 3},
        10.0,
    )
    assert any(
        strategy.primary_candidate == "tier-1"
        and strategy.escalation_candidate == "tier-2-expensive"
        for strategy in route.evaluated_strategies
    )
    assert any(
        strategy.primary_candidate == "tier-1"
        and strategy.escalation_candidate == "tier-3-cheap"
        for strategy in route.evaluated_strategies
    )
    assert route.primary_candidate == "tier-1"
    assert route.escalation_candidate == "tier-3-cheap"


def test_failing_primary_and_fallback_preserve_chained_residual_risk() -> None:
    metrics = QualityMetrics(1.0, 0.0, 0.0, 1.0, 1.0, 0.0, 1.0)

    def candidate(candidate_id: str, cost: float) -> CandidateAssessment:
        return CandidateAssessment(
            task="chain-failure",
            candidate_id=candidate_id,
            provider="Virtual",
            expected_observations=1,
            observed_observations=1,
            dev_observations=0,
            holdout_observations=1,
            dev_metrics=None,
            metrics=metrics,
            dev_costs=None,
            costs=simple_cost(cost),
            preflight_rejections=(),
            failed_holdout_runs=(),
            holdout_escalation_probability=1.0,
            qualified=True,
            gate_failures=(),
            normalized_score=1.0,
        )

    primary = candidate("primary", 1.0)
    cheap_fallback = candidate("cheap-fallback", 0.1)
    route = _recommend_route(
        "chain-failure",
        ("primary", "cheap-fallback"),
        (primary, cheap_fallback),
        {"primary": 1, "cheap-fallback": 2},
        10.0,
    )
    strategy = next(
        item
        for item in route.evaluated_strategies
        if item.primary_candidate == "primary"
        and item.escalation_candidate == "cheap-fallback"
    )
    assert strategy.escalation_probability == 1.0
    assert strategy.escalation_cost == pytest.approx(0.1)
    assert strategy.residual_failure_probability == 1.0
    assert strategy.residual_failure_handling == "manual_review"
    assert strategy.manual_review_cost == pytest.approx(10.0)
    assert strategy.total_expected_cost == pytest.approx(11.1)
    # A safe route is preferred once manual review is priced.
    safe = replace(cheap_fallback, holdout_escalation_probability=0.0)
    safe_route = _recommend_route(
        "chain-failure",
        ("primary", "cheap-fallback"),
        (primary, safe),
        {"primary": 1, "cheap-fallback": 2},
        10.0,
    )
    assert safe_route.primary_candidate == "cheap-fallback"
    assert safe_route.escalation_candidate is None
    assert safe_route.escalation_probability == 0.0
    assert safe_route.escalation_cost == 0.0
    assert safe_route.residual_failure_probability == 0.0
    assert safe_route.residual_failure_handling is None
    assert safe_route.manual_review_cost == 0.0
    assert safe_route.total_expected_cost == pytest.approx(0.1)


def test_huge_cost_values_with_real_differences_are_normalized() -> None:
    metrics = QualityMetrics(1.0, 0.0, 0.0, 1.0, 1.0, 0.0, 1.0)
    candidates = tuple(
        CandidateAssessment(
            task="huge",
            candidate_id=candidate_id,
            provider="Virtual",
            expected_observations=1,
            observed_observations=1,
            dev_observations=0,
            holdout_observations=1,
            dev_metrics=None,
            metrics=metrics,
            dev_costs=None,
            costs=simple_cost(cost),
            preflight_rejections=(),
            failed_holdout_runs=(),
            holdout_escalation_probability=0.5,
            qualified=True,
            gate_failures=(),
            normalized_score=None,
        )
        for candidate_id, cost in (
            ("low", 1_000_000_000_000.0),
            ("middle", 1_000_000_000_500.0),
            ("high", 1_000_000_001_000.0),
        )
    )
    weights = RankingWeights(0, 0, 0, 0, 0, 0, 1, 0)
    scores = {
        candidate.candidate_id: candidate.normalized_score
        for candidate in _rank_qualified(candidates, weights)
    }
    assert scores == {"low": 1.0, "middle": 0.5, "high": 0.0}


def test_no_stronger_fallback_reports_residual_manual_review_risk() -> None:
    metrics = QualityMetrics(1.0, 0.0, 0.0, 1.0, 1.0, 0.0, 1.0)
    candidate = CandidateAssessment(
        task="residual",
        candidate_id="top-tier",
        provider="Virtual",
        expected_observations=5,
        observed_observations=5,
        dev_observations=0,
        holdout_observations=5,
        dev_metrics=None,
        metrics=metrics,
        dev_costs=None,
        costs=simple_cost(1.0),
        preflight_rejections=(),
        failed_holdout_runs=(),
        holdout_escalation_probability=0.2,
        qualified=True,
        gate_failures=(),
        normalized_score=1.0,
    )
    route = _recommend_route(
        "residual",
        ("top-tier",),
        (candidate,),
        {"top-tier": 5},
        10.0,
    )
    assert route.escalation_candidate is None
    assert route.escalation_probability == 0.0
    assert route.escalation_cost == 0.0
    assert route.manual_review_cost == pytest.approx(2.0)
    assert route.total_expected_cost == pytest.approx(3.0)
    assert route.total_expected_cost == pytest.approx(
        route.primary_cost + route.escalation_cost + route.manual_review_cost
    )
    assert route.residual_failure_probability == 0.2
    assert route.residual_failure_handling == "manual_review"


def test_no_qualified_candidate_returns_explicit_no_route() -> None:
    impossible = _task(build_offline_lab().assess(), "impossible_safety")
    assert impossible.qualified_ranking == ()
    assert impossible.route.primary_candidate is None
    assert impossible.route.escalation_candidate is None
    assert impossible.route.total_expected_cost == 0.0
    assert impossible.route.residual_failure_probability == 0.0
    assert impossible.route.residual_failure_handling == "unavailable"
    assert impossible.route.evaluated_strategies == ()
    assert impossible.route.reason == "no candidate passed every hard gate"
