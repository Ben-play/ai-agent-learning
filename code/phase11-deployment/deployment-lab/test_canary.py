import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock, patch

import canary


class CanaryTests(unittest.TestCase):
    def test_both_arms_execute_full_independent_cohort(self):
        expected = [
            ("review-denied", "denied", "denied", 0, 0, 0, 0, 0, None, 30),
            ("policy-retention", "answered", None, 0, 0, 0, 0, 0, None, 45),
            ("no-evidence", "needs_evidence", None, 0, 0, 0, 0, 0, None, 24),
            ("lost-reply", "replayed", "saved", 1, 1, 1, 1, 0, True, 100),
            ("review-pending", "pending", "pending", 0, 0, 0, 0, 0, None, 12),
            ("draft-committed", "saved", "saved", 1, 0, 1, 1, 0, None, 60),
        ]
        live = Mock(wraps=canary.GATE["exercise"])
        with patch.dict(canary.GATE, {"exercise": live}):
            report = canary.run()
        self.assertEqual(live.call_count, 12)
        self.assertEqual(live.call_args_list[::2], live.call_args_list[1::2])
        self.assertEqual(report["decision"], "CONTINUE_LOCAL")
        self.assertTrue(report["complete"])
        self.assertTrue(report["cohort_digest_valid"])
        self.assertEqual(report["cohort_digest"], report["expected_cohort_digest"])
        self.assertEqual(report["cohort_digest"], "5b3d7409f65c60fea1a79e7da62d259a1f6396f34ae71c682c3e215538062076")
        self.assertNotEqual(report["cohort_digest"], report["phase8_fingerprint"])
        for arm in ("control", "candidate"):
            summary = report[arm]
            fields = ("case_id", "status", "checkpoint", "dispatches", "recoveries", "writes",
                      "saved_rows", "replay_writes", "same_receipt", "simulated_ms")
            self.assertEqual([tuple(row[key] for key in fields) for row in summary["rows"]], expected)
            self.assertEqual((summary["successes"], summary["n"], summary["errors"], summary["p95_ms"]), (6, 6, 0, 100))
            self.assertEqual(summary["rows"][0]["approval_probe"], {"reason": "approval_required", "checkpoint": "pending",
                                    "dispatches": 0, "writes": 0, "rows": 0, "receipt": False})

    def test_metric_stop_uses_full_cohort_even_if_error_count_is_zero(self):
        report = canary.run("v2-slow")
        self.assertIs(report["complete"], True)
        self.assertEqual([report[arm]["p95_ms"] for arm in ("control", "candidate")], [100, 124])
        self.assertEqual(report["decision"], "STOP_AND_ROLLBACK")
        self.assertEqual(report["reasons"], ["p95_absolute", "p95_regression"])
        self.assertEqual(report["candidate"]["successes"], 6)
        self.assertEqual(report["candidate"]["errors"], 0)

    def test_missing_citation_is_not_a_status_error_and_stays_in_cohort(self):
        report = canary.run("v2-uncited")
        failed = [row for row in report["candidate"]["rows"] if not row["passed"]]
        self.assertEqual([(r["case_id"], r["status"], r["mismatches"], r["citation_keys"]) for r in failed],
                         [("policy-retention", "answered", ["citations"], [])])
        self.assertEqual((report["candidate"]["successes"], report["candidate"]["n"], report["candidate"]["timed"]), (5, 6, 6))
        self.assertEqual(report["reasons"], ["success_rate"])

    def test_fault_signals_stop_without_starting_the_next_trial(self):
        for fixture, n, reason in (("v2-authority-fault", 1, "authority_probe_failed"),
                                    ("v2-recovery-fault", 4, "recovery_probe_failed")):
            with self.subTest(fixture=fixture):
                observed = Mock(wraps=canary.observe)
                with patch.object(canary, "observe", observed):
                    report = canary.run(fixture)
                self.assertEqual(observed.call_count, n * 2)
                self.assertEqual(report["decision"], "STOP_AND_ROLLBACK")
                self.assertEqual(report["reasons"], report["fault_fixture"])
                self.assertEqual(report["reasons"], [reason])
                self.assertIs(report["complete"], False)
                self.assertEqual([report[a]["successes"] for a in ("control", "candidate")], [n, n])
                self.assertEqual(report["candidate"]["rows"][-1]["hard_signals"], [])

    def test_actual_recovery_readback_can_hard_stop_the_control(self):
        exercise = canary.GATE["exercise"]

        def wrong_receipt(case, **kwargs):
            row = exercise(case, **kwargs)
            return replace(row, same_receipt=False) if case["id"] == "lost-reply" else row

        with patch.dict(canary.GATE, {"exercise": wrong_receipt}):
            report = canary.run()
        self.assertEqual((report["control"]["n"], report["candidate"]["n"]), (4, 3))
        self.assertEqual(report["decision"], "STOP_AND_ROLLBACK")
        self.assertEqual(report["reasons"], ["recovery_probe_failed"])
        self.assertEqual(report["fault_fixture"], [])

    def test_recovery_mismatch_still_hard_stops_if_events_are_unknown(self):
        exercise = canary.GATE["exercise"]

        def wrong_receipt(case, **kwargs):
            row = exercise(case, **kwargs)
            if case["id"] == "lost-reply":
                return replace(row, same_receipt=False, events=("recover-unmetered",))
            return row

        with patch.dict(canary.GATE, {"exercise": wrong_receipt}):
            report = canary.run()
        row = report["control"]["rows"][-1]
        self.assertEqual((row["case_id"], row["simulated_ms"]), ("lost-reply", None))
        self.assertEqual(report["decision"], "STOP_AND_ROLLBACK")
        self.assertEqual(report["reasons"], ["recovery_probe_failed"])
        self.assertEqual(report["candidate"]["n"], 3)

    def test_unavailable_authority_readback_fails_closed_without_timing(self):
        with patch.dict(canary.GATE, {"exercise": Mock(side_effect=AssertionError("readback missing"))}):
            report = canary.run()
        self.assertEqual((report["control"]["n"], report["candidate"]["n"]), (1, 0))
        self.assertEqual(report["decision"], "STOP_AND_ROLLBACK")
        self.assertEqual(report["reasons"], ["authority_probe_failed"])
        self.assertIsNone(report["control"]["p95_ms"])
        self.assertEqual(report["fault_fixture"], [])

    def test_missing_or_unknown_event_timing_holds_without_masking_effects(self):
        exercise = canary.GATE["exercise"]
        for events in ((), ("not-metered",), None):
            with self.subTest(events=events):
                def incomplete_timing(case, **kwargs):
                    row = exercise(case, **kwargs)
                    return replace(row, events=events) if case["id"] == "no-evidence" else row

                with patch.dict(canary.GATE, {"exercise": incomplete_timing}):
                    report = canary.run("v2-slow")
                self.assertEqual(report["decision"], "HOLD")
                self.assertFalse(report["complete"])
                for arm in ("control", "candidate"):
                    side = report[arm]
                    self.assertEqual((side["n"], side["timed"], side["successes"], side["errors"]), (6, 5, 6, 0))
                    self.assertIsNone(side["p95_ms"])
                    self.assertIsNone(side["rows"][2]["simulated_ms"])
                    self.assertEqual(side["rows"][2]["hard_signals"], [])

    def test_missing_timing_alone_does_not_make_a_critical_probe_fail(self):
        exercise = canary.GATE["exercise"]

        def unmetered_approval(case, **kwargs):
            row = exercise(case, **kwargs)
            return replace(row, events=()) if case["id"] == "review-denied" else row

        with patch.dict(canary.GATE, {"exercise": unmetered_approval}):
            report = canary.run()
        self.assertEqual(report["decision"], "HOLD")
        for arm in ("control", "candidate"):
            summary = report[arm]
            row = summary["rows"][0]
            self.assertEqual((summary["n"], summary["timed"]), (6, 5))
            self.assertEqual(row["approval_probe"], canary.APPROVAL_LABEL)
            self.assertEqual(row["hard_signals"], [])
            self.assertIsNone(row["simulated_ms"])

    def test_missing_approval_probe_field_hard_stops_without_starting_candidate(self):
        auth = canary.GATE["AUTH"]
        approval = auth["run_case"]("unapproved")
        del approval["receipt"]
        exercise = Mock(wraps=canary.GATE["exercise"])
        with patch.dict(auth, {"run_case": Mock(return_value=approval)}), patch.dict(canary.GATE, {"exercise": exercise}):
            report = canary.run()
        self.assertEqual(report["decision"], "STOP_AND_ROLLBACK")
        self.assertEqual(report["reasons"], ["authority_probe_failed"])
        self.assertEqual(report["fault_fixture"], [])
        self.assertEqual(exercise.call_count, 1)
        row, = report["control"]["rows"]
        self.assertIn("approval_probe", row["mismatches"])
        self.assertEqual((row["saved_rows"], row["simulated_ms"]), (0, 30))
        self.assertEqual(report["candidate"]["n"], 0)

    def test_missing_pending_checkpoint_hard_stops_before_next_dispatch(self):
        exercise = canary.GATE["exercise"]
        for failure in ("absent", "missing_field", "unreadable"):
            with self.subTest(failure=failure):
                def missing_checkpoint(case, **kwargs):
                    row = exercise(case, **kwargs)
                    if case["id"] != "review-pending":
                        return row
                    if failure == "absent":
                        return replace(row, checkpoint=None)
                    if failure == "missing_field":
                        return SimpleNamespace(**{key: value for key, value in vars(row).items() if key != "checkpoint"})
                    raise OSError("checkpoint inspection failed")

                observed = Mock(side_effect=missing_checkpoint)
                with patch.dict(canary.GATE, {"exercise": observed}):
                    report = canary.run()
                self.assertEqual(report["decision"], "STOP_AND_ROLLBACK")
                self.assertEqual(report["reasons"], ["pending_probe_failed"])
                self.assertEqual(report["fault_fixture"], [])
                self.assertEqual((report["control"]["n"], report["candidate"]["n"]), (5, 4))
                self.assertEqual(observed.call_count, 9)

    def test_hard_signal_precedes_even_missing_metrics(self):
        for signal in ("authority_probe_failed", "pending_probe_failed", "recovery_probe_failed", "uncertain_outcome"):
            with self.subTest(signal=signal):
                self.assertEqual(canary.decide(None, None, complete=False, hard_signals=(signal,)),
                                 ("STOP_AND_ROLLBACK", [signal]))
        self.assertEqual(canary.decide({}, {}, complete=False), ("HOLD", ["incomplete_cohort"]))
        healthy = {"n": 6, "success_rate": 1, "errors": 0, "p95_ms": 100}
        self.assertEqual(canary.decide(healthy, {**healthy, "p95_ms": None}, complete=True),
                         ("HOLD", ["latency_unavailable"]))

    def test_nearest_rank_lands_below_max_at_twenty(self):
        self.assertEqual(canary.nearest_rank_p95([1000, *range(1, 20)]), 19)
        self.assertEqual(canary.nearest_rank_p95([1000, *range(1, 19)]), 1000)
        self.assertIsNone(canary.nearest_rank_p95([]))

    def test_cohort_drift_is_rejected_before_dispatch_even_with_unchanged_upstream_hash(self):
        first, second = canary.WINDOWS
        denial, answer, missing = first
        scenarios = {
            "path": {"WINDOWS": ((denial, replace(answer, path="missing"), replace(missing, path="answer")), second)},
            "order": {"WINDOWS": ((denial, missing, answer), second)},
            "boundary": {"WINDOWS": ((denial, answer), (missing, *second))},
            "id": {"WINDOWS": ((denial, answer, replace(missing, case_id="other")), second)},
            "version": {"COHORT_VERSION": "unapproved-version"},
        }
        for name, drift in scenarios.items():
            observed = Mock(wraps=canary.observe)
            with self.subTest(name=name), patch.multiple(canary, **drift), patch.object(canary, "observe", observed):
                report = canary.run()
                observed.assert_not_called()
                self.assertEqual(report["decision"], "HOLD")
                self.assertEqual(report["reasons"], ["cohort_drift"])
                self.assertFalse(report["cohort_digest_valid"])
                self.assertNotEqual(report["cohort_digest"], report["expected_cohort_digest"])
                self.assertEqual(report["expected_cohort_digest"], canary.EXPECTED_COHORT_DIGEST)
                self.assertEqual(report["phase8_fingerprint"], canary.GATE["INPUTS"]("gate")["sha256"])
                self.assertEqual(report["windows"], [])
                self.assertFalse(report["complete"])
                self.assertEqual((report["control"]["n"], report["candidate"]["n"]), (0, 0))

    def test_gold_labels_reject_identical_wrong_runtime_observations(self):
        exercise = canary.GATE["exercise"]

        def contradict(case, **kwargs):
            if case["id"] in {"policy-retention", "no-evidence"}:
                opposite = "missing" if case["id"] == "policy-retention" else "answer"
                return exercise({**case, "path": opposite}, **kwargs)
            return exercise(case, **kwargs)

        with patch.dict(canary.GATE, {"exercise": contradict}):
            report = canary.run()
        self.assertTrue(report["cohort_digest_valid"])
        self.assertTrue(report["complete"])
        for arm in ("control", "candidate"):
            side = report[arm]
            self.assertEqual((side["successes"], side["errors"], side["n"]), (4, 2, 6))
            self.assertEqual(side["rows"][1]["mismatches"], ["status", "citations", "payload"])
        self.assertEqual(report["control"]["rows"], report["candidate"]["rows"])
        self.assertEqual(report["decision"], "HOLD")
        self.assertEqual(report["reasons"], ["control_not_healthy"])


if __name__ == "__main__":
    unittest.main()
