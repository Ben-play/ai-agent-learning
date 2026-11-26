"""Rehearse a local promotion contract. This module cannot authorize production."""

import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import runpy
import subprocess

PHASE8 = Path(__file__).resolve().parents[2] / "phase8-agent-engineering/engineering-lab"
_REPLAY_VARIANTS = {"baseline": "baseline", "drop_citation": "drop-citation", "restored": "baseline"}
CANDIDATE_ARTIFACT = b"support-agent-1.4.2\nfixture bundle\n"
_ROLLBACK_ARTIFACT = b"support-agent-1.4.1\nfixture bundle\n"
_AS_OF = 1_800_000_000  # Fixed classroom clock, not a production timestamp.
_MAX_AGE_SECONDS = 900


def sample_contract():
    """Return an editable manifest and hypothetical compatibility observations for the lab."""
    manifest = {
        "contract_version": "local-promotion-v1",
        "environment": "classroom",
        "candidate": {
            "build_version": "support-agent-1.4.2",
            "artifact_sha256": "0223f007bb2b1953d3887f85a5564f53b1ebd24de8ecdd6e527bbf97d5cd2e95",
            "writer_schema": 2,
            "config_fingerprint": "03d2ad2b721328f5579f3feb077ab2d91633d0a3025c5349567856c15ce16c45",
        },
        "rollback_target": {
            "build_version": "support-agent-1.4.1",
            "artifact_sha256": "b4d31f465efb659a953c273100698edbc269c6279059dbf99e084956c1757143",
            "writer_schema": 1,
            "config_fingerprint": "07e10d1469a900bb5157bfa4778608c6d6d9d0df6e32c29de0e8985f68d8803b",
        },
    }
    evidence = {
        "kind": "synthetic-compatibility-v1",
        "environment": "classroom",
        "observed_at": 1_799_999_700,
        "candidate": deepcopy(manifest["candidate"]),
        "rollback_target": deepcopy(manifest["rollback_target"]),
        "observations": {
            "legacy_shape_refusals": 2,
            "candidate_dispatches": 0,
            "candidate_writes": 0,
            "rollback_saves": 1,
            "rollback_replay_writes": 0,
        },
    }
    return manifest, evidence


