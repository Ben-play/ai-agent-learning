"""L88–L89: local evidence readers and observable, synthetic accounting."""

from dataclasses import dataclass, replace
from pathlib import Path
import runpy


ROOT = Path(__file__).resolve().parents[4]
RAG = runpy.run_path(str(ROOT / "code/phase7-data-rag/rag-lab/lab.py"))
WORKLOAD = "support-evidence-v1"
POLICY = ("EXPORT-POLICY", 1, "§1")
OPS = ("EXPORT-OPS", 1, "§2")
Key = tuple[str, int, str]
Actor = tuple[str, str]


@dataclass(frozen=True)
class Case:
    name: str
    actor: Actor  # Fixed by the trusted test host, never supplied by a worker.
    question: str
    timeout_followup: bool = False


CASES = (
    Case("support-retention", ("support", "mei"), "retention"),
    Case("operations-retention", ("operations", "mei"), "retention"),
    Case("expiry", ("support", "mei"), "expiry"),
    Case("expiry-no-grant", ("support", "lin"), "expiry"),
    Case("expiry-timeout", ("support", "mei"), "expiry", timeout_followup=True),
    Case("unlisted", ("support", "mei"), "unlisted"),
)
WORKER_COHORT = tuple(case for case in CASES if case.question == "expiry")


@dataclass(frozen=True)
class Budget:
    credits: int = 12  # Includes one credit reserved for a possible review ticket.
    reads: int = 2
    workers: int = 1

    def __post_init__(self):
        counts = (self.credits, self.reads, self.workers)
        if (any(type(count) is not int for count in counts)
                or self.credits < 1 or self.reads < 0 or self.workers not in (0, 1)):
            raise ValueError("invalid trial budget")


@dataclass(frozen=True)
class Evidence:
    actor: Actor
    key: Key
    text: str


@dataclass(frozen=True)
class Event:
    operation: str
    status: str
    actor: Actor
    key: Key | None
    cost: int
    ms: int
    dispatched: bool


@dataclass(frozen=True)
class Outcome:
    status: str
    reason: str
    evidence: tuple[Evidence, ...] = ()


@dataclass(frozen=True)
class Trial:
    case: str
    actor: Actor
    budget: Budget
    outcome: Outcome
    events: tuple[Event, ...]
    source_calls: tuple[tuple[Actor, Key], ...]

    @property
    def cost(self) -> int:
        return sum(event.cost for event in self.events)

    @property
    def ms(self) -> int:
        return sum(event.ms for event in self.events)

    @property
    def dispatches(self) -> tuple[Event, ...]:
        return tuple(event for event in self.events if event.dispatched)


RATES = {"choose": (1, 3), "read": (2, 8), "timeout": (3, 24), "worker": (1, 4),
         "merge": (1, 2), "review": (1, 5), "blocked": (0, 1)}


class Stop(Exception):
    """An expected terminal route; there is no automatic retry."""


class Host:
    def __init__(self, case, budget, source):
        self.case, self.budget, self.source = case, budget, source
        self.events: list[Event] = []
        self.allowed = {"retention": (POLICY,), "expiry": (POLICY, OPS)}.get(case.question, ())

    @property
    def remaining(self) -> int:
        return self.budget.credits - sum(event.cost for event in self.events)

    def emit(self, operation, status, key=None, *, dispatched=True):
        cost, ms = RATES["timeout" if operation == "read" and status == "timeout" else operation]
        self.events.append(Event(operation, status, self.case.actor, key, cost, ms, dispatched))

    def block(self, reason):
        self.emit("blocked", reason, dispatched=False)
        raise Stop(reason)

    def require(self, cost):
        if self.remaining < cost + RATES["review"][0]:
            self.block("budget_exhausted")

    def observe(self, operation, action):
        """Charge at the local dispatch boundary, even when a dispatched step fails."""
        self.require(RATES[operation][0])
        try:
            result = action()
        except Stop as error:
            self.emit(operation, str(error))
            raise
        self.emit(operation, "ok")
        return result

    def read(self, key):
        if key not in self.allowed:
            self.block("out_of_scope")
        if sum(event.operation == "read" for event in self.events) >= self.budget.reads:
            self.block("budget_exhausted")
        # Reserve the worst possible attempt before dispatch, charge the observed outcome.
        self.require(RATES["timeout"][0])
        try:
            result = self._read_adapter(key)
        except Stop as error:
            self.emit("read", str(error), key)
            raise
        self.emit("read", "ok" if result is not None else "not_visible", key)
        if result is None:
            raise Stop("source_not_visible")
        return Evidence(self.case.actor, result.key, result.text)

    def _read_adapter(self, key):
        if key == OPS and self.case.timeout_followup:
            raise Stop("timeout")  # Real local adapter call; no SQLite source call on this fault.
        return self.source(*self.case.actor, key)

    def review(self, reason):
        # A local ticket stub; no email, remote call, or human response is simulated.
        self.emit("review", reason)
        return Outcome("handoff", reason)


