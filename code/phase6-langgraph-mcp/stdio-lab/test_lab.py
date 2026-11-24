"""Independent checks of the course CLI, JSON-RPC wire and host gate."""

import asyncio
from contextlib import ExitStack
import json
from pathlib import Path
import runpy
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

LAB = Path(__file__).resolve().with_name("lab.py")
PYTHON = [sys.executable, "-I", "-X", "utf8", str(LAB)]
API = runpy.run_path(str(LAB))
META = {"io.modelcontextprotocol/protocolVersion": "2026-07-28",
        "io.modelcontextprotocol/clientCapabilities": {}}


class StdioLabTests(unittest.TestCase):
    def test_acceptance_cli_prints_only_its_marker(self):
        for mode, marker in (("worked", b"L57 ACCEPTED"), ("transfer", b"L57 TRANSFER PASSED")):
            with self.subTest(mode=mode):
                run = subprocess.run([*PYTHON, mode], capture_output=True, timeout=20, check=True)
                self.assertEqual(run.stdout.splitlines(), [marker])
                self.assertEqual(run.stderr, b"")

    def send(self, *requests):
        lines = b"".join(json.dumps({"jsonrpc": "2.0", "id": index, "method": method, "params": params})
                         .encode("utf-8") + b"\n" for index, (method, params) in enumerate(requests, 1))
        run = subprocess.run([*PYTHON, "--serve"], input=lines, capture_output=True, timeout=10, check=True)
        responses = [json.loads(line) for line in run.stdout.decode("utf-8").splitlines()]
        self.assertEqual([msg["id"] for msg in responses], list(range(1, len(requests) + 1)))
        self.assertTrue(all(msg["jsonrpc"] == "2.0" for msg in responses))
        self.assertTrue(run.stdout.endswith(b"\n"))
        return responses, run.stderr.decode("utf-8").splitlines()

    def test_modern_wire_missing_metadata_does_not_inherit_discovery(self):
        replies, audit = self.send(("server/discover", {"_meta": META}), ("tools/list", {}),
                                   ("tools/list", {"_meta": META}))
        self.assertEqual(replies[0]["result"]["supportedVersions"], ["2026-07-28"])
        self.assertEqual(replies[0]["result"]["capabilities"], {"tools": {}})
        self.assertEqual(replies[1]["error"]["code"], -32602)
        self.assertEqual(replies[2]["result"]["resultType"], "complete")
        self.assertEqual([tool["name"] for tool in replies[2]["result"]["tools"]], ["read_evidence"])
        for successful in (replies[0]["result"], replies[2]["result"]):
            self.assertEqual((successful.get("ttlMs"), successful.get("cacheScope")), (0, "public"))
        self.assertEqual(audit, [])

    def test_mismatch_and_legacy_handshake_are_rejected(self):
        replies, audit = self.send(
            ("server/discover", {"_meta": {**META, "io.modelcontextprotocol/protocolVersion": "2025-11-25"}}),
            ("initialize", {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {}}),
        )
        self.assertEqual(replies[0]["error"]["code"], -32022)
        self.assertEqual(replies[0]["error"]["data"], {"supported": ["2026-07-28"], "requested": "2025-11-25"})
        self.assertEqual(replies[1]["error"]["code"], -32602)
        self.assertEqual(audit, [])

    def test_only_the_valid_call_reaches_evidence(self):
        args = {"scope": "export", "source_id": "KB-01"}
        requests = [("tools/call", {"_meta": META, "name": name, "arguments": values}) for name, values in (
            ("read_evidence", {}), ("read_evidence", {**args, "unused": 0}),
            ("read_evidence", {**args, "source_id": 1}), ("read_evidence", {**args, "source_id": "PICKUP-01"}),
            ("unknown", args), ("read_evidence", []), ("read_evidence", args),
        )]
        replies, audit = self.send(*requests)
        for reply in replies[:4]:
            self.assertTrue(reply["result"]["isError"])
            self.assertNotIn("structuredContent", reply["result"])
        for reply in replies[4:6]:
            self.assertEqual(reply["error"]["code"], -32602)
            self.assertNotIn("result", reply)
        valid = replies[-1]["result"]
        self.assertEqual(valid["structuredContent"], {**args, "excerpt": "导出文件生成后保留 7 天。"})
        self.assertEqual(json.loads(valid["content"][0]["text"]), valid["structuredContent"])
        self.assertEqual(audit, ["evidence-read export KB-01"])

    def test_host_rejects_bad_shape_wrong_scope_and_tool_error(self):
        base = {"scope": "export", "source_id": "KB-01", "excerpt": "合成证据"}
        for evidence in ({**base, "scope": "north-campus"}, {**base, "excerpt": 7},
                         {**base, "excerpt": ""}, {**base, "excerpt": "x" * 121}, {**base, "extra": 1},
                         {**base, "source_id": "KB-02"}, None):
            with self.subTest(evidence=evidence), self.assertRaises(ValueError):
                API["model_evidence"]({"result": {"resultType": "complete", "structuredContent": evidence}},
                                      expected_scope="export", expected_source="KB-01")
        with self.assertRaises(ValueError):
            API["model_evidence"]({"result": {"resultType": "complete", "isError": True, "structuredContent": base}},
                                  expected_scope="export", expected_source="KB-01")

    def test_request_timeout_exits_the_child(self):
        async def run():
            async with API["StdioClient"]() as client:
                # Drop the write in the test. The real child waits on stdin, the host on stdout.
                with patch.object(client.process.stdin, "write"):
                    with self.assertRaisesRegex(TimeoutError, "no complete reply"):
                        await client.request("server/discover")
            self.assertEqual(client.returncode, 0)

        start = time.monotonic()
        asyncio.run(run())
        self.assertLess(time.monotonic() - start, 10)

    def test_child_not_given_eof_is_terminated_and_reaped(self):
        async def run():
            client = API["StdioClient"]()
            with self.assertRaisesRegex(RuntimeError, "forced=True"), ExitStack() as patches:
                async with client:
                    # Withhold EOF during shutdown, leaving the real child waiting for input.
                    patches.enter_context(patch.object(client.process.stdin, "close"))
                    self.assertEqual((await client.request("server/discover"))["id"], 1)
            self.assertIsNotNone(client.returncode)
            self.assertNotEqual(client.returncode, 0)

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
