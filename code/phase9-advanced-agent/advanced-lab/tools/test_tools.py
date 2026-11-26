"""Independent acceptance, permission, typing and bounded-result checks for L81."""

from dataclasses import replace
import json
from pathlib import Path
import runpy
import unittest
from unittest.mock import patch

lab = runpy.run_path(str(Path(__file__).with_name("main.py")))


class ToolTests(unittest.TestCase):
    def test_fixed_cohort_and_full_context(self):
        self.assertEqual(lab["COHORT_VERSION"], "phase9-tools/v1")
        for name, hits, reads, size, blocked in (
            ("small", 2, 2, 1248, ("policy-and-sync", "duty")),
            ("all-authorized", 4, 4, 4838, ()),
            ("lazy", 4, 4, 2483, ()),
        ):
            with self.subTest(name=name):
                rows = lab["replay"](name)
                self.assertEqual(rows, lab["replay"](name))
                report = lab["compare"](rows, strategy=name)
                self.assertEqual((report.candidate_hits, report.expected_candidates, report.read_calls,
                                  report.context_bytes, report.ineligible_tasks), (hits, 4, reads, size, blocked))
                self.assertEqual(report.manifest_errors, ())
                self.assertEqual(report.eligible, not blocked)
                for row in rows:
                    payload = json.loads(row.context)
                    self.assertEqual(set(payload), {"manifest", "results"})
                    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
                    self.assertEqual(row.context, canonical.encode("utf-8"))
                    self.assertGreater(row.context_bytes, len(canonical))
                    self.assertNotIn(b"read_ops_retention", row.context)
                    self.assertEqual(len(payload["results"]), len(row.selected))
        routine, paired, _ = lab["replay"]("lazy")
        self.assertEqual([item["type"] for item in json.loads(paired.context)["manifest"]],
                         ["definitions", "discovery", "discovery_result", "definitions", "discovery_result", "definitions"])
        self.assertEqual(routine.records, (lab["Record"]("support", "EXPORT-POLICY", 1, "§1", "导出文件生成后保留 7 天。"),))
        self.assertEqual(tuple(lab["replay"](name)[0].context_bytes for name in lab["STRATEGIES"]),
                         (456, 1564, 677))
        tail = lab["replay"]("lazy")[1:]
        damaged = replace(routine, records=(replace(routine.records[0], version=2),))
        report = lab["compare"]((damaged, *tail), strategy="lazy")
        self.assertEqual((report.ineligible_tasks, report.manifest_errors), (("routine",), ()))
        payload = json.loads(routine.context)
        payload["results"][0]["records"][0].pop("locator")
        damaged = replace(routine, context=lab["serialize"](payload))
        report = lab["compare"]((damaged, *tail), strategy="lazy")
        self.assertEqual((report.ineligible_tasks, report.manifest_errors), (("routine",), ()))
        self.assertEqual(lab["ranked"](("read_retention_notes", "read_retention"), "retention"),
                         ("read_retention", "read_retention_notes"))

    def test_omitted_manifest_counts_bytes_but_blocks_an_otherwise_correct_task(self):
        routine, paired, duty = lab["replay"]("lazy")
        payload = json.loads(paired.context)
        del payload["manifest"]
        damaged = replace(paired, context=lab["serialize"](payload))

        report = lab["compare"]((routine, damaged, duty), strategy="lazy")

        self.assertEqual((report.candidate_hits, report.expected_candidates, report.read_calls), (4, 4, 4))
        self.assertEqual(report.context_bytes, len(routine.context) + len(damaged.context) + len(duty.context))
        self.assertLess(report.context_bytes, 2483)
        self.assertEqual(report.manifest_errors, ("policy-and-sync",))
        self.assertEqual(report.ineligible_tasks, ("policy-and-sync",))
        self.assertFalse(report.eligible)

    def test_lazy_manifest_requires_exact_definitions_and_discovery_in_order(self):
        rows = lab["replay"]("lazy")
        for case in ("description", "schema", "integer as float", "boolean as integer", "discovery entry",
                     "discovery description", "topic", "candidate missing", "candidate wrong", "entry order", "unlisted name"):
            with self.subTest(case=case):
                payload = json.loads(rows[1].context)
                manifest = payload["manifest"]
                definition = manifest[3]["tools"][0]
                match case:
                    case "description":
                        definition["description"] = "查留存。"
                    case "schema":
                        del definition["input_schema"]["required"]
                    case "integer as float":
                        definition["input_schema"]["properties"]["limit"]["minimum"] = 1.0
                    case "boolean as integer":
                        definition["input_schema"]["additionalProperties"] = 0
                    case "discovery entry":
                        del manifest[2]
                    case "discovery description":
                        manifest[1]["description"] = "查已授权工具。"
                    case "topic":
                        manifest[2]["topic"] = "schedule"
                    case "candidate missing":
                        manifest[2]["candidates"] = []
                    case "candidate wrong":
                        manifest[2]["candidates"] = ["read_retention_notes"]
                    case "entry order":
                        manifest[2], manifest[3] = manifest[3], manifest[2]
                    case "unlisted name":
                        definition["name"] = "unlisted_training_tool"
                damaged = replace(rows[1], context=lab["serialize"](payload))
                report = lab["compare"]((rows[0], damaged, rows[2]), strategy="lazy")
                self.assertEqual((report.manifest_errors, report.ineligible_tasks),
                                 (("policy-and-sync",), ("policy-and-sync",)))
                self.assertEqual((report.candidate_hits, report.expected_candidates, report.read_calls), (4, 4, 4))

    def test_all_authorized_requires_every_definition_in_order(self):
        rows = lab["replay"]("all-authorized")
        for changed in ("omitted", "reordered"):
            with self.subTest(changed=changed):
                payload = json.loads(rows[0].context)
                tools = payload["manifest"][0]["tools"]
                if changed == "omitted":
                    del tools[0]  # The routine task still used the correct retention tool.
                else:
                    tools.reverse()
                damaged = replace(rows[0], context=lab["serialize"](payload))
                report = lab["compare"]((damaged, *rows[1:]), strategy="all-authorized")
                self.assertEqual((report.manifest_errors, report.ineligible_tasks), (("routine",), ("routine",)))
                expected_bytes = 4838 - len(rows[0].context) + len(damaged.context)
                self.assertEqual(report.context_bytes, expected_bytes)
                self.assertEqual(report.context_bytes < 4838, changed == "omitted")

    def test_compare_uses_only_the_caller_chosen_strategy(self):
        rows = lab["replay"]("all-authorized")
        with self.assertRaises(TypeError):
            lab["compare"](rows)
        with self.assertRaisesRegex(ValueError, "unknown strategy"):
            lab["compare"](rows, strategy="unknown")
        for other in ("small", "lazy"):
            with self.subTest(strategy=other):
                report = lab["compare"](rows, strategy=other)
                self.assertEqual((report.manifest_errors, report.ineligible_tasks),
                                 (("routine", "policy-and-sync", "duty"),) * 2)
                self.assertEqual((report.candidate_hits, report.read_calls, report.context_bytes), (4, 4, 4838))

    def test_runtime_catalogue_drift_does_not_change_the_expected_manifest(self):
        catalogue = lab["CATALOG"]
        edited = replace(catalogue["read_retention"], description="查留存。")
        before = lab["replay"]("all-authorized")
        with patch.dict(catalogue, {"read_retention": edited}):
            self.assertTrue(lab["compare"](before, strategy="all-authorized").eligible)
            rows = lab["replay"]("all-authorized")
            report = lab["compare"](rows, strategy="all-authorized")
        self.assertEqual((report.candidate_hits, report.read_calls), (4, 4))
        self.assertEqual(report.manifest_errors, ("routine", "policy-and-sync", "duty"))
        self.assertFalse(report.eligible)

    def test_prefilter_and_dispatch_rechecks_current_identity_and_scope(self):
        for change in ("scope", "tenant", "actor"):
            with self.subTest(change=change):
                host = lab["Host"]()
                session = lab["Session"]("lazy", host)
                name = session.select("retention")
                self.assertEqual(name, "read_retention")
                self.assertIn(name, session.visible)
                self.assertIsNone(session.select("read_ops_retention"))
                self.assertNotIn("read_ops_retention", str(session.manifest))
                self.assertEqual(session.dispatch("read_ops_retention", {"limit": 1}), "not_allowed")
                if change == "scope":
                    host.scopes = frozenset({"desk:read"})
                elif change == "tenant":
                    host.principal = lab["OPERATIONS"]
                else:
                    host.principal = lab["Principal"]("support", "lin")
                self.assertEqual(session.dispatch(name, {"limit": 1}), "not_allowed")
                self.assertIsNone(session.select("retention"))
                self.assertEqual((session.reads, session.records), ([], []))
        host = lab["Host"](scopes=frozenset({"desk:read"}))
        for strategy in lab["STRATEGIES"]:
            session = lab["Session"](strategy, host)
            self.assertIsNone(session.select("retention"))
            self.assertNotIn(b"read_retention", session.emitted())
            self.assertEqual(session.dispatch("read_retention", {"limit": 1}), "not_allowed")
            self.assertEqual(session.reads, [])

    def test_typed_validation_precedes_real_reads(self):
        session = lab["Session"]("all-authorized", lab["Host"]())
        name = session.select("retention")
        for invalid in ({}, {"limit": True}, {"limit": 1.0}, {"limit": "1"}, {"limit": 0}, {"limit": 3},
                        {"limit": 1, "tenant": "support"}, [{"limit": 1}]):
            self.assertEqual(session.dispatch(name, invalid), "invalid_arguments")
        self.assertEqual(session.dispatch([], {"limit": 1}), "not_allowed")
        self.assertEqual(session.reads, [])
        self.assertEqual(session.dispatch(name, {"limit": 1}), "ok")
        self.assertEqual(session.reads, ["read_retention"])
        self.assertEqual(session.records[0].text, "导出文件生成后保留 7 天。")

    def test_aggregate_limits_do_not_make_an_incomplete_task_eligible(self):
        for limits in (lab["Limits"](calls=1, rows=2), lab["Limits"](calls=2, rows=1)):
            rows = lab["replay"]("lazy", limits=limits)
            report = lab["compare"](rows, strategy="lazy")
            self.assertEqual((report.candidate_hits, report.read_calls, report.ineligible_tasks), (4, 3, ("policy-and-sync",)))
            self.assertEqual(report.manifest_errors, ())
            self.assertEqual(json.loads(rows[1].context)["results"][-1], {"status": "budget_exhausted"})
        session = lab["Session"]("lazy", lab["Host"](), lab["Limits"](calls=3, rows=2))
        self.assertEqual(session.dispatch(session.select("retention"), {"limit": 2}), "ok")
        self.assertEqual(session.dispatch(session.select("schedule"), {"limit": 1}), "budget_exhausted")
        self.assertEqual(session.reads, ["read_retention"])
        self.assertEqual([r.doc_id for r in session.records], ["EXPORT-POLICY", "EXPORT-OPS"])


if __name__ == "__main__":
    unittest.main()
