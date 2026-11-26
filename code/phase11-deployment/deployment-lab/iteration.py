"""A local incident-to-regression exercise; no external traffic, raw evidence or credentials in reports."""

import argparse
from dataclasses import dataclass, replace
import json
from pathlib import Path
import runpy


CODE = Path(__file__).resolve().parents[2]
RAG = runpy.run_path(str(CODE / "phase7-data-rag/rag-lab/lab.py"))


@dataclass(frozen=True)
class Case:
    case_id: str
    tenant: str
    actor: str
    key: tuple[str, int, str]
    transition: str = "unchanged"


DEV = (
    Case("dev-retention-revoked", "support", "mei", ("EXPORT-POLICY", 1, "§1"), "revoke"),
    Case("dev-retention-current", "support", "lin", ("EXPORT-POLICY", 1, "§1")),
    Case("dev-miss", "support", "mei", ("TRAINING-ABSENT", 1, "§1")),
)
HELD_OUT = (
    Case("hold-retention-new-version", "support", "mei", ("EXPORT-POLICY", 1, "§1"), "replace"),
    Case("hold-appendix-revoked", "support", "mei", ("EXPORT-OPS", 1, "§2"), "revoke"),
    Case("hold-operations-current", "operations", "mei", ("EXPORT-POLICY", 1, "§1")),
    Case("hold-appendix-current", "support", "mei", ("EXPORT-OPS", 1, "§2")),
)
VERSIONS = {"dev": "citation-dev-v1", "held_out": "citation-held-out-v1"}
BASELINE, CANDIDATE = "cached-citation-v1", "exact-current-citation-v2"

@dataclass(frozen=True)
class Label:
    split: str
    subject: tuple[str, str]
    key: tuple[str, int, str]
    transition: str
    initial_quote: str | None
    outcome: tuple[str, bool, bool | None]


# Written independently of DEV/HELD_OUT and of either rule. Raw labels stay in the lab.
GOLD = {
    "dev-retention-revoked": Label("dev", ("support", "mei"), ("EXPORT-POLICY", 1, "§1"), "revoke",
                                    "导出文件生成后保留 7 天。", ("handoff", False, None)),
    "dev-retention-current": Label("dev", ("support", "lin"), ("EXPORT-POLICY", 1, "§1"), "unchanged",
                                    "导出文件生成后保留 7 天。", ("citation_ready", True, True)),
    "dev-miss": Label("dev", ("support", "mei"), ("TRAINING-ABSENT", 1, "§1"), "unchanged",
                      None, ("needs_evidence", False, None)),
    "hold-retention-new-version": Label("held_out", ("support", "mei"), ("EXPORT-POLICY", 1, "§1"), "replace",
                                         "导出文件生成后保留 7 天。", ("handoff", False, None)),
    "hold-appendix-revoked": Label("held_out", ("support", "mei"), ("EXPORT-OPS", 1, "§2"), "revoke",
                                   "导出文件过期后，需重新发起导出。", ("handoff", False, None)),
    "hold-operations-current": Label("held_out", ("operations", "mei"), ("EXPORT-POLICY", 1, "§1"), "unchanged",
                                      "运维导出文件保留 30 天。", ("citation_ready", True, True)),
    "hold-appendix-current": Label("held_out", ("support", "mei"), ("EXPORT-OPS", 1, "§2"), "unchanged",
                                   "导出文件过期后，需重新发起导出。", ("citation_ready", True, True)),
}
FIELDS = ("status", "selected", "selection_current")
BINDING_FLAGS = ("input_matches", "lookup_matches", "initial_evidence_matches", "citation_matches")
OBSERVATION_FIELDS = ("case_id", *FIELDS, "cache_hit", "visible_exact", "rechecks", *BINDING_FLAGS)


def _query(store, reads, tenant, actor, key):
    reads.append(((tenant, actor), key))
    return store.source(tenant, actor, key)


def _quote(chunk):
    return (chunk.key, chunk.text) if chunk is not None else None


def _select(rule, cached, reread):
    if cached is None:
        return "needs_evidence", None
    if rule == CANDIDATE and _quote(reread()) != _quote(cached):
        return "handoff", None
    return "citation_ready", cached


