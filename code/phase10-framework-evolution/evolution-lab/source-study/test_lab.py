from dataclasses import replace
from pathlib import Path
import runpy
import unittest

LAB = runpy.run_path(str(Path(__file__).with_name("lab.py")))


class SourceStudyTests(unittest.TestCase):
    def check(self, records, status, receipt=None, *, tenant="support", actor="mei"):
        self.assertEqual(LAB["inspect"](records, tenant=tenant, actor=actor),
                         {"status": status, "receipt": receipt})

    def test_transcript_does_not_choose_approval(self):
        pending = LAB["PENDING"]
        self.check(pending, "wait_for_review")
        self.check(replace(pending, transcript=(), approval=LAB["BOUND"]), "ready_for_host_review")
        self.check(replace(pending, approval=replace(LAB["BOUND"], revision=1)), "wait_for_review")

    def test_exact_receipt_without_relying_on_transcript(self):
        record = LAB["COMMITTED"]
        receipt, = record.receipts
        self.check(replace(record, transcript=()), "receipt_verified", "fixture-receipt-02")
        for changed in ((), (receipt, receipt), (replace(receipt, body="同步任务每天 03:00 运行。"),),
                        (replace(receipt, binding=replace(receipt.binding, action="preview")),)):
            self.check(replace(record, receipts=changed), "reconcile")
        self.check(record, "not_available", tenant="operations")

    def test_different_ids_on_the_same_binding_require_reconciliation(self):
        record = LAB["COMMITTED"]
        receipt, = record.receipts
        duplicate = replace(receipt, operation_id="another-fixture-receipt")
        self.check(replace(record, receipts=(receipt, duplicate)), "reconcile")
        unrelated = replace(duplicate, binding=replace(receipt.binding, task="other-training-task"))
        self.check(replace(record, receipts=(receipt, unrelated)), "receipt_verified", receipt.operation_id)
        id_collision = replace(unrelated, operation_id=receipt.operation_id)
        self.check(replace(record, receipts=(receipt, id_collision)), "reconcile")

    def test_existing_receipt_keeps_ambiguous_task_in_reconciliation(self):
        record = LAB["COMMITTED"]
        task = replace(record.task, operation_id=None, committed_hint=False)
        self.check(replace(record, task=task), "reconcile")


if __name__ == "__main__":
    unittest.main()
