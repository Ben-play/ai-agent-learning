"""One offline acceptance suite for the Phase 7 read and Phase 5 local-save seams."""

import argparse
from dataclasses import dataclass
import json
from math import ceil, isfinite
from pathlib import Path
import runpy
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent
CODE = ROOT.parents[1]
RAG = runpy.run_path(str(CODE / "phase7-data-rag/rag-lab/lab.py"))
HARNESS = runpy.run_path(str(CODE / "phase5-agent-harness/harness-lab/main.py"))
AUTH = runpy.run_path(str(ROOT / "authority.py"))
READBACK = runpy.run_path(str(ROOT / "observations.py"))["saved_drafts"]
INPUTS = runpy.run_path(str(ROOT / "provenance.py"))["input_fingerprint"]
DATA = ROOT / "fixtures/acceptance-v2.json"
VARIANTS = ("baseline", "drop-citation", "extra-proposal", "extra-read")
PATHS = {"answer", "missing", "pending", "deny", "save", "replay"}
EFFECT_COUNTS = ("dispatches", "recoveries", "writes", "saved_rows", "replay_writes")
REQUIRED = {"status", "checkpoint", "citations", "payload", "same_receipt", *EFFECT_COUNTS}


@dataclass(frozen=True)
class Observation:
    case_id: str
    status: str
    checkpoint: str | None
    citations: tuple[tuple[str, int, str, str], ...]
    payload: str | None  # answer text or independently verified durable body, not copied from gold
    dispatches: int  # approved first-call entries; recovery has its own counter
    recoveries: int
    writes: int
    saved_rows: int
    replay_writes: int
    same_receipt: bool | None
    extra_proposals: int
    events: tuple[str, ...]  # observed local entries, not a per-path cost estimate


def exercise(case, *, variant="baseline") -> Observation:
    """Guarded host commands. Every trial owns a new evidence store and a temporary DB."""
    path = case["path"]
    if variant not in VARIANTS or path not in PATHS:
        raise ValueError("unknown fixture variant or workflow path")
    citations, writes, events = [], [], []
    checkpoint, same_receipt, payload = None, None, None
    replay_writes = 0
    actor, job = HARNESS["Actor"]("support", "mei"), "engineering-fixture"
    with RAG["open_demo"]() as evidence:
        if path in {"answer", "missing", "save", "replay"}:
            term = ("未收录的领取规则" if path == "missing" else
                    "同步" if path in {"save", "replay"} else "保留")
            def retrieve():
                events.append("retrieve")
                return evidence.search(actor.tenant, actor.name, RAG["Query"]((term,)), k=1)

            hits = retrieve()
            if variant == "extra-read" and path == "replay":
                # Redundant but authorized local read; the draft and its approval are unchanged.
                hits = retrieve()
            for hit in hits:
                current = evidence.source("support", "mei", hit.chunk.key)
                if current is None or current != hit.chunk:
                    raise ValueError("retrieved evidence failed current-source validation")
                citations.append((*current.key, current.text))
    with TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "draft.sqlite3"
        authority = AUTH["DraftAuthority"](actor, None, None, frozenset(), False)
        with HARNESS["open_store"](db_path, on_draft_write_attempt=writes.append) as store:
            def approve(owner, binding, *, lose_reply=False):
                events.append("approved_call")
                return store.resume(owner, job, binding, HARNESS["Review"].APPROVE, lose_reply=lose_reply)

            if path in {"answer", "missing"}:
                if citations:
                    events.append("render_answer")
                    payload = citations[0][3]
                status = "answered" if payload else "needs_evidence"
                if variant == "drop-citation" and path == "answer":
                    citations.clear()  # known benign regression: correct text, no source
                if variant == "extra-proposal" and path == "answer":
                    authority.submit(AUTH["SAVE"], None, save=approve)
            elif path in {"save", "replay"} and not citations:
                status = "needs_evidence"
            else:
                events.append("stage")
                staged = store.stage(actor, job, 1, "同步任务几点运行？")
                if path == "pending":
                    status = staged.status
                elif path == "deny":
                    events.append("deny")
                    status = store.resume(actor, job, staged.binding, HARNESS["Review"].DENY).status
                else:
                    # Two teaching seams, not a shared document schema. Link synthetic facts
                    # before saving; Phase 5 keeps its legacy source ID and owns the draft.
                    if (staged.draft.body != citations[0][3] or staged.draft.source_ids != ("KB-03",)
                            or citations[0][0] != "SYNC-POLICY"):
                        raise ValueError("local draft is not aligned with the retrieved fixture")
                    authority = AUTH["DraftAuthority"](actor, staged.binding, staged.binding,
                                                       frozenset({AUTH["SCOPE"]}), True)
                    if path == "save":
                        _, result = authority.submit(AUTH["SAVE"], staged.binding, save=approve)
                        status = result.status
                        if result.status == "saved" and (not result.op_id or result.draft != staged.draft):
                            raise ValueError("save returned an inconsistent receipt or draft")
                    else:
                        status = "reply_lost"
                        try:
                            authority.submit(AUTH["SAVE"], staged.binding,
                                             save=lambda owner, binding: approve(owner, binding, lose_reply=True))
                        except HARNESS["LostReply"]:
                            pass
                        else:
                            raise AssertionError("loss fixture did not run")
        with HARNESS["open_store"](db_path, on_draft_write_attempt=writes.append) as reopened:
            final = reopened.checkpoint(actor, job)
            checkpoint = final.status if final else None
            if path == "replay" and final is not None:
                before = len(writes)
                events.append("recover")  # At the recovery call, not inferred from the case ID.
                replay = reopened.resume(actor, job, staged.binding, HARNESS["Review"].APPROVE)
                status = replay.status
                replay_writes = len(writes) - before
                same_receipt = (final.op_id is not None and replay.op_id == final.op_id
                                and replay.draft == staged.draft == final.draft)
        committed = READBACK(db_path)
        saved_rows = len(committed)
        if saved_rows == 1 and final is not None and path in {"save", "replay"}:
            op_id, tenant, user, row_job, persisted_payload = committed[0]
            title, body, ids = persisted_payload
            belongs = (tenant, user, row_job) == (actor.tenant, actor.name, job)
            persisted = HARNESS["Draft"](title, body, tuple(ids))
            if belongs and op_id == final.op_id and persisted == staged.draft == final.draft:
                payload = body
                if path == "save" and (status != "saved" or result.op_id != op_id):
                    raise ValueError("save receipt does not match the committed row")
        if path == "replay" and payload is None:
            same_receipt = False
    return Observation(case["id"], status, checkpoint, tuple(citations), payload,
                       len(authority.dispatches), events.count("recover"), len(writes), saved_rows,
                       replay_writes, same_receipt, authority.extra_proposals, tuple(events))


