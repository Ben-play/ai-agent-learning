"""Hand-written facts, terminal paths and effects for the frozen support cohort."""

from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
import runpy


LAB = runpy.run_path(str(Path(__file__).with_name("evidence_lab.py")))

# Written from the business question and the Phase 7 fixtures, not from replay output.
P = ("EXPORT-POLICY", 1, "§1")
O = ("EXPORT-OPS", 1, "§2")
SUPPORT = (P, "导出文件生成后保留 7 天。")
OPERATIONS = (P, "运维导出文件保留 30 天。")
FOLLOWUP = (O, "导出文件过期后，需重新发起导出。")
GOLD = {
    "support-retention": (("support", "mei"), "answered", "complete", (SUPPORT,)),
    "operations-retention": (("operations", "mei"), "answered", "complete", (OPERATIONS,)),
    "expiry": (("support", "mei"), "answered", "complete", (SUPPORT, FOLLOWUP)),
    "expiry-no-grant": (("support", "lin"), "handoff", "source_not_visible", ()),
    "expiry-timeout": (("support", "mei"), "handoff", "timeout", ()),
    "unlisted": (("support", "mei"), "refused", "out_of_scope", ()),
}

# Each token describes one observed event (including pre-dispatch blocks).
# These are independent effect labels, not intended plans supplied by the arms.
THIN_STOP = "P h:needs_followup"
TRACES = {
    "support-retention": dict(thin="P", workflow="P", single="c P", worker="c P"),
    "operations-retention": dict(thin="P", workflow="P", single="c P", worker="c P"),
    "expiry": dict(thin=THIN_STOP, workflow="P O", single="c P c O", worker="c P c w O m"),
    "expiry-no-grant": dict(thin=THIN_STOP, workflow="P D h:source_not_visible",
                            single="c P c D h:source_not_visible", worker="c P c w:source_not_visible D h:source_not_visible"),
    "expiry-timeout": dict(thin=THIN_STOP, workflow="P T h:timeout",
                           single="c P c T h:timeout", worker="c P c w:timeout T h:timeout"),
    "unlisted": dict.fromkeys(("thin", "workflow", "single", "worker"), "b:out_of_scope"),
}
EVENTS = {
    "c": ("choose", None, "ok", True),
    "P": ("read", P, "ok", True),
    "O": ("read", O, "ok", True),
    "D": ("read", O, "not_visible", True),
    "T": ("read", O, "timeout", True),
    "w": ("worker", O, "ok", True),
    "m": ("merge", None, "ok", True),
    "h": ("review", None, "", True),
    "b": ("blocked", None, "", False),
}

# Acceptance tariff (credits, simulated milliseconds), not the host's runtime rates.
TARIFF = {"choose": (1, 3), "read": (2, 8), "timeout": (3, 24), "worker": (1, 4),
          "merge": (1, 2), "review": (1, 5), "blocked": (0, 1)}


def valid_accounting(row):
    cost = ms = 0
    for event in row.events:
        rate = TARIFF.get("timeout" if event.operation == "read" and event.status == "timeout"
                          else event.operation)
        if (rate is None or type(event.cost) is not int or type(event.ms) is not int
                or (event.cost, event.ms) != rate):
            return False
        cost += rate[0]
        ms += rate[1]
    return (row.cost, row.ms) == (cost, ms)


def check_outcome(row, expected):
    actor, status, reason, citations = expected
    outcome = row.outcome
    errors = []
    if (outcome.status, outcome.reason, tuple((e.key, e.text) for e in outcome.evidence)) != (
            status, reason, citations):
        errors.append("outcome")
    if row.actor != actor or any(e.actor != actor for e in outcome.evidence):
        errors.append("actor")
    return tuple(errors)


def check_behavior(row, trace, actor):
    tokens = trace.split()
    expected_events = []
    for token in tokens:
        code, _, reason = token.partition(":")
        operation, key, status, dispatched = EVENTS[code]
        expected_events.append((operation, key, reason or status, dispatched, actor))
    observed = [(e.operation, e.key, e.status, e.dispatched, e.actor) for e in row.events]
    expected_sources = tuple((actor, EVENTS[t][1]) for t in tokens if t in {"P", "O", "D"})
    errors = []
    if observed != expected_events:
        errors.append("events")
    if row.source_calls != expected_sources:
        errors.append("source_calls")
    return tuple(errors)


def within_budget(row, budget):
    return (row.budget == budget and row.cost <= budget.credits
            and sum(e.operation == "read" for e in row.dispatches) <= budget.reads
            and sum(e.operation == "worker" for e in row.dispatches) <= budget.workers)


def check_execution(row, trace, actor, budget):
    errors = list(check_behavior(row, trace, actor))
    if not valid_accounting(row):
        errors.append("accounting")
    if not within_budget(row, budget):
        errors.append("budget")
    return tuple(errors)


def check_observation(row, trace, expected_outcome, budget):
    """Audit answer, scoped behavior and accounting without conflating them."""
    return check_outcome(row, expected_outcome) + check_execution(row, trace, expected_outcome[0], budget)


@dataclass(frozen=True)
class Summary:
    """Observed metrics; any contract error makes the arm ineligible."""

    correct_answers: int
    tasks: int
    total_cost: int
    p95_ms: int
    dispatches: int
    contract_errors: tuple[str, ...]

    @property
    def cost_per_answer(self):
        return Fraction(self.total_cost, self.correct_answers) if self.correct_answers else None


def measure(arm, rows, cohort, budget):
    if not rows or tuple(c.name for c in cohort) != tuple(row.case for row in rows):
        raise ValueError("preserve the whole frozen cohort in order")
    errors = []
    successes = 0
    for row in rows:
        expected = GOLD[row.case]
        outcome_errors = check_outcome(row, expected)
        # Count exactly correct answers, not correctly stopped tasks or audited ledgers.
        if row.outcome.status == "answered" and not outcome_errors:
            successes += 1
        execution_errors = check_execution(row, TRACES[row.case][arm], expected[0], budget)
        errors.extend(f"{row.case}:{problem}" for problem in outcome_errors + execution_errors)
    times = sorted(row.ms for row in rows)
    rank = (95 * len(times) + 99) // 100  # Nearest rank, on all trials.
    return Summary(successes, len(rows), sum(row.cost for row in rows), times[rank - 1],
                   sum(len(row.dispatches) for row in rows), tuple(errors))


def comparison(arms, cohort):
    budget = LAB["Budget"]()
    rows = {arm: LAB["replay"](arm, cohort, budget=budget) for arm in arms}
    return rows, {arm: measure(arm, trials, cohort, budget) for arm, trials in rows.items()}


def verify(row, trace, outcome, budget):
    errors = check_observation(row, trace, outcome, budget)
    if errors:
        raise AssertionError((row.case, errors))


def stopped(case, reason):
    return GOLD[case][0], "handoff", reason, ()
