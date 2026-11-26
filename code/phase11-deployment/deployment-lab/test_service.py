"""SDK-free checks across child lifetimes, plus fixed local control observations."""

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import authority_rehearsal as authority
import service_rehearsal as service
from host import DraftStore, Host, Review, audit
from transport import StartupRefused, Worker


def empty_reply(status, *, reads=0):
    return {"status": status, "draft": None, "receipt": None, "read_calls": reads, "inserts": []}


class ServiceTests(unittest.TestCase):
    def test_replacement_preserves_approval_during_dependency_outage(self):
        row = service.worked()
        bind = row["staged"]["binding"]
        gold = service.GOLD["export"]
        self.assertEqual(bind, {"tenant": "support", "actor": "mei", "job": "export", "action": "save_local_draft",
                                "revision": 1, "digest": gold["digest"]})
        self.assertEqual(row["answer"]["evidence"], [{"tenant": "support", "key": gold["key"], "quote": gold["quote"]}])
        self.assertEqual(row["staged"]["draft"], gold["draft"])
        self.assertEqual(row["staged"]["inserts"], [])
        self.assertEqual(row["pending"], {**empty_reply("pending"), "binding": bind})
        self.assertEqual(row["approval"], empty_reply("review_recorded"))
        self.assertEqual(row["blocked"], empty_reply("dependency_unavailable"))
        self.assertEqual(row["during"]["checkpoints"], row["before"]["checkpoints"])
        expected_review = [["support", "mei", "export", "save_local_draft", 1, gold["digest"], "approve"]]
        self.assertEqual(row["during"]["reviews"], expected_review)
        self.assertEqual(row["during"]["saved"], [])
        receipt = "840aaa0f6e5be39e7c9d275b6ebc0695d08afd03fcc35819f4a86744e681d6cc"
        self.assertEqual(row["resumed"], {"status": "saved", "draft": gold["draft"], "receipt": receipt,
                                           "read_calls": 2, "inserts": [receipt]})
        self.assertEqual(row["after"]["saved"], [[receipt, "support", "mei", "export", gold["draft"]]])
        self.assertEqual(row["after"]["reviews"], expected_review)

    def test_empty_directory_and_stale_approval_do_not_restore(self):
        row = service.transfer()
        self.assertEqual(row["missing"], empty_reply("not_available"))
        self.assertEqual(row["empty"]["checkpoints"], [])
        self.assertEqual(row["wrong"], empty_reply("rejected"))
        self.assertEqual(row["denied"], empty_reply("denied"))
        self.assertEqual(row["original"]["draft"], row["revised"]["draft"])
        current = row["revised"]["binding"]
        self.assertEqual(current["revision"], 2)
        self.assertEqual(row["before"]["reviews"], [["support", "mei", "sync", "save_local_draft", 2, current["digest"], "deny"]])
        self.assertEqual(row["after"]["checkpoints"], [["support", "mei", "sync", 2, service.GOLD["sync"]["draft"], "denied", None]])
        self.assertEqual(row["after"]["saved"], [])

    def test_partial_mount_is_not_initialized_as_a_new_task_store(self):
        with TemporaryDirectory() as tmp:
            source, partial = Path(tmp) / "source", Path(tmp) / "partial"
            with Worker(source) as worker:
                worker.call("stage", job="sync", revision=1, topic="sync")
            partial.mkdir()
            old = (source / "business.sqlite").read_bytes()
            (partial / "business.sqlite").write_bytes(old)
            with self.assertRaisesRegex(StartupRefused, "incompatible_schema"), Worker(partial):
                self.fail("partial bundle was treated as a new store")
            self.assertEqual((partial / "business.sqlite").read_bytes(), old)
            self.assertFalse((partial / "review.sqlite").exists())

    def test_transport_error_does_not_reuse_the_pipe_or_retry(self):
        with TemporaryDirectory() as tmp, Worker(Path(tmp)) as worker:
            with patch.object(worker, "_receive", side_effect=RuntimeError("no response")) as receive:
                with self.assertRaisesRegex(RuntimeError, "no response"):
                    worker.call("ask", topic="sync")
                self.assertEqual(receive.call_count, 1)
            with self.assertRaisesRegex(RuntimeError, "not running"):
                worker.call("ask", topic="sync")

    def test_closed_transport_cannot_dispatch(self):
        with TemporaryDirectory() as tmp:
            worker = Worker(Path(tmp))
            with worker:
                self.assertEqual(worker.call("ask", topic="sync")["status"], "answered")
            with self.assertRaisesRegex(RuntimeError, "not running"):
                worker.call("ask", topic="sync")


