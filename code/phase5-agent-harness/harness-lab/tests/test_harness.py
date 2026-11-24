import tempfile
import unittest
from contextlib import redirect_stdout
from dataclasses import replace
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from main import Actor, LostReply, ReadCall, Review, Task, open_store, run_acceptance, run_loop


class ReadLoopTests(unittest.TestCase):
    def test_fixed_and_dynamic_routes_start_with_the_same_question(self):
        call = ReadCall(Task.EVIDENCE_QA, "导出文件有效期？")
        fixed = run_loop(call, dynamic=False)
        dynamic = run_loop(call)

        self.assertEqual((fixed.status, fixed.calls), ("failed", 1))
        self.assertEqual(dynamic.states, ("pending", "pending", "complete"))
        self.assertEqual(dynamic.calls, 2)
        self.assertEqual(dynamic.source_ids, ("KB-01", "KB-02"))
        self.assertIn("保留 7 天", dynamic.answer)

    def test_no_new_dispatch_at_budget_and_last_allowed_call_can_complete(self):
        call = ReadCall(Task.EVIDENCE_QA, "导出文件有效期？")
        zero = run_loop(call, budget=0)
        one = run_loop(call, budget=1)
        direct = run_loop(ReadCall(Task.EVIDENCE_QA, "导出文件保留多久？"), budget=1)
        self.assertEqual((zero.status, zero.calls), ("exhausted", 0))
        self.assertEqual((one.status, one.calls, one.answer), ("exhausted", 1, None))
        self.assertEqual((direct.status, direct.calls), ("complete", 1))

    def test_unknown_task_invalid_arguments_and_free_text_never_dispatch(self):
        for proposal in (ReadCall("save_local_draft", "导出文件保留多久？"),
                         ReadCall(Task.EVIDENCE_QA, " "), "complete"):
            with self.subTest(proposal=proposal):
                result = run_loop(proposal)
                self.assertEqual((result.status, result.calls, result.answer), ("failed", 0, None))

    def test_missing_evidence_without_a_scripted_rephrase_fails_closed(self):
        result = run_loop(ReadCall(Task.EVIDENCE_QA, "导出文件能否恢复？"))
        self.assertEqual((result.status, result.calls, result.source_ids), ("failed", 1, ()))

    def test_evidence_loop_does_not_open_a_draft_store(self):
        with patch("sqlite3.connect", side_effect=AssertionError("read-only loop must not open SQLite")):
            result = run_loop(ReadCall(Task.EVIDENCE_QA, "导出文件保留多久？"))
        self.assertEqual(result.status, "complete")


class DraftWorkflowTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db = Path(tmp.name) / "drafts.sqlite3"
        self.actor = Actor("tenant-a", "reviewer")

    def test_waiting_checkpoint_survives_connection_close_without_saving(self):
        with open_store(self.db) as store:
            staged = store.stage(self.actor, "export", 1, "导出文件保留多久？")

        with open_store(self.db) as store:
            reopened = store.checkpoint(self.actor, "export")

        self.assertEqual(reopened, staged)
        self.assertEqual(reopened.status, "pending")
        self.assertEqual(reopened.draft.source_ids, ("KB-01", "KB-02"))
        self.assertIsNone(reopened.op_id)

    def test_retry_after_lost_reply_returns_the_same_saved_draft_once(self):
        with open_store(self.db) as store:
            staged = store.stage(self.actor, "export", 1, "导出文件保留多久？")
            review = Review.APPROVE
            self.assertEqual(store.saved_count(self.actor, "export"), 0)
        with open_store(self.db) as store, self.assertRaises(LostReply):
            store.resume(self.actor, "export", staged.binding, review, lose_reply=True)
        with open_store(self.db) as store:
            committed = store.checkpoint(self.actor, "export")
            replay = store.resume(self.actor, "export", staged.binding, review)
            self.assertEqual((committed.status, replay.status), ("saved", "replayed"))
            self.assertEqual(replay.op_id, committed.op_id)
            self.assertEqual(replay.draft, staged.draft)
            self.assertEqual(store.saved_count(self.actor, "export"), 1)
            with self.assertRaises(ValueError):
                store.stage(self.actor, "export", 2, "同步任务几点运行？")

    def test_observes_only_the_approved_local_draft_write_attempt(self):
        actor, other = self.actor, Actor(self.actor.tenant, "other-reviewer")
        question = "导出文件保留多久？"
        attempts: list[tuple[str, int]] = []

        def observe(op_id: str) -> None:
            # The same connection would see the new row if the INSERT had already run.
            attempts.append((op_id, store.saved_count(actor, "export")))

        with open_store(self.db, on_draft_write_attempt=observe) as store:
            stale = store.stage(actor, "export", 1, "同步任务几点运行？")
            pending = store.stage(actor, "export", 2, question)
            store.stage(other, "export", 2, question)
            denied = store.stage(actor, "denied", 1, question)
            self.assertEqual(attempts, [])
            for case, caller, job, binding, review, status in (
                ("missing review", actor, "export", pending.binding, None, "rejected"),
                ("wrong actor", other, "export", pending.binding, Review.APPROVE, "rejected"),
                ("denial", actor, "denied", denied.binding, Review.DENY, "denied"),
                ("approval after denial", actor, "denied", denied.binding, Review.APPROVE, "denied"),
                ("stale binding", actor, "export", stale.binding, Review.APPROVE, "rejected"),
            ):
                with self.subTest(case=case):
                    self.assertEqual(store.resume(caller, job, binding, review).status, status)
                    self.assertEqual(attempts, [])
            for scope, job in ((actor, "export"), (other, "export"), (actor, "denied")):
                self.assertEqual(store.saved_count(scope, job), 0)
            with self.assertRaises(LostReply):
                store.resume(actor, "export", pending.binding, Review.APPROVE, lose_reply=True)

        with open_store(self.db, on_draft_write_attempt=observe) as store:
            committed = store.checkpoint(actor, "export")
            self.assertEqual(committed.status, "saved")
            self.assertEqual(attempts, [(committed.op_id, 0)])
            self.assertEqual(store.saved_count(actor, "export"), 1)
            replay = store.resume(actor, "export", pending.binding, Review.APPROVE)
            self.assertEqual((replay.status, replay.op_id, replay.draft),
                             ("replayed", committed.op_id, pending.draft))
            self.assertEqual(attempts, [(committed.op_id, 0)])
            self.assertEqual(store.saved_count(actor, "export"), 1)

    def test_denial_survives_reopen_and_cannot_be_replaced_by_approval(self):
        with open_store(self.db) as store:
            staged = store.stage(self.actor, "export", 1, "导出文件保留多久？")
            self.assertEqual(store.resume(self.actor, "export", staged.binding, Review.DENY).status, "denied")
        with open_store(self.db) as store:
            denied = store.resume(self.actor, "export", staged.binding, Review.APPROVE)
            self.assertEqual((denied.status, denied.op_id), ("denied", None))
            self.assertEqual(store.saved_count(self.actor, "export"), 0)

    def test_approval_cannot_cross_scope_or_authorize_another_action(self):
        with open_store(self.db) as store:
            staged = store.stage(self.actor, "export", 1, "导出文件保留多久？")
            for other in (Actor("tenant-b", "reviewer"), Actor("tenant-a", "different")):
                self.assertIsNone(store.checkpoint(other, "export"))
                store.stage(other, "export", 1, "导出文件保留多久？")
                self.assertEqual(store.resume(other, "export", staged.binding, Review.APPROVE).status, "rejected")
                self.assertEqual(store.saved_count(other, "export"), 0)
            store.stage(self.actor, "another-job", 1, "导出文件保留多久？")
            self.assertEqual(store.resume(self.actor, "another-job", staged.binding, Review.APPROVE).status,
                             "rejected")
            for binding, review in ((replace(staged.binding, action="submit"), Review.APPROVE),
                                    (replace(staged.binding, version=True), Review.APPROVE),
                                    (staged.binding, "approve")):
                self.assertEqual(store.resume(self.actor, "export", binding, review).status, "rejected")
            self.assertEqual(store.saved_count(self.actor, "export"), 0)

    def test_changed_version_and_changed_digest_require_current_approval(self):
        with open_store(self.db) as store:
            earlier = store.stage(self.actor, "draft", 1, "导出文件保留多久？")
            changed = store.stage(self.actor, "draft", 2, "同步任务几点运行？")
            self.assertNotEqual(earlier.binding.digest, changed.binding.digest)
            stale_bindings = (earlier.binding, replace(changed.binding, digest=earlier.binding.digest),
                              replace(changed.binding, version=earlier.binding.version))
            for binding in stale_bindings:
                self.assertEqual(store.resume(self.actor, "draft", binding, Review.APPROVE).status, "rejected")
            self.assertEqual(store.saved_count(self.actor, "draft"), 0)
            self.assertEqual(store.resume(self.actor, "draft", changed.binding, Review.APPROVE).status, "saved")

    def test_missing_evidence_does_not_create_a_checkpoint(self):
        with open_store(self.db) as store:
            with self.assertRaises(ValueError):
                store.stage(self.actor, "missing", 1, "导出文件能否恢复？")
            self.assertIsNone(store.checkpoint(self.actor, "missing"))


class AcceptanceTests(unittest.TestCase):
    def test_acceptance_is_quiet_repeatable_and_reports_observed_outcomes(self):
        out = StringIO()
        with redirect_stdout(out):
            result = run_acceptance()
            self.assertEqual(run_acceptance(), result)
        self.assertEqual(out.getvalue(), "")
        self.assertEqual(result["budget"], {"status": "exhausted", "calls": 1})
        self.assertEqual(result["dynamic"]["source_ids"], ["KB-01", "KB-02"])
        self.assertEqual(result["draft"], {
            "pending": "pending", "missing_review": "rejected", "unauthorized": "rejected",
            "denied": "denied", "changed": "rejected", "commit": "saved", "replay": "replayed",
            "saved_count": 1,
            "write_attempts": {"pending": 0, "missing_review": 0, "unauthorized": 0,
                               "denied": 0, "changed": 0, "commit": 1, "replay": 0},
        })


if __name__ == "__main__":
    unittest.main()
