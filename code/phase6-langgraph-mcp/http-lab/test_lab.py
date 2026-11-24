"""Run from the repo root: python -I -X utf8 code/phase6-langgraph-mcp/http-lab/test_lab.py"""
import runpy
import unittest
from pathlib import Path


lab = runpy.run_path(str(Path(__file__).with_name("main.py")))


class TransportTests(unittest.TestCase):
    def test_json_and_post_sse_return_the_same_evidence(self):
        with lab["local_lab"]() as (client, state):
            args = {"source_id": "KB-01"}
            plain = client.post(lab["rpc"](1, "tools/call", name="read_evidence", arguments=args))
            stream = client.post(lab["rpc"](2, "tools/call", name="read_evidence", arguments=args,
                                            progress="read-2"))
            self.assertEqual((plain.status, plain.media_type), (200, "application/json"))
            self.assertEqual((stream.status, stream.media_type), (200, "text/event-stream"))
            self.assertEqual(stream.headers.get("X-Accel-Buffering"), "no")
            self.assertEqual(stream.messages[0], {
                "jsonrpc": "2.0", "method": "notifications/progress",
                "params": {"progressToken": "read-2", "progress": 1, "total": 2},
            })
            self.assertEqual(len(stream.messages), 2)
            self.assertEqual((plain.final["id"], stream.final["id"]), (1, 2))
            self.assertEqual(plain.final["result"], stream.final["result"])
            self.assertEqual(stream.final["result"]["structuredContent"], {
                "source_id": "KB-01", "quote": "导出文件生成后保留 7 天。",
            })
            self.assertEqual(state.read_entries, ["KB-01", "KB-01"])

    def test_negotiation_and_bad_headers_stop_before_dispatch(self):
        with lab["local_lab"]() as (client, state):
            args = {"source_id": "KB-01"}
            valid = lab["rpc"](1, "tools/call", name="read_evidence", arguments=args)
            unknown = lab["rpc"](2, "tools/call", name="read_evidence", arguments=args,
                                 version="1900-01-01")
            for header, wrong in (("MCP-Protocol-Version", "1900-01-01"),
                                  ("Mcp-Method", "tools/list"), ("Mcp-Name", "unrelated")):
                for value in (None, wrong):
                    with self.subTest(header=header, value=value):
                        response = client.post(valid, headers={header: value})
                        self.assertEqual((response.status, response.final["error"]["code"]), (400, -32020))
                        self.assertEqual(state.read_entries, [])
            response = client.post(unknown)
            self.assertEqual(response.status, 400)
            self.assertEqual(response.final["error"], {"code": -32022, "message": "Unsupported protocol version",
                                                      "data": {"supported": ["2026-07-28"], "requested": "1900-01-01"}})
            self.assertEqual(state.read_entries, [])
            response = client.post(valid, headers={"mcp-method": "tools/call",
                                                   "mcp-name": "=?base64?cmVhZF9ldmlkZW5jZQ==?="})
            self.assertEqual(response.status, 200)
            self.assertEqual(state.read_entries, ["KB-01"])

    def test_discovery_catalog_and_core_metadata(self):
        with lab["local_lab"]() as (client, state):
            discovery = client.post(lab["rpc"](1, "server/discover")).final["result"]
            self.assertEqual(discovery["supportedVersions"], ["2026-07-28"])
            self.assertEqual(discovery["capabilities"], {"tools": {}})
            request = lab["rpc"](2, "tools/list")
            del request["params"]["_meta"]["io.modelcontextprotocol/clientInfo"]  # Optional.
            catalog = client.post(request).final["result"]
            self.assertEqual((catalog["ttlMs"], catalog["cacheScope"]), (0, "public"))
            self.assertEqual([tool["name"] for tool in catalog["tools"]], ["read_evidence"])
            del request["params"]["_meta"]["io.modelcontextprotocol/clientCapabilities"]
            malformed = client.post(request)
            self.assertEqual((malformed.status, malformed.final["error"]["code"]), (400, -32602))
            request["params"]["_meta"]["io.modelcontextprotocol/clientCapabilities"] = {}
            del request["params"]["_meta"]["io.modelcontextprotocol/protocolVersion"]
            missing_version = client.post(request)
            self.assertEqual((missing_version.status, missing_version.final["error"]["code"]), (400, -32602))
            unsupported = client.post(lab["rpc"](3, "initialize"))
            self.assertEqual((unsupported.status, unsupported.final["error"]["code"]), (404, -32601))
            self.assertEqual(state.read_entries, [])

    def test_origin_checked_and_no_get_or_delete_stream(self):
        with lab["local_lab"]() as (client, state):
            request = lab["rpc"](1, "tools/call", name="read_evidence", arguments={"source_id": "KB-02"})
            self.assertEqual(client.post(request, headers={"Origin": "null"}).status, 403)
            self.assertEqual(client.exchange("GET", headers={"Origin": "null"}).status, 403)
            for verb in ("GET", "DELETE"):
                response = client.exchange(verb)
                self.assertEqual((response.status, response.headers.get("Allow")), (405, "POST"))
                self.assertNotIn("Mcp-Session-Id", response.headers)
            self.assertEqual(client.post(request, headers={"Accept": "application/json"}).status, 406)
            self.assertEqual(state.read_entries, [])
            response = client.post(request, headers={"Origin": client.origin})
            self.assertEqual((response.status, state.read_entries), (200, ["KB-02"]))
            self.assertNotIn("Mcp-Session-Id", response.headers)

    def test_unknown_evidence_and_body_limit_do_not_enter_the_tool(self):
        with lab["local_lab"]() as (client, state):
            request = lab["rpc"](1, "tools/call", name="read_evidence", arguments={"source_id": "KB-99"})
            response = client.post(request)
            self.assertTrue(response.final["result"]["isError"])
            self.assertEqual(response.final["result"]["structuredContent"], {"status": "unknown_evidence"})
            response = client.exchange("POST", b" " * 8193, {"Content-Type": "application/json"})
            self.assertEqual(response.status, 413)
            self.assertEqual(state.read_entries, [])


