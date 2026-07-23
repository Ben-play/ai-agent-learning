"""Stable public interface for the offline Phase 2 assessment lab."""

from pathlib import Path

from .assessment import AssessmentLab
from .contracts import AssessmentReport


def build_offline_lab(fixture_root: Path | None = None) -> AssessmentLab:
    """Build the deterministic lab without network or environment access."""

    resolved = fixture_root or Path(__file__).resolve().parents[1] / "fixtures"
    return AssessmentLab(resolved)


__all__ = ["AssessmentLab", "AssessmentReport", "build_offline_lab"]