def evaluate(suite, observations):
    """Score actual observations against independently authored JSON expectations."""
    observations = tuple(observations)
    expected = {row["id"]: row["expected"] for row in suite["cases"]}
    received = {row.case_id: row for row in observations}
    if len(expected) != len(suite["cases"]) or len(received) != len(observations) or received.keys() != expected.keys():
        raise ValueError("missing, unexpected or duplicate case ID")
    if not observations:
        raise ValueError("suite cannot be empty")
    tariff = suite["event_tariff"]
    if not tariff or any(not isinstance(pair, (list, tuple)) or len(pair) != 2
                         or any(type(value) is not int or value < 0 for value in pair)
                         for pair in tariff.values()):
        raise ValueError("event charges and durations must be nonnegative integer pairs")
    failures, hard, cases = {}, [], {}
    credits, latency, proposals = 0, [], 0
    for case_id, row in received.items():
        spec = expected[case_id]
        if spec.keys() != REQUIRED:
            raise ValueError("gold case must cover every contract field")
        actual = {"status": row.status, "checkpoint": row.checkpoint,
                  "citations": [list(cite) for cite in row.citations], "payload": row.payload,
                  **{key: getattr(row, key) for key in EFFECT_COUNTS}, "same_receipt": row.same_receipt}
        wrong = [field for field, value in spec.items() if actual[field] != value]
        if wrong:
            failures[case_id] = wrong
        if any(type(values[key]) is not int or values[key] < 0
               for key in EFFECT_COUNTS for values in (actual, spec)):
            raise ValueError("effect counts must be nonnegative integers")
        if (any(actual[key] > spec[key] for key in EFFECT_COUNTS) or row.replay_writes != 0
                or (spec["same_receipt"] is True and row.same_receipt is not True)):
            hard.append(case_id)
        if not row.events or any(event not in tariff for event in row.events):
            raise ValueError("missing or unknown metered event")
        if type(row.extra_proposals) is not int or row.extra_proposals < 0:
            raise ValueError("proposal count must be a nonnegative integer")
        charged = sum(tariff[event][0] for event in row.events)
        elapsed = sum(tariff[event][1] for event in row.events)
        credits += charged
        latency.append(elapsed)
        proposals += row.extra_proposals
        # No answer or source text in the normal CI report, even for these fixtures.
        cases[case_id] = {"status": row.status, "checkpoint": row.checkpoint,
                          "citation_keys": [list(cite[:3]) for cite in row.citations],
                          **{key: actual[key] for key in EFFECT_COUNTS}, "same_receipt": row.same_receipt,
                          "extra_proposals": row.extra_proposals, "events": list(row.events),
                          "credits": charged, "elapsed_ms": elapsed}
    successes = len(observations) - len(failures)
    unit = credits / successes if successes else None
    p95 = sorted(latency)[ceil(0.95 * len(latency)) - 1]
    limits = suite["thresholds"]
    if (limits.keys() != {"min_success_rate", "max_credits_per_success", "max_p95_ms", "max_extra_proposals"}
            or any(type(value) not in (int, float) or not isfinite(value) or value < 0
                   for value in limits.values()) or limits["min_success_rate"] > 1):
        raise ValueError("invalid fixture thresholds")
    success_rate = successes / len(observations)
    blocks = []
    if hard:
        blocks.append("forbidden_or_duplicate_effect")
    if any("citations" in wrong for wrong in failures.values()):
        blocks.append("citation_contract")
    if success_rate < limits["min_success_rate"]:
        blocks.append("success_rate")
    if unit is None or unit > limits["max_credits_per_success"]:
        blocks.append("credits_per_success")
    if p95 > limits["max_p95_ms"]:
        blocks.append("p95_ms")
    if proposals > limits["max_extra_proposals"]:
        blocks.append("extra_proposals")
    return {"suite_version": suite["suite_version"], "metric_version": suite["metric_version"],
            "cases": len(observations), "successes": successes, "success_rate": success_rate,
            "total_credits": credits, "credits_per_success": unit, "p95_ms": p95,
            "extra_proposals": proposals, "hard_failures": sorted(hard), "failures": failures,
            "by_case": cases, "blocks": blocks, "passed": not blocks}


def run(variant="baseline") -> dict:
    inputs = INPUTS("gate")["sha256"]
    suite = json.loads(DATA.read_text(encoding="utf-8"))
    report = evaluate(suite, (exercise(case, variant=variant) for case in suite["cases"]))
    return {**report, "input_fingerprint": inputs}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=VARIANTS, default="baseline")
    args = parser.parse_args()
    report = run(args.variant)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
