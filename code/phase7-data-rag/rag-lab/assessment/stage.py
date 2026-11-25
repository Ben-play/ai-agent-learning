"""Check the Phase 7 handoff with hand-labeled, synthetic evidence. Use --report to see each case."""

import argparse
from dataclasses import dataclass, replace
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[1]
LAB = runpy.run_path(str(ROOT / "lab.py"))
CHECKS = runpy.run_path(str(ROOT / "assessment" / "checks.py"))
LIFECYCLE = runpy.run_path(str(ROOT / "lifecycle" / "main.py"))
pack, Packed = LIFECYCLE["pack"], LIFECYCLE["Packed"]
Scope, Citation, Evidence, Claim, Answer, ClaimGrade = (
    CHECKS[name] for name in ("Scope", "Citation", "Evidence", "Claim", "Answer", "ClaimGrade")
)
cite, admit_evidence, grade_retrieval, grade_generation, assert_authorized_snapshot = (
    CHECKS[name] for name in ("cite", "admit_evidence", "grade_retrieval", "grade_generation",
                              "assert_authorized_snapshot")
)

MEI, OTHER = Scope("support", "mei"), Scope("operations", "mei")
QUERY = LAB["Query"](("保留", "有效期", "同步"))
TOP_K, MAX_CHARS = 2, 120
ROOMY_BYTES, TIGHT_BYTES = 256, 120
OLD_POLICY, SYNC = CHECKS["DEMO_POLICY"], CHECKS["DEMO_SYNC"]

# Approved keys, quotes and labels are written before querying. Do not copy an answer or a hit here.
POLICY = Citation("support", ("EXPORT-POLICY", 2, "§3"), "导出文件生成后保留 7 天。〔交班样张〕")
APPROVED = (CHECKS["DEMO_APPROVED"][MEI] - {OLD_POLICY}) | {POLICY}
TRUTH = {"retention": "7 天", "schedule": "02:00"}
LABELS = {"retention": frozenset({POLICY.key}), "schedule": frozenset({SYNC.key})}
SUPPORT = frozenset({Claim("retention", "7 天", POLICY), Claim("schedule", "02:00", SYNC)})
FACTS = frozenset(TRUTH)
PASSED_CLAIM = ClaimGrade(True, True, True, True)


def revise_policy(db):
    old = db.source(MEI.tenant, MEI.user, OLD_POLICY.key)
    current = replace(old, version=2, locator="§3", text=old.text + "〔交班样张〕")
    db.replace_document(MEI.tenant, old.doc_id, 2, (current,))
    return old, current


def retrieve(db, scope, k):
    hits = db.search(scope.tenant, scope.user, QUERY, mode="lexical", k=k)
    return grade_retrieval(MEI, APPROVED, scope, hits, LABELS, k=k), hits


def make_packet(db, row, hits, max_bytes) -> tuple[tuple[Evidence, ...] | None, Packed | None]:
    # A scope or citation failure blocks the packet, not just one row in it.
    if not row.scope_ok or row.violations:
        return None, None
    admitted = {}
    for hit in hits:
        item = admit_evidence(db, MEI, cite(MEI, hit.chunk))
        if item is None:
            return None, None
        admitted[hit.chunk.key] = item
    packed = pack(hits, top_k=TOP_K, max_chars=MAX_CHARS, max_bytes=max_bytes)
    return tuple(admitted[key] for key in packed.citations), packed


def assess(db, packet: tuple[Evidence, ...], answer):
    assert all(isinstance(item, Evidence) and item.scope == MEI and item.tag == "untrusted_data"
               for item in packet)
    # Only the evaluator expects bare citations. The handoff packet keeps scope and data tags.
    return grade_generation(db, MEI, tuple(item.citation for item in packet), answer, TRUTH, SUPPORT)


@dataclass(frozen=True)
class Case:
    name: str
    retrieval_gaps: frozenset[str]
    budget_gaps: frozenset[str]
    supported_facts: frozenset[str]
    accepted: bool


