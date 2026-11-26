"""Offline contract tests; executable directly under isolated Python."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import runpy
import unittest
from unittest.mock import patch

lab = runpy.run_path(str(Path(__file__).with_name("release_gate.py")))
sample_contract = lab["sample_contract"]
validate_contract = lab["validate_contract"]
promote_offline = lab["promote_offline"]
rehearse = lab["rehearse"]


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.manifest, self.evidence = sample_contract()

    def test_manifest_matches_independently_hashed_inputs(self):
        self.assertEqual(self.manifest["candidate"], {
            "build_version": "support-agent-1.4.2",
            "artifact_sha256": sha256(b"support-agent-1.4.2\nfixture bundle\n").hexdigest(),
            "writer_schema": 2,
            "config_fingerprint": sha256(b'{"approval":"host-only","store":"sqlite-v2"}').hexdigest(),
        })
        self.assertEqual(self.manifest["rollback_target"], {
            "build_version": "support-agent-1.4.1",
            "artifact_sha256": sha256(b"support-agent-1.4.1\nfixture bundle\n").hexdigest(),
            "writer_schema": 1,
            "config_fingerprint": sha256(b'{"approval":"host-only","store":"sqlite-v1"}').hexdigest(),
        })
        self.assertEqual(validate_contract(self.manifest, self.evidence), {"passed": True, "reasons": []})

    def test_missing_stale_future_and_failed_evidence(self):
        for evidence, reason in (
            (None, "evidence:missing"),
            ({k: v for k, v in self.evidence.items() if k != "observed_at"}, "evidence.observed_at:missing"),
            (dict(self.evidence, observed_at=1_799_999_099), "evidence.observed_at:stale"),
            (dict(self.evidence, observed_at=1_800_000_001), "evidence.observed_at:future"),
            (dict(self.evidence, observations=dict(self.evidence["observations"], candidate_writes=1)),
             "evidence.observations.candidate_writes:mismatched"),
        ):
            with self.subTest(reason=reason):
                self.assertEqual(validate_contract(self.manifest, evidence), {"passed": False, "reasons": [reason]})
        self.assertTrue(validate_contract(self.manifest, dict(self.evidence, observed_at=1_799_999_100))["passed"])

    def test_booleans_and_success_markers_are_not_evidence(self):
        for value in (True, "P10 LANGGRAPH APPLICATION REHEARSAL PASSED", {"passed": True}):
            with self.subTest(value=value):
                self.assertFalse(validate_contract(self.manifest, value)["passed"])
        self.evidence["observations"]["candidate_writes"] = False
        self.assertEqual(validate_contract(self.manifest, self.evidence)["reasons"],
                         ["evidence.observations.candidate_writes:malformed"])

    def test_both_submissions_cannot_relabel_artifact_to_match_tampered_bytes(self):
        tampered = b"not the candidate bundle"
        for item in (self.manifest, self.evidence):
            item["candidate"]["artifact_sha256"] = sha256(tampered).hexdigest()
        outcome = validate_contract(self.manifest, self.evidence, artifact=tampered)
        self.assertFalse(outcome["passed"])
        self.assertEqual(outcome["reasons"], ["artifact.sha256:mismatched", "manifest.candidate.artifact_sha256:mismatched",
                                              "evidence.candidate.artifact_sha256:mismatched"])
        self.assertEqual(validate_contract(self.manifest, self.evidence, artifact=None)["reasons"], ["artifact:missing"])

    def test_candidate_and_rollback_bindings_are_checked_independently(self):
        for party, field, value in (("candidate", "writer_schema", 3),
                                    ("candidate", "config_fingerprint", "0" * 64),
                                    ("rollback_target", "build_version", "latest"),
                                    ("rollback_target", "artifact_sha256", "0" * 64),
                                    ("rollback_target", "writer_schema", 2),
                                    ("rollback_target", "config_fingerprint", "0" * 64)):
            with self.subTest(party=party, field=field):
                manifest, evidence = deepcopy((self.manifest, self.evidence))
                manifest[party][field] = evidence[party][field] = value
                self.assertEqual(validate_contract(manifest, evidence)["reasons"],
                                 [f"manifest.{party}.{field}:mismatched", f"evidence.{party}.{field}:mismatched"])

    def test_green_phase8_cannot_promote_with_wrong_rollback_evidence(self):
        self.evidence["rollback_target"]["artifact_sha256"] = self.manifest["candidate"]["artifact_sha256"]
        report = promote_offline(self.manifest, self.evidence)
        self.assertTrue(report["baseline"]["passed"])
        self.assertTrue(report["phase8_replay"]["passed"])
        self.assertEqual(report["offline_contract"], {
            "passed": False, "reasons": ["evidence.rollback_target.artifact_sha256:mismatched"],
        })
        self.assertEqual(set(report["classroom_promotion"].values()), {"blocked"})
        self.assertEqual(report["production"], "blocked")


class RehearsalTests(unittest.TestCase):
    def test_gate_unavailable_is_not_a_detected_regression(self):
        with patch.dict(rehearse.__globals__, PHASE8=Path(__file__).with_suffix(".not-a-directory")):
            report = rehearse()
        self.assertEqual(report["offline_contract"], {"passed": True, "reasons": []})
        self.assertEqual(report["phase8_replay"], {"passed": False, "reasons": ["phase8.replay:unavailable"]})
        self.assertIsNone(report["drop_citation"]["exit_code"])
        self.assertEqual(set(report["classroom_promotion"].values()), {"blocked"})
        self.assertEqual(report["production"], "blocked")

    def test_real_phase8_green_red_green_and_production_separate(self):
        report = rehearse()
        self.assertEqual(report, json.loads(json.dumps(report)))
        names = ("baseline", "drop_citation", "restored")
        arms = [report[name] for name in names]
        self.assertEqual([arm["exit_code"] for arm in arms], [0, 1, 0])
        self.assertEqual([arm["passed"] for arm in arms], [True, False, True])
        self.assertEqual([arm["successes"] for arm in arms], [6, 5, 6])
        self.assertEqual(arms[0], arms[2])
        self.assertEqual(arms[1]["failures"], {"retention": ["citations"]})
        self.assertEqual(arms[1]["blocks"], ["citation_contract", "success_rate"])
        self.assertRegex(arms[0]["fingerprint"], r"^[0-9a-f]{64}$")
        self.assertEqual(len({arm["fingerprint"] for arm in arms}), 1)
        self.assertEqual(report["offline_contract"], {"passed": True, "reasons": []})
        self.assertEqual(report["phase8_replay"], {"passed": True, "reasons": []})
        self.assertEqual(list(report["classroom_promotion"].values()), ["eligible", "blocked", "eligible"])
        self.assertEqual(report["compatibility_labels"], "synthetic-only")
        self.assertEqual(report["l87_evidence"]["status"], "not_verified")
        self.assertEqual(report["production"], "blocked")


if __name__ == "__main__":
    unittest.main()
