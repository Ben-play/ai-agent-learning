from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from phase2_practices import build_offline_lab
from phase2_practices.assessment import FixtureIntegrityError

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_NAMES = (
    "provider-profiles.json",
    "evaluation-cases.json",
    "observations.json",
    "prices.json",
    "evidence-corpus.json",
    "case-manifest.json",
)


def copied_fixtures(tmp_path: Path) -> Path:
    fixture_root = tmp_path / "fixtures"
    fixture_root.mkdir()
    for name in FIXTURE_NAMES:
        (fixture_root / name).write_text(
            (ROOT / "fixtures" / name).read_text(encoding="utf-8"), encoding="utf-8"
        )
    return fixture_root


def load(path: Path) -> dict[str, Any]:
    value: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return value


def save(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def test_wrong_answer_cannot_hide_behind_fixture_annotations(tmp_path: Path) -> None:
    fixture_root = copied_fixtures(tmp_path)
    path = fixture_root / "observations.json"
    payload = load(path)
    payload["observations"][0]["answer"] = "not-the-reference-answer"
    payload["observations"][0]["factual_errors"] = 0
    save(path, payload)
    with pytest.raises(FixtureIntegrityError, match="answer and factual-error annotation disagree"):
        build_offline_lab(fixture_root).assess()


def test_correct_answer_cannot_claim_a_factual_error(tmp_path: Path) -> None:
    fixture_root = copied_fixtures(tmp_path)
    path = fixture_root / "observations.json"
    payload = load(path)
    row = next(
        item
        for item in payload["observations"]
        if item["case_id"] == "routine-label" and item["candidate_id"] == "Cedar-S"
    )
    assert row["answer"] == "routine"
    row["factual_errors"] = 1
    save(path, payload)
    with pytest.raises(FixtureIntegrityError, match="answer and factual-error annotation disagree"):
        build_offline_lab(fixture_root).assess()


def test_facts_checked_cannot_dilute_exact_answer_error(tmp_path: Path) -> None:
    fixture_root = copied_fixtures(tmp_path)
    path = fixture_root / "observations.json"
    payload = load(path)
    row = next(
        item
        for item in payload["observations"]
        if item["candidate_id"] == "Spruce-S" and item["case_id"] == "grounded-capital"
    )
    assert row["factual_errors"] == 1
    row["facts_checked"] = 100
    save(path, payload)
    with pytest.raises(FixtureIntegrityError, match="facts_checked == 1"):
        build_offline_lab(fixture_root).assess()


def test_negative_usage_is_rejected(tmp_path: Path) -> None:
    fixture_root = copied_fixtures(tmp_path)
    path = fixture_root / "observations.json"
    payload = load(path)
    payload["observations"][0]["meter"]["fresh_in"] = -1
    save(path, payload)
    with pytest.raises(FixtureIntegrityError, match="usage cannot be negative"):
        build_offline_lab(fixture_root).assess()


def test_impossible_first_cache_read_is_rejected(tmp_path: Path) -> None:
    fixture_root = copied_fixtures(tmp_path)
    path = fixture_root / "observations.json"
    payload = load(path)
    row = next(
        item
        for item in payload["observations"]
        if item["candidate_id"] == "Spruce-S"
        and item["case_id"] == "grounded-capital"
        and item["repeat"] == 1
    )
    row["meter"]["saved_write"] = 0
    row["meter"]["saved_read"] = 80
    row["cache_entry_available_before"] = False
    row["cache_origin"] = "none"
    save(path, payload)
    with pytest.raises(FixtureIntegrityError, match="cache read has no valid prior or preexisting"):
        build_offline_lab(fixture_root).assess()


def test_declared_prewarmed_cache_read_is_valid(tmp_path: Path) -> None:
    fixture_root = copied_fixtures(tmp_path)
    path = fixture_root / "observations.json"
    payload = load(path)
    row = next(
        item
        for item in payload["observations"]
        if item["candidate_id"] == "Spruce-S"
        and item["case_id"] == "grounded-capital"
        and item["repeat"] == 1
    )
    row["meter"]["saved_write"] = 0
    row["meter"]["saved_read"] = 80
    row["cache_entry_available_before"] = True
    row["cache_origin"] = "declared-preexisting"
    for later in payload["observations"]:
        if (
            later["candidate_id"] == "Spruce-S"
            and later["case_id"] == "grounded-capital"
            and later["repeat"] > 1
        ):
            later["cache_origin"] = "declared-preexisting"
    save(path, payload)
    assert build_offline_lab(fixture_root).assess().fixture_integrity_validated


def test_prior_write_then_read_sequence_is_valid() -> None:
    assert build_offline_lab().assess().fixture_integrity_validated


def test_mapped_controls_are_consumed_and_validated(tmp_path: Path) -> None:
    fixture_root = copied_fixtures(tmp_path)
    path = fixture_root / "observations.json"
    payload = load(path)
    payload["observations"][0]["mapped_controls"]["sample_spread"] = "high"
    save(path, payload)
    with pytest.raises(ValueError, match="mapped controls differ"):
        build_offline_lab(fixture_root).assess()


@pytest.mark.parametrize("evidence_id", ["invented-evidence", "rule-bridge-a"])
def test_invented_or_cross_case_evidence_is_rejected(
    tmp_path: Path, evidence_id: str
) -> None:
    fixture_root = copied_fixtures(tmp_path)
    path = fixture_root / "observations.json"
    payload = load(path)
    row = next(
        item
        for item in payload["observations"]
        if item["case_id"] == "unsupported-moon"
    )
    row["evidence_ids"] = [evidence_id]
    save(path, payload)
    with pytest.raises(FixtureIntegrityError, match="invented or cross-case evidence"):
        build_offline_lab(fixture_root).assess()


def test_trusted_case_manifest_itself_cannot_be_rewritten(tmp_path: Path) -> None:
    fixture_root = copied_fixtures(tmp_path)
    path = fixture_root / "case-manifest.json"
    payload = load(path)
    payload["cases"][0]["split"] = "holdout"
    canonical = json.dumps(
        payload["cases"], sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    payload["manifest_digest"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    save(path, payload)
    with pytest.raises(
        FixtureIntegrityError,
        match="case manifest is not the registered trusted manifest",
    ):
        build_offline_lab(fixture_root).assess()


def test_case_split_swap_fails_trusted_manifest_even_when_labels_are_coordinated(
    tmp_path: Path,
) -> None:
    fixture_root = copied_fixtures(tmp_path)
    path = fixture_root / "evaluation-cases.json"
    payload = load(path)
    short_hard = next(
        case for case in payload["cases"] if case["case_id"] == "short-hard-proof"
    )
    unsupported = next(
        case for case in payload["cases"] if case["case_id"] == "unsupported-proof-fact"
    )
    short_hard["split"] = "dev"
    unsupported["split"] = "holdout"
    save(path, payload)
    with pytest.raises(
        FixtureIntegrityError,
        match="evaluation cases differ from trusted case manifest",
    ):
        build_offline_lab(fixture_root).assess()


def test_holdout_only_task_requires_explicit_negative_policy(tmp_path: Path) -> None:
    fixture_root = copied_fixtures(tmp_path)
    path = fixture_root / "evaluation-cases.json"
    payload = load(path)
    impossible = next(
        policy for policy in payload["task_policies"] if policy["task"] == "impossible_safety"
    )
    impossible["holdout_only_negative_policy"] = False
    save(path, payload)
    with pytest.raises(FixtureIntegrityError, match="explicit holdout-only negative policy"):
        build_offline_lab(fixture_root).assess()


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("evaluator_version", "offline-evaluator-v999"),
        ("rubric_version", "reference-rubric-v999"),
        ("tool_policy_id", "different-tool-policy"),
    ],
)
def test_observation_provenance_binds_evaluator_rubric_and_tool_policy(
    tmp_path: Path, field: str, replacement: str
) -> None:
    fixture_root = copied_fixtures(tmp_path)
    path = fixture_root / "evaluation-cases.json"
    payload = load(path)
    payload[field] = replacement
    save(path, payload)
    with pytest.raises(FixtureIntegrityError, match=f"unsupported local contract identity: {field}"):
        build_offline_lab(fixture_root).assess()


def test_coordinated_unknown_contract_labels_still_fail_registry(tmp_path: Path) -> None:
    fixture_root = copied_fixtures(tmp_path)
    cases_path = fixture_root / "evaluation-cases.json"
    cases = load(cases_path)
    cases["evaluator_version"] = "other"
    cases["rubric_version"] = "other"
    cases["tool_policy_id"] = "other"
    save(cases_path, cases)
    observations_path = fixture_root / "observations.json"
    observations = load(observations_path)
    observations["provenance"]["evaluator_version"] = "other"
    observations["provenance"]["rubric_version"] = "other"
    observations["provenance"]["tool_policy_id"] = "other"
    save(observations_path, observations)
    with pytest.raises(FixtureIntegrityError, match="unsupported local contract identity"):
        build_offline_lab(fixture_root).assess()


def test_observation_provenance_binds_candidate_config_ids(tmp_path: Path) -> None:
    fixture_root = copied_fixtures(tmp_path)
    path = fixture_root / "provider-profiles.json"
    payload = load(path)
    payload["candidates"][0]["config_id"] = "cfg-mutated"
    save(path, payload)
    with pytest.raises(FixtureIntegrityError, match="provenance mismatch for candidate config IDs"):
        build_offline_lab(fixture_root).assess()


def test_colluding_fake_evidence_ids_fail_at_trusted_case_manifest(tmp_path: Path) -> None:
    fixture_root = copied_fixtures(tmp_path)
    cases_path = fixture_root / "evaluation-cases.json"
    cases = load(cases_path)
    case = next(item for item in cases["cases"] if item["case_id"] == "short-hard-proof")
    case["allowed_evidence_ids"] = ["fake-a", "fake-b"]
    case["required_evidence_ids"] = ["fake-a", "fake-b"]
    save(cases_path, cases)
    observations_path = fixture_root / "observations.json"
    observations = load(observations_path)
    for row in observations["observations"]:
        if row["case_id"] == "short-hard-proof":
            row["evidence_ids"] = ["fake-a", "fake-b"]
    save(observations_path, observations)
    with pytest.raises(FixtureIntegrityError, match="evaluation cases differ from trusted case manifest"):
        build_offline_lab(fixture_root).assess()


def test_required_evidence_cannot_be_deleted_past_trusted_manifest(tmp_path: Path) -> None:
    fixture_root = copied_fixtures(tmp_path)
    path = fixture_root / "evaluation-cases.json"
    payload = load(path)
    case = next(item for item in payload["cases"] if item["case_id"] == "short-hard-proof")
    case["required_evidence_ids"] = []
    case["evidence_required"] = 0
    save(path, payload)
    with pytest.raises(FixtureIntegrityError, match="evaluation cases differ from trusted case manifest"):
        build_offline_lab(fixture_root).assess()


def test_evidence_content_digest_is_verified(tmp_path: Path) -> None:
    fixture_root = copied_fixtures(tmp_path)
    path = fixture_root / "evidence-corpus.json"
    payload = load(path)
    payload["records"][0]["content_digest"] = "0" * 64
    save(path, payload)
    with pytest.raises(FixtureIntegrityError, match="digest does not match content"):
        build_offline_lab(fixture_root).assess()


def test_unknown_ranking_weight_key_is_rejected(tmp_path: Path) -> None:
    fixture_root = copied_fixtures(tmp_path)
    path = fixture_root / "evaluation-cases.json"
    payload = load(path)
    payload["task_policies"][0]["weights"]["unknown"] = 0.0
    save(path, payload)
    with pytest.raises(FixtureIntegrityError, match="ranking-weight keys"):
        build_offline_lab(fixture_root).assess()


@pytest.mark.parametrize("task", ["high_stakes_reasoning", "impossible_safety"])
def test_registered_noncompensable_policy_cannot_disable_joint_run_gate(
    tmp_path: Path, task: str
) -> None:
    fixture_root = copied_fixtures(tmp_path)
    path = fixture_root / "evaluation-cases.json"
    payload = load(path)
    policy = next(item for item in payload["task_policies"] if item["task"] == task)
    policy["require_every_holdout_run"] = False
    save(path, payload)
    with pytest.raises(
        FixtureIntegrityError,
        match=f"registered noncompensable task {task} must require every holdout run",
    ):
        build_offline_lab(fixture_root).assess()


def test_disjoint_high_stakes_runs_cannot_aggregate_compensate(tmp_path: Path) -> None:
    fixture_root = copied_fixtures(tmp_path)
    cases_path = fixture_root / "evaluation-cases.json"
    cases = load(cases_path)
    policy = next(
        item for item in cases["task_policies"] if item["task"] == "high_stakes_reasoning"
    )
    policy["hard_gates"]["minimum_quality"] = 0.0
    policy["hard_gates"]["maximum_factual_error_rate"] = 0.6
    policy["hard_gates"]["minimum_evidence_coverage"] = 0.4
    policy["hard_gates"]["minimum_correct_abstention_rate"] = 0.0
    save(cases_path, cases)
    observations_path = fixture_root / "observations.json"
    observations = load(observations_path)
    rows = [
        item
        for item in observations["observations"]
        if item["candidate_id"] == "Flint-E" and item["case_id"] == "short-hard-proof"
    ]
    for row in rows:
        if row["repeat"] in {1, 2, 3}:
            # Correct answer, but no required evidence.
            row["answer"] = "holds"
            row["factual_errors"] = 0
            row["evidence_ids"] = []
        else:
            # Wrong answer with complete evidence.
            row["answer"] = "fails"
            row["factual_errors"] = 1
            row["evidence_ids"] = ["rule-bridge-a", "rule-bridge-b"]
    save(observations_path, observations)
    report = build_offline_lab(fixture_root).assess()
    hard = next(task for task in report.tasks if task.task == "high_stakes_reasoning")
    flint = next(candidate for candidate in hard.candidates if candidate.candidate_id == "Flint-E")
    assert flint.metrics is not None
    assert flint.metrics.factual_error_rate == 0.4
    assert flint.metrics.evidence_coverage == 0.4
    assert not flint.qualified
    assert flint.failed_holdout_runs == (
        "short-hard-proof#1",
        "short-hard-proof#2",
        "short-hard-proof#3",
        "short-hard-proof#4",
        "short-hard-proof#5",
    )
    assert "noncompensable holdout run gate failed" in flint.gate_failures


def test_missing_evidence_contributes_to_high_stakes_failure_probability(
    tmp_path: Path,
) -> None:
    fixture_root = copied_fixtures(tmp_path)
    observations_path = fixture_root / "observations.json"
    observations = load(observations_path)
    row = next(
        item
        for item in observations["observations"]
        if item["candidate_id"] == "Flint-E"
        and item["case_id"] == "short-hard-proof"
        and item["repeat"] == 1
    )
    row["evidence_ids"] = []
    save(observations_path, observations)
    report = build_offline_lab(fixture_root).assess()
    hard = next(task for task in report.tasks if task.task == "high_stakes_reasoning")
    flint = next(candidate for candidate in hard.candidates if candidate.candidate_id == "Flint-E")
    assert flint.holdout_escalation_probability == 0.2


def test_high_stakes_one_failed_run_cannot_be_averaged_away(tmp_path: Path) -> None:
    fixture_root = copied_fixtures(tmp_path)
    cases_path = fixture_root / "evaluation-cases.json"
    cases = load(cases_path)
    policy = next(
        item for item in cases["task_policies"] if item["task"] == "high_stakes_reasoning"
    )
    # Make aggregate gates permissive enough that one failure in five passes.
    policy["hard_gates"]["maximum_factual_error_rate"] = 0.25
    policy["hard_gates"]["minimum_evidence_coverage"] = 0.8
    save(cases_path, cases)
    observations_path = fixture_root / "observations.json"
    observations = load(observations_path)
    row = next(
        item
        for item in observations["observations"]
        if item["candidate_id"] == "Flint-E"
        and item["case_id"] == "short-hard-proof"
        and item["repeat"] == 1
    )
    row["answer"] = "fails"
    row["factual_errors"] = 1
    row["evidence_ids"] = []
    save(observations_path, observations)
    report = build_offline_lab(fixture_root).assess()
    hard = next(task for task in report.tasks if task.task == "high_stakes_reasoning")
    flint = next(candidate for candidate in hard.candidates if candidate.candidate_id == "Flint-E")
    assert flint.metrics is not None
    assert flint.metrics.factual_error_rate == 0.2
    assert flint.metrics.evidence_coverage == 0.8
    assert not flint.qualified
    assert flint.failed_holdout_runs == ("short-hard-proof#1",)
    assert "noncompensable holdout run gate failed" in flint.gate_failures


@pytest.mark.parametrize("value", [0, -1, float("inf")])
def test_manual_review_unit_cost_must_be_finite_and_strictly_positive(
    tmp_path: Path, value: float
) -> None:
    fixture_root = copied_fixtures(tmp_path)
    path = fixture_root / "evaluation-cases.json"
    payload = load(path)
    payload["task_policies"][0]["manual_review_unit_cost"] = value
    save(path, payload)
    with pytest.raises(FixtureIntegrityError, match="manual review unit cost|non-finite JSON"):
        build_offline_lab(fixture_root).assess()


def test_nonfinite_json_is_rejected(tmp_path: Path) -> None:
    fixture_root = copied_fixtures(tmp_path)
    path = fixture_root / "prices.json"
    text = path.read_text(encoding="utf-8").replace('"uncached_input": 0.8', '"uncached_input": NaN', 1)
    path.write_text(text, encoding="utf-8")
    with pytest.raises(FixtureIntegrityError, match="non-finite JSON"):
        build_offline_lab(fixture_root).assess()