def _identity(version, artifact, writer_schema, config):
    canonical = json.dumps(config, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return {
        "build_version": version,
        "artifact_sha256": sha256(artifact).hexdigest(),
        "writer_schema": writer_schema,
        "config_fingerprint": sha256(canonical.encode("ascii")).hexdigest(),
    }


def _compare(actual, expected, path, reasons):
    """Compare exact keys and types; in Python, False would otherwise compare equal to zero."""
    if type(actual) is not type(expected):
        reasons.append(f"{path}:malformed")
    elif isinstance(expected, dict):
        if actual.keys() - expected.keys():
            reasons.append(f"{path}:unexpected_fields")
        for field, target in expected.items():
            name = f"{path}.{field}"
            if field not in actual:
                reasons.append(f"{name}:missing")
            else:
                _compare(actual[field], target, name, reasons)
    elif actual != expected:
        reasons.append(f"{path}:mismatched")


def validate_contract(manifest, evidence, *, artifact=CANDIDATE_ARTIFACT):
    """Check submitted descriptions against fixture bytes, runtime metadata and an independent oracle.

    A passing result means only that the local manifest and synthetic evidence agree with
    this classroom policy. No real L87 evidence can be submitted through this interface.
    """
    if not isinstance(artifact, bytes):
        reason = "missing" if artifact is None else "malformed"
        return {"passed": False, "reasons": [f"artifact:{reason}"]}
    # Known bundle and runtime metadata come from the lab, not either submission.
    build = _identity("support-agent-1.4.2", CANDIDATE_ARTIFACT, 2,
                      {"store": "sqlite-v2", "approval": "host-only"})
    rollback = _identity("support-agent-1.4.1", _ROLLBACK_ARTIFACT, 1,
                         {"store": "sqlite-v1", "approval": "host-only"})
    bindings = {"environment": "classroom", "candidate": build, "rollback_target": rollback}
    reasons = []
    if sha256(artifact).hexdigest() != build["artifact_sha256"]:
        reasons.append("artifact.sha256:mismatched")
    _compare(manifest, {"contract_version": "local-promotion-v1", **bindings}, "manifest", reasons)
    if evidence is None:
        reasons.append("evidence:missing")
    else:
        observed_at = evidence.get("observed_at") if isinstance(evidence, dict) else None
        _compare(evidence, {
            "kind": "synthetic-compatibility-v1", **bindings,
            "observed_at": observed_at if type(observed_at) is int else 0,
            "observations": {
                "legacy_shape_refusals": 2, "candidate_dispatches": 0, "candidate_writes": 0,
                "rollback_saves": 1, "rollback_replay_writes": 0,
            },
        }, "evidence", reasons)
        if type(observed_at) is int:
            if observed_at > _AS_OF:
                reasons.append("evidence.observed_at:future")
            elif _AS_OF - observed_at > _MAX_AGE_SECONDS:
                reasons.append("evidence.observed_at:stale")
    return {"passed": not reasons, "reasons": reasons}


def _phase8_replay():
    """Use the Phase 8 handoff's CLI collector and its actual provenance allowlist."""
    handoff = runpy.run_path(str(PHASE8 / "handoff.py"))
    fingerprint = handoff["PROVENANCE"]["input_fingerprint"]
    before = fingerprint("gate")
    runs = {name: handoff["check_cli"](variant) for name, variant in _REPLAY_VARIANTS.items()}
    baseline, negative, restored = runs.values()
    good, red = baseline["report"], negative["report"]
    expected_red_cases = dict(good["by_case"], retention=dict(good["by_case"]["retention"], citation_keys=[]))
    reasons = []
    if (any(arm["report"]["input_fingerprint"] != before["sha256"]
            for arm in (baseline, negative, restored)) or fingerprint("gate") != before):
        reasons.append("phase8.input_fingerprint:mismatched")
    if (baseline["exit_code"] != 0 or good["passed"] is not True or good["blocks"] != []
            or good["failures"] != {} or not good["by_case"]["retention"]["citation_keys"]
            or baseline != restored):
        reasons.append("phase8.baseline_or_restore:mismatched")
    if (negative["exit_code"] != 1 or red["passed"] is not False
            or red["blocks"] != ["citation_contract", "success_rate"]
            or red["failures"] != {"retention": ["citations"]}
            or red["by_case"] != expected_red_cases
            or any(red[key] != good[key] for key in ("suite_version", "metric_version", "cases", "total_credits"))):
        reasons.append("phase8.drop_citation:mismatched")
    arms = {}
    for name, arm in runs.items():
        report = arm["report"]
        arms[name] = {"exit_code": arm["exit_code"], "passed": report["passed"] is True and arm["exit_code"] == 0,
                      "fingerprint": report["input_fingerprint"], "blocks": report["blocks"],
                      "failures": report["failures"], "successes": report["successes"], "cases": report["cases"]}
    return arms, reasons


def promote_offline(manifest, evidence, *, artifact=CANDIDATE_ARTIFACT):
    """Apply both the manifest contract and observed Phase 8 gate; never deploy."""
    validation = validate_contract(manifest, evidence, artifact=artifact)
    try:
        arms, gate_reasons = _phase8_replay()
    except (OSError, RuntimeError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
        arms = {name: {"passed": False, "fingerprint": "", "exit_code": None, "blocks": [],
                       "failures": {}, "successes": None, "cases": None} for name in _REPLAY_VARIANTS}
        gate_reasons = ["phase8.replay:unavailable"]
    return {
        **arms,
        "reviewed_manifest": deepcopy(manifest) if validation["passed"] else None,
        "offline_contract": validation,
        "phase8_replay": {"passed": not gate_reasons, "reasons": gate_reasons},
        "classroom_promotion": {
            name: "eligible" if validation["passed"] and not gate_reasons and arm["passed"] else "blocked"
            for name, arm in arms.items()
        },
        "compatibility_labels": "synthetic-only",
        "l87_evidence": {"status": "not_verified", "required_sections": [
            "phase6_original_snapshots", "phase10_application_fixtures",
        ]},
        "production": "blocked",
        "production_blockers": ["l87_real_compatibility_not_verified", "no_production_authority_in_classroom"],
    }


def rehearse():
    """Return the JSON-ready L94 handoff. Live L87 compatibility is never inferred or read from input."""
    return promote_offline(*sample_contract())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()  # No promotion-approval or L87 override flags.
    report = rehearse()
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report["offline_contract"]["passed"] and report["phase8_replay"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
