from __future__ import annotations

from dataclasses import replace

import pytest

from phase2_practices import build_offline_lab
from phase2_practices.acceptance import assert_accepted


def rejected(report: object, message: str) -> None:
    with pytest.raises(AssertionError, match=message):
        assert_accepted(report)  # type: ignore[arg-type]


def test_acceptance_rejects_provider_count_mutations() -> None:
    report = build_offline_lab().assess()
    first = report.provider_observation_counts[0]
    rejected(
        replace(report, provider_observation_counts=(replace(first, provider=""),)),
        "provider names",
    )
    rejected(
        replace(report, provider_observation_counts=(replace(first, observations=-1),)),
        "provider observations",
    )
    rejected(
        replace(report, provider_observation_counts=(first, first)),
        "provider names must be unique",
    )


def test_acceptance_rejects_run_spec_and_count_mutations() -> None:
    report = build_offline_lab().assess()
    rejected(replace(report, case_count=report.case_count + 1), "case count")
    rejected(replace(report, observation_count=report.observation_count + 1), "observation count")
    rejected(
        replace(report, run_spec=replace(report.run_spec, fixture_digest="bad")),
        "fixture digest",
    )
    rejected(
        replace(report, run_spec=replace(report.run_spec, evaluator_version="other")),
        "evaluator version",
    )
    rejected(
        replace(
            report,
            run_spec=replace(
                report.run_spec,
                candidate_config_ids=(
                    report.run_spec.candidate_config_ids[0],
                    report.run_spec.candidate_config_ids[0],
                ),
            ),
        ),
        "candidate config IDs must be unique",
    )
    first_case = report.run_spec.cases[0]
    swapped_split = replace(
        first_case,
        split="holdout" if first_case.split == "dev" else "dev",
    )
    rejected(
        replace(
            report,
            run_spec=replace(
                report.run_spec,
                cases=(swapped_split,) + report.run_spec.cases[1:],
            ),
        ),
        "run spec cases do not match trusted case manifest",
    )
    ghost_case = replace(
        first_case,
        allowed_evidence_ids=first_case.allowed_evidence_ids + ("ghost",),
        required_evidence_ids=first_case.required_evidence_ids + ("ghost",),
    )
    rejected(
        replace(
            report,
            run_spec=replace(
                report.run_spec,
                cases=(ghost_case,) + report.run_spec.cases[1:],
            ),
        ),
        "run spec cases do not match trusted case manifest",
    )


def test_acceptance_rejects_metric_ranking_and_qualification_mutations() -> None:
    report = build_offline_lab().assess()
    routine = next(task for task in report.tasks if task.task == "routine_triage")
    spruce = next(candidate for candidate in routine.candidates if candidate.candidate_id == "Spruce-S")
    assert spruce.metrics is not None
    bad_metrics = replace(spruce.metrics, quality=2.0)
    bad_candidate = replace(spruce, metrics=bad_metrics)
    bad_task = replace(
        routine,
        candidates=tuple(bad_candidate if candidate.candidate_id == "Spruce-S" else candidate for candidate in routine.candidates),
    )
    rejected(
        replace(report, tasks=tuple(bad_task if task.task == routine.task else task for task in report.tasks)),
        "quality must be",
    )
    rejected(
        replace(report, tasks=tuple(replace(routine, qualified_ranking=("Spruce-S", "Spruce-S")) if task.task == routine.task else task for task in report.tasks)),
        "qualified ranking contains duplicate",
    )
    forged_spruce = replace(
        spruce,
        normalized_score=(spruce.normalized_score or 0.0) + 0.001,
    )
    forged_task = replace(
        routine,
        candidates=tuple(
            forged_spruce if candidate.candidate_id == "Spruce-S" else candidate
            for candidate in routine.candidates
        ),
    )
    rejected(
        replace(
            report,
            tasks=tuple(
                forged_task if task.task == routine.task else task
                for task in report.tasks
            ),
        ),
        "normalized scores do not match recomputed weighted scores",
    )
    wrong_task_candidate = replace(spruce, task="different")
    wrong_task = replace(
        routine,
        candidates=tuple(
            wrong_task_candidate if candidate.candidate_id == "Spruce-S" else candidate
            for candidate in routine.candidates
        ),
    )
    rejected(
        replace(
            report,
            tasks=tuple(
                wrong_task if task.task == routine.task else task
                for task in report.tasks
            ),
        ),
        "candidate task does not match containing task",
    )
    forged_ranking = tuple(reversed(routine.qualified_ranking))
    forged_scores = {
        candidate_id: float(len(forged_ranking) - index)
        for index, candidate_id in enumerate(forged_ranking)
    }
    forged_candidates = tuple(
        replace(candidate, normalized_score=forged_scores[candidate.candidate_id])
        if candidate.candidate_id in forged_scores
        else candidate
        for candidate in routine.candidates
    )
    rejected(
        replace(
            report,
            tasks=tuple(
                replace(
                    routine,
                    candidates=forged_candidates,
                    qualified_ranking=forged_ranking,
                )
                if task.task == routine.task
                else task
                for task in report.tasks
            ),
        ),
        "normalized scores do not match recomputed weighted scores",
    )
    unqualified_spruce = replace(spruce, qualified=False, normalized_score=None, gate_failures=("mutated",))
    unqualified_task = replace(
        routine,
        candidates=tuple(unqualified_spruce if candidate.candidate_id == "Spruce-S" else candidate for candidate in routine.candidates),
    )
    rejected(
        replace(report, tasks=tuple(unqualified_task if task.task == routine.task else task for task in report.tasks)),
        "qualified ranking does not exactly cover",
    )


