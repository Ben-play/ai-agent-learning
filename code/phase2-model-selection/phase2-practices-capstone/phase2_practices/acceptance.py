"""Executable semantic acceptance checks for the offline capstone."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter

from . import __all__ as public_names
from . import build_offline_lab
_SUPPORTED_CASE_MANIFEST_DIGEST = (
    "154232ed82f87b01b7903233655fd551a5711ad17dc2ce1224cec92b61bf1ee6"
)

from .contracts import (
    AssessmentReport,
    AssessmentRunSpec,
    CandidateAssessment,
    CandidateRunSpec,
    CostBreakdown,
    HardGates,
    HoldoutTrial,
    QualityMetrics,
    RankingWeights,
    RouteRecommendation,
    RouteStrategy,
    TaskAssessment,
)


def assert_accepted(report: AssessmentReport) -> None:
    """Reject malformed reports as well as semantic assessment regressions."""

    _check(
        public_names == ["AssessmentLab", "AssessmentReport", "build_offline_lab"],
        "public interface changed",
    )
    _check(report.fixture_integrity_validated, "fixture integrity was not validated")
    _validate_run_spec(report.run_spec)
    _check(_nonnegative_int(report.case_count), "case count must be a nonnegative integer")
    _check(
        report.case_count == len(report.run_spec.cases),
        "case count does not reconcile with run spec",
    )
    _check(
        _nonnegative_int(report.observation_count),
        "observation count must be a nonnegative integer",
    )

    task_names = [task.task for task in report.tasks]
    _check(all(task_names), "task names must be nonempty")
    _check(len(task_names) == len(set(task_names)), "task names must be unique")
    expected_tasks = {case.task for case in report.run_spec.cases}
    _check(set(task_names) == expected_tasks, "report tasks do not cover run-spec tasks")

    observed_by_provider: Counter[str] = Counter()
    observed_total = 0
    candidate_ids: set[str] = set()
    for task in report.tasks:
        _validate_task(task, report.run_spec)
        expected_repeats = sum(
            case.repeats for case in report.run_spec.cases if case.task == task.task
        )
        for candidate in task.candidates:
            candidate_ids.add(candidate.candidate_id)
            _check(
                candidate.expected_observations == expected_repeats,
                f"expected observations do not match run spec for {task.task}/{candidate.candidate_id}",
            )
            observed_total += candidate.observed_observations
            observed_by_provider[candidate.provider] += candidate.observed_observations

    _check(
        len(candidate_ids) == len(report.run_spec.candidate_config_ids),
        "candidate config IDs do not cover report candidates",
    )
    _check(observed_total == report.observation_count, "observation count does not reconcile")
    provider_names = [item.provider for item in report.provider_observation_counts]
    _check(all(provider_names), "provider names must be nonempty")
    _check(len(provider_names) == len(set(provider_names)), "provider names must be unique")
    _check(
        all(_nonnegative_int(item.observations) for item in report.provider_observation_counts),
        "provider observations must be nonnegative integers",
    )
    _check(
        {item.provider: item.observations for item in report.provider_observation_counts}
        == dict(observed_by_provider),
        "provider counts do not reconcile with candidate observations",
    )

    # Load-bearing scenario assertions remain semantic rather than total-count based.
    grounded = _task(report, "grounded_lookup")
    routine = _task(report, "routine_triage")
    hard = _task(report, "high_stakes_reasoning")
    impossible = _task(report, "impossible_safety")
    _check(not _candidate(grounded, "Spruce-S").qualified, "unsafe consistent candidate qualified")
    quartz_grounded = _candidate(grounded, "Quartz-E")
    _check(quartz_grounded.metrics is not None, "divergent candidate lacks metrics")
    if quartz_grounded.metrics is not None:
        _check(quartz_grounded.metrics.divergence_rate > 0, "divergent holdout answers were hidden")
    _check(bool(routine.qualified_ranking), "weighted comparison ranking is missing")
    _check(routine.route.primary_candidate == "Spruce-S", "minimum-cost routine route changed")
    _check(hard.qualified_ranking == ("Flint-E",), "short-hard task was misrouted")
    flint_hard = _candidate(hard, "Flint-E")
    _check(flint_hard.costs is not None and flint_hard.costs.escalation > 0, "observed escalation cost missing")
    _check(impossible.qualified_ranking == (), "negative policy unexpectedly qualified")
    _check(impossible.route.primary_candidate is None, "negative policy unexpectedly routed")


def _validate_run_spec(spec: AssessmentRunSpec) -> None:
    _check(bool(spec.fixture_version), "fixture version is missing")
    _sha256(spec.fixture_digest, "fixture digest")
    _sha256(spec.case_manifest_digest, "case manifest digest")
    _check(
        spec.case_manifest_digest == _SUPPORTED_CASE_MANIFEST_DIGEST,
        "run spec case manifest is not trusted",
    )
    _sha256(spec.observation_provenance_digest, "observation provenance digest")
    _check(spec.evaluator_version == "offline-evaluator-v2", "unsupported evaluator version")
    _check(spec.rubric_version == "reference-rubric-v2", "unsupported rubric version")
    _check(spec.tool_policy_id == "no-tools-offline-v1", "unsupported tool policy")
    _check(spec.configuration_split == "dev", "configuration split is not dev")
    _check(spec.decision_split == "holdout", "decision split is not holdout")
    _unique_nonempty(spec.candidate_config_ids, "candidate config IDs")
    _unique_nonempty(spec.task_policy_ids, "task policy IDs")
    policy_tasks = tuple(policy.task for policy in spec.task_policies)
    _unique_nonempty(policy_tasks, "run spec policy tasks")
    _check(
        set(policy_tasks) == {case.task for case in spec.cases},
        "run spec policy tasks do not cover cases",
    )
    _check(
        tuple(sorted(policy.policy_id for policy in spec.task_policies)) == spec.task_policy_ids,
        "run spec policies do not match task policy IDs",
    )
    for policy in spec.task_policies:
        _check(type(policy.require_every_holdout_run) is bool, "invalid joint holdout policy")
        if policy.task in {"high_stakes_reasoning", "impossible_safety"}:
            _check(policy.require_every_holdout_run, "registered task must require every holdout run")
    candidate_ids = tuple(item.candidate_id for item in spec.candidate_configs)
    config_ids = tuple(item.config_id for item in spec.candidate_configs)
    _unique_nonempty(candidate_ids, "candidate manifest IDs")
    _unique_nonempty(config_ids, "candidate manifest config IDs")
    _check(
        tuple(sorted(config_ids)) == spec.candidate_config_ids,
        "candidate config IDs do not match candidate manifest",
    )
    _check(
        all(
            item.provider
            and _nonnegative_int(item.capability_tier)
            and item.capability_tier > 0
            and len(item.supported_controls) == len(set(item.supported_controls))
            for item in spec.candidate_configs
        ),
        "candidate manifest provider/tier is invalid",
    )
    case_ids = tuple(case.case_id for case in spec.cases)
    _unique_nonempty(case_ids, "case IDs")
    _check(bool(spec.dev_case_ids), "dev split is empty")
    _check(bool(spec.holdout_case_ids), "holdout split is empty")
    manifest_projection = tuple(
        {
            "case_id": case.case_id,
            "task": case.task,
            "split": case.split,
            "expected_answer": case.expected_answer,
            "should_abstain": case.should_abstain,
            "allowed_evidence_ids": list(case.allowed_evidence_ids),
            "required_evidence_ids": list(case.required_evidence_ids),
            "repeats": case.repeats,
            "prompt_digest": case.prompt_digest,
            "policy_digest": case.policy_digest,
        }
        for case in spec.cases
    )
    rendered_manifest = json.dumps(
        list(manifest_projection),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    _check(
        hashlib.sha256(rendered_manifest.encode("utf-8")).hexdigest()
        == spec.case_manifest_digest,
        "run spec cases do not match trusted case manifest",
    )
    for case in spec.cases:
        _check(bool(case.task), "case task is empty")
        _check(case.split in {"dev", "holdout"}, "invalid case split")
        _check(bool(case.expected_answer), "case expected answer is empty")
        _check(
            case.should_abstain == (case.expected_answer == "ABSTAIN"),
            "case abstention contract is inconsistent",
        )
        _unique_nonempty(case.allowed_evidence_ids, "allowed evidence IDs", allow_empty=True)
        _sha256(case.prompt_digest, "prompt digest")
        _sha256(case.policy_digest, "policy digest")
        _check(_nonnegative_int(case.repeats) and case.repeats > 0, "case repeats must be positive")
        _unique_nonempty(case.required_evidence_ids, "required evidence IDs", allow_empty=True)
        _check(
            set(case.required_evidence_ids) <= set(case.allowed_evidence_ids),
            "required evidence is not allowlisted",
        )
    evidence_ids = tuple(item.evidence_id for item in spec.evidence_corpus)
    _unique_nonempty(evidence_ids, "evidence corpus IDs")
    case_id_set = set(case_ids)
    corpus_ids_by_case: dict[str, set[str]] = {case_id: set() for case_id in case_id_set}
    for item in spec.evidence_corpus:
        _check(item.case_id in case_id_set, "evidence references unknown case")
        corpus_ids_by_case[item.case_id].add(item.evidence_id)
        _check(bool(item.supported_answer), "evidence supported answer is empty")
        _check(bool(item.content), "evidence content is empty")
        _sha256(item.content_digest, "evidence content digest")
        _check(
            hashlib.sha256(item.content.encode("utf-8")).hexdigest() == item.content_digest,
            "evidence content digest does not match content",
        )
    for case in spec.cases:
        _check(
            set(case.allowed_evidence_ids) == corpus_ids_by_case[case.case_id],
            "case allowlist does not match evidence corpus",
        )
        for evidence_id in case.required_evidence_ids:
            matching = next(
                item for item in spec.evidence_corpus if item.evidence_id == evidence_id
            )
            _check(matching.case_id == case.case_id, "required evidence belongs to another case")
            _check(
                matching.supported_answer == case.expected_answer,
                "required evidence answer disagrees with case",
            )
    expected_task_run_keys = {
        (task, candidate_id)
        for task in {case.task for case in spec.cases}
        for candidate_id in candidate_ids
    }
    actual_task_run_keys = {
        (task_run.task, task_run.candidate_id)
        for task_run in spec.candidate_task_runs
    }
    _check(
        len(spec.candidate_task_runs) == len(actual_task_run_keys),
        "candidate-task run specs must be unique",
    )
    _check(
        actual_task_run_keys == expected_task_run_keys,
        "candidate-task run specs do not cover every task/candidate pair",
    )
    for task_run in spec.candidate_task_runs:
        for value, label in (
            (task_run.expected_observations, "expected observations"),
            (task_run.expected_dev_observations, "expected dev observations"),
            (task_run.expected_holdout_observations, "expected holdout observations"),
        ):
            _check(_nonnegative_int(value), f"candidate-task {label} must be nonnegative")
        _check(
            task_run.expected_dev_observations
            + task_run.expected_holdout_observations
            == task_run.expected_observations,
            "candidate-task split counts do not reconcile",
        )
        if task_run.dev_costs is not None:
            _validate_costs(task_run.dev_costs)
        if task_run.holdout_costs is not None:
            _validate_costs(task_run.holdout_costs)


def _validate_task(task: TaskAssessment, spec: AssessmentRunSpec) -> None:
    _check(bool(task.policy_id), "task policy ID is empty")
    _check(task.policy_id in spec.task_policy_ids, "task policy ID is not in run spec")
    _validate_gates(task.hard_gates)
    _validate_weights(task.ranking_weights)
    _check(
        math.isfinite(task.manual_review_unit_cost)
        and task.manual_review_unit_cost > 0,
        "manual review unit cost must be finite and strictly positive",
    )
    policy = next(item for item in spec.task_policies if item.task == task.task)
    _check(
        task.policy_id == policy.policy_id
        and task.hard_gates == policy.hard_gates
        and task.ranking_weights == policy.ranking_weights
        and task.manual_review_unit_cost == policy.manual_review_unit_cost,
        "task policy does not match run spec",
    )
    candidate_ids = [candidate.candidate_id for candidate in task.candidates]
    _unique_nonempty(tuple(candidate_ids), f"candidate IDs for {task.task}")
    expected_by_candidate = {
        item.candidate_id: item
        for item in spec.candidate_task_runs
        if item.task == task.task
    }
    _check(
        set(candidate_ids) == set(expected_by_candidate),
        "task candidates do not match candidate-task run spec",
    )
    qualified_ids: set[str] = set()
    manifest_by_id = {item.candidate_id: item for item in spec.candidate_configs}
    for candidate in task.candidates:
        expected_run = expected_by_candidate.get(candidate.candidate_id)
        _check(expected_run is not None, "candidate is absent from candidate-task run spec")
        if expected_run is not None:
            _check(
                candidate.observed_observations == expected_run.expected_observations
                and candidate.dev_observations == expected_run.expected_dev_observations
                and candidate.holdout_observations == expected_run.expected_holdout_observations,
                "candidate observation counts do not match candidate-task run spec",
            )
            _check(
                candidate.dev_costs == expected_run.dev_costs
                and candidate.costs == expected_run.holdout_costs,
                "candidate costs do not match candidate-task run spec",
            )
        _check(candidate.task == task.task, "candidate task does not match containing task")
        _check(candidate.candidate_id in manifest_by_id, "candidate ID is absent from run spec")
        if candidate.candidate_id in manifest_by_id:
            _check(
                candidate.provider == manifest_by_id[candidate.candidate_id].provider,
                "candidate provider does not match run spec",
            )
        _validate_candidate(candidate, task.hard_gates)
        if candidate.qualified:
            qualified_ids.add(candidate.candidate_id)
    _check(
        len(task.qualified_ranking) == len(set(task.qualified_ranking)),
        "qualified ranking contains duplicate IDs",
    )
    _check(
        set(task.qualified_ranking) == qualified_ids,
        "qualified ranking does not exactly cover qualified candidates",
    )
    ranked = [_candidate(task, candidate_id) for candidate_id in task.qualified_ranking]
    failures, costs = _audit_holdout_trials(task, spec, ranked, policy.require_every_holdout_run)
    if not ranked:
        _validate_route(task.route, task, manifest_by_id, failures, costs)
        return
    recomputed_scores = _recompute_normalized_scores(ranked, task.ranking_weights)
    _check(
        all(
            candidate.normalized_score is not None
            and math.isclose(
                candidate.normalized_score,
                recomputed_scores[candidate.candidate_id],
                abs_tol=1e-12,
                rel_tol=0.0,
            )
            for candidate in ranked
        ),
        "normalized scores do not match recomputed weighted scores",
    )
    expected_order = tuple(
        item.candidate_id
        for item in sorted(
            ranked,
            key=lambda item: (-recomputed_scores[item.candidate_id], item.candidate_id),
        )
    )
    _check(task.qualified_ranking == expected_order, "qualified ranking order is invalid")
    _validate_route(task.route, task, manifest_by_id, failures, costs)


_TrialKey = tuple[str, int]


def _audit_holdout_trials(
    task: TaskAssessment,
    spec: AssessmentRunSpec,
    qualified: list[CandidateAssessment],
    require_every_run: bool,
) -> tuple[dict[str, set[_TrialKey]], dict[str, dict[_TrialKey, float]]]:
    holdout_cases = {
        case.case_id: case for case in spec.cases
        if case.task == task.task and case.split == spec.decision_split
    }
    expected_keys = {
        (case_id, repeat)
        for case_id, case in holdout_cases.items()
        for repeat in range(1, case.repeats + 1)
    }
    rows: dict[str, dict[_TrialKey, float]] = {candidate.candidate_id: {} for candidate in qualified}
    failed: dict[str, set[_TrialKey]] = {candidate_id: set() for candidate_id in rows}
    wrong_answers: Counter[tuple[str, str]] = Counter()
    _check(isinstance(task.holdout_trials, tuple), "holdout trial ledger must be a tuple")
    for trial in task.holdout_trials:
        _check(isinstance(trial, HoldoutTrial), "invalid holdout trial row")
        _check(trial.candidate_id in rows, "holdout trial candidate is not qualified")
        key = (trial.case_id, trial.repeat)
        _check(_nonnegative_int(trial.repeat) and key in expected_keys, "unexpected holdout trial key")
        candidate_rows = rows[trial.candidate_id]
        _check(key not in candidate_rows, "duplicate holdout trial key")
        _check(
            not isinstance(trial.cost, bool) and math.isfinite(trial.cost) and trial.cost >= 0,
            "holdout trial cost must be finite and nonnegative",
        )
        candidate_rows[key] = trial.cost

        case = holdout_cases[trial.case_id]
        _check(
            isinstance(trial.evidence_ids, tuple)
            and len(set(trial.evidence_ids)) == len(trial.evidence_ids)
            and set(trial.evidence_ids) <= set(case.allowed_evidence_ids),
            "holdout trial evidence does not match case allowlist",
        )
        answer = trial.answer.strip().casefold().rstrip(".!?").strip()
        expected_answer = case.expected_answer.strip().casefold().rstrip(".!?").strip()
        _check(
            type(trial.abstained) is bool and trial.abstained == (answer == "abstain"),
            "holdout trial abstention does not match answer",
        )
        answer_wrong = answer != expected_answer
        wrong_answers[(trial.candidate_id, trial.case_id)] += answer_wrong
        if answer_wrong or (
            require_every_run and (
                trial.abstained != case.should_abstain
                or not set(case.required_evidence_ids).issubset(trial.evidence_ids)
            )
        ):
            failed[trial.candidate_id].add(key)

    for candidate in qualified:
        candidate_id = candidate.candidate_id
        _check(
            bool(expected_keys) and rows[candidate_id].keys() == expected_keys
            and candidate.holdout_observations == len(expected_keys),
            "holdout trial coverage does not match the expected holdout runs",
        )
        _check(
            candidate.costs is not None and _close(sum(rows[candidate_id].values()), candidate.costs.total),
            "holdout trial costs do not reconcile to candidate holdout spend",
        )
        _check(not require_every_run or not failed[candidate_id], "qualified candidate has failed holdout trials")
        _check(
            _close(candidate.holdout_escalation_probability, len(failed[candidate_id]) / len(expected_keys)),
            "candidate escalation probability does not match holdout trials",
        )
        factual_error = sum(
            wrong_answers[(candidate_id, case.case_id)] / case.repeats for case in holdout_cases.values()
        ) / len(holdout_cases)
        _check(
            candidate.metrics is not None and _close(candidate.metrics.factual_error_rate, factual_error),
            "candidate factual error does not match holdout trials",
        )
    return failed, rows


def _recompute_normalized_scores(
    candidates: list[CandidateAssessment], weights: RankingWeights
) -> dict[str, float]:
    raw: dict[str, dict[str, float]] = {
        "quality": {},
        "factuality": {},
        "consistency": {},
        "abstention": {},
        "evidence": {},
        "usage_accuracy": {},
        "cost": {},
        "latency": {},
    }
    for candidate in candidates:
        _check(candidate.metrics is not None and candidate.costs is not None, "ranked candidate lacks metrics/costs")
        if candidate.metrics is None or candidate.costs is None:
            continue
        metrics = candidate.metrics
        raw["quality"][candidate.candidate_id] = metrics.quality
        raw["factuality"][candidate.candidate_id] = 1 - metrics.factual_error_rate
        raw["consistency"][candidate.candidate_id] = 1 - metrics.divergence_rate
        raw["abstention"][candidate.candidate_id] = metrics.correct_abstention_rate
        raw["evidence"][candidate.candidate_id] = metrics.evidence_coverage
        raw["usage_accuracy"][candidate.candidate_id] = 1 - min(
            metrics.estimated_vs_actual_usage_delta, 1.0
        )
        raw["cost"][candidate.candidate_id] = candidate.costs.total
        raw["latency"][candidate.candidate_id] = metrics.mean_fixed_latency_ms
    higher_is_better = {
        "quality": True,
        "factuality": True,
        "consistency": True,
        "abstention": True,
        "evidence": True,
        "usage_accuracy": True,
        "cost": False,
        "latency": False,
    }
    weight_map = dict(weights.items())
    scores = {candidate.candidate_id: 0.0 for candidate in candidates}
    for metric, values_by_candidate in raw.items():
        values = tuple(values_by_candidate.values())
        low, high = min(values), max(values)
        for candidate_id, value in values_by_candidate.items():
            if math.isclose(low, high, abs_tol=1e-12, rel_tol=0.0):
                normalized = 1.0
            elif higher_is_better[metric]:
                normalized = (value - low) / (high - low)
            else:
                normalized = (high - value) / (high - low)
            scores[candidate_id] += normalized * weight_map[metric]
    return {candidate_id: round(value, 12) for candidate_id, value in scores.items()}


def _validate_candidate(candidate: CandidateAssessment, gates: HardGates) -> None:
    _check(bool(candidate.candidate_id), "candidate ID is empty")
    _check(bool(candidate.provider), "candidate provider is empty")
    for value, label in (
        (candidate.expected_observations, "expected observations"),
        (candidate.observed_observations, "observed observations"),
        (candidate.dev_observations, "dev observations"),
        (candidate.holdout_observations, "holdout observations"),
    ):
        _check(_nonnegative_int(value), f"{label} must be a nonnegative integer")
    _check(
        candidate.dev_observations + candidate.holdout_observations
        == candidate.observed_observations,
        "candidate split observations do not reconcile",
    )
    _check(
        candidate.observed_observations <= candidate.expected_observations,
        "candidate observations exceed expected coverage",
    )
    if candidate.dev_metrics is not None:
        _validate_metrics(candidate.dev_metrics)
    if candidate.metrics is not None:
        _validate_metrics(candidate.metrics)
    if candidate.dev_observations > 0:
        _check(candidate.dev_metrics is not None, "dev observations require dev metrics")
        _check(candidate.dev_costs is not None, "dev observations require dev costs")
    else:
        _check(candidate.dev_metrics is None, "zero dev observations cannot carry dev metrics")
        _check(candidate.dev_costs is None, "zero dev observations cannot carry dev costs")
    if candidate.holdout_observations > 0:
        _check(candidate.metrics is not None, "holdout observations require holdout metrics")
        _check(candidate.costs is not None, "holdout observations require holdout costs")
    else:
        _check(candidate.metrics is None, "zero holdout observations cannot carry holdout metrics")
        _check(candidate.costs is None, "zero holdout observations cannot carry holdout costs")
    if candidate.dev_costs is not None:
        _validate_costs(candidate.dev_costs)
    if candidate.costs is not None:
        _validate_costs(candidate.costs)
    _check(
        math.isfinite(candidate.holdout_escalation_probability)
        and 0 <= candidate.holdout_escalation_probability <= 1,
        "candidate escalation probability must be in [0, 1]",
    )
    if candidate.qualified:
        _check(candidate.metrics is not None and candidate.costs is not None, "qualified candidate lacks holdout metrics/costs")
        _check(not candidate.gate_failures, "qualified candidate has gate failures")
        _check(not candidate.preflight_rejections, "qualified candidate has preflight rejections")
        _check(not candidate.failed_holdout_runs, "qualified candidate has failed holdout runs")
        _check(candidate.normalized_score is not None, "qualified candidate lacks normalized score")
        if candidate.metrics is not None:
            _check(not _metric_gate_failures(candidate.metrics, gates), "qualified candidate violates hard gates")
    else:
        _check(candidate.normalized_score is None, "nonqualified candidate has normalized score")
        _check(
            bool(candidate.gate_failures or candidate.preflight_rejections or candidate.failed_holdout_runs),
            "nonqualified candidate lacks rejection evidence",
        )


def _validate_metrics(metrics: QualityMetrics) -> None:
    for value, label in (
        (metrics.quality, "quality"),
        (metrics.factual_error_rate, "factual error rate"),
        (metrics.divergence_rate, "divergence rate"),
        (metrics.correct_abstention_rate, "decision correctness"),
        (metrics.evidence_coverage, "evidence coverage"),
    ):
        _check(math.isfinite(value) and 0 <= value <= 1, f"{label} must be in [0, 1]")
    _check(
        math.isfinite(metrics.estimated_vs_actual_usage_delta)
        and metrics.estimated_vs_actual_usage_delta >= 0,
        "usage delta must be finite and nonnegative",
    )
    _check(
        math.isfinite(metrics.mean_fixed_latency_ms) and metrics.mean_fixed_latency_ms >= 0,
        "latency must be finite and nonnegative",
    )


def _validate_gates(gates: HardGates) -> None:
    for value in (
        gates.minimum_quality,
        gates.maximum_factual_error_rate,
        gates.maximum_divergence_rate,
        gates.minimum_correct_abstention_rate,
        gates.minimum_evidence_coverage,
    ):
        _check(math.isfinite(value) and 0 <= value <= 1, "hard-gate rates must be in [0, 1]")
    _check(
        math.isfinite(gates.maximum_mean_fixed_latency_ms)
        and gates.maximum_mean_fixed_latency_ms >= 0,
        "latency gate must be finite and nonnegative",
    )


def _validate_weights(weights: RankingWeights) -> None:
    values = tuple(value for _, value in weights.items())
    _check(all(math.isfinite(value) and value >= 0 for value in values), "weights must be finite and nonnegative")
    _check(math.isclose(sum(values), 1.0, abs_tol=1e-9, rel_tol=0.0), "weights must total 1")


def _validate_costs(costs: CostBreakdown) -> None:
    components = (
        costs.uncached_input,
        costs.cache_write,
        costs.cache_read,
        costs.output,
        costs.retry,
        costs.escalation,
    )
    _check(all(math.isfinite(value) and value >= 0 for value in components), "cost components must be finite and nonnegative")
    _check(math.isfinite(costs.total) and costs.total >= 0, "total cost must be finite and nonnegative")
    _check(
        math.isfinite(costs.cache_full_price_baseline)
        and costs.cache_full_price_baseline >= 0,
        "cache full-price baseline must be finite and nonnegative",
    )
    expected_savings = (
        costs.cache_full_price_baseline - costs.cache_write - costs.cache_read
    )
    _check(
        math.isclose(
            costs.cache_net_savings,
            expected_savings,
            abs_tol=1e-12,
            rel_tol=1e-12,
        ),
        "cache savings do not reconcile",
    )
    _check(math.isclose(costs.total, sum(components), abs_tol=1e-12, rel_tol=1e-12), "cost total does not reconcile")


def _validate_route(
    route: RouteRecommendation,
    task: TaskAssessment,
    manifest_by_id: dict[str, CandidateRunSpec],
    failures: dict[str, set[_TrialKey]],
    costs: dict[str, dict[_TrialKey, float]],
) -> None:
    _check(route.task == task.task, "route task does not match containing task")
    if not costs:
        _check(route.primary_candidate is None and route.escalation_candidate is None, "no-route IDs must be None")
        _check(
            route.escalation_probability == 0
            and route.primary_cost == 0
            and route.escalation_cost == 0
            and route.manual_review_cost == 0
            and route.total_expected_cost == 0,
            "no-route costs/probability must be zero",
        )
        _check(route.residual_failure_probability == 0, "no-route residual probability must be zero")
        _check(route.residual_failure_handling == "unavailable", "no-route handling must be unavailable")
        _check(route.evaluated_strategies == (), "no-route strategies must be empty")
        _check(route.reason == "no candidate passed every hard gate", "no-route reason is invalid")
        return
    _check(route.primary_candidate in costs, "route primary is not qualified")
    _check(bool(route.evaluated_strategies), "qualified route has no evaluated strategies")
    expected_strategy_keys = {
        (primary_id, fallback_id)
        for primary_id in costs
        for fallback_id in (
            tuple(
                candidate_id
                for candidate_id in costs
                if manifest_by_id[candidate_id].capability_tier > manifest_by_id[primary_id].capability_tier
            )
            or (None,)
        )
    }
    actual_strategy_keys = {
        (strategy.primary_candidate, strategy.escalation_candidate)
        for strategy in route.evaluated_strategies
    }
    _check(
        actual_strategy_keys == expected_strategy_keys,
        "route strategies do not enumerate every eligible primary/fallback",
    )
    audited_totals: dict[tuple[str, str | None], float] = {}
    for strategy in route.evaluated_strategies:
        key = (strategy.primary_candidate, strategy.escalation_candidate)
        _check(key not in audited_totals, "duplicate route strategy")
        audited_totals[key] = _audit_strategy(strategy, failures, costs, task.manual_review_unit_cost)

    ordered = tuple(
        sorted(
            route.evaluated_strategies,
            key=lambda item: (
                audited_totals[(item.primary_candidate, item.escalation_candidate)],
                item.primary_candidate,
                item.escalation_candidate or "",
            ),
        )
    )
    expected = ordered[0]
    selected = RouteStrategy(
        primary_candidate=route.primary_candidate or "",
        escalation_candidate=route.escalation_candidate,
        escalation_probability=route.escalation_probability,
        primary_cost=route.primary_cost,
        escalation_cost=route.escalation_cost,
        manual_review_cost=route.manual_review_cost,
        total_expected_cost=route.total_expected_cost,
        residual_failure_probability=route.residual_failure_probability,
        residual_failure_handling=route.residual_failure_handling,
    )
    _check(selected == expected, "chosen route is not the true minimum strategy")
    _check(route.evaluated_strategies == ordered, "evaluated strategy order is invalid")
    _check(route.reason == "lowest total expected cost among holdout-qualified strategies", "route reason is invalid")


def _audit_strategy(
    strategy: RouteStrategy,
    failures: dict[str, set[_TrialKey]],
    costs: dict[str, dict[_TrialKey, float]],
    manual_review_unit_cost: float,
) -> float:
    primary_costs = costs[strategy.primary_candidate]
    primary_failures = failures[strategy.primary_candidate]
    n_trials = len(primary_costs)
    fallback_id = strategy.escalation_candidate
    triggered = primary_failures if fallback_id is not None else set()
    unresolved = primary_failures if fallback_id is None else primary_failures & failures[fallback_id]
    primary_cost = math.fsum(primary_costs.values()) / n_trials
    fallback_cost = (
        math.fsum(costs[fallback_id][key] for key in triggered) / n_trials
        if fallback_id is not None else 0.0
    )
    residual = len(unresolved) / n_trials
    review_cost = residual * manual_review_unit_cost
    total = primary_cost + fallback_cost + review_cost
    for observed, expected, label in (
        (strategy.primary_cost, primary_cost, "primary cost"),
        (strategy.escalation_probability, len(triggered) / n_trials, "escalation probability"),
        (strategy.escalation_cost, fallback_cost, "escalation cost"),
        (strategy.residual_failure_probability, residual, "residual probability"),
        (strategy.manual_review_cost, review_cost, "manual review cost"),
        (strategy.total_expected_cost, total, "total expected cost"),
    ):
        _check(math.isfinite(observed) and observed >= 0 and _close(observed, expected), f"strategy {label} mismatch")
    _check(
        strategy.residual_failure_handling == ("manual_review" if unresolved else None),
        "strategy residual handling mismatch",
    )
    return total


def _close(observed: float, expected: float) -> bool:
    return math.isclose(observed, expected, abs_tol=1e-12, rel_tol=1e-12)


def _metric_gate_failures(metrics: QualityMetrics, gates: HardGates) -> bool:
    return (
        metrics.quality < gates.minimum_quality
        or metrics.factual_error_rate > gates.maximum_factual_error_rate
        or metrics.divergence_rate > gates.maximum_divergence_rate
        or metrics.correct_abstention_rate < gates.minimum_correct_abstention_rate
        or metrics.evidence_coverage < gates.minimum_evidence_coverage
        or metrics.mean_fixed_latency_ms > gates.maximum_mean_fixed_latency_ms
    )


def accept(report: AssessmentReport) -> None:
    """Validate a report and emit the single acceptance line."""

    assert_accepted(report)
    print("PHASE 2 PRACTICES ACCEPTED")


def main() -> None:
    accept(build_offline_lab().assess())


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _sha256(value: str, label: str) -> None:
    _check(
        len(value) == 64 and all(character in "0123456789abcdef" for character in value),
        f"{label} must be a lowercase SHA-256 digest",
    )


def _unique_nonempty(
    values: tuple[str, ...], label: str, *, allow_empty: bool = False
) -> None:
    if not allow_empty:
        _check(bool(values), f"{label} must be nonempty")
    _check(all(values), f"{label} contain an empty value")
    _check(len(values) == len(set(values)), f"{label} must be unique")


def _nonnegative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _task(report: AssessmentReport, name: str) -> TaskAssessment:
    matches = [task for task in report.tasks if task.task == name]
    _check(len(matches) == 1, f"required task missing or duplicated: {name}")
    return matches[0]


def _candidate(task: TaskAssessment, candidate_id: str) -> CandidateAssessment:
    matches = [candidate for candidate in task.candidates if candidate.candidate_id == candidate_id]
    _check(len(matches) == 1, f"candidate missing or duplicated: {task.task}/{candidate_id}")
    return matches[0]


__all__ = ["accept", "assert_accepted", "main"]


if __name__ == "__main__":
    main()
