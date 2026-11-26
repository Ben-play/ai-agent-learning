"""L83: verify complete proposed text snapshots; never apply or run them."""

import json
from pathlib import Path
from typing import TypedDict


class Candidate(TypedDict):
    claimed_pass: bool
    files: dict[str, str]


# These are course-owned inputs. Candidate metadata never selects the target or
# supplies the baseline or expected answer.
_BASELINE = {
    "answer.md": "同步答复待整理。\n",
    "preview.md": "预览待补证据。\n",
    "notes.md": "内部备忘（合成）。\n",
    "tests/citation-cases.json": '{"locator_required": true}\n',
}
_TARGETS = {"answer": "answer.md", "preview-only": "preview.md"}
_EXPECTED = "同步任务每天 02:00 运行。\n来源：SYNC-POLICY v1 §1\n"


def load_candidates() -> dict[str, Candidate]:
    fixture = Path(__file__).with_name("candidates-v1.json")
    return json.loads(fixture.read_text(encoding="utf-8"))["candidates"]


def verify(files: dict[str, str], *, profile: str = "answer") -> dict[str, object]:
    """Compare file labels and complete text values, not filesystem paths."""
    target = _TARGETS[profile]
    added = sorted(files.keys() - _BASELINE.keys())
    removed = sorted(_BASELINE.keys() - files.keys())
    changed = sorted(name for name in files.keys() & _BASELINE.keys()
                     if files[name] != _BASELINE[name])
    scope_ok = not added and not removed and changed == [target]
    citation_ok = files.get(target) == _EXPECTED
    return {
        "accepted": scope_ok and citation_ok,
        "citation_ok": citation_ok,
        "scope_ok": scope_ok,
        "target": target,
        "delta": {"added": added, "removed": removed, "changed": changed},
    }


def main() -> None:
    candidates = load_candidates()
    groups = {
        "answer": ("valid", "missing-locator", "unrelated-edit", "test-edit"),
        "preview-only": ("valid", "preview-only", "preview-extra"),
    }
    report = {
        profile: {
            name: {"claimed_pass": candidates[name]["claimed_pass"],
                   **verify(candidates[name]["files"], profile=profile)}
            for name in names
        }
        for profile, names in groups.items()
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
