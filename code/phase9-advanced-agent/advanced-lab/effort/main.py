"""L80: offline replay with Phase 7's synthetic corpus and hand-written gold."""

from dataclasses import dataclass
from fractions import Fraction
import math
from pathlib import Path
import re
import runpy

PHASE7 = Path(__file__).resolve().parents[3] / "phase7-data-rag" / "rag-lab" / "lab.py"
open_demo = runpy.run_path(str(PHASE7))["open_demo"]
COHORT_VERSION = "phase9-effort/v1"
POLICIES = ("fixed-low", "fixed-high", "selective")


@dataclass(frozen=True)
class Task:
    id: str
    tenant: str
    question: str
    facts: tuple[str, ...]


TASKS = (
    Task("support-retention", "support", "导出文件保留多久？", ("retention",)),
    Task("ops-retention", "operations", "导出文件保留多久？", ("retention",)),
    Task("cross-check", "support", "给出导出留存期和每日同步时间，分别附出处。", ("retention", "schedule")),
    Task("missing", "support", "备份文件保留多久？", ("backup",)),
)
ACTOR = "mei"  # Host-owned fixture identity, not parsed from the question.
ROUTE = {
    "retention": ("EXPORT-POLICY", 1, "§1"),
    "schedule": ("SYNC-POLICY", 1, "§1"),
    "backup": ("BACKUP-POLICY", 1, "§1"),
}


@dataclass(frozen=True)
class Evidence:
    tenant: str
    key: tuple[str, int, str]
    quote: str


@dataclass(frozen=True)
class Claim:
    fact: str
    value: str
    source: Evidence


# Written independently of ROUTE, retrieval output and the simulated responder.
GOLD = {
    "support-retention": (Claim("retention", "7 天", Evidence(
        "support", ("EXPORT-POLICY", 1, "§1"), "导出文件生成后保留 7 天。")),),
    "ops-retention": (Claim("retention", "30 天", Evidence(
        "operations", ("EXPORT-POLICY", 1, "§1"), "运维导出文件保留 30 天。")),),
    "cross-check": (
        Claim("retention", "7 天", Evidence("support", ("EXPORT-POLICY", 1, "§1"), "导出文件生成后保留 7 天。")),
        Claim("schedule", "02:00", Evidence("support", ("SYNC-POLICY", 1, "§1"), "同步任务每天 02:00 运行。")),
    ),
    "missing": None,  # The only acceptable outcome is a scoped, no-claim refusal.
}


@dataclass(frozen=True)
class Target:
    api: str
    model: str
    thinking: str | None = None
    thinking_tokens: int | None = None


CLAUDE = Target("messages", "claude-sonnet-4-6", "adaptive")
OPENAI = Target("responses", "gpt-5-2025-08-07")


@dataclass(frozen=True)
class Limits:
    output_tokens: int = 4096
    charge_uc: int = 54
    deadline_ms: int = 150

    def __post_init__(self):
        if (type(self.output_tokens) is not int or not 1 <= self.output_tokens <= 4096
                or any(type(n) is not int or n < 0 for n in (self.charge_uc, self.deadline_ms))):
            raise ValueError("classroom limits: 1–4096 output tokens; nonnegative integer charge and deadline")


def request_fields(target: Target, effort: str, limits: Limits) -> dict:
    """Only option fragments for the two pinned model/API pairs; never send them."""
    if (target.api, target.model) == (CLAUDE.api, CLAUDE.model):
        if effort not in ("low", "medium", "high", "max"):
            raise ValueError("unsupported effort")
        mode = target.thinking
        if mode not in ("adaptive", "disabled", "enabled"):
            raise ValueError("unsupported thinking mode")
        thinking = {"type": mode}
        if mode == "enabled":  # Deprecated; only the non-interleaved configuration is modeled.
            n = target.thinking_tokens
            if type(n) is not int or not 1024 <= n < limits.output_tokens:
                raise ValueError("invalid manual thinking target")
            thinking["budget_tokens"] = n
        elif target.thinking_tokens is not None:
            raise ValueError("only manual thinking takes budget_tokens")
        return {"model": target.model, "thinking": thinking,
                "output_config": {"effort": effort}, "max_tokens": limits.output_tokens}
    if (target.api, target.model) == (OPENAI.api, OPENAI.model):
        if (target.thinking is not None or target.thinking_tokens is not None
                or effort not in ("minimal", "low", "medium", "high")):
            raise ValueError("unsupported Responses reasoning options")
        return {"model": target.model, "reasoning": {"effort": effort},
                "max_output_tokens": limits.output_tokens}
    raise ValueError("unknown model/API pair")


