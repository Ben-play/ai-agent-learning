"""Run with python -B -m unittest -v test_contract in this directory."""

import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import contract
import rehearsal
from host import connect, put_review, reply


class CheckpointContractTests(unittest.TestCase):
    def test_old_program_stops_at_three_different_boundaries(self):
        seeds = contract.run("seed")
        self.assertEqual(tuple(seeds), ("pending", "approved", "committed"))
        pending, approved, committed = seeds.values()
        self.assertEqual(pending["graph"]["next"], ["review"])
        self.assertEqual(approved["graph"], committed["graph"])
        self.assertEqual(approved["ledger"]["saved"], [])
        self.assertEqual(len(committed["ledger"]["saved"]), 1)
        self.assertIsNone(committed["fault_observer"]["reply"]["receipt"])

    def test_compare_checks_full_matrix_and_same_origin(self):
        report = contract.run("compare")  # Compares every observed effect with independent JSON gold.
        self.assertEqual(len(report), 17)
        for case, row in report.items():
            with self.subTest(case=case):
                old, new = row["arms"].values()
                self.assertEqual(old["from_origin"], row["before"]["origin"])
                self.assertEqual(new["from_origin"], row["before"]["origin"])
                self.assertEqual(old["from_prepared"], row["prepared"]["origin"])
                self.assertEqual(new["from_prepared"], row["prepared"]["origin"])
                self.assertEqual(old["reply"], new["reply"])
                self.assertEqual(old["ledger"], new["ledger"])
        self.assertEqual(report["replay"]["arms"]["v2"]["nodes"], ["apply_review", "finish"])
        self.assertIsNone(report["source_revoked"]["arms"]["v2"]["reply"]["draft"])

    def test_named_compare_cases_verify_prepared_inputs(self):
        report = contract.run("compare", cases=("wrong_action", "wrong_revision", "pending"))
        self.assertEqual(tuple(report), ("wrong_action", "wrong_revision", "pending"))
        digest = "d45c47d3c0bbccfc503cd56ac79c53aa7fc2b1a3ef40d15f1586505ed448745a"
        for case, action, revision in (("wrong_action", "submit", 2), ("wrong_revision", "save_local_draft", 1)):
            with self.subTest(case=case):
                row = report[case]
                before, prepared = row["before"], row["prepared"]
                self.assertEqual(prepared["ledger"]["reviews"],
                                 [["training", "reviewer", "export", action, revision, digest, "approve"]])
                self.assertEqual(prepared["graph"], before["graph"])
                self.assertEqual({name for name in before["origin"] if before["origin"][name] != prepared["origin"][name]},
                                 {"reviews.sqlite"})
                for arm in row["arms"].values():
                    self.assertEqual(arm["from_prepared"], prepared["origin"])
                    self.assertEqual(arm["ledger"], prepared["ledger"])
                    self.assertEqual(arm["reply"], reply("rejected"))
        pending = report["pending"]
        self.assertEqual(pending["prepared"]["origin"], pending["before"]["origin"])

    def test_refusal_restarts_and_old_path_keeps_business_contract(self):
        report = contract.run("fallback")
        self.assertEqual(len(report), 11)
        for row in report.values():
            self.assertEqual(len(row["refused"]), 2)
            prepared = row["prepared"]
            for refusal in row["refused"]:
                self.assertEqual(refusal, {"reply": reply("migration_refused"), "nodes": [], "calls": 0,
                                           "inserts": [], "origin": prepared["origin"], "after": prepared["origin"],
                                           "graph": prepared["graph"], "ledger": prepared["ledger"]})
            self.assertEqual(row["arms"]["v1"]["from_prepared"], prepared["origin"])
            self.assertEqual(row["arms"]["v1"]["from_origin"], row["before"]["origin"])
        for case in ("wrong_actor", "wrong_tenant", "wrong_revision", "old_review", "source_revoked"):
            with self.subTest(case=case):
                row = report[case]
                old = row["arms"]["v1"]
                self.assertNotEqual(row["prepared"]["origin"], row["before"]["origin"])
                self.assertEqual(old["reply"], reply("replay_withheld" if case == "source_revoked" else "rejected"))
                self.assertEqual((old["nodes"], old["calls"], old["inserts"]), ([], 0, []))
                self.assertEqual(old["after"], row["prepared"]["origin"])
                self.assertEqual(old["ledger"], row["prepared"]["ledger"])
                self.assertEqual(old["ledger"]["saved"], row["before"]["ledger"]["saved"])
        for case in ("missing_receipt", "mismatched_receipt"):
            row = report[case]
            old = row["arms"]["v1"]
            self.assertNotEqual(row["prepared"]["origin"], row["before"]["origin"])
            self.assertEqual(old["reply"], reply("inconsistent"))
            self.assertEqual((old["nodes"], old["calls"], old["inserts"]), (["apply_review"], 1, []))
            self.assertEqual(old["after"]["business.sqlite"], row["prepared"]["origin"]["business.sqlite"])
            self.assertEqual(old["ledger"], row["prepared"]["ledger"])

    def test_fallback_reopens_one_candidate_and_an_independent_old_copy(self):
        with patch.object(rehearsal.subprocess, "run", wraps=subprocess.run) as launch:
            row = contract.run("fallback", cases="source_revoked")["source_revoked"]
        commands = [call.args[0] for call in launch.call_args_list]
        first, second, old = [command[-3:] for command in commands]
        self.assertEqual(first, second)
        self.assertEqual(first[::2], ["_advance", "2"])
        self.assertEqual(old[::2], ["_advance", "1"])
        self.assertNotEqual(first[1], old[1])
        self.assertEqual(row["arms"]["v1"]["from_prepared"], row["prepared"]["origin"])

    def test_case_selection_rejects_empty_duplicate_or_out_of_mode_names(self):
        for mode, cases in (("compare", ()), ("compare", ("approve", "approve")),
                            ("fallback", ("revised",)), ("seed", ("pending",)), ("stage", ("approve",))):
            with self.subTest(mode=mode, cases=cases), self.assertRaises(ValueError):
                contract.run(mode, cases=cases)

    def test_cli_runs_only_named_cases(self):
        command = [sys.executable, "-B", contract.__file__]
        result = subprocess.run([*command, "fallback", "--case", "old_review", "--case", "source_revoked"],
                                check=True, capture_output=True, encoding="utf-8", timeout=30)
        self.assertEqual(tuple(json.loads(result.stdout)), ("old_review", "source_revoked"))
        bad = subprocess.run([*command, "fallback", "--case", "revised"],
                             capture_output=True, encoding="utf-8", timeout=30)
        self.assertEqual(bad.returncode, 2)
        self.assertIn("unknown fallback case: revised", bad.stderr)
        self.assertEqual(bad.stdout, "")

    def test_one_preparation_supplies_both_compare_arms(self):
        with patch.object(rehearsal, "change_fixture", wraps=rehearsal.change_fixture) as injector:
            row = contract.run("compare", cases="approve")["approve"]
        self.assertEqual(injector.call_count, 1)
        self.assertNotEqual(row["before"]["origin"], row["prepared"]["origin"])
        for arm in row["arms"].values():
            self.assertEqual(arm["from_prepared"], row["prepared"]["origin"])
            self.assertEqual(arm["ledger"]["reviews"], row["prepared"]["ledger"]["reviews"])

    def test_bad_action_cannot_pass_as_a_wrong_job_alone_or_in_combination(self):
        inject = rehearsal.change_fixture
        for replacement in ("wrong_job", "wrong_action"):
            def drift(directory, case, before):
                inject(directory, replacement, before)
                with connect(directory / "reviews.sqlite", write=True) as db:
                    db.execute("UPDATE decisions SET job='another-job'")

            # Either wrong field alone would cause the same rejection. Verify the inputs before dispatch.
            with (
                self.subTest(replacement=replacement),
                patch.object(rehearsal, "change_fixture", drift),
                patch.object(contract, "advance", side_effect=AssertionError("dispatched before checking inputs")),
                self.assertRaisesRegex(AssertionError, "approval binding readback"),
            ):
                contract.run("compare", cases="wrong_action")

    def test_revision_only_case_cannot_pass_as_old_review(self):
        inject = rehearsal.change_fixture

        def drift(directory, case, before):
            inject(directory, "old_review", before)

        with patch.object(rehearsal, "change_fixture", drift), self.assertRaisesRegex(
                AssertionError, "approval binding readback"):
            contract.run("compare", cases="wrong_revision")

    def test_post_injection_receipt_fault_does_not_pass_if_source_also_changes(self):
        inject = rehearsal.change_fixture

        def drift(directory, case, before):
            inject(directory, case, before)
            with connect(directory / "reviews.sqlite", write=True) as db:
                db.execute("DELETE FROM sources WHERE source_id='KB-02'")

        with patch.object(rehearsal, "change_fixture", drift), self.assertRaisesRegex(
                AssertionError, "current source records"):
            contract.run("fallback", cases="missing_receipt")

    def test_bundle_verification_detects_changed_or_unclosed_inputs(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            sealed = root / "sealed"
            origin = rehearsal.seed_bundle(contract, sealed, "pending", "named")["origin"]
            copy = rehearsal.clone(sealed, root / "copy", origin)
            journal = copy / "business.sqlite-wal"
            journal.touch()
            with self.assertRaisesRegex(AssertionError, "closed bundle entries"):
                rehearsal.hashes(copy, origin)
            with connect(sealed / "reviews.sqlite", write=True) as db:
                db.execute("DELETE FROM sources")
            with self.assertRaisesRegex(AssertionError, "sealed origin before copy"):
                rehearsal.clone(sealed, root / "other", origin)

    def test_preflight_refuses_unknown_node_and_lifecycle_mismatch_without_dispatch(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            sealed = root / "sealed"
            before = rehearsal.seed_bundle(contract, sealed, "pending", "named")
            for index, (change, status) in enumerate((
                ({"next": ["unexpected"]}, "migration_refused"),
                ({"next": "review"}, "migration_refused"),
                ({"next": ["apply_review"], "interrupts": []}, "migration_refused"),
                ({}, "inconsistent"),
            )):
                with self.subTest(change=change, status=status):
                    copy = rehearsal.clone(sealed, root / str(index), before["origin"])
                    snapshot = contract.inspect(copy)
                    put_review(copy, snapshot["values"]["binding"], "approve")
                    if change:
                        contract.write(copy, dict(snapshot, **change))
                    else:
                        with connect(copy / "business.sqlite", write=True) as db:
                            db.execute("UPDATE checkpoints SET status='denied'")
                    origin = rehearsal.hashes(copy, before["origin"])
                    for version in (1, 2):
                        self.assertEqual(contract.advance(copy, version),
                                         {"reply": reply(status), "nodes": [], "calls": 0, "inserts": []})
                        self.assertEqual(rehearsal.hashes(copy, origin), origin)

    def test_readback_rejects_an_extra_row_outside_the_demo_subject(self):
        with TemporaryDirectory() as tmp:
            directory = Path(tmp) / "seed"
            before = rehearsal.seed_bundle(contract, directory, "committed", "named")
            with connect(directory / "business.sqlite", write=True) as db:
                db.execute("""INSERT INTO saved_drafts SELECT 'extra', 'elsewhere', actor, job, payload
                              FROM saved_drafts""")
            with self.assertRaisesRegex(AssertionError, "all durable drafts"):
                rehearsal.check_ledger(rehearsal.audit(directory), before["ledger"])


if __name__ == "__main__":
    unittest.main()
