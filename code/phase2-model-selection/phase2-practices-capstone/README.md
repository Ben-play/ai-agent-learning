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
- Weighted normalized ranking is the holdout-qualified **comparison view**; it does not select the route. Routing compares qualified primary/stronger-fallback strategies by expected total cost per holdout trial. Each trial pairs candidates by task, case ID, and repeat. The replay pays for the primary on every trial, for the fallback only on trials the primary failed, and for `manual_review` only where both failed (or where the primary failed and no stronger fallback exists). Each component is divided by the full trial count, and `total_expected_cost` sums all three. Manual review uses the task's finite, strictly positive fictional unit cost. Residual failure is the observed overlap, not the product of marginal failure rates.
- The trigger is an oracle label from validated replay evidence: ordinary tasks use exact-answer errors; every-run policies also require the correct abstention decision and complete required evidence. These labels are not a runtime detector. The immutable `holdout_trials` ledger lets acceptance check exact holdout coverage for every qualified candidate and recompute the route from the per-run evidence and costs.
- Evidence coverage authenticates exact allowlisted fixture references against an independent fictional corpus: canonical synthetic text is hash-checked, and the corpus declares the expected answer for its case. This proves fixture identity/provenance, not natural-language entailment. Invented, duplicate, cross-case, missing-required, or tampered references fail before scoring; coverage counts authenticated distinct required IDs only.
- The run specification records fixture/evaluator/rubric/tool-policy identities, deterministic fixture, trusted-case-manifest, and observation-provenance digests, candidate ID/config/provider/tier records, split IDs, exact expected-answer/abstention/evidence contracts, prompt/policy digests, and repeat counts. A closed local registry pins the accepted case manifest and validation/scoring contract v2, so coordinated split relabeling is rejected; the lab validates pre-scored synthetic fixtures and does not claim to rerun a model evaluator. Raw provider shapes remain internal.
- Metrics weight cases equally regardless of repeat count. Factual error is exact-answer correctness per observation; decision correctness penalizes both missed required abstention and false abstention; divergence is per-case pairwise disagreement after only trim/casefold/terminal-punctuation fixture normalization; latency is averaged per case; estimate error is per-observation absolute relative error before equal-case averaging.
- Complete evaluation spend is split into aggregate `dev_costs` and holdout `costs`, each retaining uncached input, cache write/read, output, retry, and fixture-observed escalation. The trial ledger reconciles to holdout spend; the newly modeled fallback and manual review are route expectations, not extra charges added to either aggregate. Observed retry/escalation charges and modeled fallback invocation are separate. These virtual prices and replayed usage are not real route costs. Actual cache hits, retries, and usage may differ when a fallback is called only on some trials.
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

From this capstone directory, run the paired regression with the standard library alone:

```bash
python -B -X utf8 -m unittest discover -s tests -p test_paired_routes.py
```

With the development tools cached, run the full suite and both entry points:

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
