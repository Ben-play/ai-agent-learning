"""Behavior tests for the Phase 8 gate and its local handoff."""

from dataclasses import replace
import json
from pathlib import Path
import runpy
from tempfile import TemporaryDirectory
import unittest

LAB = Path(__file__).resolve().parents[1]
GATE = runpy.run_path(str(LAB / "gate.py"))


class GateTests(unittest.TestCase):
    def test_extra_read_changes_only_synthetic_budget_and_does_not_repeat_write(self):
        normal = GATE["run"]()
        added = GATE["run"]("extra-read")
        self.assertEqual((normal["successes"], normal["total_credits"], normal["p95_ms"]), (6, 49, 100))
        self.assertEqual((added["successes"], added["total_credits"], added["p95_ms"]), (6, 53, 124))
        self.assertEqual(added["blocks"], ["p95_ms"])
        replay = added["by_case"]["lost-response"]
        self.assertEqual((replay["dispatches"], replay["recoveries"], replay["writes"], replay["saved_rows"],
                          replay["replay_writes"], replay["same_receipt"]), (1, 1, 1, 1, 0, True))
        self.assertEqual(replay["events"], ["retrieve", "retrieve", "stage", "approved_call", "recover"])

    def test_extra_recovery_is_hard_failure_even_with_no_extra_insert(self):
        suite = json.loads(GATE["DATA"].read_text(encoding="utf-8"))
        suite["thresholds"]["min_success_rate"] = 0.5
        rows = [GATE["exercise"](case) for case in suite["cases"]]
        rows = [replace(row, recoveries=2) if row.case_id == "lost-response" else row for row in rows]
        result = GATE["evaluate"](suite, rows)
        self.assertEqual(result["hard_failures"], ["lost-response"])
        self.assertEqual(result["blocks"], ["forbidden_or_duplicate_effect"])

    def test_handoff_compares_gate_inputs_and_keeps_projection_separate(self):
        handoff = runpy.run_path(str(LAB / "handoff.py"))["run_handoff"]()
        actual = [handoff[k]["report"]["input_fingerprint"] for k in ("baseline", "regression", "restored")]
        self.assertEqual(actual, [handoff["inputs"]["gate"]["sha256"]] * 3)
        self.assertEqual(set(handoff["inputs"]), {"gate", "evaluation", "telemetry", "design", "handoff"})
        self.assertEqual(handoff["trace_sample"]["origin"], "separate-local-telemetry-fixture")
        self.assertNotEqual(handoff["trace_sample"]["projection_version"], handoff["trace_sample"]["otel_genai_version"])

    def test_fingerprints_change_with_content_not_root_or_line_endings(self):
        fingerprint = runpy.run_path(str(LAB / "provenance.py"))["fingerprint"]
        with TemporaryDirectory() as a, TemporaryDirectory() as b:
            one, two = Path(a), Path(b)
            (one / "fixture.txt").write_bytes(b"case=v1\r\n")
            (two / "fixture.txt").write_bytes(b"case=v1\n")
            first = fingerprint(one, ["fixture.txt"])
            self.assertEqual(fingerprint(two, ["fixture.txt"]), first)
            (two / "fixture.txt").write_bytes(b"case=v2\n")
            self.assertNotEqual(fingerprint(two, ["fixture.txt"])["sha256"], first["sha256"])


if __name__ == "__main__":
    unittest.main()
