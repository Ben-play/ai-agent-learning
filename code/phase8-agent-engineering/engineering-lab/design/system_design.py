"""L78: select a design and check its record; do not execute an Agent or workflow."""

from dataclasses import asdict, dataclass
import json


SCOPE = "export-support-design/v1"


@dataclass(frozen=True)
class Case:
    id: str
    adaptive_reads: bool = False
    scoped_reader: bool = True
    adaptive_eval_passed: bool = False
    needs_resume: bool = False
    accepts_approved_draft: bool = False


CASES = (
    Case("policy-lookup"),
    Case("approved-draft", needs_resume=True, accepts_approved_draft=True),
    Case("conflicting-evidence", adaptive_reads=True, adaptive_eval_passed=True),
    Case("unscoped-reader", adaptive_reads=True, scoped_reader=False, adaptive_eval_passed=True),
    Case("unvalidated-branch", adaptive_reads=True),
    Case("nightly-eval", needs_resume=True),
)


@dataclass(frozen=True)
class Contract:
    architecture: str
    reason: str
    on_stop: str
    draft_owner: str = "none"


# Review labels chosen from the case descriptions, not generated from select().
LABELS = {
    "policy-lookup": Contract("thin-function", "known-read", "return-gap"),
    "approved-draft": Contract("workflow", "approval-owned-by-host", "resume-checkpoint", "host-after-approval"),
    "conflicting-evidence": Contract("bounded-single-agent", "adaptive-evidence-only", "handoff-no-write"),
    "unscoped-reader": Contract("workflow", "no-scoped-reader", "handoff-no-write"),
    "unvalidated-branch": Contract("workflow", "no-eval-evidence", "handoff-no-write"),
    "nightly-eval": Contract("workflow", "durable-resume", "resume-checkpoint"),
}


@dataclass(frozen=True)
class Decision:
    scope: str
    case_id: str
    contract: Contract
    tradeoff: str
    revisit_if: str


def select(case: Case) -> Decision:
    """Use local project evidence, not a universal latency, step-count or quality cutoff."""
    def record(architecture: str, reason: str, on_stop: str, tradeoff: str, revisit: str,
               draft_owner: str = "none") -> Decision:
        return Decision(SCOPE, case.id, Contract(architecture, reason, on_stop, draft_owner), tradeoff, revisit)

    if not case.scoped_reader:
        return record("workflow", "no-scoped-reader", "handoff-no-write",
                      "不自动读库，停在交接；人工处理队列变长。",
                      "有独立验收的授权读取合同后，再比较取证方式。")
    if case.accepts_approved_draft:
        return record("workflow", "approval-owned-by-host", "resume-checkpoint",
                      "显式保存审批与幂等状态；缺证交人工，不用自由搜索绕过审批。",
                      "取消写草稿且不再需要等待或恢复时，重新评估只读路径。", "host-after-approval")
    if case.needs_resume:
        return record("workflow", "durable-resume", "resume-checkpoint",
                      "要维护状态和重放规则；已验收的分片不重做。",
                      "任务可在单请求内完成且不再需要断点时，重新评估函数。")
    if not case.adaptive_reads:
        return record("thin-function", "known-read", "return-gap",
                      "最少状态、调用链短；不能跟进未知证据分支。",
                      "确有需要多步或跨会话的读写任务时，重新建模。")
    if not case.adaptive_eval_passed:
        return record("workflow", "no-eval-evidence", "handoff-no-write",
                      "只做规定的检索与交接，可能多转人工。",
                      "对固定流程失败样本盲测，证实受限自适应取证有收益。")
    return record("bounded-single-agent", "adaptive-evidence-only", "handoff-no-write",
                  "可按证据选下一次授权读取；增加延迟、消耗与回归维护。",
                  "固定流程补齐已知分支，或超预算、缺证转人工上升时回查。")


def check_decision(decision: Decision, expected_case_id: str, expected: Contract) -> tuple[str, ...]:
    """Compare against an independently supplied review label, even for the case ID."""
    fields = (
        ("scope", decision.scope, SCOPE),
        ("case_id", decision.case_id, expected_case_id),
        ("architecture", decision.contract.architecture, expected.architecture),
        ("reason", decision.contract.reason, expected.reason),
        ("on_stop", decision.contract.on_stop, expected.on_stop),
        ("draft_owner", decision.contract.draft_owner, expected.draft_owner),
    )
    errors = [name for name, actual, target in fields if actual != target]
    if not decision.tradeoff.strip():
        errors.append("tradeoff")
    if not decision.revisit_if.strip():
        errors.append("revisit_if")
    return tuple(errors)


def show() -> None:
    for case in CASES:
        decision = select(case)
        errors = check_decision(decision, case.id, LABELS[case.id])
        if errors:
            raise ValueError((case.id, errors))
        print(json.dumps(asdict(decision), ensure_ascii=False))


if __name__ == "__main__":
    show()
