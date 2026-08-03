"""Deep offline assessment module: fixtures in, validated report out."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

from .adapters import (
    PreflightBudgetError,
    ProviderAdapter,
    UnsupportedControlError,
    build_adapter,
)
from .contracts import (
    AssessmentReport,
    AssessmentRunSpec,
    CandidateAssessment,
    CandidateProfile,
    CandidateRunSpec,
    CandidateTaskRunSpec,
    CaseRunSpec,
    CostBreakdown,
    EvaluationCase,
    EvidenceRecord,
    HardGates,
    Observation,
    ProviderObservationCount,
    QualityMetrics,
    RankingWeights,
    RouteRecommendation,
    RouteStrategy,
    SemanticPolicy,
    TaskAssessment,
    TaskPolicy,
    TaskPolicyRunSpec,
)

_SUPPORTED_EVALUATOR_VERSION = "offline-evaluator-v2"
_SUPPORTED_RUBRIC_VERSION = "reference-rubric-v2"
_SUPPORTED_TOOL_POLICY_ID = "no-tools-offline-v1"
_SUPPORTED_CASE_MANIFEST_DIGEST = (
    "154232ed82f87b01b7903233655fd551a5711ad17dc2ce1224cec92b61bf1ee6"
)
_NONCOMPENSABLE_TASKS = frozenset({"high_stakes_reasoning", "impossible_safety"})

_COST_COMPONENTS = (
    "uncached_input",
    "cache_write",
    "cache_read",
    "output",
    "retry",
    "escalation",
)
_METRIC_DIRECTIONS = {
    "quality": True,
    "factuality": True,
    "consistency": True,
    "abstention": True,
    "evidence": True,
    "usage_accuracy": True,
    "cost": False,
    "latency": False,
}


class FixtureIntegrityError(ValueError):
    """Raised when deterministic fixtures are incomplete or inconsistent."""


class AssessmentLab:
    """Load, validate, repeat, gate, rank, and route a fixture assessment."""

    def __init__(self, fixture_root: Path) -> None:
        self._fixture_root = fixture_root

    def assess(self) -> AssessmentReport:
        loaded = self._load_and_validate()
        observations, assessments = self._evaluate(loaded)
        candidate_task_runs = tuple(
            CandidateTaskRunSpec(
                task=task,
                candidate_id=candidate_id,
                expected_observations=assessment.observed_observations,
                expected_dev_observations=assessment.dev_observations,
                expected_holdout_observations=assessment.holdout_observations,
                dev_costs=assessment.dev_costs,
                holdout_costs=assessment.costs,
            )
            for (task, candidate_id), assessment in sorted(assessments.items())
        )
        loaded.run_spec = replace(
            loaded.run_spec,
            candidate_task_runs=candidate_task_runs,
        )
        tasks = self._gate_rank_and_route(loaded, assessments)
        counts = Counter(observation.provider for observation in observations)
        return AssessmentReport(
            fixture_integrity_validated=True,
            run_spec=loaded.run_spec,
            case_count=len(loaded.cases),
            observation_count=len(observations),
            provider_observation_counts=tuple(
                ProviderObservationCount(provider, counts[provider])
                for provider in sorted(counts)
            ),
            tasks=tasks,
        )

    def _load_and_validate(self) -> _LoadedFixtures:
        profiles_data = _load_json(self._fixture_root / "provider-profiles.json")
        cases_data = _load_json(self._fixture_root / "evaluation-cases.json")
        observations_data = _load_json(self._fixture_root / "observations.json")
        prices_data = _load_json(self._fixture_root / "prices.json")
        evidence_data = _load_json(self._fixture_root / "evidence-corpus.json")
        case_manifest_data = _load_json(self._fixture_root / "case-manifest.json")

        _validate_supported_contract_versions(cases_data)
        case_manifest_digest = _validate_case_manifest(cases_data, case_manifest_data)
        _validate_observation_provenance(
            profiles_data,
            cases_data,
            observations_data,
            case_manifest_digest,
        )
        profiles = tuple(_parse_profile(item) for item in _objects(profiles_data, "candidates"))
        cases = tuple(_parse_case(item) for item in _objects(cases_data, "cases"))
        evidence_corpus = _parse_evidence_corpus(evidence_data)
        evidence_requirements = _parse_evidence_requirements(evidence_data)
        _validate_case_evidence(cases, evidence_corpus, evidence_requirements)
        run_spec = _build_run_spec(
            profiles_data,
            cases_data,
            observations_data,
            prices_data,
            evidence_data,
            case_manifest_data,
            profiles,
            cases,
            tuple(
                _parse_task_policy(item)
                for item in _objects(cases_data, "task_policies")
            ),
            evidence_corpus,
        )
        task_policies = tuple(
            _parse_task_policy(item) for item in _objects(cases_data, "task_policies")
        )
        price_book = _parse_prices(prices_data)
        raw_observations = tuple(_mapping(item) for item in _objects(observations_data, "observations"))

        _unique((profile.candidate_id for profile in profiles), "candidate id")
        _unique((profile.config_id for profile in profiles), "candidate config id")
        _unique((case.case_id for case in cases), "case id")
        _unique((policy.task for policy in task_policies), "task policy")
        _unique((policy.policy_id for policy in task_policies), "task policy id")
        _unique(
            (
                (
                    _string(raw["candidate_id"]),
                    _string(raw["case_id"]),
                    _integer(raw["repeat"]),
                )
                for raw in raw_observations
            ),
            "observation key",
        )

        candidate_ids = {profile.candidate_id for profile in profiles}
        case_ids = {case.case_id for case in cases}
        tasks = {case.task for case in cases}
        policy_tasks = {policy.task for policy in task_policies}
        if tasks != policy_tasks:
            raise FixtureIntegrityError(
                f"task policy coverage mismatch: cases={sorted(tasks)}, policies={sorted(policy_tasks)}"
            )
        policies_by_task = {policy.task: policy for policy in task_policies}
        for task in tasks:
            policy = policies_by_task[task]
            if task in _NONCOMPENSABLE_TASKS and not policy.require_every_holdout_run:
                raise FixtureIntegrityError(
                    f"registered noncompensable task {task} must require every holdout run"
                )
            splits = {case.split for case in cases if case.task == task}
            if splits == {"holdout"} and not policies_by_task[task].holdout_only_negative_policy:
                raise FixtureIntegrityError(
                    f"task {task} needs a dev case or explicit holdout-only negative policy"
                )
            if "holdout" not in splits:
                raise FixtureIntegrityError(f"task {task} has no isolated holdout case")
        if set(price_book) != candidate_ids:
            raise FixtureIntegrityError("price coverage must exactly match candidate profiles")

        case_by_id = {case.case_id: case for case in cases}
        _unique(
            (_string(raw["observation_id"]) for raw in raw_observations),
            "observation id",
        )
        observation_lookup: dict[tuple[str, str, int], Mapping[str, Any]] = {}
        estimate_lookup_data: dict[tuple[str, str, int], Mapping[str, Any]] = {}
        for raw in raw_observations:
            candidate_id = _string(raw["candidate_id"])
            case_id = _string(raw["case_id"])
            repeat = _integer(raw["repeat"])
            if candidate_id not in candidate_ids:
                raise FixtureIntegrityError(f"unknown observation candidate: {candidate_id}")
            if case_id not in case_ids:
                raise FixtureIntegrityError(f"unknown observation case: {case_id}")
            if repeat < 1 or repeat > case_by_id[case_id].repeats:
                raise FixtureIntegrityError(
                    f"repeat out of range for {candidate_id}/{case_id}: {repeat}"
                )
            key = (candidate_id, case_id, repeat)
            observation_lookup[key] = raw
            estimate_lookup_data[key] = raw

        expected_keys = {
            (profile.candidate_id, case.case_id, repeat)
            for profile in profiles
            for case in cases
            if set(dict(case.policy.controls)) <= profile.supported_controls
            for repeat in range(1, case.repeats + 1)
        }
        actual_keys = set(observation_lookup)
        if expected_keys != actual_keys:
            missing = sorted(expected_keys - actual_keys)
            extra = sorted(actual_keys - expected_keys)
            raise FixtureIntegrityError(
                f"observation coverage mismatch: missing={missing}, extra={extra}"
            )

        for task_policy in task_policies:
            weights = tuple(weight for _, weight in task_policy.weights.items())
            if any(not math.isfinite(weight) or weight < 0 for weight in weights):
                raise FixtureIntegrityError(
                    f"ranking weights for {task_policy.task} must be finite and nonnegative"
                )
            weight_total = sum(weights)
            if not math.isclose(weight_total, 1.0, abs_tol=1e-9):
                raise FixtureIntegrityError(
                    f"ranking weights for {task_policy.task} must total 1.0"
                )

        def lookup(candidate_id: str, case_id: str, repeat: int) -> Mapping[str, Any] | None:
            return observation_lookup.get((candidate_id, case_id, repeat))

        def estimate_lookup(
            candidate_id: str, case_id: str, repeat: int
        ) -> Mapping[str, Any] | None:
            return estimate_lookup_data.get((candidate_id, case_id, repeat))

        adapters = {
            profile.candidate_id: build_adapter(profile, lookup, estimate_lookup)
            for profile in profiles
        }
        return _LoadedFixtures(
            profiles=profiles,
            cases=cases,
            run_spec=run_spec,
            task_policies={policy.task: policy for policy in task_policies},
            prices=price_book,
            adapters=adapters,
            observation_lookup=observation_lookup,
        )

    def _evaluate(
        self, loaded: _LoadedFixtures
    ) -> tuple[tuple[Observation, ...], dict[tuple[str, str], CandidateAssessment]]:
        all_observations: list[Observation] = []
        assessments: dict[tuple[str, str], CandidateAssessment] = {}
        cases_by_task: dict[str, list[EvaluationCase]] = defaultdict(list)
        for case in loaded.cases:
            cases_by_task[case.task].append(case)

        for task in sorted(cases_by_task):
            task_cases = tuple(sorted(cases_by_task[task], key=lambda item: item.case_id))
            dev_cases = tuple(case for case in task_cases if case.split == "dev")
            holdout_cases = tuple(case for case in task_cases if case.split == "holdout")
            for profile in loaded.profiles:
                adapter = loaded.adapters[profile.candidate_id]
                observations: list[Observation] = []
                unsupported: list[str] = []
                preflight_rejections: list[str] = []
                for case in task_cases:
                    for repeat in range(1, case.repeats + 1):
                        try:
                            observation = adapter.observe(case, case.policy, repeat, None)
                        except UnsupportedControlError:
                            unsupported.append(case.case_id)
                            break
                        except PreflightBudgetError as exc:
                            preflight_rejections.append(str(exc))
                            break
                        _validate_observation(case, observation)
                        observations.append(observation)
                        all_observations.append(observation)

                expected = sum(case.repeats for case in task_cases)
                dev_observations = tuple(item for item in observations if item.split == "dev")
                holdout_observations = tuple(
                    item for item in observations if item.split == "holdout"
                )
                if unsupported or preflight_rejections:
                    assessments[(task, profile.candidate_id)] = CandidateAssessment(
                        task=task,
                        candidate_id=profile.candidate_id,
                        provider=profile.provider,
                        expected_observations=expected,
                        observed_observations=len(observations),
                        dev_observations=len(dev_observations),
                        holdout_observations=len(holdout_observations),
                        dev_metrics=None,
                        metrics=None,
                        dev_costs=None,
                        costs=None,
                        preflight_rejections=tuple(preflight_rejections),
                        failed_holdout_runs=(),
                        holdout_escalation_probability=0.0,
                        qualified=False,
                        gate_failures=tuple(
                            (["unsupported controls for cases: " + ", ".join(sorted(set(unsupported)))] if unsupported else [])
                            + (["preflight estimate exceeded budget"] if preflight_rejections else [])
                        ),
                        normalized_score=None,
                    )
                    continue

                if len(observations) != expected:
                    raise FixtureIntegrityError(
                        f"runtime coverage mismatch for {task}/{profile.candidate_id}"
                    )
                _validate_cache_sequence(task_cases, observations)
                dev_metrics = (
                    _compute_metrics(dev_cases, dev_observations) if dev_cases else None
                )
                dev_costs = (
                    _compute_costs(dev_observations, loaded.prices[profile.candidate_id])
                    if dev_cases
                    else None
                )
                # Configuration is frozen after dev. Only isolated holdout
                # observations can qualify, rank, or route a candidate.
                metrics = _compute_metrics(holdout_cases, holdout_observations)
                costs = _compute_costs(
                    holdout_observations,
                    loaded.prices[profile.candidate_id],
                )
                assessments[(task, profile.candidate_id)] = CandidateAssessment(
                    task=task,
                    candidate_id=profile.candidate_id,
                    provider=profile.provider,
                    expected_observations=expected,
                    observed_observations=len(observations),
                    dev_observations=len(dev_observations),
                    holdout_observations=len(holdout_observations),
                    dev_metrics=dev_metrics,
                    metrics=metrics,
                    dev_costs=dev_costs,
                    costs=costs,
                    preflight_rejections=(),
                    failed_holdout_runs=(),
                    holdout_escalation_probability=0.0,
                    qualified=False,
                    gate_failures=(),
                    normalized_score=None,
                )

        return tuple(all_observations), assessments

    def _gate_rank_and_route(
        self,
        loaded: _LoadedFixtures,
        assessments: Mapping[tuple[str, str], CandidateAssessment],
    ) -> tuple[TaskAssessment, ...]:
        results: list[TaskAssessment] = []
        for task in sorted(loaded.task_policies):
            policy = loaded.task_policies[task]
            gated: list[CandidateAssessment] = []
            for profile in loaded.profiles:
                assessment = assessments[(task, profile.candidate_id)]
                if assessment.metrics is None:
                    gated.append(assessment)
                    continue
                failures = list(_gate_failures(assessment.metrics, policy.hard_gates))
                failed_runs = assessment.failed_holdout_runs
                if policy.require_every_holdout_run:
                    failed_runs = _joint_holdout_run_failures(
                        assessment.candidate_id,
                        tuple(
                            case
                            for case in loaded.cases
                            if case.task == task and case.split == "holdout"
                        ),
                        loaded.observation_lookup,
                    )
                    if failed_runs:
                        failures.append("noncompensable holdout run gate failed")
                gated.append(
                    _replace_assessment(
                        _replace_failed_holdout_runs(assessment, failed_runs),
                        qualified=not failures,
                        gate_failures=tuple(failures),
                        normalized_score=None,
                    )
                )

            holdout_cases = tuple(
                case
                for case in loaded.cases
                if case.task == task and case.split == "holdout"
            )
            calibrated = tuple(
                _replace_escalation_probability(
                    assessment,
                    _candidate_escalation_probability(
                        assessment.candidate_id,
                        holdout_cases,
                        loaded.observation_lookup,
                        require_every_holdout_run=policy.require_every_holdout_run,
                    ),
                )
                for assessment in gated
            )
            qualified = [assessment for assessment in calibrated if assessment.qualified]
            scored = _rank_qualified(qualified, policy.weights)
            scores = {assessment.candidate_id: assessment for assessment in scored}
            final = tuple(scores.get(item.candidate_id, item) for item in calibrated)
            ranking = tuple(
                item.candidate_id
                for item in sorted(
                    scored,
                    key=lambda item: (
                        -(item.normalized_score if item.normalized_score is not None else -1.0),
                        item.candidate_id,
                    ),
                )
            )
            capability_tiers = {
                profile.candidate_id: profile.capability_tier for profile in loaded.profiles
            }
            route = _recommend_route(
                task,
                ranking,
                final,
                capability_tiers,
                policy.manual_review_unit_cost,
            )
            results.append(
                TaskAssessment(
                    task=task,
                    policy_id=policy.policy_id,
                    hard_gates=policy.hard_gates,
                    ranking_weights=policy.weights,
                    manual_review_unit_cost=policy.manual_review_unit_cost,
                    candidates=final,
                    qualified_ranking=ranking,
                    route=route,
                )
            )
        return tuple(results)


class _LoadedFixtures:
    def __init__(
        self,
        *,
        profiles: tuple[CandidateProfile, ...],
        cases: tuple[EvaluationCase, ...],
        run_spec: AssessmentRunSpec,
        task_policies: Mapping[str, TaskPolicy],
        prices: Mapping[str, Mapping[str, float]],
        adapters: Mapping[str, ProviderAdapter],
        observation_lookup: Mapping[tuple[str, str, int], Mapping[str, Any]],
    ) -> None:
        self.profiles = profiles
        self.cases = cases
        self.run_spec = run_spec
        self.task_policies = task_policies
        self.prices = prices
        self.adapters = adapters
        self.observation_lookup = observation_lookup


def _validate_observation(case: EvaluationCase, observation: Observation) -> None:
    usage_values = (
        observation.usage.uncached_input,
        observation.usage.cache_write,
        observation.usage.cache_read,
        observation.usage.output,
    )
    if any(value < 0 for value in usage_values):
        raise FixtureIntegrityError(
            f"usage cannot be negative for {observation.observation_id}"
        )
    if observation.retries < 0 or observation.escalations < 0:
        raise FixtureIntegrityError(
            f"counters cannot be negative for {observation.observation_id}"
        )
    if observation.fixed_latency_ms < 0:
        raise FixtureIntegrityError(
            f"latency cannot be negative for {observation.observation_id}"
        )
    if observation.split != case.split:
        raise FixtureIntegrityError(
            f"observation split disagrees with case for {observation.observation_id}"
        )
    if len(set(observation.evidence_ids)) != len(observation.evidence_ids):
        raise FixtureIntegrityError(
            f"duplicate evidence IDs for {observation.observation_id}"
        )
    invalid_evidence = set(observation.evidence_ids) - case.allowed_evidence_ids
    if invalid_evidence:
        raise FixtureIntegrityError(
            f"invented or cross-case evidence IDs for {observation.observation_id}: "
            f"{sorted(invalid_evidence)}"
        )
    if observation.estimated_uncached_input_units < 0 or observation.estimated_output_units < 0:
        raise FixtureIntegrityError(
            f"provider estimates cannot be negative for {observation.observation_id}"
        )
    if not 0 <= observation.quality_score <= 1:
        raise FixtureIntegrityError(
            f"quality must be in [0, 1] for {observation.observation_id}"
        )
    if (
        observation.factual_errors < 0
        or observation.facts_checked < 0
        or observation.factual_errors > observation.facts_checked
    ):
        raise FixtureIntegrityError(
            f"factual counters are invalid for {observation.observation_id}"
        )
    if observation.facts_checked != 1:
        raise FixtureIntegrityError(
            f"exact-answer observations require facts_checked == 1 for {observation.observation_id}"
        )
    expected_errors = (
        0
        if _normalize_answer(observation.answer) == _normalize_answer(case.expected_answer)
        else 1
    )
    if observation.factual_errors != expected_errors:
        raise FixtureIntegrityError(
            f"answer and factual-error annotation disagree for {observation.observation_id}: "
            f"expected {expected_errors}, got {observation.factual_errors}"
        )


def _validate_cache_sequence(
    cases: Sequence[EvaluationCase], observations: Sequence[Observation]
) -> None:
    by_case: dict[str, list[Observation]] = defaultdict(list)
    for observation in observations:
        by_case[observation.case_id].append(observation)
    for case in cases:
        cache_available = False
        cache_created_in_sequence = False
        for observation in sorted(by_case[case.case_id], key=lambda item: item.repeat):
            allowed_origins = {"none", "prior-repeat-write", "declared-preexisting"}
            if observation.cache_origin not in allowed_origins:
                raise FixtureIntegrityError(
                    f"unknown cache origin for {observation.observation_id}: {observation.cache_origin}"
                )
            if observation.cache_entry_available_before != (
                observation.cache_origin != "none"
            ):
                raise FixtureIntegrityError(
                    f"cache availability and origin disagree for {observation.observation_id}"
                )
            if observation.cache_origin == "declared-preexisting":
                cache_available = True
            if observation.cache_origin == "prior-repeat-write" and not (
                cache_available and cache_created_in_sequence
            ):
                raise FixtureIntegrityError(
                    f"cache read has no valid prior write for {observation.observation_id}"
                )
            if (
                observation.usage.cache_read > 0
                and not observation.cache_entry_available_before
            ):
                raise FixtureIntegrityError(
                    f"cache read has no valid prior or preexisting cache for {observation.observation_id}"
                )
            if observation.usage.cache_read > 0 and observation.usage.cache_write > 0:
                raise FixtureIntegrityError(
                    f"one observation cannot both read and create the same cache entry: {observation.observation_id}"
                )
            if observation.usage.cache_write > 0:
                cache_available = True
                cache_created_in_sequence = True


def _compute_metrics(
    cases: Sequence[EvaluationCase], observations: Sequence[Observation]
) -> QualityMetrics:
    grouped: dict[str, list[Observation]] = defaultdict(list)
    for observation in observations:
        grouped[observation.case_id].append(observation)
    if not cases or any(not grouped[case.case_id] for case in cases):
        raise FixtureIntegrityError("metrics require observations for every case")

    quality_by_case: list[float] = []
    factuality_by_case: list[float] = []
    divergence_by_case: list[float] = []
    abstention_by_case: list[float] = []
    evidence_by_case: list[float] = []
    usage_delta_by_case: list[float] = []
    latency_by_case: list[float] = []

    for case in cases:
        items = grouped[case.case_id]
        for observation in items:
            if observation.abstained != (_normalize_answer(observation.answer) == "abstain"):
                raise FixtureIntegrityError(
                    f"abstention annotation disagrees with answer for {observation.observation_id}"
                )
        quality_by_case.append(_mean(item.quality_score for item in items))
        factuality_by_case.append(
            _mean(1.0 if _normalize_answer(item.answer) != _normalize_answer(case.expected_answer) else 0.0 for item in items)
        )
        pairs = len(items) * (len(items) - 1) // 2
        unequal_pairs = sum(
            1
            for index, left in enumerate(items)
            for right in items[index + 1 :]
            if _normalize_answer(left.answer) != _normalize_answer(right.answer)
        )
        divergence_by_case.append(_safe_ratio(unequal_pairs, pairs) if pairs else 0.0)
        # This decision-correctness metric rewards required abstention and
        # penalizes inappropriate abstention on supported-answer cases.
        abstention_by_case.append(
            _mean(
                1.0 if item.abstained == case.should_abstain else 0.0
                for item in items
            )
        )
        if case.required_evidence_ids:
            evidence_by_case.append(
                _mean(
                    _safe_ratio(
                        len(set(item.evidence_ids) & case.required_evidence_ids),
                        len(case.required_evidence_ids),
                    )
                    for item in items
                )
            )
        else:
            evidence_by_case.append(1.0)
        usage_delta_by_case.append(
            _mean(_usage_relative_error(item) for item in items)
        )
        latency_by_case.append(_mean(float(item.fixed_latency_ms) for item in items))

    return QualityMetrics(
        quality=_mean(quality_by_case),
        factual_error_rate=_mean(factuality_by_case),
        divergence_rate=_mean(divergence_by_case),
        correct_abstention_rate=_mean(abstention_by_case),
        evidence_coverage=_mean(evidence_by_case),
        estimated_vs_actual_usage_delta=_mean(usage_delta_by_case),
        mean_fixed_latency_ms=_mean(latency_by_case),
    )


def _normalize_answer(answer: str) -> str:
    """Normalize only fixture formatting, not general semantic equivalence."""

    return answer.strip().casefold().rstrip(".!?").strip()


def _usage_relative_error(observation: Observation) -> float:
    estimated = (
        observation.estimated_uncached_input_units
        + observation.estimated_output_units
    )
    actual = observation.usage.total
    if estimated == 0:
        return 0.0 if actual == 0 else 1.0
    return abs(actual - estimated) / estimated


def _mean(values: Iterable[float]) -> float:
    materialized = tuple(values)
    if not materialized:
        raise FixtureIntegrityError("cannot average an empty metric")
    return sum(materialized) / len(materialized)


def _compute_costs(
    observations: Sequence[Observation],
    prices: Mapping[str, float],
) -> CostBreakdown:
    unit_costs = {
        "uncached_input": sum(item.usage.uncached_input for item in observations)
        * prices["uncached_input"],
        "cache_write": sum(item.usage.cache_write for item in observations)
        * prices["cache_write"],
        "cache_read": sum(item.usage.cache_read for item in observations)
        * prices["cache_read"],
        "output": sum(item.usage.output for item in observations) * prices["output"],
        "retry": sum(item.retries for item in observations) * prices["retry"],
        "escalation": sum(item.escalations for item in observations) * prices["escalation"],
    }
    cache_baseline = sum(
        item.usage.cache_write + item.usage.cache_read for item in observations
    ) * prices["uncached_input"]
    cache_actual = unit_costs["cache_write"] + unit_costs["cache_read"]
    total = sum(unit_costs.values())
    # This escalation component is observed in the fixture. Route-level
    # expected fallback cost is optimized separately.
    return CostBreakdown(
        uncached_input=unit_costs["uncached_input"],
        cache_write=unit_costs["cache_write"],
        cache_read=unit_costs["cache_read"],
        output=unit_costs["output"],
        retry=unit_costs["retry"],
        escalation=unit_costs["escalation"],
        total=total,
        cache_full_price_baseline=cache_baseline,
        cache_net_savings=cache_baseline - cache_actual,
    )


def _gate_failures(metrics: QualityMetrics, gates: HardGates) -> tuple[str, ...]:
    failures: list[str] = []
    if metrics.quality < gates.minimum_quality:
        failures.append("quality below minimum")
    if metrics.factual_error_rate > gates.maximum_factual_error_rate:
        failures.append("factual error rate above maximum")
    if metrics.divergence_rate > gates.maximum_divergence_rate:
        failures.append("divergence rate above maximum")
    if metrics.correct_abstention_rate < gates.minimum_correct_abstention_rate:
        failures.append("correct abstention rate below minimum")
    if metrics.evidence_coverage < gates.minimum_evidence_coverage:
        failures.append("evidence coverage below minimum")
    if metrics.mean_fixed_latency_ms > gates.maximum_mean_fixed_latency_ms:
        failures.append("fixed latency above maximum")
    return tuple(failures)


def _rank_qualified(
    candidates: Sequence[CandidateAssessment], weights: RankingWeights
) -> tuple[CandidateAssessment, ...]:
    if not candidates:
        return ()
    raw_by_metric: dict[str, dict[str, float]] = defaultdict(dict)
    for candidate in candidates:
        if candidate.metrics is None or candidate.costs is None:
            raise FixtureIntegrityError(
                f"qualified candidate lacks metrics or costs: {candidate.candidate_id}"
            )
        metrics = candidate.metrics
        raw_by_metric["quality"][candidate.candidate_id] = metrics.quality
        raw_by_metric["factuality"][candidate.candidate_id] = 1 - metrics.factual_error_rate
        raw_by_metric["consistency"][candidate.candidate_id] = 1 - metrics.divergence_rate
        raw_by_metric["abstention"][candidate.candidate_id] = metrics.correct_abstention_rate
        raw_by_metric["evidence"][candidate.candidate_id] = metrics.evidence_coverage
        raw_by_metric["usage_accuracy"][candidate.candidate_id] = 1 - min(
            metrics.estimated_vs_actual_usage_delta, 1.0
        )
        raw_by_metric["cost"][candidate.candidate_id] = candidate.costs.total
        raw_by_metric["latency"][candidate.candidate_id] = metrics.mean_fixed_latency_ms

    weight_map = dict(weights.items())
    scores = {candidate.candidate_id: 0.0 for candidate in candidates}
    for metric, values_by_candidate in raw_by_metric.items():
        values = tuple(values_by_candidate.values())
        low, high = min(values), max(values)
        for candidate_id, value in values_by_candidate.items():
            if math.isclose(low, high, abs_tol=1e-12, rel_tol=0.0):
                normalized = 1.0
            elif _METRIC_DIRECTIONS[metric]:
                normalized = (value - low) / (high - low)
            else:
                normalized = (high - value) / (high - low)
            scores[candidate_id] += normalized * weight_map[metric]

    return tuple(
        _replace_assessment(
            candidate,
            qualified=True,
            gate_failures=(),
            normalized_score=round(scores[candidate.candidate_id], 12),
        )
        for candidate in candidates
    )


def _joint_holdout_run_failures(
    candidate_id: str,
    holdout_cases: Sequence[EvaluationCase],
    observations: Mapping[tuple[str, str, int], Mapping[str, Any]],
) -> tuple[str, ...]:
    failures: list[str] = []
    for case in holdout_cases:
        for repeat in range(1, case.repeats + 1):
            raw = observations.get((candidate_id, case.case_id, repeat))
            if raw is None:
                continue
            answer_correct = _normalize_answer(_string(raw["answer"])) == _normalize_answer(
                case.expected_answer
            )
            cited = set(_strings(raw["evidence_ids"]))
            evidence_complete = case.required_evidence_ids <= cited
            abstention_correct = _boolean(raw["abstained"]) == case.should_abstain
            if not (answer_correct and evidence_complete and abstention_correct):
                failures.append(f"{case.case_id}#{repeat}")
    return tuple(failures)


def _replace_failed_holdout_runs(
    assessment: CandidateAssessment, failures: tuple[str, ...]
) -> CandidateAssessment:
    return CandidateAssessment(
        task=assessment.task,
        candidate_id=assessment.candidate_id,
        provider=assessment.provider,
        expected_observations=assessment.expected_observations,
        observed_observations=assessment.observed_observations,
        dev_observations=assessment.dev_observations,
        holdout_observations=assessment.holdout_observations,
        dev_metrics=assessment.dev_metrics,
        metrics=assessment.metrics,
        dev_costs=assessment.dev_costs,
        costs=assessment.costs,
        preflight_rejections=assessment.preflight_rejections,
        failed_holdout_runs=failures,
        holdout_escalation_probability=assessment.holdout_escalation_probability,
        qualified=assessment.qualified,
        gate_failures=assessment.gate_failures,
        normalized_score=assessment.normalized_score,
    )


def _candidate_escalation_probability(
    candidate_id: str,
    holdout_cases: Sequence[EvaluationCase],
    observations: Mapping[tuple[str, str, int], Mapping[str, Any]],
    *,
    require_every_holdout_run: bool,
) -> float:
    case_by_id = {case.case_id: case for case in holdout_cases}
    outcomes = tuple(
        observations[(candidate_id, case.case_id, repeat)]
        for case in holdout_cases
        for repeat in range(1, case.repeats + 1)
        if (candidate_id, case.case_id, repeat) in observations
    )
    if not outcomes:
        return 0.0
    failures = 0
    for raw in outcomes:
        case = case_by_id[_string(raw["case_id"])]
        answer_correct = _normalize_answer(_string(raw["answer"])) == _normalize_answer(
            case.expected_answer
        )
        abstention_correct = _boolean(raw["abstained"]) == case.should_abstain
        evidence_complete = case.required_evidence_ids <= set(_strings(raw["evidence_ids"]))
        failed = not answer_correct
        if require_every_holdout_run:
            failed = not (answer_correct and abstention_correct and evidence_complete)
        if failed:
            failures += 1
    return _safe_ratio(failures, len(outcomes))


def _replace_escalation_probability(
    assessment: CandidateAssessment, probability: float
) -> CandidateAssessment:
    if not math.isfinite(probability) or not 0 <= probability <= 1:
        raise FixtureIntegrityError("candidate escalation probability must be in [0, 1]")
    return CandidateAssessment(
        task=assessment.task,
        candidate_id=assessment.candidate_id,
        provider=assessment.provider,
        expected_observations=assessment.expected_observations,
        observed_observations=assessment.observed_observations,
        dev_observations=assessment.dev_observations,
        holdout_observations=assessment.holdout_observations,
        dev_metrics=assessment.dev_metrics,
        metrics=assessment.metrics,
        dev_costs=assessment.dev_costs,
        costs=assessment.costs,
        preflight_rejections=assessment.preflight_rejections,
        failed_holdout_runs=assessment.failed_holdout_runs,
        holdout_escalation_probability=probability,
        qualified=assessment.qualified,
        gate_failures=assessment.gate_failures,
        normalized_score=assessment.normalized_score,
    )


def _recommend_route(
    task: str,
    ranking: Sequence[str],
    candidates: Sequence[CandidateAssessment],
    capability_tiers: Mapping[str, int],
    manual_review_unit_cost: float,
) -> RouteRecommendation:
    if not math.isfinite(manual_review_unit_cost) or manual_review_unit_cost <= 0:
        raise FixtureIntegrityError("manual review unit cost must be finite and strictly positive")
    by_id = {candidate.candidate_id: candidate for candidate in candidates}
    if not ranking:
        return RouteRecommendation(
            task=task,
            primary_candidate=None,
            escalation_candidate=None,
            escalation_probability=0.0,
            primary_cost=0.0,
            escalation_cost=0.0,
            manual_review_cost=0.0,
            total_expected_cost=0.0,
            residual_failure_probability=0.0,
            residual_failure_handling="unavailable",
            evaluated_strategies=(),
            reason="no candidate passed every hard gate",
        )
    strategies: list[RouteStrategy] = []
    for primary_id in ranking:
        primary = by_id[primary_id]
        if primary.costs is None:
            raise FixtureIntegrityError(f"primary route lacks costs: {primary_id}")
        stronger = sorted(
            candidate_id
            for candidate_id in ranking
            if capability_tiers[candidate_id] > capability_tiers[primary_id]
        )
        fallback_options: tuple[str | None, ...] = tuple(stronger) if stronger else (None,)
        for escalation_id in fallback_options:
            expected_escalation = 0.0
            applied_probability = 0.0
            residual_probability = primary.holdout_escalation_probability
            residual_handling: str | None = "manual_review" if residual_probability > 0 else None
            if escalation_id is not None:
                escalation = by_id[escalation_id]
                if escalation.costs is None:
                    raise FixtureIntegrityError(
                        f"escalation route lacks costs: {escalation_id}"
                    )
                applied_probability = primary.holdout_escalation_probability
                expected_escalation = escalation.costs.total * applied_probability
                residual_probability = (
                    primary.holdout_escalation_probability
                    * escalation.holdout_escalation_probability
                )
                residual_handling = (
                    "manual_review" if residual_probability > 0 else None
                )
            expected_manual_review = (
                residual_probability * manual_review_unit_cost
            )
            strategies.append(
                RouteStrategy(
                    primary_candidate=primary_id,
                    escalation_candidate=escalation_id,
                    escalation_probability=applied_probability,
                    primary_cost=primary.costs.total,
                    escalation_cost=expected_escalation,
                    manual_review_cost=expected_manual_review,
                    total_expected_cost=(
                        primary.costs.total
                        + expected_escalation
                        + expected_manual_review
                    ),
                    residual_failure_probability=residual_probability,
                    residual_failure_handling=residual_handling,
                )
            )
    evaluated = tuple(
        sorted(strategies, key=lambda item: (item.total_expected_cost, item.primary_candidate))
    )
    selected = evaluated[0]
    return RouteRecommendation(
        task=task,
        primary_candidate=selected.primary_candidate,
        escalation_candidate=selected.escalation_candidate,
        escalation_probability=selected.escalation_probability,
        primary_cost=selected.primary_cost,
        escalation_cost=selected.escalation_cost,
        manual_review_cost=selected.manual_review_cost,
        total_expected_cost=selected.total_expected_cost,
        residual_failure_probability=selected.residual_failure_probability,
        residual_failure_handling=selected.residual_failure_handling,
        evaluated_strategies=evaluated,
        reason="lowest total expected cost among holdout-qualified strategies",
    )


def _replace_assessment(
    assessment: CandidateAssessment,
    *,
    qualified: bool,
    gate_failures: tuple[str, ...],
    normalized_score: float | None,
) -> CandidateAssessment:
    return CandidateAssessment(
        task=assessment.task,
        candidate_id=assessment.candidate_id,
        provider=assessment.provider,
        expected_observations=assessment.expected_observations,
        observed_observations=assessment.observed_observations,
        dev_observations=assessment.dev_observations,
        holdout_observations=assessment.holdout_observations,
        dev_metrics=assessment.dev_metrics,
        metrics=assessment.metrics,
        dev_costs=assessment.dev_costs,
        costs=assessment.costs,
        preflight_rejections=assessment.preflight_rejections,
        failed_holdout_runs=assessment.failed_holdout_runs,
        holdout_escalation_probability=assessment.holdout_escalation_probability,
        qualified=qualified,
        gate_failures=gate_failures,
        normalized_score=normalized_score,
    )


def _parse_profile(raw: Mapping[str, Any]) -> CandidateProfile:
    adapter_kind = _string(raw["adapter_kind"])
    if adapter_kind not in {"sampling", "effort"}:
        raise FixtureIntegrityError(f"unknown adapter kind: {adapter_kind}")
    candidate_id = _string(raw["candidate_id"])
    config_id = _string(raw["config_id"])
    capability_tier = _integer(raw["capability_tier"])
    if capability_tier < 1:
        raise FixtureIntegrityError(f"capability tier must be positive for {candidate_id}")
    supported_controls = frozenset(_strings(raw["supported_controls"]))
    control_mapping = _string_mapping(raw["control_mapping"])
    usage_mapping = _string_mapping(raw["usage_mapping"])
    counter_mapping = _string_mapping(raw["counter_mapping"])
    estimate_mapping = _string_mapping(raw["estimate_mapping"])
    _exact_mapping_keys(control_mapping, supported_controls, candidate_id, "control")
    _exact_mapping_keys(
        usage_mapping,
        frozenset({"uncached_input", "cache_write", "cache_read", "output"}),
        candidate_id,
        "usage",
    )
    _exact_mapping_keys(
        counter_mapping,
        frozenset({"retries", "escalations"}),
        candidate_id,
        "counter",
    )
    _exact_mapping_keys(
        estimate_mapping,
        frozenset({"uncached_input", "output"}),
        candidate_id,
        "estimate counter",
    )
    for description, mapping in (
        ("control", control_mapping),
        ("usage", usage_mapping),
        ("counter", counter_mapping),
        ("estimate counter", estimate_mapping),
    ):
        if len(set(mapping.values())) != len(mapping):
            raise FixtureIntegrityError(
                f"{description} mapping targets must be unique for {candidate_id}"
            )
    return CandidateProfile(
        candidate_id=candidate_id,
        config_id=config_id,
        provider=_string(raw["provider"]),
        adapter_kind=cast(Any, adapter_kind),
        capability_tier=capability_tier,
        supported_controls=supported_controls,
        control_mapping=tuple(sorted(control_mapping.items())),
        usage_container=_string(raw["usage_container"]),
        usage_mapping=tuple(sorted(usage_mapping.items())),
        counter_container=_string(raw["counter_container"]),
        counter_mapping=tuple(sorted(counter_mapping.items())),
        estimate_container=_string(raw["estimate_container"]),
        estimate_mapping=tuple(sorted(estimate_mapping.items())),
    )


def _parse_case(raw: Mapping[str, Any]) -> EvaluationCase:
    policy_raw = _mapping(raw["policy"])
    case_id = _string(raw["case_id"])
    expected_answer = _string(raw["expected_answer"])
    should_abstain = _boolean(raw["should_abstain"])
    split = _string(raw["split"])
    if split not in {"dev", "holdout"}:
        raise FixtureIntegrityError(f"invalid split for {case_id}: {split}")
    allowed_evidence_ids = frozenset(_strings(raw["allowed_evidence_ids"]))
    required_evidence_ids = frozenset(_strings(raw["required_evidence_ids"]))
    evidence_required = _integer(raw["evidence_required"])
    if evidence_required != len(required_evidence_ids):
        raise FixtureIntegrityError(
            f"evidence_required disagrees with required evidence IDs for {case_id}"
        )
    if not required_evidence_ids <= allowed_evidence_ids:
        raise FixtureIntegrityError(
            f"required evidence is not allowlisted for {case_id}"
        )
    repeats = _integer(raw["repeats"])
    if repeats < 1:
        raise FixtureIntegrityError(f"repeats must be positive for {case_id}")
    if should_abstain != (expected_answer == "ABSTAIN"):
        raise FixtureIntegrityError(
            f"should_abstain and expected_answer disagree for {case_id}"
        )
    return EvaluationCase(
        case_id=case_id,
        task=_string(raw["task"]),
        split=cast(Any, split),
        prompt=_string(raw["prompt"]),
        expected_answer=expected_answer,
        should_abstain=should_abstain,
        allowed_evidence_ids=allowed_evidence_ids,
        required_evidence_ids=required_evidence_ids,
        repeats=repeats,
        policy=SemanticPolicy.create(
            controls=_scalar_mapping(policy_raw["controls"]),
            maximum_estimated_input_units=_positive_integer(
                policy_raw["maximum_estimated_input_units"],
                f"maximum estimated input for {case_id}",
            ),
        ),
    )


def _parse_task_policy(raw: Mapping[str, Any]) -> TaskPolicy:
    expected_policy_keys = {
        "task",
        "policy_id",
        "hard_gates",
        "weights",
        "manual_review_unit_cost",
        "holdout_only_negative_policy",
        "require_every_holdout_run",
    }
    if set(raw) != expected_policy_keys:
        raise FixtureIntegrityError("task policy keys must exactly match the contract")
    gates = _mapping(raw["hard_gates"])
    weights = _mapping(raw["weights"])
    expected_gate_keys = {
        "minimum_quality",
        "maximum_factual_error_rate",
        "maximum_divergence_rate",
        "minimum_correct_abstention_rate",
        "minimum_evidence_coverage",
        "maximum_mean_fixed_latency_ms",
    }
    expected_weight_keys = {
        "quality",
        "factuality",
        "consistency",
        "abstention",
        "evidence",
        "usage_accuracy",
        "cost",
        "latency",
    }
    if set(gates) != expected_gate_keys:
        raise FixtureIntegrityError("hard-gate keys must exactly match the contract")
    if set(weights) != expected_weight_keys:
        raise FixtureIntegrityError("ranking-weight keys must exactly match the contract")
    minimum_quality = _unit_rate(gates["minimum_quality"], "minimum quality")
    maximum_factual_error_rate = _unit_rate(
        gates["maximum_factual_error_rate"], "maximum factual error rate"
    )
    maximum_divergence_rate = _unit_rate(
        gates["maximum_divergence_rate"], "maximum divergence rate"
    )
    minimum_correct_abstention_rate = _unit_rate(
        gates["minimum_correct_abstention_rate"], "minimum correct abstention rate"
    )
    minimum_evidence_coverage = _unit_rate(
        gates["minimum_evidence_coverage"], "minimum evidence coverage"
    )
    maximum_latency = _number(gates["maximum_mean_fixed_latency_ms"])
    if maximum_latency < 0:
        raise FixtureIntegrityError("maximum fixed latency cannot be negative")
    return TaskPolicy(
        task=_string(raw["task"]),
        policy_id=_string(raw["policy_id"]),
        hard_gates=HardGates(
            minimum_quality=minimum_quality,
            maximum_factual_error_rate=maximum_factual_error_rate,
            maximum_divergence_rate=maximum_divergence_rate,
            minimum_correct_abstention_rate=minimum_correct_abstention_rate,
            minimum_evidence_coverage=minimum_evidence_coverage,
            maximum_mean_fixed_latency_ms=maximum_latency,
        ),
        weights=RankingWeights(
            quality=_number(weights["quality"]),
            factuality=_number(weights["factuality"]),
            consistency=_number(weights["consistency"]),
            abstention=_number(weights["abstention"]),
            evidence=_number(weights["evidence"]),
            usage_accuracy=_number(weights["usage_accuracy"]),
            cost=_number(weights["cost"]),
            latency=_number(weights["latency"]),
        ),
        manual_review_unit_cost=_positive_number(
            raw["manual_review_unit_cost"], "manual review unit cost"
        ),
        holdout_only_negative_policy=_boolean(raw["holdout_only_negative_policy"]),
        require_every_holdout_run=_boolean(raw["require_every_holdout_run"]),
    )


def _validate_supported_contract_versions(cases_data: Mapping[str, Any]) -> None:
    expected = {
        "evaluator_version": _SUPPORTED_EVALUATOR_VERSION,
        "rubric_version": _SUPPORTED_RUBRIC_VERSION,
        "tool_policy_id": _SUPPORTED_TOOL_POLICY_ID,
    }
    for key, supported in expected.items():
        if _string(cases_data[key]) != supported:
            raise FixtureIntegrityError(f"unsupported local contract identity: {key}")


def _validate_case_manifest(
    cases_data: Mapping[str, Any], manifest_data: Mapping[str, Any]
) -> str:
    if _string(manifest_data["manifest_version"]) != "case-manifest-v1":
        raise FixtureIntegrityError("unsupported case manifest version")
    trusted_cases = _objects(manifest_data, "cases")
    supplied_digest = _sha256_string(
        manifest_data["manifest_digest"], "case manifest digest"
    )
    if _digest(list(trusted_cases)) != supplied_digest:
        raise FixtureIntegrityError("case manifest digest does not match manifest")
    if supplied_digest != _SUPPORTED_CASE_MANIFEST_DIGEST:
        raise FixtureIntegrityError("case manifest is not the registered trusted manifest")
    mutable_cases = _objects(cases_data, "cases")
    if _canonical_case_manifest(mutable_cases) != trusted_cases:
        raise FixtureIntegrityError("evaluation cases differ from trusted case manifest")
    return supplied_digest


def _canonical_case_manifest(
    cases: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...]:
    return tuple(
        {
            "case_id": _string(case["case_id"]),
            "task": _string(case["task"]),
            "split": _string(case["split"]),
            "expected_answer": _string(case["expected_answer"]),
            "should_abstain": _boolean(case["should_abstain"]),
            "allowed_evidence_ids": sorted(_strings(case["allowed_evidence_ids"])),
            "required_evidence_ids": sorted(_strings(case["required_evidence_ids"])),
            "repeats": _integer(case["repeats"]),
            "prompt_digest": _digest(_string(case["prompt"])),
            "policy_digest": _digest(_mapping(case["policy"])),
        }
        for case in sorted(cases, key=lambda item: _string(item["case_id"]))
    )


def _validate_observation_provenance(
    profiles_data: Mapping[str, Any],
    cases_data: Mapping[str, Any],
    observations_data: Mapping[str, Any],
    case_manifest_digest: str,
) -> None:
    provenance = _mapping(observations_data["provenance"])
    expected_config_ids = sorted(
        _string(item["config_id"]) for item in _objects(profiles_data, "candidates")
    )
    actual_config_ids = sorted(_strings(provenance["candidate_config_ids"]))
    expected = {
        "fixture_version": _string(cases_data["fixture_version"]),
        "evaluator_version": _string(cases_data["evaluator_version"]),
        "rubric_version": _string(cases_data["rubric_version"]),
        "tool_policy_id": _string(cases_data["tool_policy_id"]),
        "case_manifest_digest": case_manifest_digest,
    }
    for key, value in expected.items():
        if _string(provenance[key]) != value:
            raise FixtureIntegrityError(
                f"observation fixture provenance mismatch for {key}"
            )
    if actual_config_ids != expected_config_ids:
        raise FixtureIntegrityError(
            "observation fixture provenance mismatch for candidate config IDs"
        )


def _parse_evidence_corpus(raw: Mapping[str, Any]) -> tuple[EvidenceRecord, ...]:
    _string(raw["corpus_version"])
    parsed_records: list[EvidenceRecord] = []
    for item in _objects(raw, "records"):
        content = _string(item["content"])
        supplied_digest = _sha256_string(item["content_digest"], "evidence content digest")
        computed_digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if supplied_digest != computed_digest:
            raise FixtureIntegrityError("evidence content digest does not match content")
        parsed_records.append(
            EvidenceRecord(
                evidence_id=_string(item["evidence_id"]),
                case_id=_string(item["case_id"]),
                supported_answer=_string(item["supported_answer"]),
                content=content,
                content_digest=computed_digest,
            )
        )
    records = tuple(parsed_records)
    _unique((record.evidence_id for record in records), "evidence corpus id")
    return tuple(sorted(records, key=lambda record: record.evidence_id))


def _parse_evidence_requirements(
    raw: Mapping[str, Any],
) -> Mapping[str, frozenset[str]]:
    result: dict[str, frozenset[str]] = {}
    for item in _objects(raw, "case_requirements"):
        case_id = _string(item["case_id"])
        if case_id in result:
            raise FixtureIntegrityError(f"duplicate evidence requirement case: {case_id}")
        result[case_id] = frozenset(_strings(item["required_evidence_ids"]))
    return result


def _validate_case_evidence(
    cases: Sequence[EvaluationCase],
    corpus: Sequence[EvidenceRecord],
    requirements: Mapping[str, frozenset[str]],
) -> None:
    by_id = {record.evidence_id: record for record in corpus}
    for case in cases:
        corpus_supported = {
            record.evidence_id for record in corpus if record.case_id == case.case_id
        }
        if case.allowed_evidence_ids != corpus_supported:
            raise FixtureIntegrityError(
                f"allowlisted evidence IDs disagree with independent corpus for {case.case_id}"
            )
        corpus_required = requirements.get(case.case_id, frozenset())
        if case.required_evidence_ids != corpus_required:
            raise FixtureIntegrityError(
                f"required evidence IDs disagree with independent corpus contract for {case.case_id}"
            )
        for evidence_id in case.allowed_evidence_ids:
            record = by_id.get(evidence_id)
            if record is None:
                raise FixtureIntegrityError(
                    f"case evidence ID is absent from independent corpus: {evidence_id}"
                )
            if record.case_id != case.case_id or record.supported_answer != case.expected_answer:
                raise FixtureIntegrityError(
                    f"evidence corpus record does not support {case.case_id}: {evidence_id}"
                )


def _build_run_spec(
    profiles_data: Mapping[str, Any],
    cases_data: Mapping[str, Any],
    observations_data: Mapping[str, Any],
    prices_data: Mapping[str, Any],
    evidence_data: Mapping[str, Any],
    case_manifest_data: Mapping[str, Any],
    profiles: Sequence[CandidateProfile],
    cases: Sequence[EvaluationCase],
    task_policies: tuple[TaskPolicy, ...],
    evidence_corpus: tuple[EvidenceRecord, ...],
    candidate_task_runs: tuple[CandidateTaskRunSpec, ...] = (),
) -> AssessmentRunSpec:
    fixture_version = _string(cases_data["fixture_version"])
    evaluator_version = _string(cases_data["evaluator_version"])
    rubric_version = _string(cases_data["rubric_version"])
    tool_policy_id = _string(cases_data["tool_policy_id"])
    fixture_digest = _digest(
        {
            "profiles": profiles_data,
            "cases": cases_data,
            "observations": observations_data,
            "prices": prices_data,
            "evidence": evidence_data,
            "case_manifest": case_manifest_data,
        }
    )
    case_specs = tuple(
        CaseRunSpec(
            case_id=case.case_id,
            task=case.task,
            split=case.split,
            expected_answer=case.expected_answer,
            should_abstain=case.should_abstain,
            allowed_evidence_ids=tuple(sorted(case.allowed_evidence_ids)),
            required_evidence_ids=tuple(sorted(case.required_evidence_ids)),
            prompt_digest=_digest(case.prompt),
            policy_digest=_digest(
                {
                    "controls": dict(case.policy.controls),
                    "maximum_estimated_input_units": case.policy.maximum_estimated_input_units,
                }
            ),
            policy_controls=tuple(sorted(key for key, _ in case.policy.controls)),
            repeats=case.repeats,
        )
        for case in sorted(cases, key=lambda item: item.case_id)
    )
    return AssessmentRunSpec(
        fixture_version=fixture_version,
        fixture_digest=fixture_digest,
        case_manifest_digest=_sha256_string(
            case_manifest_data["manifest_digest"], "case manifest digest"
        ),
        observation_provenance_digest=_digest(observations_data["provenance"]),
        evaluator_version=evaluator_version,
        rubric_version=rubric_version,
        tool_policy_id=tool_policy_id,
        configuration_split="dev",
        decision_split="holdout",
        candidate_configs=tuple(
            CandidateRunSpec(
                candidate_id=profile.candidate_id,
                config_id=profile.config_id,
                provider=profile.provider,
                capability_tier=profile.capability_tier,
                supported_controls=tuple(sorted(profile.supported_controls)),
            )
            for profile in sorted(profiles, key=lambda item: item.candidate_id)
        ),
        candidate_config_ids=tuple(sorted(profile.config_id for profile in profiles)),
        task_policies=tuple(
            TaskPolicyRunSpec(
                task=policy.task,
                policy_id=policy.policy_id,
                hard_gates=policy.hard_gates,
                ranking_weights=policy.weights,
                manual_review_unit_cost=policy.manual_review_unit_cost,
                holdout_only_negative_policy=policy.holdout_only_negative_policy,
                require_every_holdout_run=policy.require_every_holdout_run,
            )
            for policy in sorted(task_policies, key=lambda item: item.task)
        ),
        task_policy_ids=tuple(
            sorted(
                _string(policy["policy_id"])
                for policy in _objects(cases_data, "task_policies")
            )
        ),
        candidate_task_runs=candidate_task_runs,
        evidence_corpus=evidence_corpus,
        cases=case_specs,
    )


def _sha256_string(value: object, description: str) -> str:
    parsed = _string(value)
    if len(parsed) != 64 or any(character not in "0123456789abcdef" for character in parsed):
        raise FixtureIntegrityError(f"{description} must be a lowercase SHA-256 digest")
    return parsed


def _digest(value: object) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _exact_mapping_keys(
    mapping: Mapping[str, str],
    expected: frozenset[str],
    candidate_id: str,
    description: str,
) -> None:
    if set(mapping) != expected:
        raise FixtureIntegrityError(
            f"{description} mapping coverage mismatch for {candidate_id}: "
            f"expected={sorted(expected)}, actual={sorted(mapping)}"
        )


def _parse_prices(raw: Mapping[str, Any]) -> dict[str, Mapping[str, float]]:
    if _string(raw["currency"]) != "fictional_credits":
        raise FixtureIntegrityError("prices must use fictional_credits")
    if _integer(raw["per_units"]) != 1000:
        raise FixtureIntegrityError("educational prices must be per 1000 units")
    result: dict[str, Mapping[str, float]] = {}
    candidates = _objects(raw, "candidates")
    _unique((_string(candidate["candidate_id"]) for candidate in candidates), "price candidate id")
    for candidate in candidates:
        candidate_id = _string(candidate["candidate_id"])
        prices = _mapping(candidate["prices"])
        if set(prices) != set(_COST_COMPONENTS):
            raise FixtureIntegrityError(
                f"price components incomplete for {candidate_id}: {sorted(prices)}"
            )
        parsed = {
            component: _number(prices[component]) / 1000 for component in _COST_COMPONENTS
        }
        if any(not math.isfinite(value) or value < 0 for value in parsed.values()):
            raise FixtureIntegrityError("prices must be finite and nonnegative")
        result[candidate_id] = parsed
    return result


def _load_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=lambda constant: (_raise_nonfinite_json(constant)),
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise FixtureIntegrityError(f"cannot load {path.name}: {exc}") from exc
    return _mapping(value)


def _raise_nonfinite_json(constant: str) -> None:
    raise FixtureIntegrityError(f"non-finite JSON number is not allowed: {constant}")


def _objects(raw: Mapping[str, Any], key: str) -> tuple[Mapping[str, Any], ...]:
    value = raw.get(key)
    if not isinstance(value, list):
        raise FixtureIntegrityError(f"{key} must be an array")
    return tuple(_mapping(item) for item in value)


def _mapping(value: object) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise FixtureIntegrityError("expected JSON object")
    return cast(Mapping[str, Any], value)


def _string(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise FixtureIntegrityError("expected non-empty string")
    return value


def _integer(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise FixtureIntegrityError("expected integer")
    return value


def _positive_integer(value: object, description: str) -> int:
    parsed = _integer(value)
    if parsed < 1:
        raise FixtureIntegrityError(f"{description} must be positive")
    return parsed


def _number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FixtureIntegrityError("expected number")
    parsed = float(value)
    if not math.isfinite(parsed):
        raise FixtureIntegrityError("expected finite number")
    return parsed


def _positive_number(value: object, description: str) -> float:
    parsed = _number(value)
    if parsed <= 0:
        raise FixtureIntegrityError(f"{description} must be strictly positive")
    return parsed


def _unit_rate(value: object, description: str) -> float:
    parsed = _number(value)
    if not 0 <= parsed <= 1:
        raise FixtureIntegrityError(f"{description} must be in [0, 1]")
    return parsed


def _boolean(value: object) -> bool:
    if not isinstance(value, bool):
        raise FixtureIntegrityError("expected boolean")
    return value


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise FixtureIntegrityError("expected string array")
    return tuple(_string(item) for item in value)


def _string_mapping(value: object) -> dict[str, str]:
    raw = _mapping(value)
    return {_string(key): _string(item) for key, item in raw.items()}


def _scalar_mapping(value: object) -> dict[str, str | int | float | bool | None]:
    raw = _mapping(value)
    result: dict[str, str | int | float | bool | None] = {}
    for key, item in raw.items():
        if not isinstance(item, (str, int, float, bool)) and item is not None:
            raise FixtureIntegrityError("semantic controls must be scalar")
        result[_string(key)] = item
    return result


def _unique(values: Sequence[object] | Any, description: str) -> None:
    seen: set[object] = set()
    for value in values:
        if value in seen:
            raise FixtureIntegrityError(f"duplicate {description}: {value}")
        seen.add(value)


def _safe_ratio(numerator: float | int, denominator: float | int) -> float:
    if denominator == 0:
        return 0.0
    return float(numerator) / float(denominator)


__all__ = ["AssessmentLab", "FixtureIntegrityError"]