@dataclass(frozen=True)
class Lookup:
    charge_uc: int
    duration_ms: int


@dataclass(frozen=True)
class Call:
    effort: str
    options: dict
    packet: tuple[Evidence, ...]
    charge_uc: int
    duration_ms: int


@dataclass(frozen=True)
class Row:
    task_id: str
    status: str
    claims: tuple[Claim, ...]
    lookup: Lookup | None
    call: Call | None
    charge_uc: int
    elapsed_ms: int


def collect(db, task: Task) -> tuple[Evidence, ...]:
    return tuple(Evidence(task.tenant, chunk.key, chunk.text) for fact in task.facts
                 if (chunk := db.source(task.tenant, ACTOR, ROUTE[fact])) is not None)


def run_task(db, task: Task, policy: str, *, target=CLAUDE, limits=Limits(), packet=None) -> Row:
    if policy not in POLICIES:
        raise ValueError("unknown policy")
    # Fixed classroom lookup/validation overhead for every task, even refusals.
    lookup_charge, lookup_ms = 6, 15
    if limits.charge_uc < lookup_charge or limits.deadline_ms < lookup_ms:
        return Row(task.id, "budget_exhausted", (), None, None, 0, 0)

    current = collect(db, task)
    lookup = Lookup(lookup_charge, lookup_ms)

    def finish(status, claims=(), call=None):
        charge = lookup.charge_uc + (call.charge_uc if call else 0)
        duration = lookup.duration_ms + (call.duration_ms if call else 0)
        return Row(task.id, status, claims, lookup, call, charge, duration)

    incoming = current if packet is None else packet  # Explicit handoff fault control.
    if len(current) != len(task.facts):
        return finish("insufficient_evidence")
    if incoming != current:
        return finish("evidence_mismatch")
    effort = "high" if policy == "fixed-high" or (policy == "selective" and len(task.facts) > 1) else "low"
    try:
        options = request_fields(target, effort, limits)
    except ValueError:
        return finish("unsupported_config")

    # Synthetic usage schedule, not a vendor price/latency or a predictor of real usage.
    demand, charge, duration = (90, 42, 105) if effort == "high" else (38, 18, 45)
    if lookup.charge_uc + charge > limits.charge_uc or lookup.duration_ms + duration > limits.deadline_ms:
        return finish("budget_exhausted")
    call = Call(effort, options, incoming, charge, duration)  # This is the only mock dispatch point.
    if demand > limits.output_tokens:
        return finish("incomplete", call=call)

    # Script the low-effort error: on a multi-source task it overlooks all but the first fact.
    answers = zip(task.facts, incoming, strict=True)
    if effort == "low":
        answers = [next(answers)]
    patterns = {"retention": r"\d+ 天", "schedule": r"\d\d:\d\d"}
    claims = tuple(Claim(fact, match.group(), source) for fact, source in answers
                   if (match := re.search(patterns[fact], source.quote)))
    return finish("answer", claims, call)


def replay(policy: str, *, target=CLAUDE, limits=Limits()) -> tuple[Row, ...]:
    with open_demo() as db:
        return tuple(run_task(db, task, policy, target=target, limits=limits) for task in TASKS)


# Frozen audit gold, independent of the simulator's admission and event recording.
_GOLD_LOOKUP = (6, 15)
_GOLD_CALL = {"low": (18, 45), "high": (42, 105)}


def _usage(event: Lookup | Call | None) -> tuple[int, int]:
    return (event.charge_uc, event.duration_ms) if event is not None else (0, 0)


