"""Local boundary tests only; this module never imports or runs LangGraph."""

from contextlib import contextmanager
from pathlib import Path
import runpy
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from host import ACTOR, CODE, JOB, P5, binding_fields, connect, open_store, put_review
import native_phase6 as native
from rehearsal import GOLD, hashes
from snapshot_history import frontier, invoke_latest, verify_advanced, verify_start


def config(key=None):
    values = {"thread_id": GOLD["thread"]}
    if key is not None:
        values["checkpoint_id"] = key
    return {"configurable": values}


def snapshot(key, parent, status):
    return SimpleNamespace(config=config(key), parent_config=config(parent) if parent else None,
                           values={"status": status}, next=(), tasks=())


class HistoryProbe:
    """Scripted public observations, not a graph implementation or an SDK reproduction."""

    def __init__(self, *rows):
        self.rows = rows
        self.calls = []

    def get_state(self, lookup):
        key = lookup["configurable"].get("checkpoint_id")
        return next(row for row in self.rows if key is None or row.config == lookup)

    def get_state_history(self, lookup):
        return iter(self.rows)

    def invoke(self, signal, lookup, **kwargs):
        self.calls.append((signal, lookup, kwargs))


def stage_committed(business):
    with open_store(business) as store:
        current = store.stage(ACTOR, JOB, 2, P5["QUESTION"])
        store.resume(ACTOR, JOB, current.binding, P5["Review"].APPROVE)
    return current


def approve_fixture(directory):
    with connect(directory / "reviews.sqlite", write=True) as db:
        db.execute("CREATE TABLE decisions (tenant, actor, job, action, revision, digest, decision)")
    put_review(directory, GOLD["task"], "approve")


class CheckpointBoundaryTests(unittest.TestCase):
    def test_thread_lookup_drops_pinned_id_and_readback_detects_an_old_fork(self):
        old = snapshot("older", None, "pending")
        latest = snapshot("latest", "older", "reviewed")
        graph = HistoryProbe(latest, old)
        before = frontier(graph, config())
        self.assertEqual((before["id"], before["older"]["id"]), ("latest", "older"))
        self.assertIs(verify_start(graph, config(), before), latest)
        invoke_latest(graph, latest.config, None)
        self.assertEqual(graph.calls, [(None, config(), {"durability": "sync"})])
        advanced = snapshot("advanced", "latest", "saved")
        observed = verify_advanced(HistoryProbe(advanced, latest, old), config(), before)
        self.assertEqual(observed["parent_path_to_previous_latest"], ["advanced", "latest"])
        fork = snapshot("fork", "older", "saved")
        with self.assertRaisesRegex(AssertionError, "did not descend"):
            verify_advanced(HistoryProbe(fork, latest, old), config(), before)
        changed = snapshot("older", None, "changed")
        with self.assertRaisesRegex(AssertionError, "older checkpoint after invoke"):
            verify_advanced(HistoryProbe(advanced, latest, changed), config(), before)

    def test_legacy_binding_uses_fixed_host_and_compares_values_across_namespaces(self):
        fresh = runpy.run_path(str(CODE / "phase5-agent-harness/harness-lab/main.py"))
        task = GOLD["task"]
        original = fresh["Binding"](fresh["Actor"](task["tenant"], task["actor"]), task["job"],
                                    task["revision"], task["digest"])
        candidate = native.interpret({"revision": task["revision"], "digest": task["digest"], "actor": "ignored"})
        self.assertIsNot(type(original), type(candidate))
        self.assertEqual(binding_fields(original), task)
        self.assertEqual(binding_fields(candidate), task)

    def test_corrupt_or_extra_receipts_fail_closed(self):
        with TemporaryDirectory() as tmp:
            directory = Path(tmp)
            business = directory / "business.sqlite"
            current = stage_committed(business)
            approve_fixture(directory)
            values = {"status": "reviewed", "revision": current.binding.version, "digest": current.binding.digest}
            self.assertIsNone(native.check_authority(directory, values)[0])
            with patch.dict(native.SOURCES, {"KB-01": "fixed fixture source has changed"}):
                self.assertEqual(native.check_authority(directory, values)[0], "replay_withheld")
            with connect(business, write=True) as db:
                db.execute("INSERT INTO saved_drafts SELECT 'extra', 'other', actor, job, payload FROM saved_drafts")
            self.assertEqual(native.check_authority(directory, values)[0], "inconsistent")
            with connect(business, write=True) as db:
                db.execute("DELETE FROM saved_drafts WHERE op_id='extra'")
                db.execute("UPDATE saved_drafts SET payload='[]'")
            self.assertEqual(native.check_authority(directory, values)[0], "inconsistent")

    def test_inconsistent_applied_lifecycle_never_opens_the_working_saver(self):
        task = GOLD["task"]
        with TemporaryDirectory() as tmp:
            working = Path(tmp)
            business = working / "business.sqlite"
            current = stage_committed(business)
            approve_fixture(working)
            (working / "graph.sqlite").write_bytes(b"opaque stand-in; not a saver")
            origin = hashes(working, native.BUNDLE)
            saved_before_apply = snapshot("latest", "older", "pending")
            saved_before_apply.values.update(revision=task["revision"], digest=task["digest"])
            saved_before_apply.next = ("review",)
            saved_before_apply.tasks = (SimpleNamespace(interrupts=(SimpleNamespace(
                value={"job": task["job"], "revision": task["revision"]}),)),)
            graph = HistoryProbe(saved_before_apply, snapshot("older", None, "start"))
            before = frontier(graph, config())
            self.assertEqual(native.preflight(working, before["state"]), "inconsistent")

            @contextmanager
            def observe_only(probe, **kwargs):
                self.assertNotEqual(probe, working)
                self.assertEqual(kwargs, {})
                yield graph

            result = native.advance(working, observe_only, native.interpret, before)
            self.assertEqual(result["reply"], {"status": "inconsistent", "receipt": None, "draft": None})
            self.assertEqual((result["inserts"], result["business_results"], graph.calls), ([], 0, []))
            self.assertEqual(hashes(working, native.BUNDLE), origin)


if __name__ == "__main__":
    unittest.main()
