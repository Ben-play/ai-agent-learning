from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MARKER_PARTS = ("PHASE 2 PRACTICES", " ACCEPTED")


def run_module(module: str, *, optimized: bool = False) -> subprocess.CompletedProcess[str]:
    command = [sys.executable]
    if optimized:
        command.append("-O")
    command.extend(["-m", module])
    return subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_acceptance_and_main_print_exactly_one_line() -> None:
    marker = "".join(MARKER_PARTS)
    acceptance = run_module("phase2_practices.acceptance")
    assert acceptance.returncode == 0, acceptance.stderr
    assert acceptance.stdout == marker + "\n"
    main = subprocess.run(
        [sys.executable, "main.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert main.returncode == 0, main.stderr
    assert main.stdout == marker + "\n"


def test_success_marker_has_one_source_occurrence() -> None:
    marker = "".join(MARKER_PARTS)
    source_paths = list((ROOT / "phase2_practices").rglob("*.py")) + [
        ROOT / "main.py"
    ]
    occurrences = sum(
        path.read_text(encoding="utf-8").count(marker) for path in source_paths
    )
    assert occurrences == 1


@pytest.mark.parametrize(
    ("module", "targeted_assertion"),
    [
        (
            "phase2_practices.counterfactuals.consistency_as_truth",
            "consistency-as-truth accepted five consistent unsupported/wrong observations",
        ),
        (
            "phase2_practices.counterfactuals.rank_before_gate",
            "rank-before-gate selected an unsafe cheap candidate rejected by hard gates",
        ),
    ],
)
def test_counterfactuals_fail_for_the_intended_assertion(
    module: str, targeted_assertion: str
) -> None:
    marker = "".join(MARKER_PARTS)
    for optimized in (False, True):
        result = run_module(module, optimized=optimized)
        assert result.returncode != 0
        assert "CounterfactualReached" in result.stderr
        assert targeted_assertion in result.stderr
        assert "ModuleNotFoundError" not in result.stderr
        assert "ImportError" not in result.stderr
        assert marker not in result.stdout
        assert marker not in result.stderr
