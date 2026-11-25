"""Independent expectations for the shared Phase 7 course corpus."""

from dataclasses import replace
from pathlib import Path
import runpy
import sqlite3
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = runpy.run_path(str(ROOT / "lab.py"))
open_demo, Query, cosine = (MODULE[name] for name in ("open_demo", "Query", "cosine"))
POLICY = ("EXPORT-POLICY", 1, "§1")
OPS = ("EXPORT-OPS", 1, "§2")
SYNC = ("SYNC-POLICY", 1, "§1")


def keys(hits):
    return [hit.chunk.key for hit in hits]


class EvidenceContractTests(unittest.TestCase):
    def test_scopes_apply_before_each_ranker_and_citation_lookup(self):
        query = Query(("导出", "保留"), (1.0, 0.0, 0.0))
        with open_demo() as db:
            for mode in ("lexical", "vector", "hybrid"):
                with self.subTest(mode=mode):
                    # Auditor-only evidence scores strongly, but can never occupy these slots.
                    self.assertEqual(keys(db.search("support", "lin", query, mode=mode, k=1)), [POLICY])
                    self.assertEqual(keys(db.search("support", "mei", query, mode=mode, k=2)), [POLICY, OPS])
                    self.assertEqual(db.search("operations", "lin", query, mode=mode), ())
            self.assertEqual(db.source("support", "mei", POLICY).text, "导出文件生成后保留 7 天。")
            self.assertEqual(db.source("operations", "mei", POLICY).text, "运维导出文件保留 30 天。")
            self.assertIsNone(db.source("support", "lin", OPS))

    def test_retrieval_modes_have_an_independent_failure_case(self):
        with open_demo() as db:
            query = Query(("多久",), (1.0, 0.0, 0.0))
            self.assertEqual(db.search("support", "mei", query), ())
            self.assertEqual(keys(db.search("support", "mei", query, mode="vector", k=1)), [POLICY])
            query = Query(("同步",), (1.0, 0.0, 0.0))
            self.assertEqual(keys(db.search("support", "mei", query, k=1)), [SYNC])
            self.assertEqual(keys(db.search("support", "mei", query, mode="vector", k=1)), [POLICY])
            self.assertEqual(db.search("support", "mei", query, k=0), ())

    def test_reload_checks_current_version_and_individual_grants(self):
        with open_demo() as db:
            old = db.source("support", "mei", POLICY)
            revised = replace(old, version=2, text="导出文件生成后保留 14 天。")
            db.replace_document("support", "EXPORT-POLICY", 2, (revised,))
            self.assertIsNone(db.source("support", "mei", POLICY))
            self.assertEqual(db.source("support", "lin", revised.key), revised)
            db.revoke("support", "mei", "EXPORT-POLICY")
            self.assertIsNone(db.source("support", "mei", revised.key))
            self.assertEqual(db.source("support", "lin", revised.key), revised)
            db.delete_document("support", "EXPORT-POLICY")
            self.assertIsNone(db.source("support", "lin", revised.key))
            self.assertEqual(db.source("operations", "mei", POLICY).text, "运维导出文件保留 30 天。")
            self.assertEqual(db.epoch, 3)

    def test_failed_version_insert_preserves_previous_source_and_epoch(self):
        with open_demo() as db:
            old = db.source("support", "mei", POLICY)
            updated = replace(old, version=2, text=None)  # Deliberately violates NOT NULL after old rows are removed.
            with self.assertRaises(sqlite3.IntegrityError):
                db.replace_document("support", "EXPORT-POLICY", 2, (updated,))
            self.assertTrue(db.source("support", "mei", POLICY) == old and db.epoch == 0)

    def test_invalid_vector_revision_does_not_publish_or_bump_epoch(self):
        with open_demo() as db:
            old = db.source("support", "mei", POLICY)
            query = Query(("保留",), (1.0, 0.0, 0.0))
            baseline = db.search("support", "mei", query, mode="hybrid")
            for vector in ((1.0, 0.0), (1.0, 0.0, float("nan"))):
                updated = replace(old, version=2, vector=vector)
                with self.subTest(vector=vector), self.assertRaises(ValueError):
                    db.replace_document("support", old.doc_id, 2, (updated,))
                self.assertEqual(db.source("support", "mei", POLICY), old)
                self.assertIsNone(db.source("support", "mei", updated.key))
                self.assertEqual(db.search("support", "mei", query, mode="hybrid"), baseline)
                self.assertEqual(db.epoch, 0)

    def test_trusted_fixture_can_seed_multiple_chunks_with_one_grant(self):
        with open_demo() as db:
            first = db.source("support", "mei", POLICY)
        second = replace(first, locator="§2", text="同一发布版的另一段。")
        with open_demo(rows=(("reading", first, ("member",)), ("reading", second, ("member",)))) as db:
            self.assertEqual(db.authorized("reading", "member"), (first, second))
            self.assertEqual(db.authorized("reading", "guest"), ())
        with self.assertRaises(ValueError):
            with open_demo(rows=(("reading", first, ("member",)), ("reading", second, ("guest",)))):
                self.fail("inconsistent document grants should not be accepted")

    def test_comparison_keeps_hit_coverage_separate_from_rank_time(self):
        compare = runpy.run_path(str(ROOT / "compare_retrieval.py"))["compare"]
        ticks = iter(range(12))
        report = compare(repeats=2, timer=lambda: next(ticks))
        self.assertEqual(report["output_k"], 1)
        self.assertEqual(report["authorized_chunks"], 3)
        got = [(row["mode"], row["covered"], row["cases"], row["branch_candidate_scores_per_query"])
               for row in report["modes"]]
        self.assertEqual(got, [("lexical", 1, 2, 3), ("vector", 1, 2, 3), ("hybrid", 2, 2, 6)])
        self.assertTrue(all(row["median_seconds_per_case_batch"] == 1 for row in report["modes"]))

    def test_fixed_vector_boundaries(self):
        self.assertAlmostEqual(cosine((3.0, 4.0), (1.0, 0.0)), 0.6)
        self.assertEqual(cosine((0.0, 0.0), (1.0, 0.0)), 0.0)
        for invalid in ((1.0,), (float("nan"), 0.0)):
            with self.assertRaises(ValueError):
                cosine((1.0, 0.0), invalid)


if __name__ == "__main__":
    unittest.main()
