"""L97 contract: tests exercise real worker replacement, not a fake rollback."""

import sqlite3
import unittest
from contextlib import closing, contextmanager
from unittest.mock import patch

import rollback


class WorkedRollbackTest(unittest.TestCase):
    @contextmanager
    def traced_workers(self, after_candidate_close=None):
        trace = []

        class TracedWorker(rollback.Worker):
            # Forward to real workers; observe the I/O boundary independently of the report.
            def __init__(self, directory, *, build, profile):
                super().__init__(directory, build=build, profile=profile)
                self.directory, self.build = directory, build
                trace.append(("opening", build, directory))

            def __enter__(self):
                super().__enter__()
                trace.append(("ready", self.pid, self.build))
                return self

            def call(self, operation, **payload):
                reply = super().call(operation, **payload)
                job = payload["binding"]["job"] if "binding" in payload else payload["job"]
                trace.append(("call", self.pid, operation, job, reply["status"]))
                return reply

            def __exit__(self, *exc):
                super().__exit__(*exc)
                trace.append(("closed", self.pid))
                if self.build == "v2" and after_candidate_close:
                    after_candidate_close(self.directory)

        with patch.object(rollback, "Worker", TracedWorker):
            yield trace

    def assert_no_restored_worker(self, trace):
        self.assertEqual([event[1] for event in trace if event[0] == "opening"], ["v1", "v2"])
        candidate, = [event[1] for event in trace if event[0] == "ready" and event[2] == "v2"]
        self.assertEqual(trace[-1], ("closed", candidate))
        self.assertIn(("call", candidate, "fixture_lost", "lost", "reply_lost"), trace)

    def test_candidate_call_stop_close_preflight_and_restore_in_order(self):
        decide, audit = rollback.canary.decide, rollback.audit

        def observe_decision(control, candidate, *, complete, hard_signals=()):
            outcome = decide(control, candidate, complete=complete, hard_signals=hard_signals)
            trace.append(("decide", complete, tuple(hard_signals), outcome))
            return outcome

        def observe_readback(directory):
            snapshot = audit(directory)
            trace.append(("audit", directory))
            return snapshot

        with (self.traced_workers() as trace, patch.object(rollback.canary, "decide", observe_decision),
              patch.object(rollback, "audit", observe_readback)):
            result = rollback.worked()
        before, candidate, restored = (result["pids"][role] for role in ("before", "candidate", "restored"))
        prior_open, candidate_open, restore_open = [event for event in trace if event[0] == "opening"]
        directory = prior_open[2]
        self.assertEqual((candidate_open, restore_open), (("opening", "v2", directory), ("opening", "v1", directory)))
        lost = trace.index(("call", candidate, "fixture_lost", "lost", "reply_lost"))
        self.assertEqual(trace[lost - 1:lost + 6], [
            ("audit", directory), ("call", candidate, "fixture_lost", "lost", "reply_lost"),
            ("decide", False, ("uncertain_outcome",), ("STOP_AND_ROLLBACK", ["uncertain_outcome"])),
            ("closed", candidate), ("audit", directory), restore_open, ("ready", restored, "v1"),
        ])
        self.assertEqual([event[2:] for event in trace if event[:2] == ("call", before) and event[2] == "review"],
                         [("review", "pre-approve", "review_recorded"), ("review", "pre-deny", "review_recorded")])
        self.assertEqual([event[2:] for event in trace if event[:2] == ("call", candidate) and event[2] == "review"],
                         [("review", "canary-approve", "review_recorded"),
                          ("review", "canary-deny", "review_recorded"), ("review", "lost", "review_recorded")])
        restored_calls = [event[2:] for event in trace if event[:2] == ("call", restored)]
        self.assertEqual({op for op, _, _ in restored_calls}, {"recover"})
        self.assertEqual(restored_calls[-2:], [("recover", "lost", "replayed")] * 2)

        lifecycle = result["lifecycle"]
        stop, = [index for index, event in enumerate(lifecycle) if event["event"] == "stop"]
        chain = lifecycle[stop - 1:stop + 4]
        self.assertEqual([(event["event"], event["pid"]) for event in chain], [
            ("dispatch", candidate), ("stop", candidate), ("exited", candidate),
            ("preflight_passed", candidate), ("started", restored),
        ])
        self.assertEqual(len({event["store"] for event in lifecycle}), 1)
        self.assertEqual({event["build"] for event in chain[:-1]}, {"v2"})
        self.assertEqual(chain[-1]["build"], "v1")
        self.assertEqual({key: chain[1][key] for key in result["stop"]}, result["stop"])
        self.assertEqual(result["stop"], {"pid": candidate, "operation": "fixture_lost", "job": "lost",
                                         "observed_status": "reply_lost", "decision": "STOP_AND_ROLLBACK",
                                         "reasons": ["uncertain_outcome"]})

    def test_no_stop_decision_does_not_open_restored_worker(self):
        decide = rollback.canary.decide

        def missing_signal(control, candidate, *, complete, hard_signals=()):
            # Synthetic monitor omission; the actual candidate still commits and loses the reply.
            return decide(control, candidate, complete=complete)

        with self.traced_workers() as trace, patch.object(rollback.canary, "decide", missing_signal):
            with self.assertRaisesRegex(AssertionError, "candidate stop.*HOLD"):
                rollback.worked()
        self.assert_no_restored_worker(trace)

    def test_failed_close_does_not_open_restored_worker(self):
        def failed_close(_directory):
            # Inject only the close error observed by the controller, after joining the real child.
            raise RuntimeError("synthetic close failure")

        with self.traced_workers(failed_close) as trace, self.assertRaisesRegex(RuntimeError, "synthetic close failure"):
            rollback.worked()
        self.assert_no_restored_worker(trace)

    def test_incompatible_preflight_does_not_open_restored_worker(self):
        for filename, query, reason in (
                ("business.sqlite", "PRAGMA user_version = 2", "store schema versions"),
                ("review.sqlite", "PRAGMA user_version = 2", "store schema versions"),
                ("business.sqlite", "UPDATE saved_drafts SET payload='[]'", "all-subject audit")):
            def damage(directory):
                with closing(sqlite3.connect(directory / filename)) as db, db:
                    db.execute(query)

            with self.subTest(filename=filename, query=query), self.traced_workers(damage) as trace:
                with self.assertRaisesRegex(AssertionError, reason):
                    rollback.worked()
                self.assert_no_restored_worker(trace)

    def test_restored_build_resolves_tasks_from_both_eras_and_replays_lost_commit(self):
        result = rollback.worked()
        self.assertEqual(len(set(result["pids"].values())), 3)
        before, pre_stop, handoff, after = (result[key] for key in ("before", "pre_stop", "handoff", "after"))
        for snapshot in (before, pre_stop, handoff, after):
            self.assertEqual(snapshot["schemas"], {"business.sqlite": 1, "review.sqlite": 1})
        self.assertEqual(before["saved"], pre_stop["saved"])
        self.assertEqual(pre_stop["saved"], [])
        self.assertEqual({row[2]: row[-1] for row in before["reviews"]},
                         {"pre-approve": "approve", "pre-deny": "deny"})
        pre_stop_jobs = {row[2]: row[-2] for row in pre_stop["checkpoints"]}
        self.assertEqual(pre_stop_jobs, dict.fromkeys(
            ("pre-approve", "pre-deny", "canary-approve", "canary-deny", "sync", "lost"), "pending"))
        self.assertEqual({row[2]: row[-2] for row in handoff["checkpoints"]}, dict(pre_stop_jobs, lost="saved"))
        self.assertEqual(pre_stop["reviews"], handoff["reviews"])
        self.assertEqual(handoff["reviews"], after["reviews"])
        undecided = result["undecided"]
        self.assertEqual(undecided["binding"]["job"], "sync")
        self.assertEqual(undecided["outcome"], {"status": "pending", "read_calls": 0,
                                               "receipt": None, "draft": None, "inserts": []})
        self.assertNotIn("sync", {row[2] for row in after["reviews"]})
        waiting, = [row for row in handoff["checkpoints"] if row[2] == "sync"]
        self.assertEqual([row for row in after["checkpoints"] if row[2] == "sync"], [waiting])
        terminal = {row[2]: row[-2:] for row in after["checkpoints"]}
        for job in ("pre-approve", "pre-deny", "canary-approve", "canary-deny"):
            with self.subTest(job=job):
                task = result["tasks"][job]
                self.assertEqual(task["pending"]["status"], "pending")
                self.assertEqual(task["pending"]["inserts"], [])
                outcome = task["outcome"]
                binding = task["binding"]
                fields = ("tenant", "actor", "job", "action", "revision", "digest")
                decision = "approve" if job.endswith("-approve") else "deny"
                self.assertEqual(pre_stop["reviews"].count([*(binding[key] for key in fields), decision]), 1)
                if decision == "approve":
                    self.assertEqual(outcome["status"], "saved")
                    self.assertEqual(outcome["inserts"], [outcome["receipt"]])
                    self.assertEqual(terminal[job], ["saved", outcome["receipt"]])
                else:
                    self.assertEqual(outcome["status"], "denied")
                    self.assertEqual(outcome["inserts"], [])
                    self.assertEqual(outcome["read_calls"], 0)
                    self.assertIsNone(outcome["receipt"])
                    self.assertIsNone(outcome["draft"])
                    self.assertEqual(terminal[job], ["denied", None])
        lost = result["lost"]
        original, = result["handoff"]["saved"]
        self.assertEqual(lost["injection"]["status"], "reply_lost")
        self.assertEqual(lost["injection"]["inserts"], [original[0]])
        self.assertEqual(lost["persisted_receipt"], original[0])
        for replay in (lost["replay"], lost["repeated"]):
            self.assertEqual((replay["status"], replay["receipt"], replay["draft"], replay["inserts"]),
                             ("replayed", original[0], original[-1], []))
        self.assertIn(original, result["after"]["saved"])
        self.assertEqual({row[3] for row in result["after"]["saved"]},
                         {"pre-approve", "canary-approve", "lost"})


