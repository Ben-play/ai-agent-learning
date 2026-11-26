"""Handwritten expectations for two independent in-memory trust boundaries."""

from dataclasses import asdict, replace
import unittest

import l90_a2a as a2a
import l91_mcp as mcp
from support_case import LIN, MEI, OTHER_MEI, Evidence

EXPORT = Evidence("EXPORT-POLICY", 1, "§1", "导出文件生成后保留 7 天。")
SYNC = Evidence("SYNC-POLICY", 1, "§1", "同步任务每天 02:00 运行。")


class TaskBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.desk = a2a.TaskDesk()

    def test_card_does_not_allow_submit_lookup_or_cancel(self) -> None:
        card = self.desk.discover()
        self.assertEqual(card.capability, "support-evidence")
        for actor in (LIN, OTHER_MEI, None):
            self.assertEqual(self.desk.submit(actor, "task-export"), a2a.Reply("not_found"))
        started = self.desk.submit(MEI, "task-export")
        self.assertEqual(started, a2a.Reply("ok", a2a.Task(
            "task-export", MEI, "classroom-policy-desk", a2a.State.WORKING)))
        for actor, task_id in ((LIN, "task-export"), (OTHER_MEI, "task-export"), (MEI, "absent")):
            self.assertEqual(self.desk.get_task(actor, task_id), a2a.Reply("not_found"))
            self.assertEqual(self.desk.cancel_task(actor, task_id), a2a.Reply("not_found"))
        self.assertEqual(self.desk.get_task(MEI, "task-export"), started)
        self.assertEqual(self.desk.submit(MEI, "task-export"), a2a.Reply("already_exists"))

    def test_late_result_does_not_populate_canceled_task(self) -> None:
        self.desk.submit(MEI, "task-export")
        canceled = self.desk.cancel_task(MEI, "task-export")
        self.assertEqual(canceled, a2a.Reply("ok", a2a.Task(
            "task-export", MEI, "classroom-policy-desk", a2a.State.CANCELED)))
        self.assertEqual(canceled.task.state.value, "CANCELED")
        self.assertEqual(self.desk.accept_result("task-export", a2a.PeerResult(
            "task-export", "classroom-policy-desk", EXPORT)), "not_working")
        self.assertEqual(self.desk.cancel_task(MEI, "task-export"), a2a.Reply("not_cancelable"))
        self.assertEqual(self.desk.submit(MEI, "task-export"), a2a.Reply("already_exists"))
        self.assertEqual(self.desk.get_task(MEI, "task-export"), canceled)

    def test_result_binding_and_completion(self) -> None:
        started = self.desk.submit(MEI, "task-sync")
        other = self.desk.submit(MEI, "task-export")
        genuine = a2a.PeerResult("task-sync", "classroom-policy-desk", SYNC)
        for result, expected in (
            (replace(genuine, task_id="task-export"), "binding_mismatch"),
            (replace(genuine, peer="other-classroom-desk"), "binding_mismatch"),
            (replace(genuine, evidence=EXPORT), "evidence_mismatch"),
            (replace(genuine, evidence=replace(SYNC, version=2)), "evidence_mismatch"),
        ):
            with self.subTest(result=result):
                self.assertEqual(self.desk.accept_result("task-sync", result), expected)
                self.assertEqual(self.desk.get_task(MEI, "task-sync"), started)
                self.assertEqual(self.desk.get_task(MEI, "task-export"), other)
        self.assertEqual(self.desk.accept_result("absent", genuine), "not_found")
        self.assertEqual(self.desk.accept_result("task-sync", genuine), "accepted")
        completed = a2a.Reply("ok", a2a.Task(
            "task-sync", MEI, "classroom-policy-desk", a2a.State.COMPLETED, SYNC))
        self.assertEqual(self.desk.cancel_task(MEI, "task-sync"), a2a.Reply("not_cancelable"))
        self.assertEqual(self.desk.accept_result("task-sync", genuine), "not_working")
        self.assertEqual(self.desk.get_task(MEI, "task-sync"), completed)


class PolicyBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = mcp.ReadObserver()
        self.boundary = mcp.PolicyBoundary(self.store)

    def test_context_gate_and_independent_zero_reads(self) -> None:
        for context, reason in (
            (None, "missing_context"),
            (asdict(mcp.SUPPORT_CONTEXT), "invalid_context"),
            (replace(mcp.SUPPORT_CONTEXT, issuer="classroom-other-issuer"), "issuer_mismatch"),
            (replace(mcp.SUPPORT_CONTEXT, audience="classroom-index-reader"), "audience_mismatch"),
            (replace(mcp.SUPPORT_CONTEXT, scopes=frozenset({"queue:read"})), "insufficient_scope"),
            (replace(mcp.SUPPORT_CONTEXT, actor=LIN), "owner_mismatch"),
            (replace(mcp.SUPPORT_CONTEXT, actor=OTHER_MEI), "owner_mismatch"),
        ):
            with self.subTest(reason=reason):
                self.assertEqual(self.boundary.read_policy(context, {"topic": "export"}), mcp.Reply("denied"))
                self.assertEqual(self.store.reads, ())
                self.assertEqual(asdict(self.boundary.audit[-1]), {"operation": "read_policy", "reason": reason})
        self.assertEqual(self.boundary.read_policy(mcp.SUPPORT_CONTEXT, {"topic": "export"}), mcp.Reply("ok", EXPORT))
        self.assertEqual(self.store.reads, ("export",))

    def test_strict_args_and_audit_shape(self) -> None:
        for args in ({}, {"topic": "other"}, {"topic": True}, ["sync"], {"topic": ["sync"]},
                     {"topic": "sync", "note": "假设备注，仅用于测试"}):
            with self.subTest(args=args):
                self.assertEqual(self.boundary.read_policy(mcp.SUPPORT_CONTEXT, args), mcp.Reply("invalid_arguments"))
                self.assertEqual(self.store.reads, ())
                self.assertEqual(asdict(self.boundary.audit[-1]), {
                    "operation": "read_policy", "reason": "invalid_arguments"})
        self.assertEqual(self.boundary.read_policy(mcp.SUPPORT_CONTEXT, {"topic": "sync"}), mcp.Reply("ok", SYNC))
        revoked = replace(mcp.SUPPORT_CONTEXT, scopes=frozenset())
        self.assertEqual(self.boundary.read_policy(revoked, {"topic": "sync"}), mcp.Reply("denied"))
        self.assertEqual(self.store.reads, ("sync",))
        self.assertEqual(tuple(asdict(event) for event in self.boundary.audit[-2:]), (
            {"operation": "read_policy", "reason": "ok"},
            {"operation": "read_policy", "reason": "insufficient_scope"},
        ))

    def test_audit_budget_closes_before_read(self) -> None:
        for _ in range(12):
            self.assertEqual(self.boundary.read_policy(None, {"topic": "export"}), mcp.Reply("denied"))
        self.assertEqual(self.boundary.read_policy(mcp.SUPPORT_CONTEXT, {"topic": "export"}),
                         mcp.Reply("budget_exhausted"))
        self.assertEqual(len(self.boundary.audit), 12)
        self.assertEqual(self.store.reads, ())
