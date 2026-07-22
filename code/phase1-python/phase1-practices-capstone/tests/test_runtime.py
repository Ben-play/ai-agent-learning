from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import BaseModel

from phase1_practices import RunRequest, build_offline_agent
from phase1_practices.gateway import OfflineGateway
from phase1_practices.registry import ActionRegistry
from phase1_practices.runtime import PracticeAgent


def test_run_has_fresh_state_and_unknown_action_fails() -> None:
    async def scenario() -> None:
        agent = build_offline_agent()
        try:
            first = await agent.run(RunRequest.model_validate({
                "run_id": "first", "prompt": "one",
                "actions": [{"name": "remember", "arguments": {"key": "x", "value": "one"}}],
            }))
            second = await agent.run(RunRequest.model_validate({
                "run_id": "second", "prompt": "two",
                "actions": [{"name": "recall", "arguments": {"key": "x"}}],
            }))
            unknown = await agent.run(RunRequest.model_validate({
                "run_id": "bad", "prompt": "bad",
                "actions": [{"name": "missing"}],
            }))
            assert first.status == second.status == "succeeded"
            assert second.actions[0].value is None
            assert unknown.status == "failed"
            assert "unknown action" in (unknown.error or "")
        finally:
            await agent.aclose()

    asyncio.run(scenario())


def test_operation_timeout_error_is_not_mislabeled_scheduler_timeout() -> None:
    async def scenario() -> None:
        class Empty(BaseModel):
            pass

        async def operation_timeout(_: Empty, __: dict[str, Any]) -> None:
            raise TimeoutError("operation said timeout")

        registry = ActionRegistry()
        registry.register("timeout", Empty, operation_timeout)
        client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"response": "ok"})), base_url="https://offline.invalid")
        agent = PracticeAgent(OfflineGateway(client), registry)
        try:
            report = await agent.run(RunRequest.model_validate({
                "run_id": "op-timeout", "prompt": "go",
                "actions": [{"name": "timeout"}],
            }))
            assert report.status == "failed"
            assert report.error == "TimeoutError: operation said timeout"
        finally:
            await agent.aclose()

    asyncio.run(scenario())


def test_batch_isolates_items_bounds_concurrency_and_does_not_retry_whole_batch() -> None:
    async def scenario() -> None:
        active = 0
        maximum = 0
        calls: dict[str, int] = {}

        async def handler(request: httpx.Request) -> httpx.Response:
            nonlocal active, maximum
            prompt = json.loads(request.content)["prompt"]
            calls[prompt] = calls.get(prompt, 0) + 1
            active += 1
            maximum = max(maximum, active)
            try:
                await asyncio.sleep(0.02)
                if prompt == "bad":
                    return httpx.Response(200, json={"invalid": True})
                return httpx.Response(200, json={"response": prompt})
            finally:
                active -= 1

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://offline.invalid")
        agent = PracticeAgent(OfflineGateway(client), ActionRegistry())
        requests = [RunRequest(run_id=f"r-{name}", prompt=name) for name in ["a", "bad", "c"]]
        try:
            outcome = await agent.run_batch(requests, parallelism=2)
            assert [item.status for item in outcome.items] == ["succeeded", "failed", "succeeded"]
            assert maximum <= 2
            assert calls == {"a": 1, "bad": 1, "c": 1}
        finally:
            await agent.aclose()

    asyncio.run(scenario())


def test_batch_scheduler_timeout_and_cancellation_propagation() -> None:
    async def scenario() -> None:
        async def slow(_: httpx.Request) -> httpx.Response:
            await asyncio.sleep(1)
            return httpx.Response(200, json={"response": "late"})

        client = httpx.AsyncClient(transport=httpx.MockTransport(slow), base_url="https://offline.invalid")
        agent = PracticeAgent(OfflineGateway(client), ActionRegistry())
        request = RunRequest(run_id="slow", prompt="slow", operation_timeout=2)
        try:
            outcome = await agent.run_batch([request], deadline_s=0.01)
            assert outcome.items[0].status == "timed_out"
            assert "scheduler deadline" in (outcome.items[0].error or "")
            task = asyncio.create_task(agent.run_batch([request]))
            await asyncio.sleep(0)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        finally:
            await agent.aclose()

    asyncio.run(scenario())


