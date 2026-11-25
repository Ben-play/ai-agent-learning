"""Produce an auditable local handoff, without mixing independent fixture results."""

from dataclasses import asdict
import json
from pathlib import Path
import runpy
import subprocess
import sys

HERE = Path(__file__).resolve().parent
PROVENANCE = runpy.run_path(str(HERE / "provenance.py"))


def check_cli(variant):
    process = subprocess.run([sys.executable, "-I", "-X", "utf8", str(HERE / "gate.py"), "--variant", variant],
                             capture_output=True, encoding="utf-8", timeout=30, check=False)
    if process.stderr:
        raise RuntimeError(f"gate did not return a clean report for {variant}: {process.stderr.strip()}")
    return {"exit_code": process.returncode, "report": json.loads(process.stdout)}


def run_handoff():
    inputs = {group: PROVENANCE["input_fingerprint"](group) for group in PROVENANCE["GROUPS"]}
    before = check_cli("baseline")
    regression = check_cli("drop-citation")
    restored = check_cli("baseline")
    if any(item["report"]["input_fingerprint"] != inputs["gate"]["sha256"]
           for item in (before, regression, restored)):
        raise RuntimeError("three runs must use the same gate inputs")
    if before["exit_code"] != 0 or before["report"]["passed"] is not True or restored != before:
        raise RuntimeError("baseline and restored runs must match")
    if (regression["exit_code"] != 1 or regression["report"]["passed"] is not False
            or regression["report"]["blocks"] != ["citation_contract", "success_rate"]
            or regression["report"]["failures"] != {"retention": ["citations"]}
            or any(regression["report"][key] != before["report"][key]
                   for key in ("suite_version", "metric_version", "cases", "total_credits"))):
        raise RuntimeError("known citation regression was not independently detected")

    evaluation = runpy.run_path(str(HERE / "evaluation/main.py"))["run_acceptance"](repeats=2)
    if evaluation["passed"] is not True:
        raise RuntimeError("repeated evaluation fixture failed")
    eval_summary = {key: evaluation[key] for key in
                    ("dataset_version", "split", "tasks", "repeats", "passed_trials", "total_trials")}

    t = runpy.run_path(str(HERE / "telemetry/lab.py"))
    t["run_acceptance"]()
    rx = t["LocalReceiver"](t["FixedClock"]())
    trace_id = t["run_trial"](rx, task=79, trial=1, trace_key=791)
    trace = t["summarize_trace"](rx, trace_id, role="trace_reader")

    design = runpy.run_path(str(HERE / "design/system_design.py"))
    name = "approved-draft"
    choice = design["select"](next(case for case in design["CASES"] if case.id == name))
    if design["check_decision"](choice, name, design["LABELS"][name]):
        raise RuntimeError("workflow decision failed its review label")

    if any(PROVENANCE["input_fingerprint"](group) != value for group, value in inputs.items()):
        raise RuntimeError("listed inputs changed during collection")
    return {"handoff_version": "engineering-handoff-v2", "inputs": inputs,
            "baseline": before, "regression": regression, "restored": restored,
            "evaluation_summary": eval_summary, "trace_sample": trace, "decision": asdict(choice),
            "scope": "offline synthetic fixtures; the trace is not from a gate trial",
            "unverified": ["live model quality and bills", "production identity and permissions",
                           "live p95 and distributed recovery", "OTel SDK/Collector interoperability",
                           "remote PR status and branch protection"]}


if __name__ == "__main__":
    print(json.dumps(run_handoff(), ensure_ascii=False, indent=2))