def check_case(db, name, row, packet: tuple[Evidence, ...], packed: Packed, answer,
               expected, expected_claims) -> Case:
    result = assess(db, packet, answer)
    packed_facts = frozenset(fact for fact, keys in LABELS.items() if keys.intersection(packed.citations))
    case = Case(name, FACTS - row.covered_facts, row.covered_facts - packed_facts,
                FACTS - result.expected_gaps, result.accepted)
    assert case == Case(name, *expected), (name, case)
    assert result.claims == expected_claims, (name, result.claims)
    return case


def check_wrong_text():
    # Keep the original key, search terms and grants. Only the clock time in the text changes.
    bad_text = "同步任务每天 03:00 运行。"
    rows = tuple((tenant, replace(chunk, text=bad_text) if chunk.key == SYNC.key else chunk, users)
                 for tenant, chunk, users in LAB["DEMO"])
    with LAB["open_demo"](rows=rows) as db:
        _, current = revise_policy(db)
        try:
            assert_authorized_snapshot(db, MEI, APPROVED)
        except AssertionError as exc:
            assert "approved snapshot" in str(exc)
        else:
            raise AssertionError("edited sync text must not match the approved snapshot")
        row, hits = retrieve(db, MEI, 2)
        assert tuple(hit.chunk.key for hit in hits) == (POLICY.key, SYNC.key)
        assert (row.scope_ok, row.eligible_gold, row.matched_gold, row.violations, row.recall) == (
            True, {POLICY.key, SYNC.key}, {POLICY.key}, (SYNC.key,), 0.5,
        )
        assert make_packet(db, row, hits, ROOMY_BYTES) == (None, None)

        # Isolate the grader: being exact against the changed DB does not prove support.
        # This control packet is used for scoring only; the actual handoff above was blocked.
        changed = cite(MEI, hits[1].chunk)
        assert changed.quote == bad_text
        current_citation = cite(MEI, current)
        current_evidence = admit_evidence(db, MEI, current_citation)
        changed_evidence = admit_evidence(db, MEI, changed)
        assert current_evidence is not None and changed_evidence is not None
        control_packet = (current_evidence, changed_evidence)
        retention = Claim("retention", "7 天", current_citation)
        schedule = Claim("schedule", "02:00", changed)
        wrong = assess(db, control_packet, Answer("answer", (retention, schedule)))
        assert wrong.claims == (PASSED_CLAIM, ClaimGrade(True, True, True, False))
        assert wrong.expected_gaps == {"schedule"} and not wrong.gaps_ok and not wrong.accepted
        partial = Answer("partial", (retention,), frozenset({"schedule"}))
        assert assess(db, control_packet, partial).accepted
        return wrong.claims[1]


