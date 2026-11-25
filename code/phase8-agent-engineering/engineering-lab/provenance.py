"""Versioned allowlists of the local source and fixture inputs we can reproduce."""

from hashlib import sha256
import json
from pathlib import Path

LAB = Path(__file__).resolve().parent
REPO = LAB.parents[2]
PREFIX = LAB.relative_to(REPO).as_posix()
SHARED = ("code/phase4-prompt-context/main.py", "code/phase5-agent-harness/harness-lab/main.py",
          "code/phase7-data-rag/rag-lab/lab.py")
GROUPS = {
    "gate": ("gate.py", "authority.py", "observations.py", "provenance.py", "fixtures/acceptance-v2.json"),
    "evaluation": ("evaluation/main.py", "observations.py",
                   "evaluation/fixtures/v1/dev.json", "evaluation/fixtures/v1/acceptance.json"),
    "telemetry": ("telemetry/lab.py",),
    "design": ("design/system_design.py",),
    "handoff": ("handoff.py", "provenance.py"),
}


def fingerprint(root, paths):
    """Hash an explicit relative-path manifest of UTF-8 sources, with normalized line endings."""
    files = {name: sha256((Path(root) / name).read_text(encoding="utf-8").encode("utf-8")).hexdigest()
             for name in sorted(set(paths))}
    if not files:
        raise ValueError("input manifest cannot be empty")
    encoded = json.dumps(files, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii")
    return {"sha256": sha256(encoded).hexdigest(), "files": files}


def input_fingerprint(group):
    paths = tuple(f"{PREFIX}/{name}" for name in GROUPS[group])
    if group in {"gate", "evaluation"}:
        paths += SHARED
    if group == "evaluation":
        paths += ("code/phase7-data-rag/rag-lab/assessment/checks.py",)
    return fingerprint(REPO, paths)
