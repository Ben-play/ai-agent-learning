from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from draft_graph import (
    ACTOR, CONFIG, JOB, LostReply, Review, inspect_business, open_graph, open_store,
    record_fixture_review, stage_revisions,
)
from read_graph import P5, QUESTION, REPHRASE, ReadCall, Task, build_reader, read_acceptance

WORKER = r'''
import json, runpy, sys
from pathlib import Path

lab = runpy.run_path(sys.argv[1])
attempts = []
try:
    row = lab["run_step"](Path(sys.argv[2]), sys.argv[3], on_write=attempts.append,
                          lose_reply=sys.argv[4] == "lose")
except lab["LostReply"]:
    row = {"status": "reply_lost"}
print(json.dumps({"row": row, "attempts": attempts}))
'''
ENTRY = Path(__file__).resolve().parents[1] / "draft_graph.py"


def step(directory, command, *, lose=False):
    result = subprocess.run([sys.executable, "-I", "-X", "utf8", "-c", WORKER,
                             str(ENTRY), str(directory), command, "lose" if lose else "normal"],
                            capture_output=True, encoding="utf-8", check=False, timeout=20)
    if result.returncode or result.stderr:
        raise AssertionError((result.returncode, result.stdout, result.stderr))
    row = json.loads(result.stdout)
    return row["row"], row["attempts"]


class ReadTests(unittest.TestCase):
    def test_graph_uses_same_read_contract_as_harness(self):
        self.assertEqual(read_acceptance(), {
            "baseline": ("failed", 1, ()),
            "dynamic": ("complete", 2, ("KB-01", "KB-02")),
            "budget": ("exhausted", 1, ()),
        })

    def test_zero_budget_and_invalid_call_make_no_dispatch(self):
        observed = []
        read = build_reader(on_dispatch=observed.append)
        self.assertEqual(read(ReadCall(Task.EVIDENCE_QA, REPHRASE), budget=0).status, "exhausted")
        self.assertEqual(read(ReadCall(Task.EVIDENCE_QA, " ")).status, "failed")
        self.assertEqual(observed, [])

    def test_last_permitted_read_can_complete(self):
        observed = []
        read = build_reader(on_dispatch=observed.append)
        first = ReadCall(Task.EVIDENCE_QA, QUESTION)
        self.assertEqual(read(first, budget=1), P5["run_loop"](first, budget=1))
        self.assertEqual(observed, [QUESTION])


def draft_payload(draft):
    return {"title": draft.title, "body": draft.body, "source_ids": list(draft.source_ids)}


def phase5_resume(directory, binding, review, *, lose=False):
    attempts = []
    with open_store(directory / "business.sqlite", on_draft_write_attempt=attempts.append) as store:
        try:
            result = store.resume(ACTOR, JOB, binding, review, lose_reply=lose)
        except LostReply:
            return {"status": "reply_lost"}, attempts
    return {"status": result.status, "op_id": result.op_id,
            "draft": draft_payload(result.draft) if result.draft else None}, attempts