def observe(case, rule):
    """Grade the observed calls and selection privately; only return fixed statuses and flags."""
    if rule not in (BASELINE, CANDIDATE):
        raise ValueError("unknown citation rule")
    label = GOLD[case.case_id]
    subject, reads = (case.tenant, case.actor), []
    input_matches = (subject, case.key, case.transition) == (label.subject, label.key, label.transition)
    exact = (label.key, label.initial_quote) if label.initial_quote is not None else None
    with RAG["open_demo"]() as store:
        def lookup():
            return _query(store, reads, *subject, case.key)

        cached = lookup()
        # Compare the observed hit against the original request and full quote, before fixture changes.
        initial = {chunk.key: chunk for chunk in store.authorized(*label.subject)}
        before_ok = _quote(initial.get(label.key)) == exact and _quote(cached) == exact
        if case.transition == "revoke":
            store.revoke(*subject, case.key[0])
        elif case.transition == "replace" and cached is not None:
            newer = replace(cached, version=cached.version + 1, text="本地训练政策已修订。")
            store.replace_document(case.tenant, case.key[0], newer.version, (newer,))
        elif case.transition not in {"replace", "unchanged"}:
            raise ValueError("unknown fixture transition")

        status, selected = _select(rule, cached, lookup)
        # Read back under the independently labeled original scope, not the scope used by the rule.
        visible = {chunk.key: chunk for chunk in store.authorized(*label.subject)}
        selected_quote = _quote(selected)
        currently_visible = _quote(visible.get(label.key))
        lookup_matches = reads == [(label.subject, label.key)] * (1 + int(rule == CANDIDATE and exact is not None))
        return {"case_id": case.case_id, "status": status, "cache_hit": cached is not None,
                "selected": selected is not None,
                "selection_current": selected_quote == currently_visible if selected is not None else None,
                "visible_exact": currently_visible is not None, "rechecks": len(reads) - 1,
                "input_matches": input_matches, "lookup_matches": lookup_matches,
                "initial_evidence_matches": before_ok,
                "citation_matches": selected is None or selected_quote == exact}


def verdict(case_ids, observations):
    """Score full observed outputs against independent, case-ID-bound labels."""
    rows = tuple(observations)
    received = {row["case_id"]: row for row in rows}
    if (not case_ids or len(set(case_ids)) != len(case_ids) or len(received) != len(rows)
            or set(received) != set(case_ids) or set(case_ids) - GOLD.keys()):
        raise ValueError("missing, extra, unknown or duplicate case ID")
    mismatches = {}
    for case_id in case_ids:
        actual = received[case_id]
        wrong = [field for field, expected in zip(FIELDS, GOLD[case_id].outcome, strict=True)
                 if field not in actual or type(actual[field]) is not type(expected) or actual[field] != expected]
        wrong.extend(field for field in BINDING_FLAGS if actual.get(field) is not True)
        if wrong:
            mismatches[case_id] = wrong
    n = len(case_ids)
    return {"n": n, "passes": n - len(mismatches), "mismatches": mismatches}


def _public_observation(row):
    # Do not echo unexpected keys or a malformed field's value even when scoring fails.
    status = row.get("status")
    safe = {"case_id": row["case_id"], "status": status if status in
            ("needs_evidence", "citation_ready", "handoff") else "invalid_status"}
    safe.update({field: row[field] if type(row.get(field)) is bool else None
                 for field in OBSERVATION_FIELDS if field not in {"case_id", "status", "rechecks"}})
    safe["rechecks"] = row["rechecks"] if type(row.get("rechecks")) is int else None
    return safe


def compare(split):
    cases = {"dev": DEV, "held_out": HELD_OUT}[split]
    case_ids = [case.case_id for case in cases]
    if len(case_ids) != len(set(case_ids)) or set(case_ids) != {key for key, label in GOLD.items() if label.split == split}:
        raise ValueError("case IDs do not match the labeled split")
    report = {"fixture_version": VERSIONS[split], "case_ids": case_ids,
              "expected": {case_id: dict(zip(FIELDS, GOLD[case_id].outcome, strict=True)) for case_id in case_ids}}
    for side, rule in (("baseline", BASELINE), ("candidate", CANDIDATE)):
        rows = [observe(case, rule) for case in cases]
        report[side] = {"rule": rule, "verdict": verdict(case_ids, rows),
                        "observations": [_public_observation(row) for row in rows]}
    return report


