#!/usr/bin/env python3
"""Run explicitly allowlisted, offline course acceptance blocks in subprocesses.

The `foundations` suite covers selected early lessons on the standard library.
The `pydantic` suite checks L34/L36 using an existing Pydantic v2 environment.
The default suite includes both and uses loopback HTTP for L58/L59/L75 and Node.js
for L82. The separate LangGraph suite needs graph-lab dependencies; Phase 10's
actual LangGraph rehearsal is separate from its standard-library checks.
The runner installs nothing and calls no external services.
"""

from __future__ import annotations

import argparse
from html.parser import HTMLParser
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
EARLY_CASES = (
    ("0005-L02-python-runtime-and-modules.html", ("l02-starter-check",), "L02 STARTER PASSED"),
    ("0022-L18-tokenization.html", ("l18-batch-check",), "L18 ACCEPTED"),
    ("0022-L18-tokenization.html", ("l18-request-contract-check",), "P2 CHECKPOINT REQUEST-CONTRACT PASSED"),
    ("0028-L24-phase2-capstone.html", ("l24-report", "l24-report-check"), "L24 ACCEPTED"),
)
CASES = (
    ("0030-L25-llm-api-basics.html", ("l25-adapter-check",), "L25 ACCEPTED"),
    ("0031-L26-streaming.html", ("l26-terminal-check",), "L26 ACCEPTED"),
    ("0031-L26-streaming.html", ("l26-chat-core", "l26-responses-core", "l26-messages-core", "l26-provider-check"), "L26 PROVIDERS PASSED"),
    ("0032-L27-function-calling.html", ("l27-tool-core", "l27-tool-check"), "L27 ACCEPTED"),
    ("0033-L28-structured-outputs.html", ("l28-contract-core", "l28-contract-check"), "L28 ACCEPTED"),
    ("0034-L29-multimodal-api.html", ("l29-output-core", "l29-multimodal-check"), "L29 ACCEPTED"),
    ("0035-L30-context-window-management.html", ("l30-context-core", "l30-context-check"), "L30 ACCEPTED"),
    ("0036-L31-error-handling-retry.html", ("l31-idempotency-check",), "L31 ACCEPTED"),
    ("0036-L31-error-handling-retry.html", ("l31-deadline-check",), "L31 DEADLINE PASSED"),
    ("0037-L32-routing-fallback-gateway.html", ("l32-route-core", "l32-route-check"), "L32 ACCEPTED"),
    ("0038-L33-observability.html", ("l33-telemetry-check",), "L33 ACCEPTED"),
    ("0039-L34-tool-schema-design.html", ("l34-schema-core", "l34-schema-check"), "L34 ACCEPTED"),
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
RAG_LESSONS = (
    (60, "0070-L60-rag-data-access.html"),
    (61, "0071-L61-rag-citation-chunks.html"),
    (62, "0072-L62-rag-lexical-retrieval.html"),
    (63, "0073-L63-rag-vector-retrieval.html"),
    (64, "0074-L64-rag-hybrid-retrieval.html"),
    (65, "0075-L65-rag-reranking.html"),
    (66, "0076-L66-rag-cache-invalidation.html"),
    (67, "0077-L67-rag-trust-boundary.html"),
    (68, "0078-L68-rag-retrieval-evals.html"),
    (69, "0079-L69-rag-generation-evals.html"),
)
RAG_CASES = tuple(
    (filename, (f"l{number}-{kind}-check",), f"L{number} {expected}")
    for number, filename in RAG_LESSONS
    for kind, expected in (("worked", "ACCEPTED"), ("transfer", "TRANSFER PASSED"))
) + (
    ("0076-L66-rag-cache-invalidation.html", ("l66-stage-check",), "P7 RETRIEVAL LIFECYCLE PASSED"),
    ("0079-L69-rag-generation-evals.html", ("l69-stage-check",), "P7 RAG HANDOFF PASSED"),
)
ENGINEERING_LESSONS = (
    (70, "0081-L70-agent-telemetry.html"),
    (71, "0082-L71-telemetry-privacy-alerts.html"),
    (72, "0083-L72-versioned-eval-datasets.html"),
    (73, "0084-L73-evidence-outcome-scoring.html"),
    (74, "0085-L74-judge-calibration.html"),
    (75, "0086-L75-tool-authority-bounds.html"),
    (76, "0087-L76-agent-load-cost.html"),
    (77, "0088-L77-offline-ci-gates.html"),
    (78, "0089-L78-agent-system-design.html"),
    (79, "0090-L79-engineering-baseline-handoff.html"),
)
ENGINEERING_CASES = tuple(
    (filename, (f"l{number}-{kind}-check",), f"L{number} {expected}")
    for number, filename in ENGINEERING_LESSONS
    for kind, expected in (("worked", "ACCEPTED"), ("transfer", "TRANSFER PASSED"))
) + (
    ("0085-L74-judge-calibration.html", ("l74-stage-check",), "P8 EVAL FOUNDATIONS PASSED"),
    ("0086-L75-tool-authority-bounds.html", ("l75-mcp-check",), "L75 MCP CHECK PASSED"),
    ("0090-L79-engineering-baseline-handoff.html", ("l79-stage-check",), "P8 ENGINEERING HANDOFF PASSED"),
)
ADVANCED_LESSONS = (
    (80, "0092-L80-reasoning-effort.html"),
    (81, "0093-L81-tool-discovery.html"),
    (82, "0094-L82-local-gui-preview.html"),
    (83, "0095-L83-coding-harness-boundaries.html"),
    (84, "0096-L84-long-task-recovery.html"),
)
ADVANCED_CASES = tuple(
    (filename, (f"l{number}-{kind}-check",), f"L{number} {expected}")
    for number, filename in ADVANCED_LESSONS
    for kind, expected in (("worked", "ACCEPTED"), ("transfer", "TRANSFER PASSED"))
) + (
    ("0096-L84-long-task-recovery.html", ("l84-stage-check",), "P9 ADVANCED DECISION PASSED"),
)
EVOLUTION_LESSONS = (
    (85, "0098-L85-versioned-graph-state.html"),
    (86, "0099-L86-checkpoint-compatibility.html"),
    (87, "0100-L87-migration-fallback.html"),
    (88, "0101-L88-architecture-decision.html"),
    (89, "0102-L89-bounded-worker-delegation.html"),
    (90, "0103-L90-a2a-task-boundaries.html"),
    (91, "0104-L91-mcp-server-boundaries.html"),
    (92, "0105-L92-hermes-source-comparison.html"),
)
EVOLUTION_CASES = tuple(
    (filename, (f"l{number}-{kind}-check",), f"L{number} {expected}")
    for number, filename in EVOLUTION_LESSONS
    for kind, expected in (("worked", "ACCEPTED"), ("transfer", "TRANSFER PASSED"))
) + (
    ("0100-L87-migration-fallback.html", ("l87-stage-check",), "P10 LOCAL CHECKPOINT CONTRACT PASSED"),
)
DEPLOYMENT_LESSONS = (
    (93, "0107-L93-fastapi-persistent-state.html"),
    (94, "0108-L94-deployment-promotion-gate.html"),
    (95, "0109-L95-deployment-authority-audit.html"),
    (96, "0110-L96-canary-stop-conditions.html"),
    (97, "0111-L97-rollback-pending-approvals.html"),
    (98, "0112-L98-incident-evaluation-iteration.html"),
)
DEPLOYMENT_CASES = tuple(
    (filename, (f"l{number}-{kind}-check",), f"L{number} {expected}")
    for number, filename in DEPLOYMENT_LESSONS
    for kind, expected in (("worked", "ACCEPTED"), ("transfer", "TRANSFER PASSED"))
) + (
    ("0111-L97-rollback-pending-approvals.html", ("l97-stage-check",), "P11 LOCAL ROLLBACK PASSED"),
    ("0112-L98-incident-evaluation-iteration.html", ("l98-stage-check",), "P11 LOCAL HANDOFF PASSED"),
)
PHASE3_PRACTICE = (
    ("0030-L25-llm-api-basics.html", ("l25-transfer-starter", "l25-transfer-check"), "L25 TRANSFER PASSED"),
    ("0031-L26-streaming.html", ("l26-chat-core", "l26-transfer-starter", "l26-transfer-check"), "L26 TRANSFER PASSED"),
    ("0032-L27-function-calling.html", ("l27-transfer-starter", "l27-transfer-check"), "L27 TRANSFER PASSED"),
    ("0033-L28-structured-outputs.html", ("l28-transfer-starter", "l28-transfer-check"), "L28 TRANSFER PASSED"),
    ("0034-L29-multimodal-api.html", ("l29-output-core", "l29-transfer-starter", "l29-transfer-check"), "L29 TRANSFER PASSED"),
    ("0035-L30-context-window-management.html", ("l30-context-core", "l30-transfer-starter", "l30-transfer-check"), "L30 TRANSFER PASSED"),
    ("0036-L31-error-handling-retry.html", ("l31-transfer-check",), "L31 TRANSFER PASSED"),
    ("0037-L32-routing-fallback-gateway.html", ("l32-route-core", "l32-transfer-check"), "L32 TRANSFER PASSED"),
    ("0038-L33-observability.html", ("l33-transfer-starter", "l33-transfer-check"), "L33 TRANSFER PASSED"),
    ("0039-L34-tool-schema-design.html", ("l34-transfer-check",), "L34 TRANSFER PASSED"),
    ("0040-L35-function-calling-loop.html", ("l35-loop-core", "l35-transfer-starter", "l35-transfer-check"), "L35 TRANSFER PASSED"),
    ("0041-L36-tool-robustness-registry.html", ("l36-args-core", "l36-registry-core", "l36-dispatch-core", "l36-transfer-starter", "l36-transfer-check"), "L36 TRANSFER PASSED"),
    ("0042-L37-cost-engineering.html", ("l37-transfer-starter", "l37-transfer-check"), "L37 TRANSFER PASSED"),
    ("0043-L38-phase3-capstone.html", ("l38-core", "l38-transfer-check"), "L38 TRANSFER PASSED"),
)
PHASE3_CASES = tuple(case for case in (*CASES, *PHASE3_PRACTICE)
                     if 25 <= int(case[2].split()[0][1:]) <= 38)
PYDANTIC_CASES = tuple(case for case in PHASE3_CASES if case[2].split()[0] in {"L34", "L36"})
FOUNDATION_CASES = EARLY_CASES + tuple(case for case in PHASE3_CASES if case not in PYDANTIC_CASES)
ALL_CASES = (EARLY_CASES + CASES + PHASE3_PRACTICE + PRACTICE_CASES + CHECKPOINT_CASES + WALKTHROUGH_CASES
             + PHASE6_LOCAL_CASES + RAG_CASES + ENGINEERING_CASES + ADVANCED_CASES + EVOLUTION_CASES + DEPLOYMENT_CASES)


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
    suites = {"local": ALL_CASES, "foundations": FOUNDATION_CASES, "pydantic": PYDANTIC_CASES,
              "langgraph": LANGGRAPH_CASES, "rag": RAG_CASES,
              "engineering": ENGINEERING_CASES, "advanced": ADVANCED_CASES,
              "evolution": EVOLUTION_CASES, "deployment": DEPLOYMENT_CASES}
    parser.add_argument("--suite", choices=tuple(suites), default="local")
    suite = parser.parse_args().suite
    cases = suites[suite]
    failures = 0
    for filename, ids, expected in cases:
        try:
            parser = CodeBlocks()
            parser.feed((ROOT / "lessons" / filename).read_text(encoding="utf-8"))
            source = "\n\n".join(parser.blocks[block_id] for block_id in ids)
            compile(source, filename, "exec")
            result = subprocess.run(
                [sys.executable, "-I", "-B", "-X", "utf8", "-c", source],
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