class TransferRollbackTest(unittest.TestCase):
    def assert_no_result_or_side_effect(self, reply):
        self.assertEqual((reply["read_calls"], reply["inserts"], reply["receipt"], reply["draft"]),
                         (0, [], None, None))

    def test_wrong_actor_and_other_tenant_cannot_recover_or_inspect(self):
        wrong = rollback.wrong_actor()
        self.assertEqual(wrong["outcome"]["status"], "rejected")
        self.assertEqual(wrong["inspect"]["status"], "not_available")
        self.assertNotIn("binding", wrong["inspect"])
        self.assertEqual(wrong["cross_scope"]["status"], "forbidden")
        self.assertEqual(wrong["after"], wrong["before"])
        for reply in (wrong["outcome"], wrong["cross_scope"], wrong["inspect"]):
            self.assert_no_result_or_side_effect(reply)

    def test_stale_approval_does_not_advance_new_revision(self):
        stale = rollback.stale()
        self.assertEqual(stale["outcome"]["status"], "rejected")
        self.assertEqual(stale["current"]["status"], "pending")
        self.assertEqual(stale["old_binding"]["revision"], 1)
        self.assertEqual(stale["binding"], dict(stale["old_binding"], revision=2))
        old, = stale["original"]["checkpoints"]
        current, = stale["before"]["checkpoints"]
        self.assertEqual(old[3], 1)
        self.assertEqual(current, [*old[:3], 2, *old[4:]])
        self.assertEqual(current[-2:], ["pending", None])
        self.assertEqual(stale["original"]["reviews"], stale["before"]["reviews"])
        self.assertEqual(stale["after"]["reviews"], [["support", "mei", "export", "save_local_draft", 1,
                                                      stale["old_binding"]["digest"], "approve"]])
        self.assertEqual(stale["after"]["saved"], [])
        self.assertEqual(stale["after"], stale["before"])
        for reply in (stale["outcome"], stale["current"]):
            self.assert_no_result_or_side_effect(reply)

    def test_revocation_withholds_previously_releasable_receipt_without_undoing_commit(self):
        case = rollback.revoked()
        self.assertEqual(case["control"]["status"], "replayed")
        self.assertEqual(case["control"]["receipt"], case["after"]["saved"][0][0])
        self.assertEqual(case["outcome"]["status"], "replay_withheld")
        self.assertEqual(case["outcome"]["inserts"], [])
        self.assertIsNone(case["outcome"]["receipt"])
        self.assertIsNone(case["outcome"]["draft"])
        self.assertEqual(case["before"]["saved"], case["after"]["saved"])
        self.assertEqual(case["after"]["revocations"], [["support", "mei", "SYNC-POLICY"]])
    def test_corrupt_receipt_requires_reconciliation_instead_of_a_second_write(self):
        case = rollback.corrupt_receipt()
        self.assertEqual(case["original"]["checkpoints"], case["before"]["checkpoints"])
        self.assertNotEqual(case["original"]["saved"], case["before"]["saved"])
        self.assertEqual(case["after"], case["before"])
        self.assertEqual(case["outcome"], {"status": "inconsistent", "receipt": None, "draft": None,
                                           "read_calls": 0, "inserts": []})

    def test_incompatible_copy_is_refused_at_start_without_touching_either_store(self):
        case = rollback.incompatible()
        self.assertEqual(case["status"], "incompatible_schema")
        self.assertEqual(case["original"]["schema"], 1)
        self.assertEqual(case["before"]["schema"], 2)
        self.assertEqual(case["before"], case["after"])
        self.assertEqual(case["fingerprints"]["before"], case["fingerprints"]["after"])
        self.assertNotEqual(case["fingerprints"]["original"]["business.sqlite"],
                            case["fingerprints"]["after"]["business.sqlite"])
        self.assertEqual(case["fingerprints"]["original"]["review.sqlite"],
                         case["fingerprints"]["after"]["review.sqlite"])


if __name__ == "__main__":
    unittest.main()
