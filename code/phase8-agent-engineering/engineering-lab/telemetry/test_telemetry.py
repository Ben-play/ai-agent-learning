"""Run: python -I -X utf8 code/phase8-agent-engineering/engineering-lab/telemetry/test_telemetry.py"""

from copy import deepcopy
from pathlib import Path
import runpy
import unittest


lab = runpy.run_path(str(Path(__file__).with_name("lab.py")))
FixedClock, LocalReceiver, run_trial = (
    lab[name] for name in ("FixedClock", "LocalReceiver", "run_trial")
)


class TelemetryTests(unittest.TestCase):
    def test_receiver_gets_one_correlated_trace_with_exact_units(self):
        receiver = LocalReceiver(FixedClock())
        trace_id = run_trial(receiver, task=70, trial=1, trace_key=701)
        self.assertEqual(trace_id, "000000000000000000000000000002bd")
        spans = receiver.read_trace(trace_id, role="trace_reader")
        self.assertEqual([span["name"] for span in spans], [
            "agent.trial", "retrieval", "chat lesson-model", "execute_tool draft_preview",
            "approval.check", "agent.execute", "terminal.snapshot",
        ])
        root, retrieval, model, tool, approval, execution, terminal = spans
        self.assertIsNone(root["parent_span_id"])
        self.assertEqual(len({span["span_id"] for span in spans}), 7)
        self.assertTrue(all(span["trace_id"] == trace_id for span in spans))
        self.assertTrue(all(span["parent_span_id"] == root["span_id"] for span in spans[1:]))
        self.assertEqual({(s["attributes"]["phase8.task_id"], s["attributes"]["phase8.trial_id"])
                          for s in spans}, {("task-70", "trial-1")})
        self.assertEqual([s["start_offset_ms"] for s in spans], [0, 0, 30, 280, 700, 700, 820])
        self.assertEqual([s["duration_s"] for s in spans], [0.82, .03, .25, .02, 0, .12, 0])
        self.assertEqual([s["status"] for s in spans], ["UNSET"] * 7)
        self.assertEqual(retrieval["attributes"]["phase8.retrieved_count"], 1)
        self.assertEqual(model["attributes"]["gen_ai.usage.input_tokens"], 12)
        self.assertEqual(model["attributes"]["gen_ai.usage.output_tokens"], 4)
        self.assertEqual(tool["attributes"]["gen_ai.tool.name"], "draft_preview")
        self.assertEqual(approval["attributes"]["phase8.approval"], "granted")
        self.assertEqual(execution["duration_s"], .12)
        self.assertEqual(terminal["attributes"]["phase8.state"], "succeeded")

    def test_retries_are_separate_and_error_does_not_guess_missing_usage(self):
        receiver = LocalReceiver(FixedClock())
        failed = run_trial(receiver, task=63, trial=4, trace_key=631, usage=(None, None), outcome="failed")
        retried = run_trial(receiver, task=63, trial=5, trace_key=632, usage=(0, 3))
        first = receiver.read_trace(failed, role="trace_reader")
        second = receiver.read_trace(retried, role="trace_reader")
        self.assertNotEqual(failed, retried)
        self.assertEqual([s["name"] for s in first], ["agent.trial", "retrieval", "chat lesson-model",
                                                       "terminal.snapshot"])
        self.assertEqual(first[0]["status"], "ERROR")
        self.assertEqual(first[2]["status"], "ERROR")
        fields = first[2]["attributes"]
        self.assertEqual(fields["error.type"], "synthetic_model_error")
        self.assertNotIn("gen_ai.usage.input_tokens", fields)
        self.assertNotIn("gen_ai.usage.output_tokens", fields)
        self.assertEqual(first[-1]["attributes"]["phase8.state"], "failed")
        self.assertNotIn("error.type", second[2]["attributes"])
        self.assertEqual(second[2]["attributes"]["gen_ai.usage.input_tokens"], 0)
        self.assertEqual(second[2]["attributes"]["gen_ai.usage.output_tokens"], 3)
        self.assertEqual(second[-1]["attributes"]["phase8.state"], "succeeded")
        for rows, trace, trial in ((first, failed, "trial-4"), (second, retried, "trial-5")):
            self.assertTrue(all(row["trace_id"] == trace for row in rows))
            self.assertEqual({row["attributes"]["phase8.trial_id"] for row in rows}, {trial})

    def test_only_allowlisted_values_reach_the_receiver_and_reads_expire(self):
        ingress = []

        class WitnessReceiver(LocalReceiver):
            def receive(self, rows):
                ingress.extend(deepcopy(rows))
                super().receive(rows)

        clock = FixedClock()
        receiver = WitnessReceiver(clock, retention_ms=500)
        trace = run_trial(receiver, task=71, trial=1, trace_key=711, usage=("TOKEN_COUNT_CANARY", False),
                          extra_fields={"credential": "CREDENTIAL_CANARY", "phase8.task_id": "TASK_CANARY",
                                        "gen_ai.request.model": "MODEL_CANARY", "nested": {"body": "BODY_CANARY"}})
        rows = receiver.read_trace(trace, role="trace_reader")
        # Independent expected records: no use of the emitter's field list or projection function.
        expected_trace = "000000000000000000000000000002c7"
        self.assertEqual(trace, expected_trace)
        expected_steps = (
            ("0000000000000001", None, "agent.trial", 0, .82, {}),
            ("0000000000000002", "0000000000000001", "retrieval", 0, .03,
             {"gen_ai.operation.name": "retrieval", "phase8.retrieved_count": 1}),
            ("0000000000000003", "0000000000000001", "chat lesson-model", 30, .25,
             {"gen_ai.operation.name": "chat", "gen_ai.provider.name": "synthetic_fixture",
              "gen_ai.request.model": "lesson-model"}),
            ("0000000000000004", "0000000000000001", "execute_tool draft_preview", 280, .02,
             {"gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": "draft_preview",
              "gen_ai.tool.type": "function"}),
            ("0000000000000005", "0000000000000001", "approval.check", 700, 0,
             {"phase8.approval": "granted"}),
            ("0000000000000006", "0000000000000001", "agent.execute", 700, .12, {}),
            ("0000000000000007", "0000000000000001", "terminal.snapshot", 820, 0,
             {"phase8.state": "succeeded", "phase8.state_since_ms": 820}),
        )
        expected = tuple({
            "trace_id": expected_trace, "span_id": span, "parent_span_id": parent, "name": name,
            "kind": "INTERNAL", "start_offset_ms": offset, "duration_s": duration, "status": "UNSET",
            "attributes": {"phase8.task_id": "task-71", "phase8.trial_id": "trial-1", **attrs},
        } for span, parent, name, offset, duration, attrs in expected_steps)
        for marker in ("CANARY", "SYNTHETIC QUERY", "SYNTHETIC EVIDENCE", "SYNTHETIC PROMPT",
                       "SYNTHETIC REPLY", "SYNTHETIC DRAFT", "SYNTHETIC PREVIEW"):
            self.assertNotIn(marker, repr(ingress))
        self.assertEqual(tuple(ingress), expected)
        self.assertEqual(rows, expected)
        with self.assertRaises(PermissionError):
            receiver.read_trace(trace, role="support")
        clock.advance(499)
        self.assertEqual(receiver.read_trace(trace, role="trace_reader"), rows)
        clock.advance(1)
        self.assertEqual(receiver.purge(), 1)
        self.assertEqual(receiver.read_trace(trace, role="trace_reader"), ())
        self.assertEqual(receiver.purge(), 0)

    def test_handoff_summary_retains_only_versioned_diagnostic_fields(self):
        clock = FixedClock()
        receiver = LocalReceiver(clock, retention_ms=500)
        trace = run_trial(receiver, task=79, trial=1, trace_key=791,
                          extra_fields={"credential": "SUMMARY_CANARY"})
        summarize_trace = lab["summarize_trace"]
        self.assertEqual(summarize_trace(receiver, trace, role="trace_reader"), {
            "summary_version": "telemetry-summary-v1",
            "projection_version": "telemetry-projection-v1",
            "otel_genai_version": "v0.1.0",
            "origin": "separate-local-telemetry-fixture",
            "trace_id": "00000000000000000000000000000317",
            "task_id": "task-79", "trial_id": "trial-1", "terminal": "succeeded",
            "spans": [
                {"name": "agent.trial", "duration_s": .82},
                {"name": "retrieval", "duration_s": .03},
                {"name": "chat lesson-model", "duration_s": .25},
                {"name": "execute_tool draft_preview", "duration_s": .02},
                {"name": "approval.check", "duration_s": 0},
                {"name": "agent.execute", "duration_s": .12},
                {"name": "terminal.snapshot", "duration_s": 0},
            ],
        })
        with self.assertRaises(PermissionError):
            summarize_trace(receiver, trace, role="support")
        clock.advance(500)
        with self.assertRaisesRegex(ValueError, "trace is missing or expired"):
            summarize_trace(receiver, trace, role="trace_reader")

    def test_waiting_age_never_triggers_execution_timeout(self):
        alert = lab["evaluate_alert"]
        clock = FixedClock()
        receiver = LocalReceiver(clock)
        waiting = run_trial(receiver, task=71, trial=5, trace_key=715, outcome="waiting_approval")
        active = run_trial(receiver, task=71, trial=6, trace_key=716, outcome="executing")

        def evaluate(trace_id):
            return alert(receiver, trace_id, execution_budget_ms=200, approval_sla_ms=1000)

        self.assertEqual(evaluate(waiting), {"signal": None, "state": "waiting_approval", "age_ms": 700})
        clock.advance(199)
        self.assertEqual(evaluate(active), {"signal": None, "state": "executing", "age_ms": 199})
        clock.advance(1)
        self.assertEqual(evaluate(active), {"signal": "execution_timeout", "state": "executing", "age_ms": 200})
        self.assertEqual(evaluate(waiting), {"signal": None, "state": "waiting_approval", "age_ms": 900})
        clock.advance(100)
        self.assertEqual(evaluate(waiting), {"signal": "approval_sla", "state": "waiting_approval", "age_ms": 1000})
        self.assertEqual(evaluate("missing"), {"signal": "trace_missing", "state": None, "age_ms": None})


if __name__ == "__main__":
    unittest.main()
