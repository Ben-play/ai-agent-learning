from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from phase2_practices.adapters import (
    EffortFixtureAdapter,
    PolicyMismatchError,
    PreflightBudgetError,
    ProviderAdapter,
    SamplingFixtureAdapter,
    UnsupportedControlError,
)
from phase2_practices.assessment import FixtureIntegrityError
from phase2_practices.contracts import CandidateProfile, EvaluationCase, SemanticPolicy

ROOT = Path(__file__).resolve().parents[1]


def adapter_fixture() -> tuple[CandidateProfile, EvaluationCase, dict[str, Any]]:
    profile = CandidateProfile(
        candidate_id="Fixture-S",
        config_id="cfg-fixture-s-v1",
        provider="Virtual",
        adapter_kind="sampling",
        capability_tier=1,
        supported_controls=frozenset({"creativity", "response_budget"}),
        control_mapping=(("creativity", "sample_spread"), ("response_budget", "output_limit")),
        usage_container="meter",
        usage_mapping=(("cache_read", "cr"), ("cache_write", "cw"), ("output", "o"), ("uncached_input", "i")),
        counter_container="attempts",
        counter_mapping=(("escalations", "e"), ("retries", "r")),
        estimate_container="preflight",
        estimate_mapping=(("output", "predicted_o"), ("uncached_input", "predicted_i")),
    )
    case = EvaluationCase(
        case_id="counted",
        task="routine",
        split="holdout",
        prompt="fixture",
        expected_answer="ok",
        should_abstain=False,
        allowed_evidence_ids=frozenset(),
        required_evidence_ids=frozenset(),
        repeats=1,
        policy=SemanticPolicy.create(
            {"creativity": "low", "response_budget": 10},
            maximum_estimated_input_units=100,
        ),
    )
    raw: dict[str, Any] = {
        "observation_id": "obs-counted",
        "candidate_id": "Fixture-S",
        "case_id": "counted",
        "repeat": 1,
        "provider": "Virtual",
        "mapped_controls": {"sample_spread": "low", "output_limit": 10},
        "answer": "ok",
        "quality_score": 1.0,
        "factual_errors": 0,
        "facts_checked": 1,
        "abstained": False,
        "evidence_ids": [],
        "cache_entry_available_before": False,
        "cache_origin": "none",
        "fixed_latency_ms": 1,
        "meter": {"i": 12, "cw": 0, "cr": 0, "o": 3},
        "attempts": {"r": 0, "e": 0},
        "preflight": {"predicted_i": 17, "predicted_o": 5},
    }
    return profile, case, raw


def test_real_provider_adapter_seam_has_two_implementations() -> None:
    assert issubclass(SamplingFixtureAdapter, ProviderAdapter)
    assert issubclass(EffortFixtureAdapter, ProviderAdapter)
    assert SamplingFixtureAdapter.__dict__["observe"] is not EffortFixtureAdapter.__dict__["observe"]


def test_unsupported_control_fails_before_observation_lookup() -> None:
    lookup_calls = 0

    def lookup(candidate_id: str, case_id: str, repeat: int) -> None:
        nonlocal lookup_calls
        lookup_calls += 1
        return None

    profile = CandidateProfile(
        candidate_id="Fixture-S",
        config_id="cfg-fixture-s-v1",
        provider="Virtual",
        adapter_kind="sampling",
        capability_tier=1,
        supported_controls=frozenset({"creativity", "response_budget"}),
        control_mapping=(
            ("creativity", "sample_spread"),
            ("response_budget", "output_limit"),
        ),
        usage_container="meter",
        usage_mapping=(
            ("cache_read", "r"),
            ("cache_write", "w"),
            ("output", "o"),
            ("uncached_input", "i"),
        ),
        counter_container="attempts",
        counter_mapping=(("escalations", "e"), ("retries", "r")),
        estimate_container="preflight",
        estimate_mapping=(("output", "o"), ("uncached_input", "i")),
    )
    adapter = SamplingFixtureAdapter(profile, lookup)
    case = EvaluationCase(
        case_id="unsupported",
        task="hard",
        split="holdout",
        prompt="fixture",
        expected_answer="fixture",
        should_abstain=False,
        allowed_evidence_ids=frozenset(),
        required_evidence_ids=frozenset(),
        repeats=1,
        policy=SemanticPolicy.create(
            {"creativity": "low", "response_budget": 10, "reasoning_depth": "high"},
            maximum_estimated_input_units=100,
        ),
    )

    with pytest.raises(UnsupportedControlError, match="reasoning_depth"):
        adapter.observe(case, case.policy, 1, None)
    assert lookup_calls == 0


