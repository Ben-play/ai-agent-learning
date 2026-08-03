from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from phase2_practices import AssessmentLab, AssessmentReport, build_offline_lab
from phase2_practices.contracts import CandidateAssessment, TaskAssessment


def _task(report: AssessmentReport, name: str) -> TaskAssessment:
    return next(task for task in report.tasks if task.task == name)


def _candidate(task: TaskAssessment, candidate_id: str) -> CandidateAssessment:
    return next(
        candidate for candidate in task.candidates if candidate.candidate_id == candidate_id
    )


def test_public_interface_is_deep_small_and_immutable() -> None:
    from phase2_practices import __all__

    assert __all__ == ["AssessmentLab", "AssessmentReport", "build_offline_lab"]
    lab = build_offline_lab()
    assert isinstance(lab, AssessmentLab)
    assert [name for name in dir(lab) if not name.startswith("_")] == ["assess"]
    report = lab.assess()
    with pytest.raises(FrozenInstanceError):
        report.case_count = 0  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        report.run_spec.fixture_version = "changed"  # type: ignore[misc]


def test_assessment_and_audit_metadata_are_deterministic() -> None:
    first = build_offline_lab().assess()
    second = build_offline_lab().assess()
    assert first == second
    assert first.run_spec == second.run_spec
    assert first.fixture_integrity_validated
    assert first.case_count == len(first.run_spec.cases)
    assert first.observation_count == 94
    assert first.run_spec.fixture_version == "phase2-fixtures-v2"
    assert len(first.run_spec.fixture_digest) == 64
    assert first.run_spec.configuration_split == "dev"
    assert first.run_spec.decision_split == "holdout"
    assert first.run_spec.dev_case_ids
    assert first.run_spec.holdout_case_ids
    assert sum(item.observations for item in first.provider_observation_counts) == 94


def test_quality_dimensions_are_separate_not_consistency_as_truth() -> None:
    grounded = _task(build_offline_lab().assess(), "grounded_lookup")
    spruce = _candidate(grounded, "Spruce-S")
    quartz = _candidate(grounded, "Quartz-E")
    assert spruce.metrics is not None
    assert spruce.metrics.divergence_rate == 0.0
    assert spruce.metrics.factual_error_rate > 0.0
    assert not spruce.qualified
    assert quartz.metrics is not None
    assert quartz.metrics.divergence_rate > 0.0
    assert quartz.metrics.correct_abstention_rate < 1.0
    assert quartz.metrics.evidence_coverage == 1.0


def test_dev_metrics_are_reported_but_holdout_alone_controls_decisions() -> None:
    report = build_offline_lab().assess()
    grounded = _task(report, "grounded_lookup")
    spruce = _candidate(grounded, "Spruce-S")
    cedar = _candidate(grounded, "Cedar-S")
    assert spruce.dev_observations == 5
    assert spruce.holdout_observations == 5
    assert spruce.dev_metrics is not None
    assert spruce.metrics is not None
    assert cedar.dev_metrics is not None
    assert cedar.metrics is not None
    # Spruce dev and holdout metrics differ; the holdout factuality failure wins.
    assert spruce.dev_metrics.quality != spruce.metrics.quality
    assert "factual error rate above maximum" in spruce.gate_failures
    # Every routed candidate must qualify on holdout, never on dev alone.
    for task in report.tasks:
        if task.route.primary_candidate is not None:
            selected = _candidate(task, task.route.primary_candidate)
            assert selected.qualified
            assert selected.holdout_observations > 0


def test_provider_native_estimates_are_candidate_specific() -> None:
    routine = _task(build_offline_lab().assess(), "routine_triage")
    deltas = {
        candidate.candidate_id: candidate.metrics.estimated_vs_actual_usage_delta
        for candidate in routine.candidates
        if candidate.metrics is not None
    }
    assert deltas["Spruce-S"] == 0.0
    assert len(set(deltas.values())) == len(deltas)