class DurableTests(unittest.TestCase):
    def test_same_preview_after_real_process_exit_without_approval(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp)
            staged = step(path, "stage")  # The worker exits before step returns.
            cp, count = inspect_business(path)
            self.assertEqual((cp.binding.version, count), (2, 0))
            preview = {"revision": 2, **draft_payload(cp.draft)}
            self.assertEqual(staged, ({"status": "pending", "interrupt": {"job": JOB, "revision": 2},
                                       "preview": preview}, []))
            reopened = step(path, "inspect")  # No draft fields are passed to this worker.
            self.assertEqual(reopened, ({"revision": 2, "status": "pending", "next": ["review"],
                                         "preview": preview}, []))
            self.assertEqual(reopened[0]["preview"], staged[0]["preview"])
            self.assert_graph_state(path, cp, "pending")
            self.assertEqual(step(path, "resume"), ({"status": "pending"}, []))
            self.assertEqual(inspect_business(path), (cp, 0))

    def test_inspect_does_not_show_a_replacement_as_the_paused_preview(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp)
            step(path, "stage")
            with open_store(path / "business.sqlite") as store:
                store.stage(ACTOR, JOB, 3, P5["QUESTION"])
            self.assertEqual(step(path, "inspect"), ({"revision": 2, "status": "pending", "next": ["review"],
                                                      "preview": None}, []))

    def test_phase5_and_graph_save_acceptance_matrix(self):
        # Reply statuses are separate. The common expectation is the durable business effect.
        # Each effect is (business checkpoint status, INSERT attempts for this call, saved rows).
        for case, phase5_reply, graph_reply, effect in (
            ("no review", "rejected", "pending", ("pending", 0, 0)),
            ("wrong actor", "rejected", "pending", ("pending", 0, 0)),
            ("wrong tenant", "rejected", "pending", ("pending", 0, 0)),
            ("wrong job", "rejected", "pending", ("pending", 0, 0)),
            ("wrong action", "rejected", "pending", ("pending", 0, 0)),
            ("denial", "denied", "denied", ("denied", 0, 0)),
            ("old approval", "rejected", "pending", ("pending", 0, 0)),
            ("valid save", "saved", "saved", ("saved", 1, 1)),
            ("postcommit lost reply", "reply_lost", "reply_lost", ("saved", 1, 1)),
        ):
            with self.subTest(case=case), TemporaryDirectory() as tmp:
                phase5, graph = Path(tmp) / "phase5", Path(tmp) / "graph"
                phase5.mkdir()
                graph.mkdir()
                old, original = stage_revisions(phase5)
                staged, attempts = step(graph, "stage")
                self.assertEqual((staged["status"], attempts), ("pending", []))
                self.assertEqual(inspect_business(graph), (original, 0))
                binding = original.binding
                reviewed = {
                    "wrong actor": replace(binding, actor=replace(ACTOR, name="other-reviewer")),
                    "wrong tenant": replace(binding, actor=replace(ACTOR, tenant="other-tenant")),
                    "wrong job": replace(binding, job="other-job"),
                    "wrong action": replace(binding, action="submit"),
                    "old approval": old.binding,
                }.get(case, binding)
                review = {"no review": None, "denial": Review.DENY}.get(case, Review.APPROVE)
                if review is not None:
                    record_fixture_review(graph, reviewed, review)
                lose = case == "postcommit lost reply"
                direct = phase5_resume(phase5, reviewed, review, lose=lose)
                facade = step(graph, "resume", lose=lose)
                before = self.assert_save_outcome(phase5, direct, original, phase5_reply, effect)
                self.assertEqual(self.assert_save_outcome(graph, facade, original, graph_reply, effect), before)
                if lose:
                    snapshot, attempts = step(graph, "inspect")
                    self.assertEqual((snapshot["next"], attempts), (["apply_review"], []))
                    replay_effect = ("saved", 0, 1)
                    for directory, replay in ((phase5, phase5_resume(phase5, reviewed, review)),
                                              (graph, step(graph, "recover"))):
                        after = self.assert_save_outcome(directory, replay, original, "replayed", replay_effect)
                        self.assertEqual(after, before)
                    self.assert_graph_state(graph, before, "replayed")
                    self.assertEqual(step(graph, "recover"), ({"status": "not_runnable"}, []))

    def assert_save_outcome(self, directory, observation, original, reply, effect):
        row, attempts = observation
        checkpoint, saved_rows = inspect_business(directory)
        self.assertEqual((checkpoint.status, len(attempts), saved_rows), effect)
        self.assertEqual((checkpoint.binding, checkpoint.draft), (original.binding, original.draft))
        if saved_rows:
            self.assertTrue(checkpoint.op_id)
        else:
            self.assertIsNone(checkpoint.op_id)
        if attempts:
            self.assertEqual(attempts, [checkpoint.op_id])
        if reply in ("pending", "reply_lost"):
            self.assertEqual(row, {"status": reply})
        else:
            has_draft = reply in ("saved", "replayed")
            self.assertEqual(row, {"status": reply, "op_id": checkpoint.op_id if has_draft else None,
                                   "draft": draft_payload(original.draft) if has_draft else None})
        return checkpoint

    def assert_graph_state(self, directory, checkpoint, status):
        with open_graph(directory) as graph:
            snapshot = graph.get_state(CONFIG)
        expected = {"revision": checkpoint.binding.version, "digest": checkpoint.binding.digest, "status": status}
        if checkpoint.op_id is not None:
            expected["op_id"] = checkpoint.op_id
        self.assertEqual(snapshot.values, expected)


if __name__ == "__main__":
    unittest.main()
