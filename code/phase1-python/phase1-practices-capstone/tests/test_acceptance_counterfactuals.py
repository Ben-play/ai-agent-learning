from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MARKER_PARTS = ("PHASE 1 PRACTICES", " ACCEPTED")


def run_module(module: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", module],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_acceptance_is_successful_and_marker_has_one_source_occurrence() -> None:
    marker = "".join(MARKER_PARTS)
    completed = run_module("phase1_practices.acceptance")
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == marker + "\n"
    occurrences = 0
    for path in ROOT.rglob("*"):
        if path.is_file() and path.suffix in {".py", ".toml", ".md"}:
            occurrences += path.read_text(encoding="utf-8").count(marker)
    assert occurrences == 1


@pytest.mark.parametrize(
    "module",
    [
        "phase1_practices.counterfactuals.whole_batch_retry",
        "phase1_practices.counterfactuals.schema_only_execution",
    ],
)
def test_counterfactuals_fail_without_marker(module: str) -> None:
    marker = "".join(MARKER_PARTS)
    completed = run_module(module)
    assert completed.returncode != 0
    assert marker not in completed.stdout
    assert marker not in completed.stderr
