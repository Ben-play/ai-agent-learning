from __future__ import annotations

import json
from pathlib import Path

import pytest

from phase1_practices.storage import atomic_write_json


def test_atomic_write_replaces_and_cleans_unique_sibling_temp(tmp_path: Path) -> None:
    destination = tmp_path / "value.json"
    destination.write_text('{"old": true}\n', encoding="utf-8")
    seen: list[Path] = []

    def hook(stage: str, path: Path) -> None:
        if stage == "created":
            seen.append(path)
            assert path.parent == destination.parent
            assert path != destination

    atomic_write_json(destination, {"new": True}, failure_hook=hook)
    assert json.loads(destination.read_text(encoding="utf-8")) == {"new": True}
    assert len(seen) == 1
    assert not seen[0].exists()


def test_atomic_write_rejects_nan_and_preserves_old_file(tmp_path: Path) -> None:
    destination = tmp_path / "value.json"
    destination.write_text('{"old": true}\n', encoding="utf-8")
    with pytest.raises(ValueError):
        atomic_write_json(destination, {"bad": float("nan")})
    assert json.loads(destination.read_text(encoding="utf-8")) == {"old": True}
    assert not list(tmp_path.glob("*.tmp"))


def test_atomic_write_failure_injection_cleans_temp(tmp_path: Path) -> None:
    destination = tmp_path / "value.json"

    def fail(stage: str, _: Path) -> None:
        if stage == "flushed":
            raise OSError("injected")

    with pytest.raises(OSError, match="injected"):
        atomic_write_json(destination, {"ok": True}, failure_hook=fail)
    assert not destination.exists()
    assert not list(tmp_path.glob("*.tmp"))
