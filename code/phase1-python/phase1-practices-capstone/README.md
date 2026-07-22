# Phase 1 Practices Capstone

An offline, deterministic example of a typed async agent. It demonstrates validation at boundaries, a deep retrying gateway, explicit tool dispatch, bounded execution, isolated batch work, safe redaction, and atomic JSON persistence.

No API key or network access is used. The gateway is backed by `httpx.AsyncClient` with `MockTransport`.

## Run

```bash
uv lock --check --offline
uv run --offline --locked python main.py
```

## Verify

```bash
uv run --offline --locked pytest -q
uv run --offline --locked mypy phase1_practices tests main.py
uv run --offline --locked python -m phase1_practices.acceptance
```

The two modules under `phase1_practices.counterfactuals` are negative demonstrations. Each exits nonzero because it deliberately asserts an unsafe design: retrying an entire batch and treating schema validation as execution.