def test_provider_estimate_counter_mapping_is_consumed() -> None:
    profile = CandidateProfile(
        candidate_id="Fixture-S",
        config_id="cfg-fixture-s-v1",
        provider="Virtual",
        adapter_kind="sampling",
        capability_tier=1,
        supported_controls=frozenset({"creativity", "response_budget"}),
        control_mapping=(("creativity", "sample_spread"), ("response_budget", "output_limit")),
        usage_container="meter",
        usage_mapping=(("cache_read", "cr"), ("cache_write", "cw"), ("output", "o"), ("uncached_input", "i")),
        counter_container="attempts",
        counter_mapping=(("escalations", "e"), ("retries", "r")),
        estimate_container="preflight",
        estimate_mapping=(("output", "predicted_o"), ("uncached_input", "predicted_i")),
    )
    case = EvaluationCase(
        case_id="counted",
        task="routine",
        split="holdout",
        prompt="fixture",
        expected_answer="ok",
        should_abstain=False,
        allowed_evidence_ids=frozenset(),
        required_evidence_ids=frozenset(),
        repeats=1,
        policy=SemanticPolicy.create(
            {"creativity": "low", "response_budget": 10},
            maximum_estimated_input_units=100,
        ),
    )
    raw = {
        "observation_id": "obs-counted",
        "candidate_id": "Fixture-S",
        "case_id": "counted",
        "repeat": 1,
        "provider": "Virtual",
        "mapped_controls": {"sample_spread": "low", "output_limit": 10},
        "answer": "ok",
        "quality_score": 1.0,
        "factual_errors": 0,
        "facts_checked": 1,
        "abstained": False,
        "evidence_ids": [],
        "cache_entry_available_before": False,
        "cache_origin": "none",
        "fixed_latency_ms": 1,
        "meter": {"i": 12, "cw": 0, "cr": 0, "o": 3},
        "attempts": {"r": 0, "e": 0},
        "preflight": {"predicted_i": 17, "predicted_o": 5},
    }
    observation = SamplingFixtureAdapter(profile).observe(case, case.policy, 1, raw)
    assert observation.estimated_uncached_input_units == 17
    assert observation.estimated_output_units == 5


def test_mismatched_passed_policy_is_rejected_including_narrower_budget() -> None:
    profile, case, raw = adapter_fixture()
    adapter = SamplingFixtureAdapter(profile)
    narrower = SemanticPolicy.create(
        dict(case.policy.controls), maximum_estimated_input_units=16
    )
    with pytest.raises(PolicyMismatchError, match="differs from frozen case policy"):
        adapter.observe(case, narrower, 1, raw)
    altered_controls = SemanticPolicy.create(
        {"creativity": "high", "response_budget": 10},
        maximum_estimated_input_units=100,
    )
    with pytest.raises(PolicyMismatchError, match="differs from frozen case policy"):
        adapter.observe(case, altered_controls, 1, raw)


@pytest.mark.parametrize(("field", "value"), [("predicted_i", -1), ("predicted_o", -1)])
def test_negative_provider_estimates_are_rejected(field: str, value: int) -> None:
    profile, case, raw = adapter_fixture()
    raw["preflight"][field] = value
    with pytest.raises(PreflightBudgetError, match="must be nonnegative"):
        SamplingFixtureAdapter(profile).observe(case, case.policy, 1, raw)