def run_stage_check():
    if not __debug__:
        raise RuntimeError("run without -O")
    with LAB["open_demo"]() as db:
        old, current = revise_policy(db)
        assert_authorized_snapshot(db, MEI, APPROVED)
        foreign, foreign_hits = retrieve(db, OTHER, 2)
        assert not foreign.scope_ok and foreign.violations == (OLD_POLICY.key,)
        assert make_packet(db, foreign, foreign_hits, ROOMY_BYTES) == (None, None)

        narrow, narrow_hits = retrieve(db, MEI, 1)
        wide, wide_hits = retrieve(db, MEI, 2)
        for row in (narrow, wide):
            assert row.scope_ok and not row.violations and row.eligible_gold == {POLICY.key, SYNC.key}
        assert (narrow.recall, narrow.matched_gold, narrow.covered_facts) == (0.5, {POLICY.key}, {"retention"})
        assert (wide.recall, wide.matched_gold, wide.covered_facts) == (1.0, {POLICY.key, SYNC.key}, FACTS)

        partial_packet, narrow_pack = make_packet(db, narrow, narrow_hits, ROOMY_BYTES)
        budget_packet, budget_pack = make_packet(db, wide, wide_hits, TIGHT_BYTES)
        full_packet, full_pack = make_packet(db, wide, wide_hits, ROOMY_BYTES)
        assert partial_packet == budget_packet == (Evidence(MEI, POLICY),)
        assert full_packet == (Evidence(MEI, POLICY), Evidence(MEI, SYNC))
        assert (budget_pack.citations, budget_pack.chars, budget_pack.utf8_bytes) == ((POLICY.key,), 53, 106)
        assert (full_pack.citations, full_pack.chars, full_pack.utf8_bytes) == ((POLICY.key, SYNC.key), 95, 177)
        assert budget_pack.utf8_bytes <= TIGHT_BYTES < full_pack.utf8_bytes
        assert full_pack.chars <= MAX_CHARS and len(full_pack.citations) == TOP_K

        retention = Claim("retention", "7 天", cite(MEI, current))
        schedule = Claim("schedule", "02:00", cite(MEI, wide_hits[1].chunk))
        no_gap, sync_gap, keep = frozenset(), frozenset({"schedule"}), frozenset({"retention"})
        partial = Answer("partial", (retention,), sync_gap)
        stale = Answer("answer", (replace(retention, citation=cite(MEI, old)), schedule))
        fixed = Answer("answer", (retention, schedule))
        cases = (
            ("窄检索／如实留缺", narrow, partial_packet, narrow_pack, partial,
             (sync_gap, no_gap, keep, True), (PASSED_CLAIM,)),
            ("窄检索／声称答齐", narrow, partial_packet, narrow_pack, fixed,
             (sync_gap, no_gap, keep, False), (PASSED_CLAIM, ClaimGrade(True, False, True, False))),
            ("宽检索／字节不足", wide, budget_packet, budget_pack, partial,
             (no_gap, sync_gap, keep, True), (PASSED_CLAIM,)),
            ("完整包／旧版引文", wide, full_packet, full_pack, stale,
             (no_gap, no_gap, FACTS, False), (ClaimGrade(False, False, True, False), PASSED_CLAIM)),
            ("完整包／当前引文", wide, full_packet, full_pack, fixed,
             (no_gap, no_gap, FACTS, True), (PASSED_CLAIM, PASSED_CLAIM)),
        )
        results = tuple(check_case(db, *case) for case in cases)

        # Only the accepted complete card is staged. Evidence cannot supply application approval.
        assert results[-1].accepted and not results[-1].budget_gaps and not results[-1].retrieval_gaps
        card_label = "；".join(claim.citation.quote for claim in fixed.claims)
        staged = CHECKS["Intent"](MEI, "preview_label", "handoff", 2, card_label)
        log, review = CHECKS["PreviewLog"](), CHECKS["review_preview"]
        waiting = review(MEI, staged, staged, None, log)
        assert waiting == "approval_required" and not log.entries
        approved = review(MEI, staged, staged, CHECKS["MockApproval"](staged), log)
        assert approved == "mock_approved_no_execution"
        assert log.entries == [staged] and "〔交班样张〕" in log.entries[0].label

    wrong_text_grade = check_wrong_text()
    return results, budget_pack.utf8_bytes, full_pack.utf8_bytes, wrong_text_grade, len(log.entries)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", action="store_true", help="show the retrieval, packing and assessment cases")
    args = parser.parse_args()
    cases, tight_size, full_size, wrong, approved_entries = run_stage_check()
    if not args.report:
        return

    def facts(items):
        return ", ".join(sorted(items)) or "无"

    print("错租户：阻断，不组包。")
    print(f"宽检索：字节上限 {TIGHT_BYTES} 时保留 {tight_size} B；上限 {ROOMY_BYTES} 时保留 {full_size} B。")
    for case in cases:
        decision = "通过" if case.accepted else "不通过"
        print(f"{case.name}：检索缺口={facts(case.retrieval_gaps)}；打包缺口={facts(case.budget_gaps)}；"
              f"正确值有证据={facts(case.supported_facts)}；答复验收={decision}")
    print("同步正文误写 03:00：预先确认的证据快照不符，实际证据包被拦。单独评分 02:00 的断言："
          f"出处精确={wrong.source_exact}；包内={wrong.in_evidence}；值正确={wrong.correct}；支持={wrong.supported}。")
    print(f"预览日志：无批准 0 条，匹配批准后 {approved_entries} 条；无业务执行。")


if __name__ == "__main__":
    main()
