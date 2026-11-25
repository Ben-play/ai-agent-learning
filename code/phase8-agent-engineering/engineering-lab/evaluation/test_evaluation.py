"""Run from a trusted repo with Python 3.11+: python -I -X utf8 <this file>."""

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import runpy
from tempfile import TemporaryDirectory
import unittest

E = runpy.run_path(str(Path(__file__).with_name("main.py")))


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.sets = E["load_datasets"]()
        self.acceptance = {task["id"]: task for task in self.sets["acceptance"]}

    def test_split_barriers_are_independent(self):
        fixtures = E["FIXTURES"]
        dev, acceptance = (json.loads((fixtures / name).read_text(encoding="utf-8"))
                           for name in ("dev.json", "acceptance.json"))
        source = dev["tasks"][0]
        for new_id, family, question, error in (
            (source["id"], "unrelated", "其他问题？", "duplicate ID"),
            ("ACC-RENAMED", source["family"], "每天什么时候同步？", "family overlap"),
            ("ACC-RENAMED", f" {source['family']}　", "每天什么时候同步？", "invalid family"),
            ("ACC-RENAMED", "renamed", "同步任务几点开始 ?", "question overlap"),
        ):
            with self.subTest(error=error), self.assertRaisesRegex(ValueError, error):
                clone = deepcopy(source)
                clone["id"], clone["family"], clone["request"]["question"] = new_id, family, question
                E["validate_splits"](dev, {**acceptance, "tasks": [*acceptance["tasks"], clone]})
        with self.assertRaisesRegex(ValueError, "invalid version"):
            E["validate_splits"](dev, {**acceptance, "dataset_version": "v0"})

    def test_both_splits_repeat_without_state_leakage(self):
        for split, passed in (("dev", 4), ("acceptance", 12)):
            result = E["run_split"](split, repeats=2)
            self.assertTrue(result["passed"])
            self.assertEqual(result["passed_trials"], passed)
            first, second = result["trials"][::2], result["trials"][1::2]
            self.assertEqual([dict(row, trial=2) for row in first], second)
        for invalid in (True, 0, 21):
            with self.assertRaises(ValueError):
                E["run_acceptance"](repeats=invalid)

    def test_citation_locator_quote_and_packet_are_independent(self):
        task = self.acceptance["ACC-HANDOFF-QA"]
        request, expected = task["request"], task["expected"]
        with E["RAG"]["open_demo"]() as db:
            packet = E["make_packet"](db, request)
            answer = E["answer_from_packet"](request, packet)
            first, second = answer.claims
            for citation, evidence, axes in (
                (replace(first.citation, key=("EXPORT-POLICY", 1, "§9")), packet, (False, False, False)),
                (replace(first.citation, quote="导出文件保留 7 天。"), packet, (True, False, False)),
                (first.citation, tuple(c for c in packet if c != first.citation), (True, True, False)),
                (second.citation, packet, (True, True, True)),
                (replace(first.citation, tenant="operations"), packet, (False, False, False)),
            ):
                with self.subTest(citation=citation, axes=axes):
                    actual = E["grade_qa"](db, request, evidence,
                                           replace(answer, claims=(replace(first, citation=citation), second)), expected)
                    row = actual["claims"][0]
                    self.assertEqual(tuple(row[k] for k in ("authorized_locator", "quote_exact", "in_packet")), axes)
                    self.assertTrue(row["value_ok"])
                    self.assertFalse(actual["passed"])

    def test_legacy_draft_requires_all_current_sources_before_preview_and_checkpoint(self):
        request = self.acceptance["ACC-EXPORT-SAVE"]["request"]
        # Lin can read KB-01's mapped policy but not KB-02's mapped renewal guidance.
        for scope in ({"actor": "lin"}, {"tenant": "operations"}):
            with self.subTest(scope=scope):
                observed = E["observe_draft"]({**request, **scope})
                self.assertIsNone(observed["draft"])
                self.assertEqual(observed["steps"], [{"action": "stage", "result": "source_blocked",
                                                      "state": None, "attempts": 0, "rows": 0}])
        # Same document, version, locator and grant; a changed whole quote is still blocked.
        rows = [(tenant, replace(chunk, text="另见导出操作说明。") if chunk.doc_id == "EXPORT-OPS"
                 else chunk, users) for tenant, chunk, users in E["RAG"]["DEMO"]]
        with E["RAG"]["open_demo"](rows=rows) as db:
            observed = E["observe_draft"](request, evidence_store=db)
        self.assertIsNone(observed["draft"])
        self.assertEqual(observed["steps"][0], {"action": "stage", "result": "source_blocked",
                                               "state": None, "attempts": 0, "rows": 0})

    def test_revocation_or_revision_after_pending_blocks_commit(self):
        request = self.acceptance["ACC-EXPORT-SAVE"]["request"]
        key = ("EXPORT-OPS", 1, "§2")
        for change in ("revoke", "revise"):
            with self.subTest(change=change), E["RAG"]["open_demo"]() as db:
                def before_review(index, db):
                    self.assertEqual(index, 1)
                    old = db.source("support", "mei", key)
                    self.assertIsNotNone(old)
                    if change == "revoke":
                        db.revoke("support", "mei", old.doc_id)
                    else:
                        db.replace_document("support", old.doc_id, 2, (replace(old, version=2, locator="§3"),))
                    self.assertIsNone(db.source("support", "mei", key))

                observed = E["observe_draft"](request, evidence_store=db, before_review=before_review)
                self.assertEqual(observed["steps"], [
                    {"action": "stage", "result": "pending", "state": "pending", "attempts": 0, "rows": 0},
                    {"action": "approve", "result": "source_blocked", "state": "pending", "attempts": 0, "rows": 0},
                ])
                self.assertIsNone(observed["draft"])
                self.assertTrue(observed["operation_ok"] and observed["cleanup_ok"])

    def test_postcommit_revocation_withholds_replay_without_rewriting_history(self):
        request = self.acceptance["ACC-EXPORT-REPLAY"]["request"]

        def revoke_after_commit(index, db):
            if index == 2:
                db.revoke("support", "mei", "EXPORT-OPS")

        observed = E["observe_draft"](request, before_review=revoke_after_commit)
        self.assertEqual(observed["steps"][1:], [
            {"action": "approve_lose_reply", "result": "lost_reply", "state": "saved", "attempts": 1, "rows": 1},
            {"action": "approve", "result": "replay_withheld", "state": "saved", "attempts": 0, "rows": 1},
        ])
        self.assertIsNone(observed["draft"])
        self.assertTrue(observed["operation_ok"] and observed["cleanup_ok"])

    def test_denial_is_safe_after_sources_are_revoked(self):
        request = self.acceptance["ACC-EXPORT-DENY"]["request"]
        observed = E["observe_draft"](request, before_review=lambda _, db: db.revoke("support", "mei", "EXPORT-OPS"))
        self.assertEqual([step["result"] for step in observed["steps"]], ["pending", "denied", "denied"])
        self.assertTrue(all(E["no_draft_write"](step) for step in observed["steps"]))
        self.assertIsNone(observed["draft"])

    def test_denied_and_pending_never_attempt_the_insert(self):
        for task_id in ("ACC-EXPORT-DENY", "ACC-EXPORT-PENDING"):
            task = self.acceptance[task_id]
            observed = E["observe_draft"](task["request"])
            self.assertTrue(all(E["no_draft_write"](step) for step in observed["steps"]))
            self.assertTrue(E["grade_draft"](observed, task["expected"])["passed"])

    def test_rollback_counts_real_insert_and_cleans_up(self):
        task = self.acceptance["ACC-EXPORT-SAVE"]
        with TemporaryDirectory() as tmp:
            for _ in range(2):
                observed = E["observe_draft"](task["request"], block_draft_insert=True, temp_parent=tmp)
                self.assertEqual(list(Path(tmp).iterdir()), [])
                self.assertTrue(observed["cleanup_ok"])
                self.assertEqual(observed["steps"][1], {"action": "approve", "result": "insert_blocked",
                                                       "state": "pending", "attempts": 1, "rows": 0})
                self.assertFalse(E["no_draft_write"](observed["steps"][1]))
                self.assertFalse(E["grade_draft"](observed, task["expected"])["passed"])
                stage, insert = observed["steps"]
                compare = dict(task["expected"], steps=[stage, dict(insert, attempts=0)])
                self.assertEqual(E["grade_draft"](observed, compare)["failures"], ["step_1.attempts"])

    def test_calibration_checks_labels_and_empty_denominators(self):
        report = E["run_calibration"]()
        self.assertEqual([report["support"][k] for k in ("TP", "TN", "FP", "FN")], [3, 1, 1, 1])
        self.assertEqual([report["completeness"][k] for k in ("TP", "TN", "FP", "FN")], [3, 2, 1, 1])
        calc = E["calibrate"]
        actual = calc([{"id": "x", "support": "uncertain"}], [{"id": "x", "support": "abstain"}], "support")
        self.assertEqual((actual["coverage"], actual["agreement"], actual["disagreement_rate"]), (None,) * 3)
        self.assertEqual((actual["uncertain"], actual["abstained"], actual["known_abstained"]), (["x"], ["x"], []))
        with self.assertRaisesRegex(ValueError, "ID sets differ"):
            calc([{"id": "x", "support": "pass"}], [{"id": "y", "support": "pass"}], "support")
        with self.assertRaisesRegex(ValueError, "invalid calibration label"):
            calc([{"id": "x", "support": "pass"}], [{"id": "x", "support": "uncertain"}], "support")

    def test_exact_provenance_not_literal_gold_controls_judge_invocation(self):
        task = self.acceptance["ACC-HANDOFF-QA"]
        request = task["request"]
        with E["RAG"]["open_demo"]() as db:
            packet = E["make_packet"](db, request)
            answer = E["answer_from_packet"](request, packet)
            retention, schedule = answer.claims
            equivalent = replace(answer, claims=(replace(retention, value="一周"),
                                                replace(schedule, value="每天凌晨两点")))
            self.assertFalse(E["grade_qa"](db, request, packet, equivalent, task["expected"])["passed"])
            calls = []

            def judge(**inputs):
                calls.append(inputs)
                return E["scripted_judge"](**inputs)

            for citation, evidence in (
                (replace(retention.citation, key=("EXPORT-POLICY", 1, "§9")), packet),
                (replace(retention.citation, quote="导出文件保留 7 天。"), packet),
                (replace(retention.citation, tenant="operations"), packet),
                (retention.citation, tuple(c for c in packet if c != retention.citation)),
                (retention.citation, (*packet, replace(retention.citation, key=("EXPORT-POLICY", 1, "§9")))),
            ):
                with self.subTest(citation=citation, evidence=evidence):
                    bad = replace(equivalent, claims=(replace(equivalent.claims[0], citation=citation),
                                                      equivalent.claims[1]))
                    result = E["judge_qa"](db, request, evidence, bad, judge=judge)
                    self.assertEqual((result["decision"], result["votes"]), ("blocked", None))
            self.assertEqual(calls, [])
            result = E["judge_qa"](db, request, packet, equivalent, judge=judge)
            self.assertEqual(result["decision"], "pass")
            self.assertEqual(result["votes"], {"support": "pass", "completeness": "pass"})
            self.assertEqual(calls, [{"question": request["question"], "facts": ("retention", "schedule"),
                                      "packet": packet, "answer": equivalent}])

    def test_judge_outcomes_keep_support_and_coverage_separate(self):
        request = self.acceptance["ACC-HANDOFF-QA"]["request"]
        with E["RAG"]["open_demo"]() as db:
            packet = E["make_packet"](db, request)
            answer = E["answer_from_packet"](request, packet)
            retention, schedule = answer.claims
            for claims, decision, votes in (
                ((retention,), "quality_fail", {"support": "pass", "completeness": "fail"}),
                ((replace(retention, value="30 天"), schedule), "quality_fail",
                 {"support": "fail", "completeness": "pass"}),
                ((retention, replace(schedule, value="凌晨稍后")), "review",
                 {"support": "abstain", "completeness": "pass"}),
                ((replace(retention, citation=schedule.citation), schedule), "quality_fail",
                 {"support": "fail", "completeness": "pass"}),
            ):
                with self.subTest(claims=claims):
                    result = E["judge_qa"](db, request, packet, replace(answer, claims=claims))
                    self.assertEqual((result["decision"], result["votes"]), (decision, votes))

    def test_stage_gate_cannot_be_outvoted(self):
        result = E["run_stage_check"]()
        decide = E["quality_decision"]
        self.assertEqual(decide(result["guarded"]["passed"], "pass", "pass"), "blocked")
        self.assertEqual(result["judge"]["bad_citation"]["decision"], "blocked")
        self.assertIsNone(result["judge"]["bad_citation"]["votes"])
        self.assertEqual(result["judge"]["equivalent"]["decision"], "pass")
        self.assertEqual(result["judge"]["calls"], 1)
        for name in ("revoke_before_save", "revise_before_save", "revoke_before_replay"):
            self.assertIsNone(result["draft_boundaries"][name]["draft"])
        self.assertEqual(decide(True, "pass", "abstain"), "review")
        self.assertEqual(decide(True, "pass", "fail"), "quality_fail")
        self.assertEqual(decide(True, "pass", "pass"), "pass")


if __name__ == "__main__":
    unittest.main()