class AuthorityTests(unittest.TestCase):
    def test_quota_is_separate_from_the_per_operation_read_cap(self):
        row = authority.worked()
        calls = row["limited"]
        self.assertEqual([(r["status"], r["read_calls"]) for r in calls],
                         [("answered", 1), ("answered", 1), ("rate_limited", 0), ("answered", 1)])
        self.assertEqual(calls[2], empty_reply("rate_limited"))
        self.assertEqual(calls[3]["evidence"], [
            {"tenant": "operations", "key": ("EXPORT-POLICY", 1, "§1"), "quote": "运维导出文件保留 30 天。"}])
        reopened = row["reopened"]
        self.assertEqual((reopened["status"], reopened["read_calls"]), ("answered", 1))
        self.assertEqual(reopened["evidence"][0]["quote"], "导出文件生成后保留 7 天。")
        for key, status in (("over", "budget_exhausted"), ("forbidden", "forbidden"), ("bait", "invalid_request")):
            self.assertEqual(row[key], empty_reply(status), key)
        self.assertEqual(row["quota_state"]["checkpoints"], [])

        sync = row["cap_one_sync"]
        stage, recovery = sync["stage"], sync["recovery"]
        self.assertEqual((stage["status"], stage["read_calls"], stage["inserts"]), ("pending", 1, []))
        self.assertEqual(sync["approval"], empty_reply("review_recorded"))
        draft = service.GOLD["sync"]["draft"]
        receipt = recovery["receipt"]
        self.assertRegex(receipt, r"^[0-9a-f]{64}$")
        self.assertEqual(recovery, {"status": "saved", "draft": draft, "receipt": receipt,
                                    "read_calls": 1, "inserts": [receipt]})
        self.assertEqual(sync["state"]["saved"], [[receipt, "support", "mei", "sync", draft]])

    def test_approved_export_recovery_reserves_its_own_read_budget(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp)
            initial = Host(path, read_cap=2)
            stage = initial.dispatch("support", "stage", {"job": "export", "topic": "export", "revision": 1})
            self.assertEqual((stage["status"], stage["read_calls"]), ("pending", 2))
            binding = stage["binding"]
            review = initial.dispatch("reviewer", "review", {"binding": binding, "decision": "approve"})
            self.assertEqual(review, empty_reply("review_recorded"))
            before = audit(path)
            self.assertEqual(before["saved"], [])

            tight = Host(path, read_cap=1)
            blocked = tight.dispatch("reviewer", "recover", {"binding": binding})
            self.assertEqual(blocked, empty_reply("budget_exhausted"))
            self.assertEqual(audit(path), before)

    def test_denial_changes_only_the_bound_checkpoint_status(self):
        authority.assert_denial(authority.worked())

    def test_denial_check_rejects_success_reply_without_checkpoint_transition(self):
        resume = DraftStore.resume

        def fake_success(store, actor, job, binding, review, **kwargs):
            if review is Review.DENY:
                return SimpleNamespace(status="denied", op_id=None, draft=None)
            return resume(store, actor, job, binding, review, **kwargs)

        # Leave SQLite and the rest of the synthetic rehearsal real.
        with patch.object(DraftStore, "resume", fake_success):
            row = authority.worked()
        self.assertEqual(row["denied"], empty_reply("denied"))
        self.assertEqual(row["events"][-1]["result"], "denied")
        self.assertEqual(row["state"], row["after_decision"])
        with self.assertRaisesRegex(AssertionError, "only the checkpoint status"):
            authority.assert_denial(row)

    def test_revocation_survives_reopen_and_withholds_replay(self):
        row = authority.transfer()
        self.assertEqual(row["hidden"], empty_reply("not_available"))
        self.assertEqual(row["withheld"], empty_reply("replay_withheld", reads=1))
        self.assertEqual(row["intake"], empty_reply("source_blocked", reads=1))
        self.assertEqual(row["after"], {**row["before"], "revocations": [["support", "mei", "SYNC-POLICY"]]})
        receipt = row["saved"]["receipt"]
        self.assertEqual(row["saved"]["inserts"], [receipt])
        self.assertEqual(row["after"]["saved"], [[receipt, "support", "mei", "sync", service.GOLD["sync"]["draft"]]])
        self.assertEqual(row["other"]["evidence"][0]["key"], ("EXPORT-POLICY", 1, "§1"))
        self.assertEqual(row["after_events"][0]["trace_id"], row["before_events"][2]["trace_id"])

    def test_decision_cannot_be_overwritten_or_accepted_from_nonreviewer(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp)
            lab = Host(path)
            stage = lab.dispatch("support", "stage", {"job": "sync", "topic": "sync", "revision": 1})
            binding = stage["binding"]
            self.assertEqual(lab.dispatch("reviewer", "recover", {"binding": binding}), empty_reply("pending"))
            self.assertEqual(lab.dispatch("other", "recover", {"binding": binding}), empty_reply("forbidden"))
            for choice, status in (("deny", "review_recorded"), ("approve", "review_conflict")):
                self.assertEqual(lab.dispatch("reviewer", "review", {"binding": binding, "decision": choice}), empty_reply(status))
            self.assertEqual(lab.dispatch("reviewer", "recover", {"binding": binding}), empty_reply("denied"))
            self.assertEqual(audit(path)["saved"], [])


if __name__ == "__main__":
    unittest.main()
