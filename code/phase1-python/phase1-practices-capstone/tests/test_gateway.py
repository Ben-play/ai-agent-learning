from __future__ import annotations

import asyncio
from contextlib import aclosing

import httpx
import pytest
from pydantic import ValidationError

from phase1_practices.gateway import (
    GatewayError,
    OfflineGateway,
    StreamTracker,
    TrackedAsyncStream,
    redact,
)


def test_gateway_alone_retries_retryable_transport_errors() -> None:
    async def scenario() -> None:
        calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            if calls < 3:
                raise httpx.ConnectError("offline failure", request=request)
            return httpx.Response(200, json={"response": "ok"})

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://offline.invalid")
        gateway = OfflineGateway(client)
        try:
            assert (await gateway.complete("hello")).response == "ok"
            assert calls == 3
        finally:
            await gateway.aclose()

    asyncio.run(scenario())


def test_gateway_final_transport_error_preserves_cause() -> None:
    async def scenario() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("terminal", request=request)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://offline.invalid")
        gateway = OfflineGateway(client, max_attempts=2)
        try:
            with pytest.raises(GatewayError) as caught:
                await gateway.complete("hello")
            assert isinstance(caught.value.__cause__, httpx.ConnectError)
        finally:
            await gateway.aclose()

    asyncio.run(scenario())


def test_gateway_does_not_retry_validation_errors() -> None:
    async def scenario() -> None:
        calls = 0

        def handler(_: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(200, json={"wrong": "shape"})

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://offline.invalid")
        gateway = OfflineGateway(client)
        try:
            with pytest.raises(ValidationError):
                await gateway.complete("hello")
            assert calls == 1
        finally:
            await gateway.aclose()

    asyncio.run(scenario())


@pytest.mark.parametrize("mode", ["normal", "early", "validation", "timeout", "cancel"])
def test_gateway_closes_real_httpx_stream_on_every_exit(mode: str) -> None:
    async def scenario() -> None:
        tracker = StreamTracker()
        delay = 0.05 if mode in {"timeout", "cancel"} else 0
        if mode == "normal":
            chunks = [b'{"response":"ok"}']
        elif mode == "validation":
            chunks = [b'{"wrong":"shape"}']
        else:
            chunks = [b'{"response":', b'"ok"}']

        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                stream=TrackedAsyncStream(chunks, tracker, delay=delay),
            )

        client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://offline.invalid",
        )
        gateway = OfflineGateway(client)

        async def consume() -> None:
            if mode in {"normal", "validation"}:
                await gateway.complete("hello")
                return
            async with aclosing(gateway.stream_chunks("hello")) as stream:
                async for _ in stream:
                    if mode == "early":
                        break

        try:
            if mode in {"normal", "early"}:
                await consume()
            elif mode == "validation":
                with pytest.raises(ValidationError):
                    await consume()
            elif mode == "timeout":
                with pytest.raises(TimeoutError):
                    await asyncio.wait_for(consume(), timeout=0.01)
            else:
                task = asyncio.create_task(consume())
                await asyncio.sleep(0)
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
            assert tracker.opened == tracker.closed == 1
        finally:
            await gateway.aclose()

    asyncio.run(scenario())


def test_redaction_hides_secret_names_and_values_recursively() -> None:
    secret = "top-secret-value"
    result = redact({"Authorization": secret, "nested": [f"Bearer {secret}", {"password": "x"}]}, [secret])
    rendered = repr(result)
    assert secret not in rendered
    assert "Bearer [REDACTED]" in rendered
    assert "Authorization" not in rendered
    assert "password" not in rendered
    assert result["[REDACTED_NAME_0]"] == "[REDACTED]"
    assert result["nested"][1]["[REDACTED_NAME_0]"] == "[REDACTED]"