class AuthorityTests(unittest.TestCase):
    def setUp(self):
        self.actor = lab["Actor"]("team-a", "u1")
        self.draft = lab["StagedDraft"](self.actor, "case-72", 2, "Training draft")
        self.approved = lab["Approval"]("save_training_draft", self.draft)

    def call(self, client, bearer="fixture-02", **changes):
        params = dict(self.draft.arguments(), **changes)
        return client.post(lab["rpc"](8, "tools/call", name="save_training_draft", arguments=params),
                           bearer=bearer)

    def test_missing_wrong_audience_and_scope_do_not_enter_save(self):
        host = lab["HostContext"](self.actor, self.draft, self.approved)
        with lab["local_lab"](host) as (client, state):
            for bearer, status, challenge in (
                (None, 401, "Bearer"),
                ("not-a-fixture", 401, 'Bearer error="invalid_token"'),
                ("fixture-03", 401, 'Bearer error="invalid_token"'),
                ("fixture-01", 403, 'Bearer error="insufficient_scope", scope="draft:save"'),
            ):
                with self.subTest(bearer=bearer):
                    response = self.call(client, bearer)
                    self.assertEqual((response.status, response.headers["WWW-Authenticate"]), (status, challenge))
                    self.assertEqual(response.messages, ())
                    self.assertEqual((state.save_entries, state.saved, state.read_entries), (0, [], []))
            read = client.post(lab["rpc"](9, "tools/call", name="read_evidence",
                                          arguments={"source_id": "KB-01"}), bearer="fixture-01")
            self.assertFalse(read.final["result"]["isError"])
            self.assertEqual((state.read_entries, state.save_entries), (["KB-01"], 0))
            saved = self.call(client)
            self.assertEqual(saved.status, 200)
            self.assertFalse(saved.final["result"]["isError"])
            self.assertEqual(saved.final["result"]["structuredContent"],
                             {"status": "saved", "draft_id": "case-72", "revision": 2})
            self.assertEqual((state.save_entries, state.saved), (1, [self.draft]))
            self.assertEqual(self.call(client, "fixture-01").status, 403)
            self.assertEqual((state.save_entries, state.saved), (1, [self.draft]))

    def test_known_tool_and_write_scope_do_not_create_a_missing_draft(self):
        with lab["local_lab"](lab["HostContext"](self.actor)) as (client, state):
            catalog = client.post(lab["rpc"](1, "tools/list"), bearer="fixture-01")
            self.assertEqual(catalog.status, 200)
            self.assertIn("save_training_draft", [tool["name"] for tool in catalog.final["result"]["tools"]])
            denied = self.call(client)
            self.assertEqual(denied.status, 200)
            self.assertTrue(denied.final["result"]["isError"])
            self.assertEqual(denied.final["result"]["structuredContent"], {"status": "not_available"})
            self.assertEqual((state.save_entries, state.saved), (0, []))

    def test_identity_intent_and_approval_are_independent_gates(self):
        other_tenant = lab["Actor"]("team-b", "u1")
        other_user = lab["Actor"]("team-a", "u2")
        old = lab["StagedDraft"](self.actor, "case-72", 1, "Training draft")
        cases = (
            (other_tenant, self.approved, {}, "not_available"),
            (other_user, self.approved, {}, "not_available"),
            (self.actor, self.approved, {"draft_id": "case-73"}, "not_available"),
            (self.actor, self.approved, {"text": "Changed draft"}, "intent_changed"),
            (self.actor, self.approved, {"revision": 1}, "intent_changed"),
            (self.actor, self.approved, {"approved": True}, "invalid_arguments"),
            (self.actor, None, {}, "approval_required"),
            (self.actor, lab["Approval"]("preview", self.draft), {}, "approval_required"),
            (self.actor, lab["Approval"]("save_training_draft", old), {}, "approval_required"),
        )
        for actor, approval, changes, denial in cases:
            with self.subTest(denial=denial, actor=actor, changes=changes):
                with lab["local_lab"](lab["HostContext"](actor, self.draft, approval)) as (client, state):
                    response = self.call(client, **changes)
                    self.assertEqual(response.status, 200)
                    self.assertNotIn("WWW-Authenticate", response.headers)
                    self.assertTrue(response.final["result"]["isError"])
                    self.assertEqual(response.final["result"]["structuredContent"], {"status": denial})
                    self.assertEqual((state.save_entries, state.saved), (0, []))


if __name__ == "__main__":
    unittest.main()
