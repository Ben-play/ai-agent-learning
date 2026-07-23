# Phase 2 Practices Capstone: Offline Model Assessment

A provider-neutral, fixture-based deep module for teaching model selection without network calls, API keys, environment secrets, branded outputs, or vendor price claims. All provider/model names, prices, latencies, prompts, evidence references, and observations are fictional educational data.

The external interface stays small:

```python
from phase2_practices import build_offline_lab

report = build_offline_lab().assess()
```

Behind that interface, the lab validates fixture integrity and coverage, maps two virtual-provider formats through a real adapter seam, and returns an immutable assessment report.

## Assessment semantics

- Each adapter consumes provider-native pre-call estimate counters before observation lookup. Over-budget estimates are rejected without response lookup, cannot produce an actual-usage delta, and cannot qualify or route. Accepted estimates produce candidate-specific per-observation absolute relative errors, averaged equally by case.
- Cases are explicitly split into `dev` and isolated `holdout` sets. Configurations and task policies have fixed identifiers and are frozen after dev inspection. Dev metrics and `dev_costs` are reported for analysis; only holdout observations can pass hard gates, enter weighted ranking, or be routed. The closed task registry makes this joint-run gate mandatory and non-disableable for `high_stakes_reasoning` and `impossible_safety`; ordinary low-risk task policies may leave it off. Every gated holdout run must jointly satisfy exact answer, abstention decision, and required evidence, so aggregate averages cannot compensate for one failed or disjoint fact/evidence run.
- Weighted normalized ranking is the final holdout-qualified **comparison winner/view** from deterministic quality weights; it does not choose the deployed route. The deployed route is a separate minimum-expected-automated-cost policy over qualified primary/stronger-fallback strategies. Expected automated cost includes model cost plus fallback-model cost times the primary's private-holdout failure rate. For a primary→fallback chain, residual failure is the primary failure probability multiplied by the fallback's own holdout failure probability; a failing fallback therefore never erases risk. Any nonzero residual is preserved with `manual_review`, including when no stronger fallback exists. Each versioned task policy supplies an explicit finite, strictly positive fictional manual-review unit cost; zero is rejected before routing. Expected manual-review cost is residual probability times that unit cost and is included in route `total_expected_cost` as a separately audited field.
- Evidence coverage authenticates exact allowlisted fixture references against an independent fictional corpus: canonical synthetic text is hash-checked, and the corpus declares the expected answer for its case. This proves fixture identity/provenance, not natural-language entailment. Invented, duplicate, cross-case, missing-required, or tampered references fail before scoring; coverage counts authenticated distinct required IDs only.
- The run specification records fixture/evaluator/rubric/tool-policy identities, deterministic fixture, trusted-case-manifest, and observation-provenance digests, candidate ID/config/provider/tier records, split IDs, exact expected-answer/abstention/evidence contracts, prompt/policy digests, and repeat counts. A closed local registry pins the accepted case manifest and validation/scoring contract v2, so coordinated split relabeling is rejected; the lab validates pre-scored synthetic fixtures and does not claim to rerun a model evaluator. Raw provider shapes remain internal.
- Metrics weight cases equally regardless of repeat count. Factual error is exact-answer correctness per observation; decision correctness penalizes both missed required abstention and false abstention; divergence is per-case pairwise disagreement after only trim/casefold/terminal-punctuation fixture normalization; latency is averaged per case; estimate error is per-observation absolute relative error before equal-case averaging.
- Complete evaluation spend is split into `dev_costs` and holdout `costs`, each retaining uncached input, cache write/read, output, retry, and observed escalation components. These are token/event price components; route-policy computation overhead is outside `CostBreakdown`, while expected manual-review cost is explicitly carried by each route strategy and recommendation. Routing uses holdout costs only.
- Cache usage has explicit lifecycle provenance. A read requires a declared preexisting entry or a deterministic earlier-repeat write; impossible first reads are rejected. The shipped fixture uses write-then-read sequences and does not claim undeclared prewarming.

## Fixture coverage

The deterministic fixtures include:

- unsupported semantic controls that fail before observation lookup;
- provider-specific controls, estimates, usage, retry, and escalation counters;
- five consistent but wrong/unsupported answers;
- divergent repeated answers;
- authenticated and rejected evidence references;
- a low-reuse scenario whose validated aggregate `cache_net_savings` is negative;
- a short-but-hard holdout task that cannot be routed by prompt length or cheap cost;
- hard-gate rejection before ranking;
- positive fixture-observed escalation charges;
- an explicit holdout-only negative policy with no qualified candidate.

## Install and lock validation

The runtime package uses only the Python standard library. `pytest` and `mypy` are locked development dependencies. Before working offline on a fresh machine, populate uv's package cache once while package indexes are available:

```bash
uv sync --locked
```

After that one-time cache priming, validate the lock without network access:

```bash
uv lock --check --offline
```

## Full offline validation

```bash
uv run --offline --locked pytest -q
uv run --offline --locked mypy phase2_practices tests main.py
uv run --offline --locked python main.py
uv run --offline --locked python -m phase2_practices.acceptance
```

Both successful entry points print exactly one line: `PHASE 2 PRACTICES ACCEPTED`.

## Counterfactuals

These deliberately unsafe designs must exit nonzero with the explicit `CounterfactualReached` sentinel and must not print the acceptance marker. Tests exercise normal and optimized (`-O`) Python entrypoints.

```bash
uv run --offline --locked python -m phase2_practices.counterfactuals.consistency_as_truth
uv run --offline --locked python -m phase2_practices.counterfactuals.rank_before_gate
```

- `consistency_as_truth` incorrectly promotes five mutually consistent unsupported/wrong observations to truth.
- `rank_before_gate` ranks cost first, lets an unsafe cheap candidate win, and only then discovers the hard-gate failure.
