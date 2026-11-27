"""Paired, offline canary trials. Hard-stop signals never route real traffic."""

import argparse
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import runpy
from sqlite3 import Error as SQLiteError


CODE = Path(__file__).resolve().parents[2]
GATE = runpy.run_path(str(CODE / "phase8-agent-engineering/engineering-lab/gate.py"))


@dataclass(frozen=True)
class Prepared:
    case_id: str
    path: str


COHORT_VERSION = "deployment-canary-v1"
# Pin the approved manifest; never derive the expected digest from the inputs being checked.
EXPECTED_COHORT_DIGEST = "5b3d7409f65c60fea1a79e7da62d259a1f6396f34ae71c682c3e215538062076"
WINDOWS = (
    (Prepared("review-denied", "deny"), Prepared("policy-retention", "answer"),
     Prepared("no-evidence", "missing")),
    (Prepared("lost-reply", "replay"), Prepared("review-pending", "pending"),
     Prepared("draft-committed", "save")),
)


def cohort_digest(version, windows):
    """Canonical JSON sorts object keys only; nested arrays retain order and boundaries."""
    manifest = {"version": version, "windows": [
        [{"case_id": case.case_id, "path": case.path} for case in window] for window in windows
    ]}
    encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()


@dataclass(frozen=True)
class Label:
    status: str
    checkpoint: str | None
    effects: tuple[int, int, int, int, int]
    same_receipt: bool | None = None
    citations: tuple = ()
    payload: str | None = None


# Hand-authored independently of WINDOWS, Phase 8's report and both runners.
ZERO = (0, 0, 0, 0, 0)
LABELS = {
    "policy-retention": Label("answered", None, ZERO, citations=(
        ("EXPORT-POLICY", 1, "§1", "导出文件生成后保留 7 天。"),), payload="导出文件生成后保留 7 天。"),
    "no-evidence": Label("needs_evidence", None, ZERO),
    "review-pending": Label("pending", "pending", ZERO),
    "review-denied": Label("denied", "denied", ZERO),
    "draft-committed": Label("saved", "saved", (1, 0, 1, 1, 0), citations=(
        ("SYNC-POLICY", 1, "§1", "同步任务每天 02:00 运行。"),), payload="同步任务每天 02:00 运行。"),
    "lost-reply": Label("replayed", "saved", (1, 1, 1, 1, 0), True,
                        (("SYNC-POLICY", 1, "§1", "同步任务每天 02:00 运行。"),), "同步任务每天 02:00 运行。"),
}
EFFECTS = ("dispatches", "recoveries", "writes", "saved_rows", "replay_writes")
APPROVAL_LABEL = {"reason": "approval_required", "checkpoint": "pending", "dispatches": 0,
                  "writes": 0, "rows": 0, "receipt": False}
CRITICAL_PROBES = {"review-denied": "authority_probe_failed", "review-pending": "pending_probe_failed",
                   "lost-reply": "recovery_probe_failed"}
READBACK_ERRORS = (AssertionError, AttributeError, KeyError, OSError, RuntimeError, TypeError,
                   ValueError, SQLiteError)
# The timing contract is independent of observed events and business readback.
EXPECTED_TIMING_EVENTS = {
    "review-denied": ("stage", "deny"),
    "policy-retention": ("retrieve", "render_answer"),
    "no-evidence": ("retrieve",),
    "lost-reply": ("retrieve", "stage", "approved_call", "recover"),
    "review-pending": ("stage",),
    "draft-committed": ("retrieve", "stage", "approved_call"),
}
SIMULATED_MS = {"retrieve": 24, "render_answer": 21, "stage": 12, "deny": 18,
                "approved_call": 24, "recover": 40}
MIN_SAMPLE = 6
MAX_P95_MS = 110
MAX_P95_INCREASE_MS = 10
CANDIDATES = ("v2", "v2-slow", "v2-uncited", "v2-authority-fault", "v2-recovery-fault")
# These fixtures simulate broken monitor signals only, never authorization or recovery code.
SIGNAL_FIXTURES = {"v2-authority-fault": ("review-denied", "authority_probe_failed"),
                   "v2-recovery-fault": ("lost-reply", "recovery_probe_failed")}


