from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ActionRequest(StrictModel):
    name: str = Field(min_length=1, max_length=64)
    arguments: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("action name must not be blank")
        return normalized


class RunRequest(StrictModel):
    run_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    prompt: str = Field(min_length=1, max_length=2_000)
    actions: list[ActionRequest] = Field(default_factory=list, max_length=8)
    operation_timeout: float = Field(default=1.0, gt=0, le=30)

    @field_validator("prompt")
    @classmethod
    def normalize_prompt(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("prompt must not be blank")
        return normalized


class ActionResult(StrictModel):
    name: str
    value: Any


class RunReport(StrictModel):
    run_id: str
    status: Literal["succeeded", "failed", "timed_out"]
    response: str | None = None
    actions: list[ActionResult] = Field(default_factory=list)
    error: str | None = None
    attempts: int = Field(default=0, ge=0)


class BatchOutcome(StrictModel):
    items: list[RunReport]
    succeeded: int = Field(ge=0)
    failed: int = Field(ge=0)
    timed_out: int = Field(ge=0)


class GatewayReply(StrictModel):
    response: str = Field(min_length=1, max_length=2_000)
    attempts: int = Field(default=0, ge=0)