def _ledger_matches(row: Row, limits: Limits, measured: tuple[int, int]) -> bool:
    charge, duration = measured
    lookup_fits = _GOLD_LOOKUP[0] <= limits.charge_uc and _GOLD_LOOKUP[1] <= limits.deadline_ms
    if lookup_fits:
        lookup_ok = row.lookup is not None and _usage(row.lookup) == _GOLD_LOOKUP
    else:
        lookup_ok = row.lookup is None and row.call is None and row.status == "budget_exhausted"
    if row.status in ("answer", "incomplete"):
        call_ok = row.call is not None and _usage(row.call) == _GOLD_CALL.get(row.call.effort)
    else:
        call_ok = row.call is None
    return (lookup_ok and call_ok and (row.charge_uc, row.elapsed_ms) == measured
            and 0 <= charge <= limits.charge_uc and 0 <= duration <= limits.deadline_ms)


@dataclass(frozen=True)
class Report:
    quality_errors: tuple[str, ...]
    evidence_errors: tuple[str, ...]
    dispatch_errors: tuple[str, ...]
    ledger_errors: tuple[str, ...]
    successes: int
    total_charge: int
    p95_ms: int

    @property
    def eligible(self) -> bool:
        return not (self.quality_errors or self.evidence_errors or self.dispatch_errors or self.ledger_errors)

    @property
    def charge_per_success(self) -> Fraction | None:
        return Fraction(self.total_charge, self.successes) if self.successes else None


def compare(rows: tuple[Row, ...], *, target=CLAUDE, limits=Limits()) -> Report:
    """Audit the ordered cohort; keep quality, evidence, dispatch, and ledger gates separate."""
    if tuple(row.task_id for row in rows) != tuple(GOLD):
        raise ValueError("not the same ordered cohort")
    quality, evidence, dispatch, ledger = [], [], [], []
    successes = total_charge = 0
    elapsed = []
    for row in rows:
        gold = GOLD[row.task_id]
        call = row.call
        good_answer = row.status == "answer" and row.claims == gold
        quality_ok = good_answer or (gold is None and row.status == "insufficient_evidence" and not row.claims)
        if not quality_ok:
            quality.append(row.task_id)
        if call is None:
            evidence_ok = row.status != "evidence_mismatch" and (row.status != "insufficient_evidence" or gold is None)
            dispatch_ok = gold is None
        else:
            evidence_ok = gold is not None and call.packet == tuple(claim.source for claim in gold)
            dispatch_ok = gold is not None and call.effort in ("low", "high")
        if not evidence_ok:
            evidence.append(row.task_id)
        if call is not None and dispatch_ok:
            try:
                dispatch_ok = call.options == request_fields(target, call.effort, limits)
            except ValueError:
                dispatch_ok = False
        if not dispatch_ok:
            dispatch.append(row.task_id)
        lookup_charge, lookup_ms = _usage(row.lookup)
        call_charge, call_ms = _usage(call)
        measured = (lookup_charge + call_charge, lookup_ms + call_ms)
        ledger_ok = _ledger_matches(row, limits, measured)
        if not ledger_ok:
            ledger.append(row.task_id)
        successes += good_answer and evidence_ok and dispatch_ok and ledger_ok
        # Count every row's recorded events, never the row's possibly understated total.
        total_charge += measured[0]
        elapsed.append(measured[1])
    p95 = sorted(elapsed)[math.ceil(0.95 * len(rows)) - 1]
    return Report(tuple(quality), tuple(evidence), tuple(dispatch), tuple(ledger), successes, total_charge, p95)


def main():
    print(COHORT_VERSION)
    reports = {}
    for policy in POLICIES:
        rows = replay(policy)
        report = reports[policy] = compare(rows)
        print(policy, f"eligible={report.eligible}", f"delivered={report.successes}/{len(rows)}",
              f"total={report.total_charge} uc", f"uc/delivery={report.charge_per_success}",
              f"p95={report.p95_ms} ms", f"quality_errors={report.quality_errors}",
              f"evidence_errors={report.evidence_errors}", f"dispatch_errors={report.dispatch_errors}",
              f"ledger_errors={report.ledger_errors}")
    eligible = [name for name, report in reports.items() if report.eligible]
    if eligible:
        print("preferred:", min(eligible, key=lambda name: (reports[name].charge_per_success, reports[name].p95_ms)))


if __name__ == "__main__":
    main()
