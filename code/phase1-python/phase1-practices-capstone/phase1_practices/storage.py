from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .contracts import RunReport

FailureHook = Callable[[str, Path], None]


def atomic_write_json(
    destination: Path,
    value: Any,
    *,
    failure_hook: FailureHook | None = None,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, raw_temp = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temp_path = Path(raw_temp)
    try:
        if failure_hook is not None:
            failure_hook("created", temp_path)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            fd = -1
            json.dump(value, handle, ensure_ascii=False, allow_nan=False, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        if failure_hook is not None:
            failure_hook("flushed", temp_path)
        os.replace(temp_path, destination)
        if failure_hook is not None:
            failure_hook("replaced", destination)
    finally:
        if fd >= 0:
            os.close(fd)
        temp_path.unlink(missing_ok=True)


class JsonRunStore:
    def __init__(self, root: Path, *, failure_hook: FailureHook | None = None) -> None:
        self._root = root
        self._failure_hook = failure_hook

    def write(self, report: RunReport) -> Path:
        destination = self._root / f"{report.run_id}.json"
        atomic_write_json(
            destination,
            report.model_dump(mode="json"),
            failure_hook=self._failure_hook,
        )
        return destination