def nearest_rank_p95(samples):
    """Index ceil(0.95*n) in a 1-based sorted list; no interpolation."""
    ordered = sorted(samples)
    return ordered[(95 * len(ordered) + 99) // 100 - 1] if ordered else None


def approval_probe():
    """Keep only required fields; incomplete readback is not evidence of zero effects."""
    try:
        result = GATE["AUTH"]["run_case"]("unapproved")
        return {key: result[key] for key, expected in APPROVAL_LABEL.items()
                if type(result.get(key)) is type(expected)}
    except READBACK_ERRORS:
        return None


def event_timing(row, case, arm):
    try:
        events = row.events
    except READBACK_ERRORS:
        return [], None
    if not isinstance(events, (tuple, list)) or not all(isinstance(event, str) for event in events):
        return [], None
    if (tuple(events) != EXPECTED_TIMING_EVENTS[case.case_id]
            or any(event not in SIMULATED_MS for event in events)):
        return list(events), None
    elapsed = sum(SIMULATED_MS[event] for event in events)
    # A simulated response delay cannot turn unknown timing into a valid measurement.
    if arm == "v2-slow" and case.case_id == "no-evidence":
        elapsed += 100
    return list(events), elapsed


def observe(case, arm):
    """Execute the prepared case in a fresh trial; check contract, probes and timing separately."""
    label = LABELS[case.case_id]
    probe_failure = CRITICAL_PROBES.get(case.case_id)
    variant = "drop-citation" if arm == "v2-uncited" else "baseline"
    events, elapsed = [], None
    try:
        row = GATE["exercise"]({"id": case.case_id, "path": case.path}, variant=variant)
        events, elapsed = event_timing(row, case, arm)
        actual = {"status": row.status, "checkpoint": row.checkpoint,
                  "effects": tuple(getattr(row, key) for key in EFFECTS),
                  "same_receipt": row.same_receipt, "citations": row.citations, "payload": row.payload}
        if any(type(count) is not int or count < 0 for count in actual["effects"]):
            raise ValueError("invalid effect counts")
        if row.same_receipt is not None and type(row.same_receipt) is not bool:
            raise ValueError("invalid receipt comparison")
        wrong = [field for field, value in actual.items() if value != getattr(label, field)]
        if row.case_id != case.case_id:
            wrong.append("case_id")
        citation_keys = [list(cite[:3]) for cite in row.citations]
    except READBACK_ERRORS:
        # The actual effect or critical readback failed. Report no exception text or invented timing.
        return {"case_id": case.case_id, "path": case.path, "status": "trial_error", "passed": False,
                "error": True, "events": events, "simulated_ms": elapsed,
                "mismatches": ["readback_unavailable"], "hard_signals": [probe_failure] if probe_failure else []}

    approval = None
    if case.case_id == "review-denied":
        approval = approval_probe()
        if approval != APPROVAL_LABEL:
            wrong.append("approval_probe")
    hard = []
    if any(got > allowed for got, allowed in zip(actual["effects"], label.effects, strict=True)):
        hard.append("authority_probe_failed")
    if probe_failure and wrong and probe_failure not in hard:
        hard.append(probe_failure)

    return {"case_id": row.case_id, "path": case.path, "status": row.status,
            "checkpoint": row.checkpoint, **dict(zip(EFFECTS, actual["effects"], strict=True)),
            "same_receipt": row.same_receipt, "citation_keys": citation_keys,
            "approval_probe": approval, "events": events, "mismatches": wrong,
            "passed": not wrong and not hard, "error": row.status != label.status,
            "simulated_ms": elapsed, "hard_signals": hard}


def summarize(rows):
    n = len(rows)
    successes = sum(row["passed"] for row in rows)
    samples = [row["simulated_ms"] for row in rows if row["simulated_ms"] is not None]
    return {"n": n, "successes": successes, "success_rate": successes / n if n else None,
            "errors": sum(row["error"] for row in rows), "timed": len(samples),
            "p95_ms": nearest_rank_p95(samples) if len(samples) == n else None, "rows": list(rows)}


def decide(control, candidate, *, complete, hard_signals=()):
    """A pure decision: a hard signal outranks sample size, health and even missing metrics."""
    if hard_signals:
        return "STOP_AND_ROLLBACK", list(dict.fromkeys(hard_signals))
    if not complete or min(control["n"], candidate["n"]) < MIN_SAMPLE:
        return "HOLD", ["incomplete_cohort"]
    if control["p95_ms"] is None or candidate["p95_ms"] is None:
        return "HOLD", ["latency_unavailable"]
    if control["success_rate"] != 1 or control["errors"]:
        return "HOLD", ["control_not_healthy"]
    reasons = []
    if candidate["success_rate"] < control["success_rate"]:
        reasons.append("success_rate")
    if candidate["errors"] > control["errors"]:
        reasons.append("errors")
    if candidate["p95_ms"] > MAX_P95_MS:
        reasons.append("p95_absolute")
    if candidate["p95_ms"] - control["p95_ms"] > MAX_P95_INCREASE_MS:
        reasons.append("p95_regression")
    return ("STOP_AND_ROLLBACK", reasons) if reasons else ("CONTINUE_LOCAL", [])


def signal_fixture(arm, case_id):
    """Pure fault stimulus, not an end-to-end failure or an instruction to a runner."""
    target, signal = SIGNAL_FIXTURES.get(arm, (None, None))
    return (signal,) if target == case_id else ()


def run(candidate="v2"):
    if candidate not in CANDIDATES:
        raise ValueError("unknown candidate")
    version = COHORT_VERSION
    try:
        schedule = tuple(tuple(window) for window in WINDOWS)
        digest = cohort_digest(version, schedule)
    except (AttributeError, TypeError, ValueError):
        digest = None
    valid = digest is not None and digest == EXPECTED_COHORT_DIGEST
    report = {"cohort_version": version, "cohort_digest": digest,
              "expected_cohort_digest": EXPECTED_COHORT_DIGEST, "cohort_digest_valid": valid,
              "phase8_fingerprint": GATE["INPUTS"]("gate")["sha256"],
              "candidate_version": candidate, "production": "blocked"}
    if not valid:
        return {**report, "complete": False, "windows": [], "control": summarize([]),
                "candidate": summarize([]), "decision": "HOLD", "reasons": ["cohort_drift"], "fault_fixture": []}
    planned = [case.case_id for window in schedule for case in window]
    if len(set(planned)) != len(planned) or set(planned) != LABELS.keys():
        raise ValueError("the prepared cohort must match the independent labels one to one")

    control, trial, windows, hard, injected = [], [], [], [], []
    for number, window in enumerate(schedule, 1):
        start_v1, start_v2 = len(control), len(trial)
        for case in window:
            control.append(observe(case, "v1"))
            hard.extend(control[-1]["hard_signals"])
            if hard:
                break
            trial.append(observe(case, candidate))
            injected = list(signal_fixture(candidate, case.case_id))
            hard.extend((*trial[-1]["hard_signals"], *injected))
            if hard:
                break  # Do not start another trial, even in the same window.
        windows.append({"window": number, "planned": [case.case_id for case in window],
                        "control_n": len(control) - start_v1, "candidate_n": len(trial) - start_v2})
        if hard:
            break
    a, b = summarize(control), summarize(trial)
    complete = all(side["timed"] == len(planned) and [row["case_id"] for row in side["rows"]] == planned
                   and all(row["status"] != "trial_error" for row in side["rows"]) for side in (a, b))
    decision, reasons = decide(a, b, complete=complete, hard_signals=hard)
    return {**report, "complete": complete, "windows": windows, "control": a, "candidate": b,
            "decision": decision, "reasons": reasons, "fault_fixture": injected}


def rehearse():
    normal, slow, uncited, authority, recovery = (run(arm) for arm in CANDIDATES)
    return {"normal": normal, "metric_stop": slow, "citation_stop": uncited,
            "authority_stop": authority, "recovery_stop": recovery,
            "passed": (normal["decision"] == "CONTINUE_LOCAL"
                       and slow["reasons"] == ["p95_absolute", "p95_regression"]
                       and uncited["reasons"] == ["success_rate"]
                       and authority["reasons"] == ["authority_probe_failed"]
                       and recovery["reasons"] == ["recovery_probe_failed"]
                       and authority["candidate"]["n"] == 1 and recovery["candidate"]["n"] == 4
                       and authority["decision"] == recovery["decision"] == "STOP_AND_ROLLBACK")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", choices=CANDIDATES)
    candidate = parser.parse_args().candidate
    report = run(candidate) if candidate else rehearse()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if (report["decision"] == "CONTINUE_LOCAL" if candidate else report["passed"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