def test_acceptance_rejects_zero_manual_review_unit_cost() -> None:
    report = build_offline_lab().assess()
    routine = next(task for task in report.tasks if task.task == "routine_triage")
    rejected(
        replace(
            report,
            tasks=tuple(
                replace(routine, manual_review_unit_cost=0.0)
                if task.task == routine.task
                else task
                for task in report.tasks
            ),
        ),
        "manual review unit cost must be finite and strictly positive",
    )


def test_acceptance_rejects_cost_route_and_no_route_mutations() -> None:
    report = build_offline_lab().assess()
    routine = next(task for task in report.tasks if task.task == "routine_triage")
    spruce = next(candidate for candidate in routine.candidates if candidate.candidate_id == "Spruce-S")
    assert spruce.costs is not None
    bad_cost = replace(spruce.costs, total=spruce.costs.total + 1)
    bad_candidate = replace(spruce, costs=bad_cost)
    bad_task = replace(
        routine,
        candidates=tuple(bad_candidate if candidate.candidate_id == "Spruce-S" else candidate for candidate in routine.candidates),
    )
    rejected(
        replace(report, tasks=tuple(bad_task if task.task == routine.task else task for task in report.tasks)),
        "candidate costs do not match candidate-task run spec",
    )
    missing_dev_costs = replace(spruce, dev_costs=None)
    missing_dev_task = replace(
        routine,
        candidates=tuple(
            missing_dev_costs if candidate.candidate_id == "Spruce-S" else candidate
            for candidate in routine.candidates
        ),
    )
    rejected(
        replace(
            report,
            tasks=tuple(
                missing_dev_task if task.task == routine.task else task
                for task in report.tasks
            ),
        ),
        "candidate costs do not match candidate-task run spec",
    )
    bad_savings = replace(spruce.costs, cache_net_savings=999.984)
    bad_savings_candidate = replace(spruce, costs=bad_savings)
    bad_savings_task = replace(
        routine,
        candidates=tuple(
            bad_savings_candidate if candidate.candidate_id == "Spruce-S" else candidate
            for candidate in routine.candidates
        ),
    )
    rejected(
        replace(
            report,
            tasks=tuple(
                bad_savings_task if task.task == routine.task else task
                for task in report.tasks
            ),
        ),
        "candidate costs do not match candidate-task run spec",
    )
    rejected(
        replace(report, tasks=tuple(replace(routine, route=replace(routine.route, total_expected_cost=routine.route.total_expected_cost + 1)) if task.task == routine.task else task for task in report.tasks)),
        "chosen route is not the true minimum",
    )
    omitted_route = replace(
        routine.route,
        evaluated_strategies=routine.route.evaluated_strategies[1:],
    )
    rejected(
        replace(
            report,
            tasks=tuple(
                replace(routine, route=omitted_route)
                if task.task == routine.task
                else task
                for task in report.tasks
            ),
        ),
        "route strategies do not enumerate every eligible",
    )
    first_strategy = routine.route.evaluated_strategies[0]
    forged_probability_strategy = replace(
        first_strategy,
        escalation_probability=(first_strategy.escalation_probability + 0.123) % 1.0,
    )
    forged_probability_route = replace(
        routine.route,
        evaluated_strategies=(forged_probability_strategy,)
        + routine.route.evaluated_strategies[1:],
    )
    rejected(
        replace(
            report,
            tasks=tuple(
                replace(routine, route=forged_probability_route)
                if task.task == routine.task
                else task
                for task in report.tasks
            ),
        ),
        "strategy escalation probability|escalation cost|residual",
    )
    bad_strategy = replace(
        first_strategy,
        residual_failure_probability=1.0,
        residual_failure_handling=None,
    )
    bad_route = replace(
        routine.route,
        evaluated_strategies=(bad_strategy,) + routine.route.evaluated_strategies[1:],
    )
    rejected(
        replace(
            report,
            tasks=tuple(
                replace(routine, route=bad_route) if task.task == routine.task else task
                for task in report.tasks
            ),
        ),
        "residual",
    )
    impossible = next(task for task in report.tasks if task.task == "impossible_safety")
    bad_impossible = replace(impossible, route=replace(impossible.route, primary_candidate="Spruce-S"))
    rejected(
        replace(report, tasks=tuple(bad_impossible if task.task == impossible.task else task for task in report.tasks)),
        "no-route IDs must be None",
    )
