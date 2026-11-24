import json
import unittest
from unittest.mock import patch

from main import fixture_adapter, run

QUESTION = "导出文件保留多久？"


class EvidenceLabTests(unittest.TestCase):
    def test_answer_quotes_supplied_sources_without_drafting(self):
        result = run(QUESTION)

        self.assertEqual(result["status"], "answered")
        self.assertEqual(result["selected_ids"], ["KB-01", "KB-02"])
        self.assertIn("导出文件生成后保留 7 天。", result["answer"])
        self.assertEqual(result["citations"][0], {
            "source_id": "KB-01", "quote": "导出文件生成后保留 7 天。",
        })
        self.assertIsNone(result["draft"])
        self.assertIsNone(result["skill"])

    def test_explicit_draft_intent_selects_skill_and_returns_unsent_draft(self):
        result = run(QUESTION, intent="draft")

        self.assertEqual(result["status"], "drafted")
        self.assertEqual(result["skill"], "ticket-draft")
        self.assertIn("导出文件生成后保留 7 天。", result["draft"]["body"])
        self.assertEqual(result["draft"]["source_ids"], ["KB-01", "KB-02"])

    def test_no_evidence_asks_for_sources_and_does_not_call_adapter(self):
        def unexpected_call(_payload):
            self.fail("证据为空时不应请求适配器")

        result = run("导出文件能否恢复？", intent="draft", adapter=unexpected_call)

        self.assertEqual(result["status"], "needs_evidence")
        self.assertIn("请补充", result["message"])
        self.assertEqual(result["citations"], [])
        self.assertIsNone(result["answer"])
        self.assertIsNone(result["draft"])

    def test_budget_keeps_primary_source_at_the_byte_boundary(self):
        baseline = run(QUESTION)
        exact = baseline["usage"]["input_bytes"]
        self.assertEqual(run(QUESTION, input_limit=exact)["selected_ids"], ["KB-01", "KB-02"])

        tighter = run(QUESTION, input_limit=exact - 1)
        self.assertEqual(tighter["status"], "answered")
        self.assertEqual(tighter["selected_ids"], ["KB-01"])
        self.assertLessEqual(tighter["usage"]["input_bytes"], exact - 1)

    def test_budget_rejects_unapproved_limits_and_stops_when_primary_cannot_fit(self):
        cases = (({"input_limit": 641}, "invalid_request"),
                 ({"output_limit": True}, "invalid_request"),
                 ({"input_limit": 1}, "budget_exceeded"))
        for options, status in cases:
            with self.subTest(options=options):
                result = run(QUESTION, **options)
                self.assertEqual(result["status"], status)
                self.assertEqual(result["usage"], {"input_bytes": 0, "output_bytes": 0, "adapter_calls": 0})
                self.assertIsNone(result["answer"])

    def test_oversized_response_is_counted_but_not_returned(self):
        result = run(QUESTION, intent="draft", output_limit=1)

        self.assertEqual(result["status"], "budget_exceeded")
        self.assertGreater(result["usage"]["output_bytes"], 1)
        self.assertEqual(result["usage"]["adapter_calls"], 1)
        self.assertIsNone(result["draft"])

    def test_prompt_snapshots_are_used_and_comparable_on_the_same_input(self):
        requests = []

        def capture(payload):
            reply = fixture_adapter(payload)
            requests.append((payload, reply))
            return reply

        v1 = run(QUESTION, version="v1", adapter=capture)
        v2 = run(QUESTION, version="v2", adapter=capture)

        self.assertEqual([v1["prompt_version"], v2["prompt_version"]], ["v1", "v2"])
        first, second = (json.loads(payload) for payload, _ in requests)
        self.assertNotEqual(first["prompt"], second["prompt"])
        self.assertEqual(first["evidence"], second["evidence"])
        self.assertEqual(v1["answer"], v2["answer"])
        for result, (payload, reply) in zip((v1, v2), requests):
            self.assertEqual(result["usage"], {"input_bytes": len(payload.encode("utf-8")),
                                               "output_bytes": len(reply.encode("utf-8")), "adapter_calls": 1})
        self.assertLess(v1["usage"]["input_bytes"], v2["usage"]["input_bytes"])
        self.assertEqual(run(QUESTION, version="missing")["status"], "invalid_request")

    def test_invalid_links_fail_closed_even_for_drafts(self):
        tight_limit = run(QUESTION)["usage"]["input_bytes"] - 1
        for citation in (
            {"source_id": "KB-03", "quote": "同步任务每天 02:00 运行。"},  # 不相关但存在
            {"source_id": "KB-02", "quote": "超过保留期需重新发起导出。"},  # 相关但未入选
            {"source_id": "KB-99", "quote": "导出文件生成后保留 7 天。"},
            {"source_id": "KB-01", "quote": "导出文件生成后保留 30 天。"},
        ):
            with self.subTest(citation=citation):
                def forged_reply(_payload):
                    return json.dumps({"status": "completed", "citations": [citation]}, ensure_ascii=False)

                result = run(QUESTION, intent="draft", input_limit=tight_limit, adapter=forged_reply)
                self.assertEqual(result["selected_ids"], ["KB-01"])
                self.assertEqual(result["status"], "invalid_response")
                self.assertEqual(result["citations"], [])
                self.assertIsNone(result["answer"])
                self.assertIsNone(result["draft"])

    def test_supplemental_only_citation_is_rejected_even_when_both_sources_are_sent(self):
        requests = []
        supplemental = {"source_id": "KB-02", "quote": "超过保留期需重新发起导出。"}
        raw = json.dumps({"status": "completed", "citations": [supplemental]}, ensure_ascii=False)

        def supplemental_only(payload):
            requests.append(json.loads(payload)["evidence"])
            return raw

        for intent in ("answer", "draft"):
            with self.subTest(intent=intent):
                result = run(QUESTION, intent=intent, adapter=supplemental_only)
                sent = requests[-1]
                self.assertEqual([row["source_id"] for row in sent], ["KB-01", "KB-02"])
                self.assertIn(supplemental, sent)  # 引用逐字吻合，问题在于漏引主来源。
                self.assertEqual(result["selected_ids"], ["KB-01", "KB-02"])
                self.assertEqual(result["usage"], {
                    "input_bytes": 387, "output_bytes": len(raw.encode("utf-8")), "adapter_calls": 1,
                })
                self.assertEqual(result["status"], "invalid_response")
                self.assertEqual(result["citations"], [])
                self.assertIsNone(result["answer"])
                self.assertIsNone(result["draft"])
                self.assertIsNone(result["skill"])

    def test_primary_only_citation_is_accepted_even_when_both_sources_are_sent(self):
        requests = []
        primary = {"source_id": "KB-01", "quote": "导出文件生成后保留 7 天。"}

        def primary_only(payload):
            requests.append(json.loads(payload)["evidence"])
            return json.dumps({"status": "completed", "citations": [primary]}, ensure_ascii=False)

        for intent, status in (("answer", "answered"), ("draft", "drafted")):
            with self.subTest(intent=intent):
                result = run(QUESTION, intent=intent, adapter=primary_only)
                self.assertEqual([row["source_id"] for row in requests[-1]], ["KB-01", "KB-02"])
                self.assertEqual(result["status"], status)
                self.assertEqual(result["answer"], primary["quote"])
                self.assertEqual(result["citations"], [primary])
                if intent == "draft":
                    self.assertEqual(result["draft"]["body"], primary["quote"])
                    self.assertEqual(result["draft"]["source_ids"], ["KB-01"])
                else:
                    self.assertIsNone(result["draft"])

    def test_noncompleted_or_malformed_response_cannot_leak_a_partial_draft(self):
        citation = {"source_id": "KB-01", "quote": "导出文件生成后保留 7 天。"}
        cases = (
            ('{"status":"refused","citations":[]}', "refused"),
            (json.dumps({"status": "incomplete", "citations": [citation]}, ensure_ascii=False), "incomplete"),
            ('{"status":"pending","citations":[]}', "invalid_response"),
            ('{"status":"completed","citations":[]}', "invalid_response"),
            ('{"status":"refused","status":"completed","citations":[]}', "invalid_response"),
            ("{", "invalid_response"),
            (None, "invalid_response"),
        )
        for raw, status in cases:
            with self.subTest(raw=raw):
                result = run(QUESTION, intent="draft", adapter=lambda _: raw)
                self.assertEqual(result["status"], status)
                self.assertEqual(result["citations"], [])
                self.assertIsNone(result["answer"])
                self.assertIsNone(result["draft"])

    def test_adapter_failure_is_terminal_with_unknown_output_usage(self):
        def unavailable(_payload):
            raise RuntimeError("虚构的适配器故障")

        result = run(QUESTION, adapter=unavailable)
        self.assertEqual(result["status"], "adapter_error")
        self.assertEqual(result["usage"]["adapter_calls"], 1)
        self.assertIsNone(result["usage"]["output_bytes"])
        self.assertIsNone(result["answer"])

    def test_draft_performs_no_external_io_and_send_intent_is_rejected(self):
        # 监测本项目常见的外部 I/O 边界；不是通用沙箱证明。
        with (patch("builtins.open") as open_file, patch("io.open") as io_open,
              patch("os.open") as os_open, patch("socket.socket") as connect,
              patch("sqlite3.connect") as database, patch("subprocess.Popen") as launch):
            draft = run(QUESTION, intent="draft")
            denied = run(QUESTION, intent="send")

        for boundary in (open_file, io_open, os_open, connect, database, launch):
            boundary.assert_not_called()
        self.assertEqual(draft["status"], "drafted")
        self.assertEqual(denied["status"], "invalid_request")
        self.assertIsNone(denied["skill"])
        self.assertIsNone(denied["draft"])
        self.assertEqual(denied["usage"]["adapter_calls"], 0)
