"""Boundary cases beyond the two Phase 7 lesson walkthroughs. Run with Python -I -X utf8."""

from dataclasses import astuple, replace
from pathlib import Path
import runpy
import unittest
from unittest.mock import call, patch

LAB = runpy.run_path(str(Path(__file__).with_name("main.py")))
Query, Hit, Plan, EvidenceCaches, open_demo, pack, rerank = (
    LAB[name] for name in ("Query", "Hit", "Plan", "EvidenceCaches", "open_demo", "pack", "rerank")
)
POLICY = ("EXPORT-POLICY", 1, "§1")
OPS = ("EXPORT-OPS", 1, "§2")
QUERY = Query(("导出", "保留"), (1., 0., 0.))
CUES = ("过期", "重新生成")
ABSTAIN = ("没有可用证据，无法回答。", "", ())
OPS_TEXT = "导出文件过期后，需重新发起导出。"
POLICY_TEXT = "导出文件生成后保留 7 天。"


class LifecycleTests(unittest.TestCase):
    def test_rerank_checks_full_candidate_value_and_uniqueness(self):
        with open_demo() as db:
            pool = db.authorized("support", "mei")
            hits = db.search("support", "mei", QUERY, mode="hybrid", k=2)
            self.assertEqual(tuple(h.chunk.key for h in hits), (POLICY, OPS))
            other_tenant = db.source("operations", "mei", POLICY)
            self.assertEqual(other_tenant.key, hits[0].chunk.key)
            self.assertNotEqual(other_tenant.text, hits[0].chunk.text)
            for invalid in ((Hit(other_tenant, hits[0].score), hits[1]), hits + (hits[0],)):
                with self.assertRaises(ValueError):
                    rerank(invalid, pool, CUES)
            self.assertEqual(tuple(h.chunk.key for h in rerank(hits, pool, CUES)), (OPS, POLICY))

    def test_multi_entry_budget_measures_heading_citations_and_delimiters(self):
        with open_demo() as db:
            pool = db.authorized("support", "mei")
            hits = db.search("support", "mei", QUERY, mode="hybrid", k=2)
            ordered = rerank(hits, pool, CUES)
            full = pack(ordered, top_k=2, max_chars=90, max_bytes=178)
            self.assertEqual(full.context, "证据：\n"
                             "[EXPORT-OPS v1 §2] 导出过期处理：导出文件过期后，需重新发起导出。\n"
                             "[EXPORT-POLICY v1 §1] 导出保留期：导出文件生成后保留 7 天。\n")
            self.assertEqual((full.citations, full.chars, full.utf8_bytes), ((OPS, POLICY), 90, 178))
            for chars, byte_limit in ((89, 178), (90, 177)):
                short = pack(ordered, top_k=2, max_chars=chars, max_bytes=byte_limit)
                self.assertEqual((short.citations, short.chars, short.utf8_bytes), ((OPS,), 47, 100))

    def test_expiry_refuses_with_nonempty_pack_but_answers_when_supported(self):
        query = Query(("导出", "过期"))
        with open_demo() as db:
            caches = EvidenceCaches(db)
            for user, key, text in (("lin", POLICY, POLICY_TEXT), ("mei", OPS, OPS_TEXT)):
                self.assertEqual(caches.retrieve("support", user, query).citations, (key,))
                self.assertEqual(db.source("support", user, key).text, text)
                answer = caches.answer("support", user, query)
                expected = ABSTAIN if user == "lin" else (
                    OPS_TEXT, "证据：\n[EXPORT-OPS v1 §2] 导出过期处理：" + OPS_TEXT + "\n", (OPS,)
                )
                self.assertEqual(astuple(answer), expected)
                self.assertEqual(caches.answer("support", user, query), answer)
            self.assertEqual(astuple(caches.stats), (2, 2, 2, 2))

    def test_budget_miss_refuses_independently_even_for_mei(self):
        plan = Plan(mode="hybrid", candidate_k=2, cues=CUES, max_bytes=99)
        with open_demo() as db:
            caches = EvidenceCaches(db)
            self.assertEqual(caches.retrieve("support", "mei", QUERY, plan).citations, (POLICY,))
            self.assertEqual(astuple(caches.answer("support", "mei", QUERY, plan, required_terms=CUES)), ABSTAIN)
            exact = replace(plan, max_bytes=100)
            answer = caches.answer("support", "mei", QUERY, exact, required_terms=CUES)
            self.assertEqual((answer.text, answer.citations), (OPS_TEXT, (OPS,)))

    def test_answer_terms_isolate_hits_and_select_support_past_first_chunk(self):
        plan = Plan(mode="hybrid", candidate_k=2, top_k=2, max_chars=90, max_bytes=178)
        with open_demo() as db:
            caches = EvidenceCaches(db)
            self.assertEqual(caches.retrieve("support", "mei", QUERY, plan).citations, (POLICY, OPS))
            for required, key, text in ((None, POLICY, POLICY_TEXT), (CUES, OPS, OPS_TEXT),
                                        (("保留", "过期"), None, None), ((), None, None)):
                answer = caches.answer("support", "mei", QUERY, plan, required_terms=required)
                if key is None:
                    self.assertEqual(astuple(answer), ABSTAIN)
                else:
                    self.assertEqual((answer.text, answer.citations), (text, (key,)))
                    self.assertIn(text, answer.context)
                    self.assertNotIn(OPS_TEXT if key == POLICY else POLICY_TEXT, answer.context)
                self.assertEqual(caches.answer("support", "mei", QUERY, plan, required_terms=required), answer)
            self.assertEqual(astuple(caches.stats), (1, 4, 4, 4))

    def test_each_warm_path_reads_all_current_dependencies(self):
        plan = Plan(mode="hybrid", candidate_k=2, cues=CUES, top_k=2, max_chars=90, max_bytes=178)
        with open_demo() as db:
            caches = EvidenceCaches(db)
            old = caches.answer("support", "mei", QUERY, plan, required_terms=CUES)
            self.assertEqual(old.citations, (OPS,))
            reads = [call("support", "mei", OPS), call("support", "mei", POLICY)]
            with patch.object(db, "source", wraps=db.source) as source:
                retrieved = caches.retrieve("support", "mei", QUERY, plan)
                self.assertEqual(retrieved.citations, (OPS, POLICY))
                self.assertEqual(source.call_args_list, reads)
                source.reset_mock()
                self.assertEqual(caches.answer("support", "mei", QUERY, plan, required_terms=CUES), old)
                self.assertEqual(source.call_args_list, reads)
            self.assertEqual(astuple(caches.stats), (1, 1, 1, 1))

    def test_warm_answer_revalidates_body_as_well_as_key(self):
        with open_demo() as db:
            caches = EvidenceCaches(db)
            old = caches.answer("support", "mei", QUERY)
            self.assertEqual((old.text, old.citations), (POLICY_TEXT, (POLICY,)))
            corrected_text = "导出文件生成后保留 8 天。"
            corrected = replace(db.source("support", "mei", POLICY), text=corrected_text)
            # Stub a different value at the same key to exercise the warm comparison
            # in isolation. The real store requires a new version for updates.
            with patch.object(db, "source", return_value=corrected):
                fresh = caches.answer("support", "mei", QUERY)
                self.assertEqual((fresh.text, fresh.citations), (corrected_text, (POLICY,)))
                self.assertIn("[EXPORT-POLICY v1 §1] 导出保留期：" + corrected_text, fresh.context)
                self.assertNotIn(POLICY_TEXT, fresh.context)
                self.assertEqual(caches.answer("support", "mei", QUERY), fresh)
            self.assertEqual(astuple(caches.stats), (1, 1, 2, 1))

    def test_delete_removes_active_rows_only_in_target_tenant(self):
        def counts(connection, tenant):
            # Inspect the test fixture's active tables, not only its authorized read view.
            args = (tenant, POLICY[0])
            return tuple(connection.execute(sql, args).fetchone()[0] for sql in (
                "SELECT count(*) FROM documents WHERE tenant=? AND doc_id=?",
                "SELECT count(*) FROM chunks WHERE tenant=? AND doc_id=?",
                "SELECT count(*) FROM grants WHERE tenant=? AND doc_id=?",
            ))

        with open_demo() as db:
            self.assertEqual(counts(db._conn, "support"), (1, 1, 2))
            self.assertEqual(counts(db._conn, "operations"), (1, 1, 1))
            db.delete_document("support", POLICY[0])
            self.assertEqual(counts(db._conn, "support"), (0, 0, 0))
            self.assertEqual(counts(db._conn, "operations"), (1, 1, 1))

    def test_revision_invalidates_warm_empty_results(self):
        query = Query(("新口径",))
        expected_key = ("EXPORT-POLICY", 2, "§1")
        new_text = "导出文件生成后保留 14 天。"
        with open_demo() as db:
            caches = EvidenceCaches(db)
            old = caches.answer("support", "lin", query)
            self.assertEqual(astuple(old), ABSTAIN)
            self.assertEqual(caches.retrieve("support", "lin", query).citations, ())
            self.assertEqual(caches.answer("support", "lin", query), old)
            self.assertEqual(astuple(caches.stats), (1, 1, 1, 1))

            chunk = db.source("support", "lin", POLICY)
            new = replace(chunk, version=2, text=new_text, terms=("新口径",))
            db.replace_document("support", POLICY[0], 2, (new,))
            fresh = caches.answer("support", "lin", query)
            self.assertEqual((fresh.text, fresh.citations), (new_text, (expected_key,)))
            self.assertEqual(astuple(caches.stats), (2, 1, 2, 1))


if __name__ == "__main__":
    unittest.main()
