from __future__ import annotations

import asyncio
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

import phase1_practices
from phase1_practices.contracts import RunRequest
from phase1_practices.registry import ActionRegistry


def test_public_api_is_exact() -> None:
    assert phase1_practices.__all__ == [
        "RunRequest",
        "RunReport",
        "BatchOutcome",
        "PracticeAgent",
        "build_offline_agent",
    ]


def test_request_normalizes_and_rejects_extra_fields() -> None:
    request = RunRequest(run_id="one", prompt="  hello   world ")
    assert request.prompt == "hello world"
    with pytest.raises(ValidationError):
        RunRequest.model_validate({"run_id": "one", "prompt": "ok", "extra": True})


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: int


def test_registry_validates_before_handler_and_registers_once() -> None:
    async def scenario() -> None:
        registry = ActionRegistry()
        calls: list[int] = []

        async def handler(data: Input, state: dict[str, Any]) -> int:
            calls.append(data.value)
            return data.value

        registry.register("Do", Input, handler)
        with pytest.raises(ValueError):
            registry.register("do", Input, handler)
        with pytest.raises(ValidationError):
            await registry.dispatch("do", {"value": "bad"}, {})
        assert calls == []
        assert await registry.dispatch(" DO ", {"value": 3}, {}) == 3
        assert calls == [3]

    asyncio.run(scenario())


def test_registry_unknown_action_fails() -> None:
    async def scenario() -> None:
        registry = ActionRegistry()
        with pytest.raises(LookupError, match="unknown action"):
            await registry.dispatch("missing", {}, {})

    asyncio.run(scenario())