def thin(host):
    first = host.read(POLICY)
    if host.case.question == "expiry":
        raise Stop("needs_followup")
    return (first,)


def workflow(host):
    first = host.read(POLICY)
    return (first, host.read(OPS)) if host.case.question == "expiry" else (first,)


def choose(question, observed=()):
    """Fixed stand-in for one Agent choosing the next action from visible evidence."""
    if not observed:
        return POLICY
    if question == "expiry" and observed[0].key == POLICY and "保留" in observed[0].text:
        return OPS
    raise Stop("needs_followup")


def single(host, *, delegate=False, fault=None):
    first = host.read(host.observe("choose", lambda: choose(host.case.question)))
    if host.case.question != "expiry":
        return (first,)
    next_key = host.observe("choose", lambda: choose(host.case.question, (first,)))
    followup = delegated_read(host, next_key, fault) if delegate else host.read(next_key)
    return first, followup


def worker(order, read_once, *, fault):
    """No Agent loop, database handle, or another worker; only one scoped callback."""
    seen = read_once(order["key"])
    if fault == "repeat_read":
        read_once(order["key"])
    if fault == "omit_evidence":
        return order, ()
    if fault == "wrong_source":
        seen = replace(seen, key=("EXPORT-OPS", 2, "§2"))
    if fault == "wrong_result_scope":
        seen = replace(seen, actor=("operations", "mei"))
    return order, (seen,)


def delegated_read(host, key, fault):
    # The order is constructed from trusted task state, then checked before any dispatch.
    expected = {"case": host.case.name, "actor": host.case.actor, "key": OPS,
                "max_reads": 1, "credits": RATES["timeout"][0]}
    order = {**expected, "key": key}
    if fault == "omit_budget":
        del order["credits"]
    if fault == "wrong_scope":
        order["actor"] = ("operations", "mei")
    if order != expected or key not in host.allowed:
        host.block("invalid_handoff")
    if sum(event.operation == "worker" for event in host.events) >= host.budget.workers:
        host.block("budget_exhausted")
    if sum(event.operation == "read" for event in host.events) >= host.budget.reads:
        host.block("budget_exhausted")
    host.require(RATES["worker"][0] + order["credits"] + RATES["merge"][0])

    receipt = None
    used = False

    def read_once(requested):
        nonlocal receipt, used
        if used or requested != key:
            # The enclosing worker dispatch records the denial even if no read ran.
            raise Stop("read_lease_denied")
        used = True
        receipt = host.read(key)
        return receipt

    # Account for admission before the worker can make its read against the same budget.
    index = len(host.events)
    host.emit("worker", "started", key)
    try:
        binding, evidence = worker(order.copy(), read_once, fault=fault)
    except Stop as error:
        host.events[index] = replace(host.events[index], status=str(error))
        raise
    host.events[index] = replace(host.events[index], status="ok")

    def merge():
        if binding != expected or receipt is None or evidence != (receipt,):
            raise Stop("invalid_worker_result")
        return receipt

    return host.observe("merge", merge)


def run(case: Case, arm: str, *, budget=Budget(), fault=None) -> Trial:
    if arm not in {"thin", "workflow", "single", "worker"}:
        raise ValueError("unknown architecture")
    if fault not in {None, "omit_budget", "omit_evidence", "wrong_scope", "wrong_source",
                     "wrong_result_scope", "repeat_read"}:
        raise ValueError("unknown teaching fault")
    if fault is not None and (arm != "worker" or case.question != "expiry"):
        raise ValueError("worker-only fault")
    source_calls = []
    with RAG["open_demo"]() as store:
        def authorized_source(tenant, user, key):
            # Independent of the adapter ledger, and no store or SQL is exposed to the worker.
            source_calls.append(((tenant, user), key))
            return store.source(tenant, user, key)

        host = Host(case, budget, authorized_source)
        if not host.allowed:
            host.emit("blocked", "out_of_scope", dispatched=False)
            outcome = Outcome("refused", "out_of_scope")
        else:
            try:
                if arm == "thin":
                    result = thin(host)
                elif arm == "workflow":
                    result = workflow(host)
                else:
                    result = single(host, delegate=arm == "worker", fault=fault)
                outcome = Outcome("answered", "complete", result)
            except Stop as error:
                outcome = host.review(str(error))
    return Trial(case.name, case.actor, budget, outcome, tuple(host.events), tuple(source_calls))


def replay(arm, cases=CASES, *, budget=Budget()):
    return tuple(run(case, arm, budget=budget) for case in cases)
