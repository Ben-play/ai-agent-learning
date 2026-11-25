"""L76: deterministic attempt ledger, not provider usage, prices, or timings."""

from dataclasses import dataclass
from fractions import Fraction


WORKLOAD_VERSION = "export-support-load/v1"
PREFIX_VERSION = "export-help-prefix/v1"
PREFIX_TOKENS, RETRY_DELAY_MS = 100, 40
POLICY = {"support": "7 天", "operations": "30 天"}
POLICY_KEY = "EXPORT-POLICY/v1 §1"
# Ordinary input, prefix write, prefix read, and output, in microcredits/token.
RATES = {"standard": (3, 4, 1, 5), "lite": (2, 3, 1, 3)}
BASE_MS = {"standard": 60, "lite": 30}


@dataclass(frozen=True)
class Request:
    id: str
    tenant: str
    kind: str
    required_input: int  # After the fixed prefix.
    optional_input: int
    needed_output: int
    desired_output: int
    queue_ms: int
    evidence_ms: int
    timeouts: int = 0  # Number of initial attempts that time out.
    approved: bool = False
    routine: bool = False  # Trusted fixture classification, not derived from the question text.


WORKLOAD = (
    Request("s-lookup", "support", "lookup", 20, 30, 16, 30, 5, 10, routine=True),
    Request("s-repeat", "support", "lookup", 20, 30, 16, 30, 8, 10, routine=True),
    Request("o-lookup", "operations", "lookup", 20, 30, 16, 30, 5, 10, routine=True),
    Request("s-draft", "support", "draft", 40, 40, 30, 50, 9, 24, timeouts=1, approved=True),
    Request("s-recover", "support", "lookup", 45, 45, 20, 35, 12, 20, timeouts=2),
)


@dataclass(frozen=True)
class Arm:
    cache: bool = False
    route: bool = False
    input_cap: int | None = None
    output_cap: int | None = None


ARMS = {
    "baseline": Arm(),
    "prefix": Arm(cache=True),
    "route": Arm(route=True),
    "input-145": Arm(input_cap=145),
    "output-30": Arm(output_cap=30),
}


@dataclass(frozen=True)
class Evidence:
    tenant: str
    key: str
    retention: str


@dataclass(frozen=True)
class Outcome:
    status: str
    evidence: Evidence | None = None
    draft_writes: int = 0


# Hand labeled independently of replay's source lookup and status logic.
LABELS = {
    "s-lookup": Outcome("answered", Evidence("support", "EXPORT-POLICY/v1 §1", "7 天")),
    "s-repeat": Outcome("answered", Evidence("support", "EXPORT-POLICY/v1 §1", "7 天")),
    "o-lookup": Outcome("answered", Evidence("operations", "EXPORT-POLICY/v1 §1", "30 天")),
    "s-draft": Outcome("draft_saved", Evidence("support", "EXPORT-POLICY/v1 §1", "7 天"), 1),
    "s-recover": Outcome("unavailable"),
}


@dataclass(frozen=True)
class Attempt:
    model: str
    ordinary: int
    write: int
    read: int
    output: int
    status: str
    cache_owner: str | None = None

    @property
    def charge(self) -> int:
        usage = self.ordinary, self.write, self.read, self.output
        return sum(tokens * rate for tokens, rate in zip(usage, RATES[self.model], strict=True))

    @property
    def elapsed_ms(self) -> int:
        return BASE_MS[self.model] + self.ordinary + self.write + self.read // 5 + 2 * self.output


@dataclass(frozen=True)
class Row:
    request_id: str
    attempts: tuple[Attempt, ...]
    outcome: Outcome
    queue_ms: int
    evidence_ms: int
    retry_ms: int

    @property
    def elapsed_ms(self) -> int:
        return self.queue_ms + self.evidence_ms + self.retry_ms + sum(a.elapsed_ms for a in self.attempts)


