"""Immutable contracts used by the offline assessment module."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping

JsonScalar = str | int | float | bool | None
AdapterKind = Literal["sampling", "effort"]
EvaluationSplit = Literal["dev", "holdout"]


@dataclass(frozen=True, slots=True)
class SemanticPolicy:
    """Provider-neutral controls and preflight input budget."""

    controls: tuple[tuple[str, JsonScalar], ...]
    maximum_estimated_input_units: int

    @classmethod
    def create(
        cls,
        controls: Mapping[str, JsonScalar],
        maximum_estimated_input_units: int,
    ) -> SemanticPolicy:
        return cls(
            controls=tuple(sorted(controls.items())),
            maximum_estimated_input_units=maximum_estimated_input_units,
        )


@dataclass(frozen=True, slots=True)
class CandidateProfile:
    candidate_id: str
    config_id: str
    provider: str
    adapter_kind: AdapterKind
    capability_tier: int
    supported_controls: frozenset[str]
    control_mapping: tuple[tuple[str, str], ...]
    usage_container: str
    usage_mapping: tuple[tuple[str, str], ...]
    counter_container: str
    counter_mapping: tuple[tuple[str, str], ...]
    estimate_container: str
    estimate_mapping: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    case_id: str
    task: str
    split: EvaluationSplit
    prompt: str
    expected_answer: str
    should_abstain: bool
    allowed_evidence_ids: frozenset[str]
    required_evidence_ids: frozenset[str]
    repeats: int
    policy: SemanticPolicy


@dataclass(frozen=True, slots=True)
class HardGates:
    minimum_quality: float
    maximum_factual_error_rate: float
    maximum_divergence_rate: float
    minimum_correct_abstention_rate: float
    minimum_evidence_coverage: float
    maximum_mean_fixed_latency_ms: float


@dataclass(frozen=True, slots=True)
class RankingWeights:
    quality: float
    factuality: float
    consistency: float
    abstention: float
    evidence: float
    usage_accuracy: float
    cost: float
    latency: float

    def items(self) -> tuple[tuple[str, float], ...]:
        return (
            ("quality", self.quality),
            ("factuality", self.factuality),
            ("consistency", self.consistency),
            ("abstention", self.abstention),
            ("evidence", self.evidence),
            ("usage_accuracy", self.usage_accuracy),
            ("cost", self.cost),
            ("latency", self.latency),
        )


@dataclass(frozen=True, slots=True)
class TaskPolicy:
    task: str
    policy_id: str
    hard_gates: HardGates
    weights: RankingWeights
    manual_review_unit_cost: float
    holdout_only_negative_policy: bool
    require_every_holdout_run: bool


@dataclass(frozen=True, slots=True)
class Usage:
    uncached_input: int
    cache_write: int
    cache_read: int
    output: int

    @property
    def total(self) -> int:
        return self.uncached_input + self.cache_write + self.cache_read + self.output


@dataclass(frozen=True, slots=True)
class Observation:
    observation_id: str
    provider: str
    candidate_id: str
    case_id: str
    split: EvaluationSplit
    repeat: int
    estimated_uncached_input_units: int
    estimated_output_units: int
    answer: str
    quality_score: float
    factual_errors: int
    facts_checked: int
    abstained: bool
    evidence_ids: tuple[str, ...]
    cache_entry_available_before: bool
    cache_origin: str
    usage: Usage
    retries: int
    escalations: int
    fixed_latency_ms: int


@dataclass(frozen=True, slots=True)
class QualityMetrics:
    quality: float
    factual_error_rate: float
    divergence_rate: float
    correct_abstention_rate: float
    evidence_coverage: float
    estimated_vs_actual_usage_delta: float
    mean_fixed_latency_ms: float


@dataclass(frozen=True, slots=True)
class CostBreakdown:
    uncached_input: float
    cache_write: float
    cache_read: float
    output: float
    retry: float
    escalation: float
    total: float
    cache_full_price_baseline: float
    cache_net_savings: float


@dataclass(frozen=True, slots=True)
class CandidateAssessment:
    task: str
    candidate_id: str
    provider: str
    expected_observations: int
    observed_observations: int
    dev_observations: int
    holdout_observations: int
    dev_metrics: QualityMetrics | None
    metrics: QualityMetrics | None
    dev_costs: CostBreakdown | None
    costs: CostBreakdown | None
    preflight_rejections: tuple[str, ...]
    failed_holdout_runs: tuple[str, ...]
    holdout_escalation_probability: float
    qualified: bool
    gate_failures: tuple[str, ...]
    normalized_score: float | None


@dataclass(frozen=True, slots=True)
class RouteStrategy:
    primary_candidate: str
    escalation_candidate: str | None
    escalation_probability: float
    primary_cost: float
    escalation_cost: float
    manual_review_cost: float
    total_expected_cost: float
    residual_failure_probability: float
    residual_failure_handling: str | None


@dataclass(frozen=True, slots=True)
class RouteRecommendation:
    task: str
    primary_candidate: str | None
    escalation_candidate: str | None
    escalation_probability: float
    primary_cost: float
    escalation_cost: float
    manual_review_cost: float
    total_expected_cost: float
    residual_failure_probability: float
    residual_failure_handling: str | None
    evaluated_strategies: tuple[RouteStrategy, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class TaskAssessment:
    task: str
    policy_id: str
    hard_gates: HardGates
    ranking_weights: RankingWeights
    manual_review_unit_cost: float
    candidates: tuple[CandidateAssessment, ...]
    qualified_ranking: tuple[str, ...]
    route: RouteRecommendation


@dataclass(frozen=True, slots=True)
class ProviderObservationCount:
    provider: str
    observations: int


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    evidence_id: str
    case_id: str
    supported_answer: str
    content: str
    content_digest: str


@dataclass(frozen=True, slots=True)
class CandidateRunSpec:
    candidate_id: str
    config_id: str
    provider: str
    capability_tier: int
    supported_controls: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CandidateTaskRunSpec:
    task: str
    candidate_id: str
    expected_observations: int
    expected_dev_observations: int
    expected_holdout_observations: int
    dev_costs: CostBreakdown | None
    holdout_costs: CostBreakdown | None


@dataclass(frozen=True, slots=True)
class TaskPolicyRunSpec:
    task: str
    policy_id: str
    hard_gates: HardGates
    ranking_weights: RankingWeights
    manual_review_unit_cost: float
    holdout_only_negative_policy: bool
    require_every_holdout_run: bool


@dataclass(frozen=True, slots=True)
class CaseRunSpec:
    case_id: str
    task: str
    split: EvaluationSplit
    expected_answer: str
    should_abstain: bool
    allowed_evidence_ids: tuple[str, ...]
    required_evidence_ids: tuple[str, ...]
    prompt_digest: str
    policy_digest: str
    policy_controls: tuple[str, ...]
    repeats: int


@dataclass(frozen=True, slots=True)
class AssessmentRunSpec:
    fixture_version: str
    fixture_digest: str
    case_manifest_digest: str
    observation_provenance_digest: str
    evaluator_version: str
    rubric_version: str
    tool_policy_id: str
    configuration_split: EvaluationSplit
    decision_split: EvaluationSplit
    candidate_configs: tuple[CandidateRunSpec, ...]
    candidate_config_ids: tuple[str, ...]
    task_policies: tuple[TaskPolicyRunSpec, ...]
    task_policy_ids: tuple[str, ...]
    candidate_task_runs: tuple[CandidateTaskRunSpec, ...]
    evidence_corpus: tuple[EvidenceRecord, ...]
    cases: tuple[CaseRunSpec, ...]

    @property
    def dev_case_ids(self) -> tuple[str, ...]:
        return tuple(case.case_id for case in self.cases if case.split == "dev")

    @property
    def holdout_case_ids(self) -> tuple[str, ...]:
        return tuple(case.case_id for case in self.cases if case.split == "holdout")


@dataclass(frozen=True, slots=True)
class AssessmentReport:
    fixture_integrity_validated: bool
    run_spec: AssessmentRunSpec
    case_count: int
    observation_count: int
    provider_observation_counts: tuple[ProviderObservationCount, ...]
    tasks: tuple[TaskAssessment, ...]


__all__ = [
    "AssessmentReport",
    "AssessmentRunSpec",
    "CandidateAssessment",
    "CandidateProfile",
    "CandidateRunSpec",
    "CandidateTaskRunSpec",
    "CaseRunSpec",
    "CostBreakdown",
    "EvaluationCase",
    "EvaluationSplit",
    "EvidenceRecord",
    "HardGates",
    "JsonScalar",
    "Observation",
    "ProviderObservationCount",
    "QualityMetrics",
    "RankingWeights",
    "RouteRecommendation",
    "RouteStrategy",
    "SemanticPolicy",
    "TaskAssessment",
    "TaskPolicy",
    "TaskPolicyRunSpec",
    "Usage",
]