def minimize(observation):
    """Emit only the frozen incident reproduction's allowlisted structural facts."""
    if (observation["case_id"] != "dev-retention-revoked" or observation["status"] != "citation_ready"
            or observation["cache_hit"] is not True or observation["visible_exact"] is not False
            or observation["selected"] is not True or observation["selection_current"] is not False
            or any(observation.get(field) is not True for field in BINDING_FLAGS)):
        return None
    return {"id": "local-incident-01", "fixture_version": VERSIONS["dev"],
            "case_id": "dev-retention-revoked", "observed": "cached_citation_selected_after_revocation",
            "expected": "handoff_without_citation", "containment": "keep_candidate_out_of_release",
            "scope": "cache_hit_citation_selection_only",
            "review_when": ["authorization_or_document_version_changes", "valid_citations_are_withheld"]}


def _improves(split):
    a, b = (split[arm]["verdict"] for arm in ("baseline", "candidate"))
    return a["passes"] < b["passes"] == b["n"] and not b["mismatches"]


def rehearse():
    ids = [{case.case_id for case in group} for group in (DEV, HELD_OUT)]
    scenarios = [{(c.tenant, c.actor, c.key, c.transition) for c in group} for group in (DEV, HELD_OUT)]
    if ids[0] & ids[1] or scenarios[0] & scenarios[1] or ids[0] | ids[1] != GOLD.keys():
        raise ValueError("development and held-out scenarios must be separate and fully labeled")
    dev, held = compare("dev"), compare("held_out")
    incident = minimize(dev["baseline"]["observations"][0])
    retain = incident is not None and _improves(dev) and _improves(held)
    return {"incident": incident, "dev": dev, "held_out": held,
            "decision": "retain_local_rule" if retain else "revert_and_review", "production": "blocked"}


def _linked_stop(worked):
    """Tie the stop to the last actual candidate response and its closed store, not a detached signal fixture."""
    events = worked["lifecycle"]
    candidates = [row for row in events if row["role"] == "candidate"]
    joins = [row for row in events if row["event"] in {"stop", "exited", "preflight_passed", "pre_stop_audited", "started"}
             and row["role"] in {"candidate", "restored"}]
    if [(row["role"], row["event"]) for row in joins] != [
            ("candidate", "started"), ("candidate", "pre_stop_audited"), ("candidate", "stop"),
            ("candidate", "exited"), ("candidate", "preflight_passed"), ("restored", "started"), ("restored", "exited")]:
        return False
    start, pre_stop, stop, _, _, restored, _ = joins
    stop_index = events.index(stop)
    loss = events[stop_index - 1]
    stop_fields = {"pid": start["pid"], "operation": "fixture_lost", "job": "lost",
                   "observed_status": "reply_lost", "decision": "STOP_AND_ROLLBACK",
                   "reasons": ["uncertain_outcome"]}
    return (worked["stop"] == stop_fields
            and all(stop.get(key) == value for key, value in stop_fields.items())
            and events[stop_index - 2] == pre_stop and worked["pre_stop"]["saved"] == []
            and len(worked["handoff"]["saved"]) == 1
            and worked["handoff"]["saved"][0][0] == worked["lost"]["persisted_receipt"]
            and tuple(loss.get(key) for key in ("event", "role", "operation", "job", "status")) == (
                "dispatch", "candidate", "fixture_lost", "lost", "reply_lost")
            and worked["lost"]["injection"]["status"] == "reply_lost"
            and all(row["pid"] == start["pid"] and row["build"] == "v2" for row in candidates)
            and all(row["store"] == start["store"] for row in events)
            and not any(row["event"] == "dispatch" and row["role"] == "candidate" for row in events[stop_index + 1:])
            and restored["build"] == "v1" and restored["pid"] != start["pid"])


