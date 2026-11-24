#!/usr/bin/env python3
"""Run explicitly allowlisted, offline course acceptance blocks in subprocesses.

Uses only the standard library to run explicit allowlists. The default suite needs
Pydantic v2 for L36 and uses loopback HTTP for L58/L59; it never calls external
services. The separate LangGraph suite needs the graph-lab dependencies.
No dependencies are installed by this script.
"""

from __future__ import annotations

import argparse
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
    ("0053-L45-function-workflow-agent.html", ("l45-architecture-check",), "L45 ACCEPTED"),
    ("0054-L46-bounded-agent-loop.html", ("l46-loop-check",), "L46 ACCEPTED"),
    ("0055-L47-typed-tool-contract.html", ("l47-tool-check",), "L47 ACCEPTED"),
    ("0056-L48-context-notes-compaction.html", ("l48-context-check",), "L48 ACCEPTED"),
    ("0057-L49-memory-lifecycle.html", ("l49-memory-check",), "L49 ACCEPTED"),
    ("0058-L50-approval-boundaries.html", ("l50-approval-check",), "L50 ACCEPTED"),
    ("0059-L51-approval-checkpoint-resume.html", ("l51-checkpoint-check",), "L51 ACCEPTED"),
    ("0060-L52-idempotent-draft-replay.html", ("l52-replay-check",), "L52 ACCEPTED"),
    ("0061-L53-harness-regression.html", ("l53-regression-check",), "L53 ACCEPTED"),
    ("0062-L54-harness-acceptance.html", ("l54-harness-check",), "L54 ACCEPTED"),
)

# Near-transfer checks run independently of the worked examples above.
PRACTICE_LESSONS = tuple(
    (int(expected.split()[0][1:]), name)
    for name, _, expected in CASES
    if 39 <= int(expected.split()[0][1:]) <= 54
)
PRACTICE_CASES = tuple(
    (name, (f"l{number}-transfer-check",), f"L{number} TRANSFER PASSED")
    for number, name in PRACTICE_LESSONS
)
CHECKPOINT_CASES = (
    ("0051-L43-progressive-skill-disclosure.html", ("l43-stage-check",), "P4 CONTEXT AND SKILL PASSED"),
    ("0056-L48-context-notes-compaction.html", ("l48-stage-check",), "P5 HARNESS BOUNDARIES PASSED"),
    ("0060-L52-idempotent-draft-replay.html", ("l52-stage-check",), "P5 DURABLE APPROVAL PASSED"),
    ("0068-L59-mcp-skill-authority.html", ("l59-stage-check",), "P6 SKILL AND AUTHORITY PASSED"),
)
WALKTHROUGH_CASES = (
    ("0055-L47-typed-tool-contract.html", ("l47-protocol-walkthrough",), "L47 PROTOCOL PASSED"),
    ("0055-L47-typed-tool-contract.html", ("l47-generic-walkthrough",), "L47 GENERIC PASSED"),
)
PHASE6_LOCAL_CASES = (
    ("0065-L56-langgraph-durable-resume.html", ("l56-transfer-check",), "L56 TRANSFER PASSED"),
    ("0066-L57-mcp-stdio.html", ("l57-stdio-check",), "L57 ACCEPTED"),
    ("0066-L57-mcp-stdio.html", ("l57-transfer-check",), "L57 TRANSFER PASSED"),
    ("0067-L58-mcp-streamable-http.html", ("l58-http-check",), "L58 ACCEPTED"),
    ("0067-L58-mcp-streamable-http.html", ("l58-transfer-check",), "L58 TRANSFER PASSED"),
    ("0068-L59-mcp-skill-authority.html", ("l59-auth-check",), "L59 ACCEPTED"),
    ("0068-L59-mcp-skill-authority.html", ("l59-transfer-check",), "L59 TRANSFER PASSED"),
)
LANGGRAPH_CASES = (
    ("0064-L55-langgraph-state-graph.html", ("l55-graph-check",), "L55 ACCEPTED"),
    ("0064-L55-langgraph-state-graph.html", ("l55-transfer-check",), "L55 TRANSFER PASSED"),
    ("0065-L56-langgraph-durable-resume.html", ("l56-resume-check",), "L56 ACCEPTED"),
)
ALL_CASES = CASES + PRACTICE_CASES + CHECKPOINT_CASES + WALKTHROUGH_CASES + PHASE6_LOCAL_CASES


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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=("local", "langgraph"), default="local")
    suite = parser.parse_args().suite
    cases = ALL_CASES if suite == "local" else LANGGRAPH_CASES
    failures = 0
    for filename, ids, expected in cases:
        try:
            parser = CodeBlocks()
            parser.feed((ROOT / "lessons" / filename).read_text(encoding="utf-8"))
            source = "\n\n".join(parser.blocks[block_id] for block_id in ids)
            compile(source, filename, "exec")
            result = subprocess.run(
                [sys.executable, "-I", "-X", "utf8", "-c", source],
                cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                timeout=120 if expected == "L56 ACCEPTED" else 30,
                check=False,
            )
            if result.returncode or result.stdout.strip() != expected or result.stderr.strip():
                failures += 1
                print(f"FAIL {filename}")
                print(result.stdout.strip())
                print(result.stderr.strip())
            else:
                print(f"PASS {expected}")
        except (KeyError, OSError, ValueError, SyntaxError, subprocess.TimeoutExpired) as exc:
            failures += 1
            print(f"FAIL {filename}: {exc}")
    print(f"{suite} examples: {len(cases) - failures}/{len(cases)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
