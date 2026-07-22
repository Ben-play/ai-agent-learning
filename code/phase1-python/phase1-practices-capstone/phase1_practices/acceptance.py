from __future__ import annotations

import asyncio
import json
import tempfile
from collections import Counter
from pathlib import Path

import httpx

import phase1_practices
from phase1_practices.contracts import ActionRequest, RunRequest
from phase1_practices.gateway import StreamTracker, TrackedAsyncStream, redact
from phase1_practices.runtime import PracticeAgent, build_offline_agent
from phase1_practices.storage import atomic_write_json


async def _assert_runtime() -> None:
    calls: Counter[str] = Counter()
    active = 0
    peak = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active, peak
        prompt = str(json.loads(request.content)["prompt"])
        calls[prompt] += 1
        active += 1
        peak = max(peak, active)
        try:
            await asyncio.sleep(0)
            if prompt == "retry" and calls[prompt] == 1:
                raise httpx.ConnectError("temporary", request=request)
            if prompt == "invalid":
                return httpx.Response(200, json={"wrong": "shape"})
            return httpx.Response(200, json={"response": f"ready:{prompt}"})
        finally:
            active -= 1

    with tempfile.TemporaryDirectory() as raw:
        store_dir = Path(raw)
        async with build_offline_agent(store_dir=store_dir, handler=handler) as agent:
            first = await agent.run(RunRequest(
                run_id="first",
                prompt="retry",
                actions=[
                    ActionRequest(
                        name="remember", arguments={"key": "x", "value": "safe"}
                    ),
                    ActionRequest(name="recall", arguments={"key": "x"}),
                ],
            ))
            second = await agent.run(RunRequest(
                run_id="second",
                prompt="fresh",
                actions=[ActionRequest(name="recall", arguments={"key": "x"})],
            ))
            assert first.status == second.status == "succeeded"
            assert first.attempts == 2
            assert first.actions[-1].value == "safe"
            assert second.actions[-1].value is None

            batch = await agent.run_batch(
                [
                    RunRequest(run_id="batch-ok", prompt="ok"),
                    RunRequest(run_id="batch-bad", prompt="invalid"),
                ],
                parallelism=2,
                deadline_s=0.2,
            )
            assert [item.status for item in batch.items] == ["succeeded", "failed"]
            assert calls["ok"] == calls["invalid"] == 1
            assert peak == 2

        assert json.loads((store_dir / "first.json").read_text(encoding="utf-8"))[
            "status"
        ] == "succeeded"
        assert not list(store_dir.glob("*.tmp"))


async def _assert_httpx_stream_close() -> None:
    tracker = StreamTracker()

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            stream=TrackedAsyncStream(
                [b'{"response":', b'"streamed"}'], tracker
            ),
        )

    async with build_offline_agent(handler=handler) as agent:
        report = await agent.run(RunRequest(run_id="stream", prompt="stream"))
        assert report.status == "succeeded"
        assert report.response == "streamed"
    assert tracker.opened == tracker.closed == 1


def _assert_storage_failure() -> None:
    with tempfile.TemporaryDirectory() as raw:
        path = Path(raw) / "report.json"
        old = b'{"version": 1}\n'
        path.write_bytes(old)
        injected = OSError("injected replace failure")

        def fail(stage: str, _: Path) -> None:
            if stage == "flushed":
                raise injected

        try:
            atomic_write_json(path, {"version": 2}, failure_hook=fail)
        except OSError as caught:
            assert caught is injected
        else:
            raise AssertionError("storage failure must propagate")
        assert path.read_bytes() == old
        assert not list(path.parent.glob("*.tmp"))


def main() -> None:
    assert phase1_practices.__all__ == [
        "RunRequest",
        "RunReport",
        "BatchOutcome",
        "PracticeAgent",
        "build_offline_agent",
    ]
    assert PracticeAgent is not None
    fake_secret = "phase1-placeholder-not-a-real-key"
    hidden = redact(
        {"Authorization": fake_secret, "note": f"token={fake_secret}"},
        [fake_secret],
    )
    rendered = repr(hidden)
    assert fake_secret not in rendered
    assert "Authorization" not in rendered
    _assert_storage_failure()
    asyncio.run(_assert_runtime())
    asyncio.run(_assert_httpx_stream_close())
    print("PHASE 1 PRACTICES ACCEPTED")


if __name__ == "__main__":
    main()
