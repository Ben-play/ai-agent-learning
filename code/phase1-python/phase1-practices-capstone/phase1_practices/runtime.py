from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from typing import Any, Coroutine, TypeVar

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .contracts import ActionResult, BatchOutcome, RunReport, RunRequest
from .gateway import GatewayAttempts, OfflineGateway, redact_text
from .registry import ActionRegistry, PreparedAction
from .storage import JsonRunStore

T = TypeVar("T")
_SENSITIVE_NAMES = ("authorization", "api-key", "api_key", "password", "secret", "token")


def _all_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, dict):
        return [item for child in value.values() for item in _all_strings(child)]
    if isinstance(value, (list, tuple, set, frozenset)):
        return [item for child in value for item in _all_strings(child)]
    return []


def _secret_values(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if any(name in str(key).lower() for name in _SENSITIVE_NAMES):
                found.extend(_all_strings(item))
            else:
                found.extend(_secret_values(item))
    elif isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            found.extend(_secret_values(item))
    return found


class SchedulerTimeoutError(TimeoutError):
    pass


class RememberInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    key: str = Field(min_length=1, max_length=80)
    value: str = Field(max_length=1_000)


class RecallInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    key: str = Field(min_length=1, max_length=80)


async def _remember(data: RememberInput, state: dict[str, Any]) -> str:
    memory = state.setdefault("memory", {})
    assert isinstance(memory, dict)
    memory[data.key] = data.value
    return data.value


async def _recall(data: RecallInput, state: dict[str, Any]) -> Any:
    memory = state.setdefault("memory", {})
    assert isinstance(memory, dict)
    return memory.get(data.key)


async def _with_scheduler_timeout(awaitable: Awaitable[T], timeout: float) -> T:
    task = asyncio.ensure_future(awaitable)
    try:
        done, _ = await asyncio.wait({task}, timeout=timeout)
        if not done:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            raise SchedulerTimeoutError(
                f"scheduler deadline exceeded after {timeout:g}s"
            )
        return task.result()
    except asyncio.CancelledError:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        raise


class PracticeAgent:
    async def __aenter__(self) -> PracticeAgent:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: Any,
    ) -> None:
        await self.aclose()

    def __init__(
        self,
        gateway: OfflineGateway,
        registry: ActionRegistry,
        *,
        store: JsonRunStore | None = None,
        max_actions: int = 8,
    ) -> None:
        self._gateway = gateway
        self._registry = registry
        self._store = store
        self._max_actions = max_actions

    async def run(self, request: RunRequest) -> RunReport:
        state: dict[str, Any] = {}
        gateway_attempts = GatewayAttempts()
        secrets = _secret_values(request.model_dump(mode="python"))

        def safe_error(error: BaseException) -> str:
            return redact_text(f"{type(error).__name__}: {error}", secrets)

        try:
            if len(request.actions) > self._max_actions:
                raise ValueError(f"at most {self._max_actions} actions are allowed")
            prepared: list[PreparedAction] = [
                self._registry.prepare(action.name, action.arguments)
                for action in request.actions
            ]
            reply = await _with_scheduler_timeout(
                self._gateway.complete(request.prompt, gateway_attempts),
                request.operation_timeout,
            )
            action_results: list[ActionResult] = []
            for action in prepared:
                value = await _with_scheduler_timeout(
                    self._registry.execute_prepared(action, state),
                    request.operation_timeout,
                )
                action_results.append(ActionResult(name=action.name, value=value))
            report = RunReport(
                run_id=request.run_id,
                status="succeeded",
                response=reply.response,
                actions=action_results,
                attempts=gateway_attempts.count,
            )
        except asyncio.CancelledError:
            raise
        except SchedulerTimeoutError as exc:
            report = RunReport(
                run_id=request.run_id,
                status="timed_out",
                error=safe_error(exc),
                attempts=gateway_attempts.count,
            )
        except (LookupError, ValueError, ValidationError, httpx.HTTPError, RuntimeError, TimeoutError) as exc:
            report = RunReport(
                run_id=request.run_id,
                status="failed",
                error=safe_error(exc),
                attempts=gateway_attempts.count,
            )
        if self._store is not None:
            self._store.write(report)
        return report

    async def run_batch(
        self,
        requests: Sequence[RunRequest],
        *,
        parallelism: int = 3,
        deadline_s: float | None = None,
    ) -> BatchOutcome:
        if parallelism < 1:
            raise ValueError("parallelism must be positive")
        semaphore = asyncio.Semaphore(parallelism)

        async def run_one(request: RunRequest) -> RunReport:
            async def invoke() -> RunReport:
                async with semaphore:
                    return await self.run(request)

            try:
                if deadline_s is None:
                    return await invoke()
                return await _with_scheduler_timeout(invoke(), deadline_s)
            except asyncio.CancelledError:
                raise
            except SchedulerTimeoutError as exc:
                return RunReport(run_id=request.run_id, status="timed_out", error=str(exc))
            except Exception as exc:
                return RunReport(
                    run_id=request.run_id,
                    status="failed",
                    error=f"{type(exc).__name__}: {exc}",
                )

        items = list(await asyncio.gather(*(run_one(request) for request in requests)))
        return BatchOutcome(
            items=items,
            succeeded=sum(item.status == "succeeded" for item in items),
            failed=sum(item.status == "failed" for item in items),
            timed_out=sum(item.status == "timed_out" for item in items),
        )

    async def aclose(self) -> None:
        await self._gateway.aclose()


def build_offline_agent(
    *,
    store_dir: Path | None = None,
    handler: (
        Callable[[httpx.Request], httpx.Response]
        | Callable[[httpx.Request], Coroutine[None, None, httpx.Response]]
        | None
    ) = None,
) -> PracticeAgent:
    def default_handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        prompt = str(payload["prompt"])
        return httpx.Response(200, json={"response": f"offline: {prompt}"})

    transport = httpx.MockTransport(handler or default_handler)
    client = httpx.AsyncClient(transport=transport, base_url="https://offline.invalid")
    registry = ActionRegistry()
    registry.register("remember", RememberInput, _remember)
    registry.register("recall", RecallInput, _recall)
    store = JsonRunStore(store_dir) if store_dir is not None else None
    return PracticeAgent(OfflineGateway(client), registry, store=store)
