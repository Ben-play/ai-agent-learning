"""Dependency-free regressions at the assessment and acceptance boundaries."""

from __future__ import annotations

import json
import shutil
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TypedDict

from phase2_practices import AssessmentReport, build_offline_lab
from phase2_practices.acceptance import assert_accepted
from phase2_practices.assessment import FixtureIntegrityError
from phase2_practices.contracts import TaskAssessment


class _StrategyMutation(TypedDict, total=False):
    residual_failure_probability: float
    manual_review_cost: float
    escalation_cost: float
    total_expected_cost: float


def _grounded_task(report: AssessmentReport) -> TaskAssessment:
    return next(task for task in report.tasks if task.task == "grounded_lookup")


def _with_task(report: AssessmentReport, task: TaskAssessment) -> AssessmentReport:
    return replace(report, tasks=tuple(task if item.task == task.task else item for item in report.tasks))


class PairedRoutesTest(unittest.TestCase):
    def _paired_fixture_root(self, primary_failure_repeat: int) -> Path:
        root = Path(self.enterContext(TemporaryDirectory())) / "fixtures"
        shutil.copytree(Path(__file__).resolve().parents[1] / "fixtures", root)

        # Keep the registered holdout cases and repeats. Qualify exactly Cedar
        # and Flint on this task even with one incorrect answer out of five.
        path = root / "evaluation-cases.json"
        cases = json.loads(path.read_text(encoding="utf-8"))
        policy = next(item for item in cases["task_policies"] if item["task"] == "grounded_lookup")
        policy["hard_gates"].update(
            minimum_quality=0.8,
            maximum_factual_error_rate=0.2,
            maximum_divergence_rate=0.4,
            minimum_correct_abstention_rate=0.8,
        )
        path.write_text(json.dumps(cases), encoding="utf-8")

        path = root / "observations.json"
        observations = json.loads(path.read_text(encoding="utf-8"))
        failed_repeats = {"Cedar-S": primary_failure_repeat, "Flint-E": 1}
        for row in observations["observations"]:
            if row["case_id"] != "unsupported-moon":
                continue
            if row["repeat"] == failed_repeats.get(row["candidate_id"]):
                # One normalization leaves a non-abstention ("abstain!").
                row.update(answer="ABSTAIN! .", abstained=False, factual_errors=1)
            if row["candidate_id"] == "Flint-E" and row["repeat"] == 1:
                # Flint's first run costs 0.692 credits; others cost 0.282.
                row["consumption"]["answer_units"] = 52
                row["events"].update(retry_events=1, escalation_events=1)
        observations["observations"].reverse()
        path.write_text(json.dumps(observations), encoding="utf-8")
        return root

    def test_same_twenty_percent_marginals_have_different_paired_residuals(self) -> None:
        for primary_repeat, residual, fallback_cost, review, total, handling in (
            (1, 0.2, 0.1384, 1.2, 1.5168, "manual_review"),
            (2, 0.0, 0.0564, 0.0, 0.2348, None),
        ):
            with self.subTest(primary_repeat=primary_repeat):
                report = build_offline_lab(self._paired_fixture_root(primary_repeat)).assess()
                grounded = _grounded_task(report)
                qualified = {candidate.candidate_id: candidate for candidate in grounded.candidates if candidate.qualified}
                self.assertEqual(
                    {name: candidate.holdout_escalation_probability for name, candidate in qualified.items()},
                    {"Cedar-S": 0.2, "Flint-E": 0.2},
                )
                self.assertEqual((grounded.route.primary_candidate, grounded.route.escalation_candidate), ("Cedar-S", "Flint-E"))
                route = grounded.route
                self.assertEqual(route.residual_failure_probability, residual)
                self.assertEqual(route.residual_failure_handling, handling)
                self.assertEqual(route.escalation_probability, 0.2)
                self.assertAlmostEqual(route.primary_cost, 0.1784)
                self.assertAlmostEqual(route.escalation_cost, fallback_cost)
                self.assertAlmostEqual(route.manual_review_cost, review)
                self.assertAlmostEqual(route.total_expected_cost, total)

                flint = qualified["Flint-E"].costs
                assert flint is not None
                self.assertAlmostEqual(flint.total, 1.82)
                self.assertAlmostEqual(flint.retry, 0.035)
                self.assertAlmostEqual(flint.escalation, 0.075)
                assert_accepted(report)

    def test_acceptance_rejects_consistent_marginal_shortcuts(self) -> None:
        report = build_offline_lab(self._paired_fixture_root(1)).assess()
        assert_accepted(report)
        grounded = _grounded_task(report)
        route = grounded.route
        # Change both the chosen route and its strategy, including the total.
        # Neither the candidate marginals nor the holdout spend changes.
        mutations: tuple[tuple[_StrategyMutation, str], ...] = (
            (
                {"residual_failure_probability": 0.04, "manual_review_cost": 0.24, "total_expected_cost": 0.5568},
                "strategy residual probability",
            ),
            (
                {"escalation_cost": 0.0728, "total_expected_cost": 1.4512},
                "strategy escalation cost",
            ),
        )
        for fields, message in mutations:
            with self.subTest(message=message):
                forged = replace(route.evaluated_strategies[0], **fields)
                bad_route = replace(
                    route, evaluated_strategies=(forged,) + route.evaluated_strategies[1:], **fields
                )
                with self.assertRaisesRegex(AssertionError, message):
                    assert_accepted(_with_task(report, replace(grounded, route=bad_route)))

    def test_acceptance_uses_recomputed_totals_to_break_ties(self) -> None:
        report = build_offline_lab().assess()
        routine = next(task for task in report.tasks if task.task == "routine_triage")
        route = routine.route
        winner, tied, *rest = route.evaluated_strategies
        self.assertEqual(winner.total_expected_cost, tied.total_expected_cost)
        self.assertEqual((winner.escalation_candidate, tied.escalation_candidate), ("Cedar-S", "Quartz-E"))
        forged = replace(tied, total_expected_cost=tied.total_expected_cost - 1e-13)
        bad_route = replace(
            route,
            escalation_candidate=forged.escalation_candidate,
            total_expected_cost=forged.total_expected_cost,
            evaluated_strategies=(forged, winner, *rest),
        )
        with self.assertRaisesRegex(AssertionError, "chosen route is not the true minimum"):
            assert_accepted(_with_task(report, replace(routine, route=bad_route)))

    def test_assessment_rejects_missing_or_duplicate_pairs(self) -> None:
        root = self._paired_fixture_root(1)
        path = root / "observations.json"
        observations = json.loads(path.read_text(encoding="utf-8"))
        rows = observations["observations"]
        missing = next(
            row for row in rows
            if (row["candidate_id"], row["case_id"], row["repeat"]) == ("Flint-E", "unsupported-moon", 1)
        )
        rows_without_match = [row for row in rows if row is not missing]
        duplicate = next(
            row for row in rows_without_match
            if (row["candidate_id"], row["case_id"], row["repeat"]) == ("Flint-E", "unsupported-moon", 2)
        )
        for cohort, message in (
            (rows_without_match, "observation coverage mismatch"),
            (rows_without_match + [dict(duplicate, observation_id="duplicate-trial")], "duplicate observation key"),
        ):
            with self.subTest(message=message):
                observations["observations"] = cohort
                path.write_text(json.dumps(observations), encoding="utf-8")
                with self.assertRaisesRegex(FixtureIntegrityError, message):
                    build_offline_lab(root).assess()

    def test_acceptance_binds_trial_identity_evidence_and_cost(self) -> None:
        report = build_offline_lab(self._paired_fixture_root(1)).assess()
        grounded = _grounded_task(report)
        row, *rest = grounded.holdout_trials
        for rows, message in (
            (tuple(rest), "holdout trial coverage"),
            ((rest[0], *rest), "duplicate holdout trial"),
            ((replace(row, case_id="grounded-capital"), *rest), "unexpected holdout trial key"),
            ((replace(row, repeat=6), *rest), "unexpected holdout trial key"),
            ((replace(row, evidence_ids=("atlas-capital",)), *rest), "holdout trial evidence"),
            ((replace(row, cost=row.cost + 1.0), *rest), "holdout trial costs"),
        ):
            with self.subTest(message=message):
                forged = replace(grounded, holdout_trials=rows)
                with self.assertRaisesRegex(AssertionError, message):
                    assert_accepted(_with_task(report, forged))