def _preserved_decisions(worked):
    tasks, before, after = worked["tasks"], worked["handoff"], worked["after"]
    outcomes = {"pre-approve": "saved", "pre-deny": "denied", "canary-approve": "saved", "canary-deny": "denied"}
    if set(tasks) != set(outcomes):
        return False
    bindings = ("tenant", "actor", "job", "action", "revision", "digest")
    for job, status in outcomes.items():
        task = tasks[job]
        decision = "approve" if status == "saved" else "deny"
        expected = [*(task["binding"][key] for key in bindings), decision]
        if (task["outcome"]["status"] != status or before["reviews"].count(expected) != 1
                or not any(row[2] == job and row[-2:] == ["pending", None] for row in before["checkpoints"])):
            return False
    pending_job = worked["undecided"]["binding"]["job"]
    prior_pending = [row for row in before["checkpoints"] if row[2] == pending_job]
    final_pending = [row for row in after["checkpoints"] if row[2] == pending_job]
    return (worked["pre_stop"]["reviews"] == before["reviews"] == after["reviews"]
            and not any(row[2] == pending_job for row in before["reviews"])
            and len(prior_pending) == 1 and prior_pending == final_pending and prior_pending[0][-2:] == ["pending", None]
            and worked["undecided"]["outcome"]["status"] == "pending"
            and not any(row["event"] == "dispatch" and row["role"] == "restored" and row["operation"] == "review"
                        for row in worked["lifecycle"]))


def handoff():
    """Run the local proofs without conflating their different inputs or granting production clearance."""
    from canary import EXPECTED_COHORT_DIGEST, rehearse as canary_rehearse
    from release_gate import rehearse as release_rehearse
    from rollback import rehearse as rollback_rehearse

    gate, canary, rollback, iteration = release_rehearse(), canary_rehearse(), rollback_rehearse(), rehearse()
    worked = rollback["worked"]
    lost = worked["lost"]
    replays = (lost["replay"], lost["repeated"])
    same_receipt = bool(lost["persisted_receipt"]) and all(row["receipt"] == lost["persisted_receipt"] for row in replays)
    rollback_summary = {"decision": rollback["decision"], "replay_status": replays[0]["status"],
                        "same_receipt": same_receipt, "replay_inserts": sum(len(row["inserts"]) for row in replays),
                        "stop": worked["stop"], "schemas": worked["handoff"]["schemas"],
                        "transition": [{key: row[key] for key in ("event", "role", "build", "pid", "store")}
                                       for row in worked["lifecycle"] if row["event"] != "dispatch"],
                        "task_outcomes": {job: task["outcome"]["status"] for job, task in worked["tasks"].items()}}
    canary_runs = [row for name, row in canary.items() if name != "passed"]
    checks = {
        "gate_fail_restore": (gate["offline_contract"]["passed"] is True
                              and gate["phase8_replay"]["passed"] is True
                              and [gate[key]["passed"] for key in ("baseline", "drop_citation", "restored")]
                              == [True, False, True]),
        "same_phase8_inputs": all(gate[key]["fingerprint"] == canary["normal"]["phase8_fingerprint"]
                                  for key in ("baseline", "drop_citation", "restored")),
        "frozen_canary_cohort": bool(canary_runs) and all(
            row["cohort_digest_valid"] is True and row["cohort_digest"] == row["expected_cohort_digest"]
            == EXPECTED_COHORT_DIGEST for row in canary_runs),
        "canary_stop_conditions": canary["passed"] is True,
        "stop_linked_to_rollback": _linked_stop(worked) and all(
            worked[phase]["schemas"] == {"business.sqlite": 1, "review.sqlite": 1}
            for phase in ("before", "pre_stop", "handoff", "after")),
        "rollback_keeps_approvals": rollback_summary["decision"] == "LOCAL_ROLLBACK_VERIFIED" and _preserved_decisions(worked),
        "rollback_keeps_original_receipt": same_receipt and all(
            row["status"] == "replayed" and row["inserts"] == [] for row in replays),
        "iteration_generalizes_locally": iteration["decision"] == "retain_local_rule",
        "no_production_clearance": (gate["production"] == iteration["production"] == "blocked"
                                    and all(row["production"] == "blocked" for row in canary_runs)),
    }
    return {"release_gate": gate, "canary": canary, "rollback": rollback_summary, "iteration": iteration,
            "checks": checks, "passed": all(checks.values()), "production": "blocked",
            "outstanding": ["real_l87_checkpoint_compatibility", "real_artifact_and_operating_environment",
                            "production_identity_approval_durability_and_recovery", "authorized_rollout_and_live_slo"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", action="store_true", help="run the full Phase 11 local handoff")
    args = parser.parse_args()
    report = handoff() if args.stage else rehearse()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.stage and report["passed"]:
        print("P11 LOCAL HANDOFF PASSED")
    return 0 if (report["passed"] if args.stage else report["decision"] == "retain_local_rule") else 1


if __name__ == "__main__":
    raise SystemExit(main())
