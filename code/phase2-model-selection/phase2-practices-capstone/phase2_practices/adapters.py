"""Provider profile adapters for deterministic fixture observations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from typing import Any, cast

from .contracts import CandidateProfile, EvaluationCase, JsonScalar, Observation, SemanticPolicy, Usage


class UnsupportedControlError(ValueError):
    """Raised before lookup when a semantic control is unsupported."""


class PreflightBudgetError(ValueError):
    """Raised before observation lookup when provider count is invalid."""


class PolicyMismatchError(ValueError):
    """Raised when a caller substitutes a policy for the frozen case policy."""


class ProviderAdapter(ABC):
    """Internal seam mapping provider-specific fixtures to one observation."""

    def __init__(
        self,
        profile: CandidateProfile,
        lookup: Callable[[str, str, int], Mapping[str, Any] | None] | None = None,
        estimate_lookup: Callable[[str, str, int], Mapping[str, Any] | None] | None = None,
    ) -> None:
        self.profile = profile
        self._lookup = lookup
        self._estimate_lookup = estimate_lookup

    @abstractmethod
    def observe(
        self,
        case: EvaluationCase,
        policy: SemanticPolicy,
        repeat: int,
        raw_observation: Mapping[str, Any] | None,
    ) -> Observation:
        """Validate controls/budget, then map one common observation."""

    def _validated_policy(
        self, case: EvaluationCase, policy: SemanticPolicy
    ) -> SemanticPolicy:
        if policy != case.policy:
            raise PolicyMismatchError(
                f"passed policy differs from frozen case policy for {case.case_id}"
            )
        return policy

    def _mapped_controls(self, policy: SemanticPolicy) -> dict[str, JsonScalar]:
        unsupported = sorted(set(dict(policy.controls)) - self.profile.supported_controls)
        if unsupported:
            raise UnsupportedControlError(
                f"{self.profile.candidate_id} does not support semantic controls: "
                + ", ".join(unsupported)
            )
        names = dict(self.profile.control_mapping)
        return {names[key]: value for key, value in policy.controls}

    def _preflight(
        self,
        case: EvaluationCase,
        policy: SemanticPolicy,
        repeat: int,
        raw: Mapping[str, Any] | None,
    ) -> tuple[int, int]:
        estimate_raw = raw
        if estimate_raw is None and self._estimate_lookup is not None:
            estimate_raw = self._estimate_lookup(self.profile.candidate_id, case.case_id, repeat)
        if estimate_raw is None:
            raise LookupError("provider-native preflight estimate fixture is missing")
        self._validate_fixture_identity(estimate_raw, case, repeat, "estimate")
        container = _mapping(estimate_raw[self.profile.estimate_container])
        mapping = dict(self.profile.estimate_mapping)
        estimated_input = _integer(container[mapping["uncached_input"]])
        estimated_output = _integer(container[mapping["output"]])
        if estimated_input < 0 or estimated_output < 0:
            raise PreflightBudgetError(
                f"{self.profile.candidate_id}/{case.case_id} provider estimates must be nonnegative"
            )
        if estimated_input > policy.maximum_estimated_input_units:
            raise PreflightBudgetError(
                f"{self.profile.candidate_id}/{case.case_id} estimated input {estimated_input} "
                f"exceeds budget {policy.maximum_estimated_input_units}"
            )
        return estimated_input, estimated_output

    def _require_raw(
        self, case: EvaluationCase, repeat: int, raw: Mapping[str, Any] | None
    ) -> Mapping[str, Any]:
        resolved = raw
        if resolved is None and self._lookup is not None:
            resolved = self._lookup(self.profile.candidate_id, case.case_id, repeat)
        if resolved is None:
            raise LookupError("validated controls had no matching observation fixture")
        self._validate_fixture_identity(resolved, case, repeat, "observation")
        return resolved

    def _validate_fixture_identity(
        self,
        raw: Mapping[str, Any],
        case: EvaluationCase,
        repeat: int,
        fixture_kind: str,
    ) -> None:
        expected = {
            "candidate_id": self.profile.candidate_id,
            "case_id": case.case_id,
            "repeat": repeat,
        }
        actual = {
            "candidate_id": _string(raw["candidate_id"]),
            "case_id": _string(raw["case_id"]),
            "repeat": _integer(raw["repeat"]),
        }
        for field, expected_value in expected.items():
            if actual[field] != expected_value:
                raise ValueError(
                    f"{fixture_kind} fixture {field} mismatch: "
                    f"expected {expected_value}, got {actual[field]}"
                )
        if "provider" in raw and _string(raw["provider"]) != self.profile.provider:
            raise ValueError(
                f"{fixture_kind} fixture provider mismatch: "
                f"expected {self.profile.provider}, got {_string(raw['provider'])}"
            )

    def _validate_mapped_controls(
        self, raw: Mapping[str, Any], mapped: Mapping[str, JsonScalar]
    ) -> None:
        actual = _mapping(raw["mapped_controls"])
        if actual != mapped:
            raise ValueError(
                f"mapped controls differ for {self.profile.candidate_id}: "
                f"expected {mapped}, fixture has {actual}"
            )

    def _usage(self, raw: Mapping[str, Any]) -> Usage:
        container = _mapping(raw[self.profile.usage_container])
        mapping = dict(self.profile.usage_mapping)
        return Usage(
            uncached_input=_integer(container[mapping["uncached_input"]]),
            cache_write=_integer(container[mapping["cache_write"]]),
            cache_read=_integer(container[mapping["cache_read"]]),
            output=_integer(container[mapping["output"]]),
        )

    def _counters(self, raw: Mapping[str, Any]) -> tuple[int, int]:
        container = _mapping(raw[self.profile.counter_container])
        mapping = dict(self.profile.counter_mapping)
        return (
            _integer(container[mapping["retries"]]),
            _integer(container[mapping["escalations"]]),
        )

    def _common_observation(
        self,
        case: EvaluationCase,
        repeat: int,
        raw: Mapping[str, Any],
        estimate: tuple[int, int],
    ) -> Observation:
        retries, escalations = self._counters(raw)
        return Observation(
            observation_id=_string(raw["observation_id"]),
            provider=self.profile.provider,
            candidate_id=self.profile.candidate_id,
            case_id=case.case_id,
            split=case.split,
            repeat=repeat,
            estimated_uncached_input_units=estimate[0],
            estimated_output_units=estimate[1],
            answer=_string(raw["answer"]),
            quality_score=_number(raw["quality_score"]),
            factual_errors=_integer(raw["factual_errors"]),
            facts_checked=_integer(raw["facts_checked"]),
            abstained=_boolean(raw["abstained"]),
            evidence_ids=_strings(raw["evidence_ids"]),
            cache_entry_available_before=_boolean(raw["cache_entry_available_before"]),
            cache_origin=_string(raw["cache_origin"]),
            usage=self._usage(raw),
            retries=retries,
            escalations=escalations,
            fixed_latency_ms=_integer(raw["fixed_latency_ms"]),
        )


class SamplingFixtureAdapter(ProviderAdapter):
    """Maps sampling-style controls, count fixtures, and response usage."""

    def observe(
        self,
        case: EvaluationCase,
        policy: SemanticPolicy,
        repeat: int,
        raw_observation: Mapping[str, Any] | None,
    ) -> Observation:
        policy = self._validated_policy(case, policy)
        mapped = self._mapped_controls(policy)
        if "sample_spread" not in mapped or "output_limit" not in mapped:
            raise ValueError("sampling profile has incomplete control mapping")
        estimate = self._preflight(case, policy, repeat, raw_observation)
        raw = self._require_raw(case, repeat, raw_observation)
        self._validate_mapped_controls(raw, mapped)
        return self._common_observation(case, repeat, raw, estimate)


class EffortFixtureAdapter(ProviderAdapter):
    """Maps effort-style controls, count fixtures, and response usage."""

    def observe(
        self,
        case: EvaluationCase,
        policy: SemanticPolicy,
        repeat: int,
        raw_observation: Mapping[str, Any] | None,
    ) -> Observation:
        policy = self._validated_policy(case, policy)
        mapped = self._mapped_controls(policy)
        if "response_variance" not in mapped or "response_cap" not in mapped:
            raise ValueError("effort profile has incomplete control mapping")
        estimate = self._preflight(case, policy, repeat, raw_observation)
        raw = self._require_raw(case, repeat, raw_observation)
        self._validate_mapped_controls(raw, mapped)
        return self._common_observation(case, repeat, raw, estimate)


def build_adapter(
    profile: CandidateProfile,
    lookup: Callable[[str, str, int], Mapping[str, Any] | None] | None = None,
    estimate_lookup: Callable[[str, str, int], Mapping[str, Any] | None] | None = None,
) -> ProviderAdapter:
    if profile.adapter_kind == "sampling":
        return SamplingFixtureAdapter(profile, lookup, estimate_lookup)
    if profile.adapter_kind == "effort":
        return EffortFixtureAdapter(profile, lookup, estimate_lookup)
    raise ValueError(f"unknown adapter kind: {profile.adapter_kind}")


def _mapping(value: object) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise TypeError("expected fixture object")
    return cast(Mapping[str, Any], value)


def _string(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("expected fixture string")
    return value


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise TypeError("expected fixture string array")
    return tuple(_string(item) for item in value)


def _integer(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("expected fixture integer")
    return value


def _number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("expected fixture number")
    return float(value)


def _boolean(value: object) -> bool:
    if not isinstance(value, bool):
        raise TypeError("expected fixture boolean")
    return value


__all__ = [
    "EffortFixtureAdapter",
    "PolicyMismatchError",
    "PreflightBudgetError",
    "ProviderAdapter",
    "SamplingFixtureAdapter",
    "UnsupportedControlError",
]
