"""Independent acceptance and negative controls for L80; no provider calls."""

from dataclasses import replace
from fractions import Fraction
from pathlib import Path
import runpy
import unittest

lab = runpy.run_path(str(Path(__file__).with_name("main.py")))


class EffortTests(unittest.TestCase):
    def test_same_cohort_quality_then_accounting(self):
        self.assertEqual(lab["COHORT_VERSION"], "phase9-effort/v1")
        for policy, errors, delivered, total, unit, p95 in (
            ("fixed-low", ("cross-check",), 2, 78, 39, 60),
            ("fixed-high", (), 3, 150, 50, 120),
            ("selective", (), 3, 102, 34, 120),
        ):
            with self.subTest(policy=policy):
                rows = lab["replay"](policy)
                self.assertEqual(tuple(r.task_id for r in rows),
                                 ("support-retention", "ops-retention", "cross-check", "missing"))
                self.assertEqual([r.claims[0].value for r in rows[:2]], ["7 天", "30 天"])
                self.assertEqual((rows[-1].status, rows[-1].claims, rows[-1].call), ("insufficient_evidence", (), None))
                self.assertEqual([(r.lookup.charge_uc, r.lookup.duration_ms) for r in rows], [(6, 15)] * 4)
                report = lab["compare"](rows)
                self.assertEqual((report.quality_errors, report.evidence_errors, report.dispatch_errors,
                                  report.ledger_errors), (errors, (), (), ()))
                self.assertEqual((report.eligible, report.successes, report.total_charge, report.charge_per_success,
                                  report.p95_ms), (not errors, delivered, total, Fraction(unit), p95))
        rows = lab["replay"]("selective")
        self.assertEqual([(r.call.effort, r.call.charge_uc, r.call.duration_ms) for r in rows[:3]],
                         [("low", 18, 45), ("low", 18, 45), ("high", 42, 105)])
        with self.assertRaises(ValueError):
            lab["compare"](rows[::-1])

    def test_exposes_different_model_options(self):
        request, limits = lab["request_fields"], lab["Limits"]()
        claude, openai = lab["CLAUDE"], lab["OPENAI"]
        self.assertEqual(request(claude, "max", limits), {
            "model": "claude-sonnet-4-6", "thinking": {"type": "adaptive"},
            "output_config": {"effort": "max"}, "max_tokens": 4096,
        })
        self.assertEqual(request(openai, "minimal", limits), {
            "model": "gpt-5-2025-08-07", "reasoning": {"effort": "minimal"}, "max_output_tokens": 4096,
        })
        self.assertEqual(request(replace(claude, thinking="enabled", thinking_tokens=1024), "low", limits)["thinking"],
                         {"type": "enabled", "budget_tokens": 1024})
        self.assertEqual(request(replace(claude, thinking="disabled"), "low", limits)["thinking"], {"type": "disabled"})
        for target, effort in ((claude, "xhigh"), (openai, "none"), (openai, "max"),
                               (replace(claude, thinking="between_tools"), "low"),
                               (replace(claude, thinking_tokens=1024), "low"),
                               (replace(claude, thinking="enabled", thinking_tokens=4096), "low"),
                               (replace(openai, thinking="adaptive"), "low")):
            with self.subTest(target=target, effort=effort), self.assertRaises(ValueError):
                request(target, effort, limits)
        rows = lab["replay"]("selective", target=openai)
        self.assertTrue(lab["compare"](rows, target=openai).eligible)
        self.assertFalse(lab["compare"](rows).eligible)

    def test_gates_before_dispatch_and_independent_audit_after_dispatch(self):
        rows = lab["replay"]("selective")
        routine, operations, complex_row, _ = rows
        task = lab["TASKS"][2]
        run = lab["run_task"]
        a, b = complex_row.call.packet
        with lab["open_demo"]() as db:
            for packet in ((a,), (operations.call.packet[0], b), (a, replace(b, quote="同步任务每天 03:00 运行。"))):
                blocked = run(db, task, "selective", packet=packet)
                self.assertEqual((blocked.status, blocked.call, blocked.claims), ("evidence_mismatch", None, ()))
            bad_target = replace(lab["CLAUDE"], model="unsupported-fixture")
            rejected = run(db, task, "selective", target=bad_target)
            self.assertEqual((rejected.status, rejected.call, rejected.claims), ("unsupported_config", None, ()))
            db.revoke("support", "mei", "SYNC-POLICY")
            missing = run(db, task, "selective")
            self.assertEqual((missing.status, missing.call, missing.claims), ("insufficient_evidence", None, ()))
        gate = lab["compare"]
        for stopped in (blocked, rejected, missing):
            with self.subTest(status=stopped.status):
                self.assertEqual((stopped.charge_uc, stopped.elapsed_ms), (6, 15))
                self.assertEqual(gate((*rows[:2], stopped, rows[-1])).ledger_errors, ())
        report = gate((*rows[:2], missing, rows[-1]))
        self.assertEqual((report.quality_errors, report.evidence_errors, report.dispatch_errors), ((task.id,), (task.id,), (task.id,)))
        for packet in ((a,), (operations.call.packet[0], b), (a, replace(b, quote="同步任务每天 03:00 运行。"))):
            fake = replace(complex_row, call=replace(complex_row.call, packet=packet))
            report = gate((*rows[:2], fake, rows[-1]))
            self.assertEqual((report.quality_errors, report.evidence_errors, report.dispatch_errors), ((), (task.id,), ()))
            self.assertFalse(report.eligible)
        wrong_options = {**routine.call.options, "output_config": {"effort": "xhigh"}}
        fake = replace(routine, call=replace(routine.call, options=wrong_options))
        report = gate((fake, *rows[1:]))
        self.assertEqual((report.quality_errors, report.evidence_errors, report.dispatch_errors), ((), (), (routine.task_id,)))
        self.assertFalse(report.eligible)
        refused_but_dispatched = replace(rows[-1], call=routine.call)
        report = gate((*rows[:-1], refused_but_dispatched))
        self.assertEqual((report.quality_errors, report.evidence_errors, report.dispatch_errors), ((), ("missing",), ("missing",)))

    def test_valid_refusal_still_owes_lookup_and_obeys_both_limits(self):
        rows = lab["replay"]("selective")
        refusal = rows[-1]
        for fake in (replace(refusal, charge_uc=0, elapsed_ms=0),
                     replace(refusal, elapsed_ms=151), replace(refusal, charge_uc=55),
                     replace(refusal, lookup=None, charge_uc=0, elapsed_ms=0)):
            with self.subTest(fake=fake):
                report = lab["compare"]((*rows[:-1], fake))
                self.assertFalse(report.eligible)
                self.assertEqual(report.ledger_errors, ("missing",))
                self.assertEqual((report.quality_errors, report.evidence_errors, report.dispatch_errors), ((), (), ()))
                self.assertEqual(report.successes, 3)

    def test_correct_answer_cannot_deliver_with_unreported_lookup(self):
        rows = lab["replay"]("selective")
        answer = replace(rows[2], charge_uc=42, elapsed_ms=105)
        report = lab["compare"]((*rows[:2], answer, rows[-1]))
        self.assertFalse(report.eligible)
        self.assertEqual(report.ledger_errors, ("cross-check",))
        self.assertEqual((report.quality_errors, report.evidence_errors, report.dispatch_errors), ((), (), ()))
        self.assertEqual((report.successes, report.total_charge, report.p95_ms), (2, 102, 120))

    def test_answer_with_balanced_lookup_only_ledger_is_missing_a_call(self):
        rows = lab["replay"]("selective")
        answer = replace(rows[2], call=None, charge_uc=6, elapsed_ms=15)
        report = lab["compare"]((*rows[:2], answer, rows[-1]))
        self.assertEqual(report.ledger_errors, ("cross-check",))
        self.assertEqual(report.dispatch_errors, ("cross-check",))
        self.assertEqual(report.quality_errors, ())
        self.assertEqual(report.successes, 2)

    def test_independent_event_checks_reject_balanced_but_wrong_components(self):
        rows = lab["replay"]("selective")
        low, _, high, _ = rows
        for index, fake in (
            (2, replace(high, lookup=replace(high.lookup, duration_ms=14),
                        call=replace(high.call, duration_ms=106))),
            (2, replace(high, lookup=replace(high.lookup, charge_uc=5),
                        call=replace(high.call, charge_uc=43))),
            (2, replace(high, lookup=replace(high.lookup, charge_uc=5), charge_uc=47)),
            (2, replace(high, call=replace(high.call, duration_ms=104), elapsed_ms=119)),
            (0, replace(low, call=replace(low.call, charge_uc=17), charge_uc=23)),
            (0, replace(low, call=replace(low.call, duration_ms=44), elapsed_ms=59)),
        ):
            with self.subTest(fake=fake):
                report = lab["compare"]((*rows[:index], fake, *rows[index + 1:]))
                self.assertFalse(report.eligible)
                self.assertEqual(report.ledger_errors, (fake.task_id,))
                self.assertEqual((report.quality_errors, report.evidence_errors, report.dispatch_errors), ((), (), ()))
                self.assertEqual(report.successes, 2)

    def test_dispatch_at_exact_budget_and_stop_one_below(self):
        replay, compare, limits_cls = lab["replay"], lab["compare"], lab["Limits"]
        for field, cap in (("charge_uc", 48), ("deadline_ms", 120)):
            with self.subTest(field=field):
                exact, tight = limits_cls(**{field: cap}), limits_cls(**{field: cap - 1})
                full = replay("selective", limits=exact)
                self.assertTrue(compare(full, limits=exact).eligible)
                self.assertEqual((full[2].charge_uc, full[2].elapsed_ms), (48, 120))
                audit = compare(full, limits=tight)
                self.assertEqual(audit.ledger_errors, ("cross-check",))
                self.assertEqual((audit.quality_errors, audit.evidence_errors, audit.dispatch_errors), ((), (), ()))
                self.assertEqual((audit.eligible, audit.successes, audit.total_charge, audit.p95_ms), (False, 2, 102, 120))

                stopped = replay("selective", limits=tight)
                self.assertEqual((stopped[2].status, stopped[2].call), ("budget_exhausted", None))
                self.assertEqual((stopped[2].charge_uc, stopped[2].elapsed_ms), (6, 15))
                self.assertEqual((stopped[0].status, stopped[0].call.effort), ("answer", "low"))
                report = compare(stopped, limits=tight)
                self.assertFalse(report.eligible)
                self.assertEqual(report.ledger_errors, ())

    def test_lookup_at_exact_budget_and_zero_events_one_below(self):
        replay, compare, limits_cls = lab["replay"], lab["compare"], lab["Limits"]
        for field, cap in (("charge_uc", 6), ("deadline_ms", 15)):
            with self.subTest(field=field):
                exact, tight = limits_cls(**{field: cap}), limits_cls(**{field: cap - 1})
                looked_up = replay("selective", limits=exact)
                refusal = looked_up[-1]
                self.assertEqual((refusal.status, refusal.call, refusal.charge_uc, refusal.elapsed_ms),
                                 ("insufficient_evidence", None, 6, 15))
                self.assertEqual(compare(looked_up, limits=exact).ledger_errors, ())
                self.assertEqual(compare(looked_up, limits=tight).ledger_errors, tuple(r.task_id for r in looked_up))

                zeros = replay("selective", limits=tight)
                self.assertEqual([(r.status, r.lookup, r.call, r.charge_uc, r.elapsed_ms) for r in zeros],
                                 [("budget_exhausted", None, None, 0, 0)] * 4)
                report = compare(zeros, limits=tight)
                self.assertEqual((report.ledger_errors, report.total_charge, report.p95_ms), ((), 0, 0))
                self.assertIsNone(report.charge_per_success)
                fake = replace(zeros[-1], charge_uc=1, elapsed_ms=1)
                self.assertEqual(compare((*zeros[:-1], fake), limits=tight).ledger_errors, ("missing",))

    def test_truncation_keeps_full_recorded_attempt(self):
        limits = lab["Limits"](output_tokens=89)
        rows = lab["replay"]("selective", limits=limits)
        cut = rows[2]
        self.assertEqual((cut.status, cut.call.effort, cut.charge_uc, cut.elapsed_ms), ("incomplete", "high", 48, 120))
        report = lab["compare"](rows, limits=limits)
        self.assertFalse(report.eligible)
        self.assertEqual((report.ledger_errors, report.successes, report.total_charge, report.p95_ms), ((), 2, 102, 120))


if __name__ == "__main__":
    unittest.main()
