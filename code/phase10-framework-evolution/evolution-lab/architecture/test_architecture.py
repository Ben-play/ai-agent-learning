"""Independent effect and result regressions for the L88/L89 exercises."""

from dataclasses import asdict, replace
from fractions import Fraction
from pathlib import Path
import runpy
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
L88 = runpy.run_path(str(HERE / "l88_architecture_decision.py"))
L89 = runpy.run_path(str(HERE / "l89_bounded_worker_delegation.py"))
CHECKS = L88["CHECKS"]
LAB = CHECKS["LAB"]
EXPIRY, DENIED, TIMEOUT = LAB["WORKER_COHORT"]


class ArchitectureTests(unittest.TestCase):
    def test_l88_workload(self):
        L88["check_worked"]()

    def test_l88_equal_tight_read_cap_stops(self):
        L88["check_transfer"]()

    def test_empty_cohort_or_missing_failure_cannot_be_compared(self):
        cohort, budget = LAB["CASES"], LAB["Budget"]()
        rows = LAB["replay"]("workflow", cohort, budget=budget)
        for altered in ((), rows[:4] + rows[5:], tuple(reversed(rows))):
            with self.subTest(cases=[row.case for row in altered]):
                with self.assertRaises(ValueError):
                    CHECKS["measure"]("workflow", altered, cohort, budget)

    def test_same_citation_key_does_not_allow_tenant_substitution(self):
        budget = LAB["Budget"]()
        support, ops = LAB["replay"]("workflow", LAB["CASES"][:2], budget=budget)
        forged = replace(support, outcome=ops.outcome)
        errors = CHECKS["check_observation"](forged, "P", CHECKS["GOLD"][support.case], budget)
        self.assertEqual(errors, ("outcome", "actor"))

    def test_exact_answer_count_rejects_wrong_scope_and_citations(self):
        budget = LAB["Budget"]()
        row = LAB["run"](EXPIRY, "workflow", budget=budget)
        first, second = row.outcome.evidence
        probes = (
            (replace(row, actor=("operations", "mei")), "actor"),
            (replace(row, outcome=replace(row.outcome, evidence=(replace(first, actor=DENIED.actor), second))),
             "actor"),
            (replace(row, outcome=replace(row.outcome, evidence=(second, first))), "outcome"),
            (replace(row, outcome=replace(row.outcome, evidence=(first, replace(second, key=("EXPORT-OPS", 2, "§2"))))),
             "outcome"),
        )
        for altered, error in probes:
            with self.subTest(error=error, row=altered):
                measured = CHECKS["measure"]("workflow", (altered,), (EXPIRY,), budget)
                self.assertEqual((measured.correct_answers, measured.tasks), (0, 1))
                self.assertEqual(measured.total_cost, 4)
                self.assertIsNone(measured.cost_per_answer)
                self.assertEqual(measured.contract_errors, (f"expiry:{error}",))

    def test_denied_and_timeout_not_same_source_event(self):
        denied = LAB["run"](DENIED, "workflow")
        timeout = LAB["run"](TIMEOUT, "workflow")
        self.assertEqual(denied.source_calls, ((DENIED.actor, LAB["POLICY"]), (DENIED.actor, LAB["OPS"])))
        self.assertEqual(timeout.source_calls, ((TIMEOUT.actor, LAB["POLICY"]),))
        self.assertEqual([(e.operation, e.status) for e in timeout.dispatches],
                         [("read", "ok"), ("read", "timeout"), ("review", "timeout")])
        self.assertEqual((denied.cost, denied.ms, timeout.cost, timeout.ms), (5, 21, 6, 37))

    def test_wrong_trace_or_extra_source_call_fails_without_regrading_answer(self):
        row = LAB["run"](EXPIRY, "worker")
        probes = (
            (replace(row, events=row.events[:-1]), "events"),
            (replace(row, events=row.events + row.events[-1:]), "events"),
            (replace(row, source_calls=row.source_calls + row.source_calls[-1:]), "source_calls"),
        )
        for altered, error in probes:
            with self.subTest(error=error):
                measured = CHECKS["measure"]("worker", (altered,), (EXPIRY,), row.budget)
                self.assertEqual(measured.correct_answers, 1)
                self.assertEqual(measured.contract_errors, (f"expiry:{error}",))

    def test_runtime_read_price_drift_preserves_answers_but_disqualifies_arms(self):
        original, _, _ = L88["exercise"]()
        rates = LAB["RATES"]
        # Change only the ordinary read price, not the independent acceptance tariff.
        with patch.dict(rates, {"read": (3, 8)}):
            rows, summary, decision = L88["exercise"]()
        for arm, correct, cost in (("thin", 2, 18), ("workflow", 3, 26), ("single", 3, 34)):
            with self.subTest(arm=arm):
                before, after = original[arm], rows[arm]
                self.assertEqual([row.outcome for row in before], [row.outcome for row in after])
                self.assertEqual([row.source_calls for row in before], [row.source_calls for row in after])
                self.assertEqual((summary[arm].correct_answers, summary[arm].tasks), (correct, 6))
                self.assertEqual(summary[arm].total_cost, cost)
                self.assertEqual(summary[arm].cost_per_answer, Fraction(cost, correct))
                self.assertIn("support-retention:accounting", summary[arm].contract_errors)
                self.assertNotIn("support-retention:events", summary[arm].contract_errors)
        self.assertEqual(decision, "stop_review")

    def test_l89_price_drift_blocks_an_otherwise_better_candidate(self):
        with patch.dict(L89["LAB"]["RATES"], {"worker": (0, 4)}):
            _, summary, _ = L89["exercise"]()
        candidate = summary["worker"]
        self.assertEqual((candidate.correct_answers, candidate.total_cost, candidate.p95_ms), (1, 22, 47))
        self.assertEqual(candidate.contract_errors,
                         ("expiry:accounting", "expiry-no-grant:accounting", "expiry-timeout:accounting"))
        # Set a hypothetical benchmark so the candidate would win on metrics alone.
        base = replace(summary["single"], total_cost=25, p95_ms=47)
        self.assertEqual(L89["recommend"]({"single": base, "worker": candidate}), "keep_single")
        self.assertEqual(L89["recommend"]({"single": base, "worker": replace(candidate, contract_errors=())}),
                         "review_candidate")

    def test_l89_accounting_audits_each_event_even_when_totals_balance(self):
        cohort = LAB["WORKER_COHORT"]
        rows, summary, _ = L89["exercise"]()
        row, *failed = rows["worker"]
        choose, read, *rest = row.events
        # Swap both measurements between events; the trial totals still match the tariff.
        altered = replace(row, events=(replace(choose, cost=2, ms=8), replace(read, cost=1, ms=3), *rest))
        self.assertEqual((altered.cost, altered.ms), (8, 28))
        measured = CHECKS["measure"]("worker", (altered, *failed), cohort, row.budget)
        self.assertEqual(asdict(measured), {**asdict(summary["worker"]), "contract_errors": ("expiry:accounting",)})

    def test_latency_drift_on_failed_l89_trial_counts_in_p95(self):
        rows, summary, _ = L89["exercise"]()
        row = rows["single"][-1]
        altered = replace(row, events=(*row.events[:-1], replace(row.events[-1], ms=15)))
        measured = CHECKS["measure"]("single", (*rows["single"][:-1], altered), LAB["WORKER_COHORT"], row.budget)
        self.assertEqual(asdict(measured), {**asdict(summary["single"]), "p95_ms": 53,
                                           "contract_errors": ("expiry-timeout:accounting",)})
        self.assertEqual(L89["recommend"]({**summary, "single": measured}), "stop_review")

    def test_monetary_cap_audit_does_not_regrade_the_answer(self):
        row = LAB["run"](EXPIRY, "workflow")
        cap = LAB["Budget"](credits=3)
        measured = CHECKS["measure"]("workflow", (replace(row, budget=cap),), (EXPIRY,), cap)
        self.assertEqual((measured.correct_answers, measured.total_cost), (1, 4))
        self.assertEqual(measured.contract_errors, ("expiry:budget",))
        # Even a tariff-valid ledger with a mismatched declared budget must not pass.
        measured = CHECKS["measure"]("workflow", (row,), (EXPIRY,), LAB["Budget"](credits=11))
        self.assertEqual(measured.contract_errors, ("expiry:budget",))

    def test_l89_frozen_expiry_cohort_and_positive_control(self):
        cohort = ["expiry", "expiry-no-grant", "expiry-timeout"]
        self.assertEqual([c.name for c in LAB["WORKER_COHORT"]], cohort)
        old_rows, _, _ = L88["exercise"]()
        new_rows, _, _ = L89["exercise"]()
        self.assertEqual([asdict(row) for row in old_rows["single"] if row.case in cohort],
                         [asdict(row) for row in new_rows["single"]])
        L89["check_worked"]()

    def test_l89_handoff_scope_result_and_budget_failures(self):
        L89["check_transfer"]()

    def test_worker_cap_blocks_before_dispatch(self):
        row = LAB["run"](EXPIRY, "worker", budget=LAB["Budget"](workers=0))
        self.assertEqual(row.outcome.reason, "budget_exhausted")
        self.assertEqual([e.operation for e in row.dispatches], ["choose", "read", "choose", "review"])
        self.assertEqual(row.source_calls, ((EXPIRY.actor, LAB["POLICY"]),))

    def test_recommendation_rejects_cost_alone_despite_tail_gain(self):
        _, summary, _ = L89["exercise"]()
        base = summary["single"]
        candidate = replace(base, p95_ms=base.p95_ms - 1)
        self.assertEqual(L89["recommend"]({"single": base, "worker": candidate}), "review_candidate")
        too_costly = replace(candidate, total_cost=base.total_cost + 1)
        self.assertEqual(L89["recommend"]({"single": base, "worker": too_costly}), "keep_single")
        incomplete = replace(candidate, contract_errors=("expiry:events",))
        self.assertEqual(L89["recommend"]({"single": base, "worker": incomplete}), "keep_single")

    def test_l88_can_stop_or_keep_a_valid_single(self):
        _, summary, _ = L88["exercise"]()
        thin = summary["thin"]
        bad_workflow = replace(summary["workflow"], contract_errors=("expiry:actor",))
        single = summary["single"]
        self.assertEqual(L88["recommend"]({"thin": thin, "workflow": bad_workflow, "single": single}), "single")
        bad_single = replace(single, contract_errors=("expiry:source_calls",))
        self.assertEqual(L88["recommend"]({"thin": thin, "workflow": bad_workflow, "single": bad_single}),
                         "stop_review")


if __name__ == "__main__":
    unittest.main()
