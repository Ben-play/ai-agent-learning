"""Deterministic Phase 7 checks. Inputs marked host-owned are not request data."""

from dataclasses import dataclass
from statistics import mean

Key = tuple[str, int, str]


@dataclass(frozen=True)
class Scope:
    tenant: str
    user: str


@dataclass(frozen=True)
class Citation:
    tenant: str
    key: Key
    quote: str


def cite(scope: Scope, chunk) -> Citation:
    return Citation(scope.tenant, chunk.key, chunk.text)


# Hand-written approval for the baseline L68 fixtures; never derive it from SQLite.
DEMO_POLICY = Citation("support", ("EXPORT-POLICY", 1, "§1"), "导出文件生成后保留 7 天。")
DEMO_RENEWAL = Citation("support", ("EXPORT-OPS", 1, "§2"), "导出文件过期后，需重新发起导出。")
DEMO_SYNC = Citation("support", ("SYNC-POLICY", 1, "§1"), "同步任务每天 02:00 运行。")
DEMO_APPROVED = {
    Scope("support", "mei"): frozenset({DEMO_POLICY, DEMO_RENEWAL, DEMO_SYNC}),
    Scope("support", "lin"): frozenset({DEMO_POLICY, DEMO_SYNC}),
}


def assert_authorized_snapshot(db, scope: Scope, approved: frozenset[Citation]) -> None:
    """Cross-check the runtime pool against the independently approved keys and whole quotes."""
    observed = tuple(cite(scope, chunk) for chunk in db.authorized(scope.tenant, scope.user))
    assert len(observed) == len(approved) and frozenset(observed) == approved, (
        f"authorized rows disagree with the approved snapshot for {scope}"
    )


def exact_source(db, scope: Scope, citation: Citation) -> bool:
    """The lab quotes whole chunks; neither a partial quote nor a nearby version matches."""
    if citation.tenant != scope.tenant or not citation.quote or type(citation.key[1]) is not int:
        return False
    current = db.source(scope.tenant, scope.user, citation.key)
    return current is not None and current.key == citation.key and current.text == citation.quote


@dataclass(frozen=True)
class Evidence:
    scope: Scope
    citation: Citation
    tag: str = "untrusted_data"


def admit_evidence(db, scope: Scope, citation: Citation) -> Evidence | None:
    return Evidence(scope, citation) if exact_source(db, scope, citation) else None


@dataclass(frozen=True)
class Intent:
    owner: Scope
    action: str
    target: str
    revision: int
    label: str


@dataclass(frozen=True)
class MockApproval:
    intent: Intent


class PreviewLog:
    """Observe entries into the mock approval branch; this is not an executor."""

    def __init__(self) -> None:
        self.entries: list[Intent] = []


def review_preview(scope: Scope, staged: Intent, proposed: Intent,
                   approval: MockApproval | None, log: PreviewLog) -> str:
    """Scope, staging, approval and the local log are host-owned; proposed intent has no authority."""
    if staged.owner != scope or staged.action != "preview_label":
        return "not_allowed"
    if proposed != staged:
        return "intent_changed"
    if approval is None or approval.intent != staged:
        return "approval_required"
    log.entries.append(staged)
    return "mock_approved_no_execution"


@dataclass(frozen=True)
class RetrievalRow:
    status: str
    scope_ok: bool
    eligible_gold: frozenset[Key]
    matched_gold: frozenset[Key]
    violations: tuple[Key, ...]
    recall: float | None
    covered_facts: frozenset[str]
    coverage: float


def grade_retrieval(scope: Scope, allowed: frozenset[Citation], observed_scope: Scope, hits,
                    fact_sources: dict[str, frozenset[Key]], *, k: int) -> RetrievalRow:
    """Audit the original top k against separately approved keys and exact quotes."""
    if type(k) is not int or k < 1 or not fact_sources:
        raise ValueError("positive k and at least one labeled fact are required")
    scope_ok = observed_scope == scope
    gold = frozenset().union(*fact_sources.values())
    eligible = gold & {entry.key for entry in allowed if entry.tenant == scope.tenant}
    valid = set()
    violations = []
    for hit in hits[:k]:
        chunk = hit.chunk
        if observed_scope.tenant != scope.tenant or cite(observed_scope, chunk) not in allowed:
            violations.append(chunk.key)
        elif scope_ok:
            valid.add(chunk.key)
    matched = eligible & valid
    covered = frozenset(fact for fact, sources in fact_sources.items() if sources & matched)
    if not eligible:
        status = "no_eligible_gold"
    elif not matched:
        status = "miss"
    elif matched == eligible:
        status = "full_recall"
    else:
        status = "partial_recall"
    return RetrievalRow(status, scope_ok, frozenset(eligible), frozenset(matched), tuple(violations),
                        len(matched) / len(eligible) if eligible else None,
                        covered, len(covered) / len(fact_sources))


def summarize_retrieval(rows: tuple[RetrievalRow, ...]) -> dict:
    recalls = [row.recall for row in rows if row.recall is not None]
    return {
        "rows": len(rows),
        "scored_recall_rows": len(recalls),
        "mean_recall": mean(recalls) if recalls else None,
        "mean_fact_coverage": mean(row.coverage for row in rows) if rows else None,
        "no_eligible_gold": sum(row.status == "no_eligible_gold" for row in rows),
        "misses": sum(row.status == "miss" for row in rows),
        "scope_mismatch_rows": sum(not row.scope_ok for row in rows),
        "rows_with_violations": sum(bool(row.violations) for row in rows),
        "violating_hits": sum(len(row.violations) for row in rows),
    }


@dataclass(frozen=True)
class Claim:
    fact: str
    value: str
    citation: Citation | None


@dataclass(frozen=True)
class Answer:
    mode: str
    claims: tuple[Claim, ...] = ()
    gaps: frozenset[str] = frozenset()


@dataclass(frozen=True)
class ClaimGrade:
    source_exact: bool
    in_evidence: bool
    correct: bool
    supported: bool


@dataclass(frozen=True)
class AnswerGrade:
    claims: tuple[ClaimGrade, ...]
    expected_gaps: frozenset[str]
    gaps_ok: bool
    complete: bool

    @property
    def accepted(self) -> bool:
        return self.gaps_ok and self.complete and all(
            claim.source_exact and claim.in_evidence and claim.correct and claim.supported
            for claim in self.claims
        )


def grade_generation(db, scope: Scope, evidence: tuple[Citation, ...], answer: Answer,
                     truth: dict[str, str], support: frozenset[Claim]) -> AnswerGrade:
    """Grade a fixed packet; the caller must authorize and admit its contents before use."""
    if not truth:
        raise ValueError("at least one required fact is needed")
    packet = frozenset(evidence)
    verified = {entry for entry in packet if exact_source(db, scope, entry)}
    requested = frozenset(truth)
    answerable = frozenset(
        label.fact for label in support
        if label.citation in verified and label.fact in truth and label.value == truth[label.fact]
    )
    gaps = requested - answerable
    mode = "refuse" if not answerable else "partial" if gaps else "answer"
    grades = []
    for claim in answer.claims:
        citation = claim.citation
        exact = citation is not None and exact_source(db, scope, citation)
        in_packet = citation in packet
        grades.append(ClaimGrade(exact, in_packet,
                                 claim.fact in truth and claim.value == truth[claim.fact],
                                 exact and citation in verified and claim in support))
    facts = {claim.fact for claim in answer.claims}
    return AnswerGrade(tuple(grades), gaps,
                       answer.mode == mode and answer.gaps == gaps and not (facts & gaps),
                       facts == answerable and len(facts) == len(answer.claims))
