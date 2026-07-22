from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import ValidationError

from .contracts import GatewayReply

_SECRET_WORDS = ("authorization", "api-key", "api_key", "password", "secret", "token")


def redact(value: Any, secret_values: Iterable[str] = ()) -> Any:
    secrets = tuple(item for item in secret_values if item)
    if isinstance(value, Mapping):
        redacted_mapping: dict[str, Any] = {}
        for key, item in value.items():
            text_key = str(key)
            if any(word in text_key.lower() for word in _SECRET_WORDS):
                redacted_mapping[f"[REDACTED_NAME_{len(redacted_mapping)}]"] = "[REDACTED]"
            else:
                redacted_mapping[text_key] = redact(item, secrets)
        return redacted_mapping
    if isinstance(value, list):
        return [redact(item, secrets) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item, secrets) for item in value)
    if isinstance(value, str):
        result = value
        for secret in secrets:
            result = result.replace(secret, "[REDACTED]")
        return result
    return value


def redact_text(text: str, secret_values: Iterable[str] = ()) -> str:
    """Remove known secret values and sensitive field names from diagnostics."""
    result = text
    for secret in (item for item in secret_values if item):
        result = result.replace(secret, "[REDACTED]")
    for word in _SECRET_WORDS:
        result = re.sub(re.escape(word), "[REDACTED_NAME]", result, flags=re.I)
    return result


class GatewayError(RuntimeError):
    pass


@dataclass
class GatewayAttempts:
    count: int = 0


@dataclass
class StreamTracker:
    opened: int = 0
    closed: int = 0


class TrackedAsyncStream(httpx.AsyncByteStream):
    """A real HTTPX response stream with observable close semantics."""

    def __init__(self, chunks: Iterable[bytes], tracker: StreamTracker, *, delay: float = 0) -> None:
        self._chunks = tuple(chunks)
        self._tracker = tracker
        self._delay = delay
        self._closed = False
        self._tracker.opened += 1

    async def __aenter__(self) -> TrackedAsyncStream:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: Any,
    ) -> None:
        await self.aclose()

    async def __aiter__(self) -> AsyncIterator[bytes]:
        try:
            for chunk in self._chunks:
                if self._delay:
                    await asyncio.sleep(self._delay)
                yield chunk
        finally:
            await self.aclose()

    async def aclose(self) -> None:
        if not self._closed:
            self._closed = True
            self._tracker.closed += 1


Sleep = Callable[[float], Awaitable[None]]


class OfflineGateway:
    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        max_attempts: int = 3,
        backoff_seconds: float = 0,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        self._client = client
        self._max_attempts = max_attempts
        self._backoff_seconds = backoff_seconds
        self._sleep = sleep

    async def stream_chunks(self, prompt: str) -> AsyncGenerator[bytes, None]:
        """Yield one response body while retaining ownership of its HTTP stream."""
        async with self._client.stream(
            "POST", "/complete", json={"prompt": prompt}
        ) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes():
                yield chunk

    async def complete(
        self, prompt: str, evidence: GatewayAttempts | None = None
    ) -> GatewayReply:
        attempts = evidence or GatewayAttempts()
        last_error: httpx.TransportError | None = None
        for attempt in range(1, self._max_attempts + 1):
            attempts.count = attempt
            try:
                body = bytearray()
                async for chunk in self.stream_chunks(prompt):
                    body.extend(chunk)
                parsed = GatewayReply.model_validate_json(bytes(body))
                return parsed.model_copy(update={"attempts": attempt})
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
                if attempt == self._max_attempts:
                    break
                await self._sleep(self._backoff_seconds * attempt)
            except (httpx.HTTPStatusError, ValidationError, json.JSONDecodeError):
                raise
        assert last_error is not None
        raise GatewayError("offline transport failed after retries") from last_error

    async def aclose(self) -> None:
        await self._client.aclose()
