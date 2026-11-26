"""Independent assertions for the trusted L83 oracle and its fixed fixtures."""

from pathlib import Path
import runpy
import unittest


lab = runpy.run_path(str(Path(__file__).with_name("lab.py")))
verify = lab["verify"]


class CitationAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.candidates = lab["load_candidates"]()

    def test_accepts_the_full_citation_and_only_the_target_change(self):
        self.assertEqual(verify(self.candidates["valid"]["files"]), {
            "accepted": True,
            "citation_ok": True,
            "scope_ok": True,
            "target": "answer.md",
            "delta": {"added": [], "removed": [], "changed": ["answer.md"]},
        })

    def test_claimed_pass_does_not_supply_a_missing_locator(self):
        candidate = self.candidates["missing-locator"]
        report = verify(candidate["files"])
        self.assertTrue(candidate["claimed_pass"])
        self.assertTrue(report["scope_ok"])
        self.assertFalse(report["citation_ok"])
        self.assertFalse(report["accepted"])

    def test_checks_the_complete_output_not_just_a_citation_substring(self):
        for body in ("同步任务每天 02:00 运行。\n来源：SYNC-POLICY v2 §1\n",
                     "同步任务每天 02:00 运行。\n来源：SYNC-POLICY v1 §1\n附加说明。\n",
                     "同步任务每天 03:00 运行。\n来源：SYNC-POLICY v1 §1\n"):
            with self.subTest(body=body):
                files = {**self.candidates["valid"]["files"], "answer.md": body}
                report = verify(files)
                self.assertTrue(report["scope_ok"])
                self.assertFalse(report["citation_ok"])
                self.assertFalse(report["accepted"])

    def test_claimed_pass_cannot_hide_an_out_of_scope_change(self):
        for name, extra in (("unrelated-edit", "notes.md"),
                            ("test-edit", "tests/citation-cases.json")):
            with self.subTest(name=name):
                candidate = self.candidates[name]
                report = verify(candidate["files"])
                self.assertTrue(candidate["claimed_pass"])
                self.assertTrue(report["citation_ok"])
                self.assertEqual(report["delta"], {
                    "added": [], "removed": [], "changed": ["answer.md", extra],
                })
                self.assertFalse(report["scope_ok"])
                self.assertFalse(report["accepted"])

    def test_omitted_artifact_is_a_removal_not_an_unchanged_file(self):
        files = self.candidates["valid"]["files"].copy()
        del files["notes.md"]
        report = verify(files)
        self.assertTrue(report["citation_ok"])
        self.assertEqual(report["delta"]["removed"], ["notes.md"])
        self.assertFalse(report["scope_ok"])
        self.assertFalse(report["accepted"])

    def test_new_target_preserves_the_strict_scope_gate(self):
        reports = {name: verify(self.candidates[name]["files"], profile="preview-only")
                   for name in ("valid", "preview-only", "preview-extra")}
        old = reports["valid"]
        self.assertEqual(old["delta"]["changed"], ["answer.md"])
        self.assertFalse(old["scope_ok"])
        self.assertFalse(old["accepted"])
        good = reports["preview-only"]
        self.assertEqual(good["target"], "preview.md")
        self.assertEqual(good["delta"], {"added": [], "removed": [], "changed": ["preview.md"]})
        self.assertTrue(good["accepted"])
        extra = reports["preview-extra"]
        self.assertEqual(extra["delta"]["added"], ["preview-copy.md"])
        self.assertTrue(extra["citation_ok"])
        self.assertFalse(extra["scope_ok"])
        self.assertFalse(extra["accepted"])


if __name__ == "__main__":
    unittest.main()