@pytest.mark.parametrize(("field", "value"), [("predicted_i", True), ("predicted_o", 1.5)])
def test_noninteger_provider_estimates_are_rejected(field: str, value: object) -> None:
    profile, case, raw = adapter_fixture()
    raw["preflight"][field] = value
    with pytest.raises(TypeError, match="expected fixture integer"):
        SamplingFixtureAdapter(profile).observe(case, case.policy, 1, raw)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("candidate_id", "Other", "candidate_id mismatch"),
        ("case_id", "other-case", "case_id mismatch"),
        ("repeat", 2, "repeat mismatch"),
        ("provider", "Other Provider", "provider mismatch"),
    ],
)
def test_raw_observation_fixture_identity_is_validated(
    field: str, value: object, message: str
) -> None:
    profile, case, raw = adapter_fixture()
    raw[field] = value
    with pytest.raises(ValueError, match=message):
        SamplingFixtureAdapter(profile).observe(case, case.policy, 1, raw)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("candidate_id", "Other", "candidate_id mismatch"),
        ("case_id", "other-case", "case_id mismatch"),
        ("repeat", 2, "repeat mismatch"),
        ("provider", "Other Provider", "provider mismatch"),
    ],
)
def test_separate_estimate_fixture_identity_is_validated(
    field: str, value: object, message: str
) -> None:
    profile, case, raw = adapter_fixture()
    estimate = {
        "candidate_id": "Fixture-S",
        "case_id": "counted",
        "repeat": 1,
        "provider": "Virtual",
        "preflight": {"predicted_i": 17, "predicted_o": 5},
    }
    estimate[field] = value

    def lookup(candidate_id: str, case_id: str, repeat: int) -> dict[str, object]:
        return raw

    def estimate_lookup(
        candidate_id: str, case_id: str, repeat: int
    ) -> dict[str, object]:
        return estimate

    adapter = SamplingFixtureAdapter(profile, lookup, estimate_lookup)
    with pytest.raises(ValueError, match=message):
        adapter.observe(case, case.policy, 1, None)


def test_preflight_budget_rejects_before_observation_lookup() -> None:
    observation_lookups = 0

    def observation_lookup(candidate_id: str, case_id: str, repeat: int) -> None:
        nonlocal observation_lookups
        observation_lookups += 1
        return None

    estimate_raw: dict[str, object] = {
        "candidate_id": "Fixture-S",
        "case_id": "budgeted",
        "repeat": 1,
        "provider": "Virtual",
        "preflight": {"i": 101, "o": 1},
    }

    def estimate_lookup(
        candidate_id: str, case_id: str, repeat: int
    ) -> dict[str, object]:
        return estimate_raw

    profile = CandidateProfile(
        candidate_id="Fixture-S",
        config_id="cfg-fixture-s-v1",
        provider="Virtual",
        adapter_kind="sampling",
        capability_tier=1,
        supported_controls=frozenset({"creativity", "response_budget"}),
        control_mapping=(("creativity", "sample_spread"), ("response_budget", "output_limit")),
        usage_container="meter",
        usage_mapping=(("cache_read", "cr"), ("cache_write", "cw"), ("output", "o"), ("uncached_input", "i")),
        counter_container="attempts",
        counter_mapping=(("escalations", "e"), ("retries", "r")),
        estimate_container="preflight",
        estimate_mapping=(("output", "o"), ("uncached_input", "i")),
    )
    case = EvaluationCase(
        case_id="budgeted",
        task="routine",
        split="holdout",
        prompt="fixture",
        expected_answer="ok",
        should_abstain=False,
        allowed_evidence_ids=frozenset(),
        required_evidence_ids=frozenset(),
        repeats=1,
        policy=SemanticPolicy.create(
            {"creativity": "low", "response_budget": 10},
            maximum_estimated_input_units=100,
        ),
    )
    adapter = SamplingFixtureAdapter(profile, observation_lookup, estimate_lookup)
    with pytest.raises(PreflightBudgetError, match="exceeds budget"):
        adapter.observe(case, case.policy, 1, None)
    assert observation_lookups == 0
    estimate_raw["preflight"] = {"i": 100, "o": 1}
    with pytest.raises(LookupError, match="no matching observation"):
        adapter.observe(case, case.policy, 1, None)
    assert observation_lookups == 1


def test_fixture_referential_integrity_rejects_missing_observation(tmp_path: Path) -> None:
    fixture_root = tmp_path / "fixtures"
    fixture_root.mkdir()
    for name in (
        "provider-profiles.json",
        "evaluation-cases.json",
        "observations.json",
        "prices.json",
        "evidence-corpus.json",
        "case-manifest.json",
    ):
        (fixture_root / name).write_text(
            (ROOT / "fixtures" / name).read_text(encoding="utf-8"), encoding="utf-8"
        )
    observations = fixture_root / "observations.json"
    payload: dict[str, Any] = json.loads(observations.read_text(encoding="utf-8"))
    rows = payload["observations"]
    assert isinstance(rows, list)
    rows.pop(0)
    observations.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    from phase2_practices import build_offline_lab

    with pytest.raises(FixtureIntegrityError, match="coverage mismatch"):
        build_offline_lab(fixture_root).assess()