def replay(arm: Arm) -> tuple[Row, ...]:
    """Start cold; replay all requests once in frozen order, with at most one retry each."""
    rows = []
    cache: dict[tuple[str, str, str], str] = {}
    for request in WORKLOAD:
        model = "lite" if arm.route and request.routine else "standard"
        protected = PREFIX_TOKENS + request.required_input
        size = protected + request.optional_input
        if arm.input_cap is not None:
            size = min(size, arm.input_cap)
        attempts = []
        retry_ms = 0
        outcome = Outcome("input_too_small")
        if size >= protected:
            key = request.tenant, model, PREFIX_VERSION
            for index in range(2):
                owner = cache.get(key) if arm.cache else None
                read = PREFIX_TOKENS if owner is not None else 0
                write = PREFIX_TOKENS if arm.cache and not read else 0
                if write:
                    cache[key] = request.tenant  # This fixture fills the prefix even on timeout.
                timeout = index < request.timeouts
                output = 0 if timeout else request.desired_output
                if arm.output_cap is not None:
                    output = min(output, arm.output_cap)
                status = "timeout" if timeout else (
                    "incomplete" if output < request.needed_output else "complete"
                )
                attempts.append(Attempt(model, size - read - write, write, read, output, status, owner))
                if timeout:
                    outcome = Outcome("unavailable")
                    if index == 0:
                        retry_ms += RETRY_DELAY_MS
                    continue
                if status == "incomplete":
                    outcome = Outcome("output_incomplete")
                else:
                    evidence = Evidence(request.tenant, POLICY_KEY, POLICY[request.tenant])
                    if request.kind == "draft":
                        outcome = Outcome("draft_saved", evidence, 1) if request.approved else Outcome("handoff", evidence)
                    else:
                        outcome = Outcome("answered", evidence)
                break
        rows.append(Row(request.id, tuple(attempts), outcome, request.queue_ms, request.evidence_ms, retry_ms))
    return tuple(rows)


@dataclass(frozen=True)
class Comparison:
    quality_errors: tuple[str, ...]
    isolation_errors: tuple[str, ...]
    successes: int
    total_charge: int
    p95_ms: int

    @property
    def eligible(self) -> bool:
        return not self.quality_errors and not self.isolation_errors

    @property
    def charge_per_success(self) -> Fraction | None:
        return Fraction(self.total_charge, self.successes) if self.successes else None


def compare(rows: tuple[Row, ...]) -> Comparison:
    """Require exactly the versioned task cohort, then gate before ranking arms."""
    if tuple(row.request_id for row in rows) != tuple(request.id for request in WORKLOAD):
        raise ValueError(f"replay must preserve {WORKLOAD_VERSION} task ids and order")
    quality, isolation = [], []
    successes = 0
    for request, row in zip(WORKLOAD, rows, strict=True):
        correct = row.outcome == LABELS[request.id]
        evidence = row.outcome.evidence
        isolated = (evidence is None or evidence.tenant == request.tenant) and all(
            not a.read or a.cache_owner == request.tenant for a in row.attempts
        )
        if not correct:
            quality.append(request.id)
        if not isolated:
            isolation.append(request.id)
        if correct and isolated and row.outcome.status in ("answered", "draft_saved"):
            successes += 1
    elapsed = sorted(row.elapsed_ms for row in rows)
    nearest_rank = (95 * len(elapsed) + 99) // 100
    return Comparison(tuple(quality), tuple(isolation), successes,
                      sum(a.charge for row in rows for a in row.attempts), elapsed[nearest_rank - 1])


def format_summary(report: Comparison) -> str:
    per_success = report.charge_per_success
    return (f"{'eligible' if report.eligible else 'blocked'}; "
            f"quality={report.quality_errors}, isolation={report.isolation_errors}; "
            f"success={report.successes}/{len(WORKLOAD)}, total={report.total_charge} uc, "
            f"uc/success={per_success if per_success is not None else 'N/A'}, p95={report.p95_ms} ms")


def show() -> None:
    print(f"{WORKLOAD_VERSION} / {PREFIX_VERSION} | synthetic microcredits (uc), ms")
    for name, arm in ARMS.items():
        rows = replay(arm)
        print(f"{name}: {format_summary(compare(rows))}")
        for row in rows:
            attempts = ", ".join(f"{a.model}/{a.status}={a.charge}uc/{a.elapsed_ms}ms" for a in row.attempts)
            print(f"  {row.request_id}: {row.outcome.status} | {attempts} | "
                  f"queue/evidence/retry={row.queue_ms}/{row.evidence_ms}/{row.retry_ms}ms | {row.elapsed_ms}ms")


if __name__ == "__main__":
    show()
