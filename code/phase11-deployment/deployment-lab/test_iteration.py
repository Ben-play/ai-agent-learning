from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import patch

import iteration as lab


class IterationTests(unittest.TestCase):
    def test_minimum_incident_is_reproduced_without_retaining_raw_evidence(self):
        report = lab.rehearse()
        self.assertEqual(report["incident"], {
            "id": "local-incident-01", "fixture_version": "citation-dev-v1", "case_id": "dev-retention-revoked",
            "observed": "cached_citation_selected_after_revocation", "expected": "handoff_without_citation",
            "containment": "keep_candidate_out_of_release", "scope": "cache_hit_citation_selection_only",
            "review_when": ["authorization_or_document_version_changes", "valid_citations_are_withheld"],
        })
        obs = report["dev"]["baseline"]["observations"][0]
        self.assertEqual(obs, {"case_id": "dev-retention-revoked", "status": "citation_ready", "cache_hit": True,
                               "selected": True, "selection_current": False, "visible_exact": False, "rechecks": 0,
                               "input_matches": True, "lookup_matches": True, "initial_evidence_matches": True,
                               "citation_matches": True})
        tagged = dict(obs, raw_evidence="opaque-note", secret="opaque-credential")
        self.assertEqual(lab.minimize(tagged), report["incident"])
        self.assertIsNone(lab.minimize(dict(obs, selected=False)))
        self.assertNotIn("导出文件生成后保留 7 天。", str(report))

    def test_development_baseline_and_one_change(self):
        report = lab.compare("dev")
        a, b = (report[arm] for arm in ("baseline", "candidate"))
        self.assertEqual(report["fixture_version"], "citation-dev-v1")
        self.assertEqual(a["verdict"], {"n": 3, "passes": 2,
                         "mismatches": {"dev-retention-revoked": ["status", "selected", "selection_current"]}})
        self.assertEqual(b["verdict"], {"n": 3, "passes": 3, "mismatches": {}})
        self.assertEqual([row["rechecks"] for row in b["observations"]], [1, 1, 0])
        self.assertEqual(a["observations"][2], b["observations"][2])

    def test_held_out_reexecutes_version_change_grant_loss_and_valid_controls(self):
        report = lab.compare("held_out")
        a, b = (report[arm] for arm in ("baseline", "candidate"))
        ids = ["hold-retention-new-version", "hold-appendix-revoked", "hold-operations-current", "hold-appendix-current"]
        self.assertEqual(report["fixture_version"], "citation-held-out-v1")
        self.assertEqual(report["case_ids"], ids)
        self.assertEqual((a["verdict"]["passes"], b["verdict"]["passes"]), (2, 4))
        self.assertEqual(set(a["verdict"]["mismatches"]), set(ids[:2]))
        self.assertEqual([row["visible_exact"] for row in b["observations"]], [False, False, True, True])
        self.assertEqual([row["selected"] for row in b["observations"]], [False, False, True, True])
        self.assertEqual([row["selection_current"] for row in b["observations"]], [None, None, True, True])
        self.assertEqual([row["rechecks"] for row in b["observations"]], [1, 1, 1, 1])

    def test_rejects_all_handoff_on_held_out_even_if_it_catches_both_regressions(self):
        report = lab.compare("held_out")
        rows = [dict(row, status="handoff", selected=False, selection_current=None)
                for row in report["candidate"]["observations"]]
        bad = lab.verdict(report["case_ids"], rows)
        self.assertEqual(bad["passes"], 2)
        self.assertEqual(set(bad["mismatches"]), {"hold-operations-current", "hold-appendix-current"})

        run = lab.observe

        def overbroad(case, rule):
            obs = run(case, rule)
            return dict(obs, status="handoff", selected=False, selection_current=None) if (
                rule == lab.CANDIDATE and case.tenant == "operations") else obs

        with patch.object(lab, "observe", overbroad):
            result = lab.rehearse()
        self.assertEqual(result["dev"]["candidate"]["verdict"]["passes"], 3)
        self.assertEqual(result["held_out"]["candidate"]["verdict"]["passes"], 3)
        self.assertEqual(result["decision"], "revert_and_review")
        self.assertEqual(result["production"], "blocked")

    def test_verdict_binds_each_observation_to_its_literal_label(self):
        report = lab.compare("dev")
        ids, rows = report["case_ids"], report["candidate"]["observations"]
        self.assertEqual(lab.verdict(ids, reversed(rows))["passes"], 3)
        a, b, c = ids
        switched = [dict(rows[0], case_id=b), dict(rows[1], case_id=a), rows[2]]
        self.assertEqual(set(lab.verdict(ids, switched)["mismatches"]), {a, b})
        for invalid in (rows[1:], [rows[0], *rows], [dict(rows[0], case_id="unknown"), *rows[1:]]):
            with self.assertRaises(ValueError):
                lab.verdict(ids, invalid)

    def test_wrong_request_scope_cannot_pass_under_the_same_case_id(self):
        cases = lab.HELD_OUT
        for change in ({"tenant": "support"}, {"actor": "lin"}):
            with self.subTest(change=change):
                altered = (*cases[:2], replace(cases[2], **change), cases[3])
                with patch.object(lab, "HELD_OUT", altered):
                    report = lab.rehearse()
                self.assertEqual(report["decision"], "revert_and_review")
                candidate = report["held_out"]["candidate"]
                self.assertEqual(candidate["verdict"]["passes"], 3)
                self.assertIn("input_matches", candidate["verdict"]["mismatches"]["hold-operations-current"])
                self.assertIn("lookup_matches", candidate["verdict"]["mismatches"]["hold-operations-current"])
                self.assertEqual(report["dev"]["candidate"]["verdict"]["passes"], 3)

    def test_runtime_lookup_is_bound_even_when_the_prepared_case_is_correct(self):
        query = lab._query

        def wrong_lookup(store, reads, tenant, actor, key):
            if (tenant, actor) == ("support", "lin"):
                actor = "mei"  # Same text, different authority, in this classroom fixture.
            return query(store, reads, tenant, actor, key)

        with patch.object(lab, "_query", wrong_lookup):
            report = lab.rehearse()
        candidate = report["dev"]["candidate"]
        row = candidate["observations"][1]
        self.assertIs(row["input_matches"], True)
        self.assertIs(row["selection_current"], True)
        self.assertEqual(candidate["verdict"]["mismatches"], {"dev-retention-current": ["lookup_matches"]})
        self.assertEqual(report["decision"], "revert_and_review")

    def test_selected_quote_is_checked_even_with_correct_lookup_scope_and_key(self):
        select = lab._select

        def wrong_quote(rule, cached, reread):
            status, selected = select(rule, cached, reread)
            if rule == lab.CANDIDATE and selected and selected.text == "运维导出文件保留 30 天。":
                selected = replace(selected, text="仅供回归测试的不同原文。")
            return status, selected

        with patch.object(lab, "_select", wrong_quote):
            report = lab.rehearse()
        self.assertEqual(report["decision"], "revert_and_review")
        candidate = report["held_out"]["candidate"]
        obs = candidate["observations"][2]
        self.assertIs(obs["lookup_matches"], True)
        self.assertIs(obs["citation_matches"], False)
        self.assertEqual(candidate["verdict"]["mismatches"], {
            "hold-operations-current": ["selection_current", "citation_matches"]})
        self.assertNotIn("仅供回归测试的不同原文。", str(report))
        self.assertNotIn("运维导出文件保留 30 天。", str(report))

    def test_reports_drop_unexpected_observation_keys(self):
        observe = lab.observe
        with patch.object(lab, "observe", side_effect=lambda *args: dict(observe(*args), note="private-test")):
            report = lab.rehearse()
        self.assertNotIn("private-test", str(report))
        self.assertEqual(report["decision"], "retain_local_rule")

    def test_handoff_will_not_credit_a_detached_stop_or_late_review(self):
        from rollback import worked

        observed = worked()
        self.assertTrue(lab._linked_stop(observed))
        self.assertTrue(lab._preserved_decisions(observed))
        for change in ("different_writer", "different_store", "late_dispatch", "missing_stop_response"):
            with self.subTest(change=change):
                row = deepcopy(observed)
                events = row["lifecycle"]
                index = next(i for i, event in enumerate(events) if event["event"] == "stop")
                if change == "different_writer":
                    events[index]["pid"] += 1
                elif change == "different_store":
                    events[index + 1]["store"] = "other-store"
                elif change == "late_dispatch":
                    events.insert(index + 1, dict(events[index - 1]))
                else:
                    del events[index - 1]
                self.assertFalse(lab._linked_stop(row))
        observed["handoff"]["reviews"] = [line for line in observed["handoff"]["reviews"] if line[2] != "pre-approve"]
        self.assertFalse(lab._preserved_decisions(observed))

    def test_stage_runs_the_integrated_local_handoff_without_granting_clearance(self):
        result = lab.handoff()
        self.assertEqual(result["checks"], dict.fromkeys(("gate_fail_restore", "same_phase8_inputs", "frozen_canary_cohort",
                                                        "canary_stop_conditions", "stop_linked_to_rollback",
                                                        "rollback_keeps_approvals", "rollback_keeps_original_receipt",
                                                        "iteration_generalizes_locally", "no_production_clearance"), True))
        self.assertIs(result["passed"], True)
        self.assertEqual(result["rollback"]["replay_inserts"], 0)
        self.assertEqual(result["rollback"]["stop"]["reasons"], ["uncertain_outcome"])
        self.assertEqual(result["production"], "blocked")
        self.assertIn("real_l87_checkpoint_compatibility", result["outstanding"])


if __name__ == "__main__":
    unittest.main()
