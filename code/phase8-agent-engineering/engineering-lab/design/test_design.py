"""Focused standard-library tests for the L76 and L78 local fixtures."""

from dataclasses import replace
from fractions import Fraction
from pathlib import Path
import runpy
import unittest


HERE = Path(__file__).resolve().parent
LOAD = runpy.run_path(str(HERE / "load_cost.py"))
DESIGN = runpy.run_path(str(HERE / "system_design.py"))


class LoadCostTests(unittest.TestCase):
    def test_exact_single_lever_comparisons(self):
        expected = {
            "baseline": (4270, 653), "prefix": (3470, 493), "route": (3640, 653),
            "input-145": (3745, 583), "output-30": (4170, 613),
        }
        self.assertEqual(set(LOAD["ARMS"]), set(expected))
        for name, arm in LOAD["ARMS"].items():
            with self.subTest(arm=name):
                report = LOAD["compare"](LOAD["replay"](arm))
                total, p95 = expected[name]
                self.assertTrue(report.eligible)
                self.assertEqual((report.successes, report.total_charge, report.p95_ms), (4, total, p95))
                self.assertEqual(report.charge_per_success, Fraction(total, 4))

    def test_cache_cold_per_run_and_tenant_then_provenance_negative(self):
        arm = LOAD["ARMS"]["prefix"]
        rows = LOAD["replay"](arm)
        self.assertEqual(rows, LOAD["replay"](arm))
        self.assertEqual([(a.write, a.read, a.cache_owner) for a in (row.attempts[0] for row in rows[:3])],
                         [(100, 0, None), (0, 100, "support"), (100, 0, None)])
        self.assertEqual(rows[2].outcome.evidence.retention, "30 天")
        # A fabricated ledger row with unchanged evidence/value/charges isolates the gate being tested.
        wrong_owner = replace(rows[1].attempts[0], cache_owner="operations")
        wrong_row = replace(rows[1], attempts=(wrong_owner,))
        report = LOAD["compare"]((rows[0], wrong_row, *rows[2:]))
        self.assertEqual((report.quality_errors, report.isolation_errors), ((), ("s-repeat",)))
        self.assertEqual((report.successes, report.total_charge), (3, 3470))
        self.assertFalse(report.eligible)

    def test_failed_attempts_and_delay_are_never_dropped(self):
        rows = LOAD["replay"](LOAD["ARMS"]["baseline"])
        draft, failed = rows[-2:]
        self.assertEqual([(a.status, a.charge, a.elapsed_ms) for a in draft.attempts],
                         [("timeout", 540, 240), ("complete", 790, 340)])
        self.assertEqual((draft.retry_ms, draft.elapsed_ms, draft.outcome.draft_writes), (40, 653, 1))
        self.assertEqual([(a.status, a.charge) for a in failed.attempts], [("timeout", 570), ("timeout", 570)])
        self.assertEqual((failed.retry_ms, failed.elapsed_ms, failed.outcome.draft_writes), (40, 572, 0))

    def test_input_budget_drops_optional_tokens_not_required_evidence(self):
        reduced = LOAD["replay"](LOAD["ARMS"]["input-145"])
        self.assertEqual([(a.ordinary, a.write, a.read) for a in reduced[3].attempts], [(145, 0, 0)] * 2)
        self.assertEqual(reduced[3].outcome, LOAD["LABELS"]["s-draft"])
        blocked = LOAD["replay"](LOAD["Arm"](input_cap=139))
        draft = blocked[3]
        self.assertEqual((draft.attempts, draft.outcome.status, draft.outcome.draft_writes, draft.elapsed_ms),
                         ((), "input_too_small", 0, 33))
        self.assertIn("s-draft", LOAD["compare"](blocked).quality_errors)

    def test_tighter_output_looks_cheaper_but_fails_quality(self):
        rows = LOAD["replay"](LOAD["Arm"](output_cap=29))
        report = LOAD["compare"](rows)
        self.assertEqual((report.quality_errors, report.isolation_errors), (("s-draft",), ()))
        self.assertFalse(report.eligible)
        self.assertEqual((rows[3].outcome.status, rows[3].outcome.draft_writes), ("output_incomplete", 0))
        self.assertEqual(report.charge_per_success, Fraction(4150, 3))

    def test_zero_success_means_na_and_cohort_cannot_drop_failures(self):
        rows = LOAD["replay"](LOAD["Arm"](output_cap=15))
        report = LOAD["compare"](rows)
        self.assertEqual((report.successes, report.total_charge, report.charge_per_success), (0, 3870, None))
        self.assertIn("uc/success=N/A", LOAD["format_summary"](report))
        with self.assertRaisesRegex(ValueError, "export-support-load/v1"):
            LOAD["compare"](rows[:-1])


class SystemDesignTests(unittest.TestCase):
    def test_independent_records(self):
        self.assertEqual({c.id for c in DESIGN["CASES"]}, set(DESIGN["LABELS"]))
        for case in DESIGN["CASES"]:
            with self.subTest(case=case.id):
                decision = DESIGN["select"](case)
                self.assertEqual(DESIGN["check_decision"](decision, case.id, DESIGN["LABELS"][case.id]), ())

    def test_adaptive_case_with_new_draft_requirement_has_host_owned_write(self):
        case = replace(DESIGN["CASES"][2], id="conflict-plus-draft",
                       accepts_approved_draft=True, needs_resume=True)
        label = DESIGN["Contract"]("workflow", "approval-owned-by-host", "resume-checkpoint", "host-after-approval")
        decision = DESIGN["select"](case)
        self.assertEqual(DESIGN["check_decision"](decision, case.id, label), ())
        wrong = replace(decision, contract=replace(decision.contract, draft_owner="agent"))
        self.assertEqual(DESIGN["check_decision"](wrong, case.id, label), ("draft_owner",))

    def test_read_scope_is_required_even_with_draft_and_resume(self):
        case = DESIGN["Case"]("blocked-draft", adaptive_reads=True, scoped_reader=False,
                              adaptive_eval_passed=True, needs_resume=True, accepts_approved_draft=True)
        label = DESIGN["Contract"]("workflow", "no-scoped-reader", "handoff-no-write")
        self.assertEqual(DESIGN["check_decision"](DESIGN["select"](case), case.id, label), ())


if __name__ == "__main__":
    unittest.main()