def test_actions_validate_before_http_and_errors_redact_secrets() -> None:
    async def scenario() -> None:
        calls = 0
        secret = "phase1-probe-secret"

        def handler(_: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(200, json={"response": "should-not-run"})

        agent = build_offline_agent(handler=handler)
        try:
            report = await agent.run(RunRequest.model_validate({
                "run_id": "invalid-before-http",
                "prompt": "validate first",
                "actions": [{
                    "name": "remember",
                    "arguments": {
                        "key": "x", "value": "safe", "password": secret,
                    },
                }],
            }))
            assert report.status == "failed"
            assert report.attempts == 0
            assert calls == 0
            assert secret not in (report.error or "")
            assert "password" not in (report.error or "").lower()
        finally:
            await agent.aclose()

    asyncio.run(scenario())


def test_parent_cancellation_cancels_nested_gateway_work() -> None:
    async def scenario() -> None:
        started = asyncio.Event()
        completed = asyncio.Event()
        cancelled = asyncio.Event()

        async def handler(_: httpx.Request) -> httpx.Response:
            started.set()
            try:
                await asyncio.sleep(1)
                completed.set()
                return httpx.Response(200, json={"response": "late"})
            except asyncio.CancelledError:
                cancelled.set()
                raise

        agent = build_offline_agent(handler=handler)
        task = asyncio.create_task(agent.run_batch([
            RunRequest(run_id="cancel", prompt="cancel"),
        ]))
        try:
            await started.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert cancelled.is_set()
            assert not completed.is_set()
        finally:
            await agent.aclose()

    asyncio.run(scenario())


def test_concurrent_runs_keep_per_item_attempt_counts() -> None:
    async def scenario() -> None:
        gate = asyncio.Event()
        entered = 0

        async def handler(request: httpx.Request) -> httpx.Response:
            nonlocal entered
            entered += 1
            if entered == 2:
                gate.set()
            await gate.wait()
            prompt = json.loads(request.content)["prompt"]
            return httpx.Response(200, json={"response": prompt})

        agent = build_offline_agent(handler=handler)
        try:
            outcome = await agent.run_batch([
                RunRequest(run_id="a", prompt="a"),
                RunRequest(run_id="b", prompt="b"),
            ], parallelism=2)
            assert [(item.run_id, item.attempts) for item in outcome.items] == [
                ("a", 1), ("b", 1),
            ]
        finally:
            await agent.aclose()

    asyncio.run(scenario())


def test_failure_and_scheduler_timeout_report_exact_attempts() -> None:
    async def scenario() -> None:
        failed_calls = 0

        def always_fails(request: httpx.Request) -> httpx.Response:
            nonlocal failed_calls
            failed_calls += 1
            raise httpx.ConnectError("offline", request=request)

        failed_agent = build_offline_agent(handler=always_fails)
        try:
            failed = await failed_agent.run(
                RunRequest(run_id="failed-attempts", prompt="fail")
            )
            assert failed.status == "failed"
            assert failed_calls == failed.attempts == 3
        finally:
            await failed_agent.aclose()

        started = asyncio.Event()

        async def slow(_: httpx.Request) -> httpx.Response:
            started.set()
            await asyncio.sleep(1)
            return httpx.Response(200, json={"response": "late"})

        timeout_agent = build_offline_agent(handler=slow)
        try:
            timed_out = await timeout_agent.run(RunRequest(
                run_id="timeout-attempts",
                prompt="slow",
                operation_timeout=0.01,
            ))
            assert started.is_set()
            assert timed_out.status == "timed_out"
            assert timed_out.attempts == 1
        finally:
            await timeout_agent.aclose()

    asyncio.run(scenario())


def test_batch_deadline_includes_semaphore_queue() -> None:
    async def scenario() -> None:
        async def slow(request: httpx.Request) -> httpx.Response:
            prompt = json.loads(request.content)["prompt"]
            await asyncio.sleep(0.08 if prompt == "first" else 0)
            return httpx.Response(200, json={"response": prompt})

        agent = build_offline_agent(handler=slow)
        try:
            outcome = await agent.run_batch([
                RunRequest(run_id="first", prompt="first"),
                RunRequest(run_id="queued", prompt="queued"),
            ], parallelism=1, deadline_s=0.05)
            assert [item.status for item in outcome.items] == [
                "timed_out", "timed_out",
            ]
        finally:
            await agent.aclose()

    asyncio.run(scenario())


def test_nested_sensitive_values_are_redacted() -> None:
    async def scenario() -> None:
        secret = "opaque-credential-93847"
        agent = build_offline_agent()
        try:
            report = await agent.run(RunRequest.model_validate({
                "run_id": "nested-secret",
                "prompt": "validate first",
                "actions": [{
                    "name": "recall",
                    "arguments": {"key": "x", "password": [secret]},
                }],
            }))
            assert report.status == "failed"
            assert secret not in (report.error or "")
            assert "password" not in (report.error or "").lower()
        finally:
            await agent.aclose()

    asyncio.run(scenario())


def test_run_persists_one_atomic_report(tmp_path: Path) -> None:
    async def scenario() -> None:
        agent = build_offline_agent(store_dir=tmp_path)
        try:
            report = await agent.run(RunRequest(run_id="stored", prompt="save"))
            assert report.status == "succeeded"
            persisted = json.loads((tmp_path / "stored.json").read_text(encoding="utf-8"))
            assert persisted["run_id"] == "stored"
            assert not list(tmp_path.glob("*.tmp"))
        finally:
            await agent.aclose()

    asyncio.run(scenario())
