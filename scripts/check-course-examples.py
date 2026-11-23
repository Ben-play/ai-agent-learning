#!/usr/bin/env python3
"""Run explicitly allowlisted, offline course acceptance blocks in subprocesses.

Uses only the standard library. Never executes arbitrary lesson code, SDK examples,
network examples, or external script contents. Use a Python environment containing
Pydantic v2 for L36; no dependencies are installed by this script.
"""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
CASES = (
    ("0030-L25-llm-api-basics.html", ("l25-adapter-check",), "L25 ACCEPTED"),
    ("0031-L26-streaming.html", ("l26-terminal-check",), "L26 ACCEPTED"),
    ("0032-L27-function-calling.html", ("l27-tool-core", "l27-tool-check"), "L27 ACCEPTED"),
    ("0033-L28-structured-outputs.html", ("l28-contract-check",), "L28 ACCEPTED"),
    ("0034-L29-multimodal-api.html", ("l29-multimodal-check",), "L29 ACCEPTED"),
    ("0035-L30-context-window-management.html", ("l30-context-core", "l30-context-check"), "L30 ACCEPTED"),
    ("0036-L31-error-handling-retry.html", ("l31-idempotency-check",), "L31 ACCEPTED"),
    ("0038-L33-observability.html", ("l33-telemetry-check",), "L33 ACCEPTED"),
    ("0040-L35-function-calling-loop.html", ("l35-loop-core", "l35-loop-check"), "L35 ACCEPTED"),
    ("0041-L36-tool-robustness-registry.html", ("l36-args-core", "l36-registry-core", "l36-dispatch-core", "l36-registry-check"), "L36 ACCEPTED"),
    ("0042-L37-cost-engineering.html", ("l37-cost-check",), "L37 ACCEPTED"),
    ("0043-L38-phase3-capstone.html", ("l38-core", "l38-check"), "L38 ACCEPTED"),
    ("0047-L39-testable-task-contract.html", ("l39-contract-check",), "L39 ACCEPTED"),
    ("0048-L40-few-shot-counterexamples.html", ("l40-few-shot-check",), "L40 ACCEPTED"),
    ("0049-L41-prompt-versions-regression.html", ("l41-regression-check",), "L41 ACCEPTED"),
    ("0050-L42-context-evidence-budget.html", ("l42-context-check",), "L42 ACCEPTED"),
    ("0051-L43-progressive-skill-disclosure.html", ("l43-skill-check",), "L43 ACCEPTED"),
    ("0052-L44-project-acceptance-handoff.html", ("l44-handoff-check",), "L44 ACCEPTED"),
)


class CodeBlocks(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.current: str | None = None
        self.blocks: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        block_id = dict(attrs).get("id")
        if tag == "code" and block_id:
            if block_id in self.blocks:
                raise ValueError(f"duplicate code id: {block_id}")
            self.current = block_id
            self.blocks[block_id] = ""

    def handle_endtag(self, tag: str) -> None:
        if tag == "code":
            self.current = None

    def handle_data(self, data: str) -> None:
        if self.current is not None:
            self.blocks[self.current] += data


def main() -> int:
    failures = 0
    for filename, ids, expected in CASES:
        try:
            parser = CodeBlocks()
            parser.feed((ROOT / "lessons" / filename).read_text(encoding="utf-8"))
            source = "\n\n".join(parser.blocks[block_id] for block_id in ids)
            compile(source, filename, "exec")
            result = subprocess.run(
                [sys.executable, "-I", "-X", "utf8", "-c", source],
                cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=30,
                check=False,
            )
            if result.returncode or result.stdout.strip() != expected:
                failures += 1
                print(f"FAIL {filename}")
                print(result.stdout.strip())
                print(result.stderr.strip())
            else:
                print(f"PASS {expected}")
        except (KeyError, OSError, ValueError, SyntaxError, subprocess.TimeoutExpired) as exc:
            failures += 1
            print(f"FAIL {filename}: {exc}")
    print(f"Offline examples: {len(CASES) - failures}/{len(CASES)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
