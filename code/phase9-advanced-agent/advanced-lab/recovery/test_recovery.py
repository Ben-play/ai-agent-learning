"""Exercise the fixed worker from fresh interpreter processes."""

from pathlib import Path
import runpy
import unittest

LAB = runpy.run_path(str(Path(__file__).with_name("lab.py")))


class LongTaskTests(unittest.TestCase):
    def test_same_input_rehearsal_measures_the_benefit_of_persisting_stop(self):
        run = runpy.run_path(str(Path(__file__).with_name("checkpoint.py")))["run"]
        result = run()
        original = result["comparison"]["volatile_stop_baseline"]
        durable = result["comparison"]["durable_stop_candidate"]
        self.assertEqual(original["before_cancel"], durable["before_cancel"])
        self.assertEqual(original["before_cancel"]["citation"],
                         ["SYNC-POLICY", 1, "§1", "同步任务每天 02:00 运行。"])
        self.assertEqual(original["before_cancel"]["remaining"], 1)
        self.assertEqual(original["cancel_result"], "not_persisted")
        self.assertEqual(durable["cancel_result"], "persisted")
        self.assertEqual((original["after_restart"]["state"], original["after_restart"]["insert_attempts"],
                          original["committed_rows"]), ("saved", 1, 1))
        self.assertEqual((durable["after_restart"]["state"], durable["after_restart"]["insert_attempts"],
                          durable["committed_rows"]), ("cancelled", 0, 0))
        self.assertEqual(result["benefit"], {"subsequent_steps_avoided": 1, "inserts_avoided": 1})
        self.assertEqual(result["lost_reply_control"]["new_insert_attempts"], 0)

    def test_waiting_then_cancel_keeps_no_future_effects(self):
        with LAB["trial"]() as t:
            self.assertEqual(t.call("start", budget=3)["state"], "ready")
            self.assertEqual(t.call("advance")["remaining"], 2)
            pending = t.call("advance")
            self.assertEqual((pending["state"], pending["remaining"]), ("pending_approval", 1))
            waiting = t.call("advance")
            self.assertEqual(waiting["events"], pending["events"])
            cancelled = t.call("cancel")
            for command in ("approve", "advance", "recover"):
                row = t.call(command)
                self.assertEqual((row["state"], row["remaining"], row["events"], row["insert_attempts"]),
                                 ("cancelled", 1, cancelled["events"], 0))
                self.assertIsNone(row["receipt"])
            self.assertEqual(t.durable_rows(), [])

    def test_budget_is_not_refilled_and_exact_limit_can_save(self):
        for budget, expected in ((2, "exhausted"), (3, "saved")):
            with self.subTest(budget=budget), LAB["trial"]("retention") as t:
                t.call("start", budget=budget)
                t.call("advance")
                t.call("advance")
                t.call("approve")
                result = t.call("advance")
                self.assertEqual((result["state"], result["remaining"]), (expected, 0))
                self.assertEqual(result["insert_attempts"], int(expected == "saved"))
                self.assertEqual(len(t.durable_rows()), int(expected == "saved"))
                self.assertEqual(t.call("advance")["events"], result["events"])
                if expected == "saved":
                    self.assertEqual(t.durable_rows()[0]["citation"],
                                     ["EXPORT-POLICY", 1, "§1", "导出文件生成后保留 7 天。"])

    def test_lost_reply_recovery_does_not_resave_and_late_cancel_does_not_undo(self):
        with LAB["trial"]() as t:
            t.call("start", budget=3)
            t.call("advance")
            t.call("advance")
            t.call("approve")
            self.assertEqual(t.lose_reply(), {"exit_code": 19, "stdout": ""})
            before = t.durable_rows()
            self.assertEqual(len(before), 1)
            one, two = t.call("recover"), t.call("recover")
            for row in (one, two, t.call("cancel")):
                self.assertEqual((row["state"], row["receipt"], row["insert_attempts"], row["remaining"]),
                                 ("saved", before[0]["op_id"], 0, 0))
                self.assertEqual(row["events"], ["retrieve", "preview", "save"])
            self.assertEqual(t.durable_rows(), before)

    def test_zero_budget_and_missing_evidence_are_distinct(self):
        with LAB["trial"]("missing") as zero, LAB["trial"]("missing") as missing:
            zero.call("start", budget=0)
            missing.call("start", budget=2)
            exhausted, denied = zero.call("advance"), missing.call("advance")
            self.assertEqual((exhausted["state"], exhausted["events"]), ("exhausted", []))
            self.assertEqual((denied["state"], denied["events"], denied["remaining"]),
                             ("needs_evidence", ["retrieve"], 1))
            for t, row in ((zero, exhausted), (missing, denied)):
                for command in ("approve", "advance", "recover"):
                    self.assertEqual(t.call(command), row)
                self.assertEqual(t.durable_rows(), [])

    def test_start_cannot_replace_a_terminal_task(self):
        with LAB["trial"]() as t:
            t.call("start", budget=3)
            t.call("cancel")
            with self.assertRaisesRegex(RuntimeError, "already started"):
                t.call("start", budget=3)
            self.assertEqual(t.call("advance")["state"], "cancelled")


if __name__ == "__main__":
    unittest.main()
