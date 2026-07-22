from __future__ import annotations

import asyncio


async def main() -> None:
    executions = {"already-succeeded": 0, "flaky": 0}

    async def execute(name: str) -> bool:
        executions[name] += 1
        return name == "already-succeeded" or executions[name] > 1

    items = tuple(executions)
    while True:  # deliberately unsafe: retries successful work with the failed item
        outcomes = await asyncio.gather(*(execute(item) for item in items))
        if all(outcomes):
            break
    assert executions["already-succeeded"] == 1, "whole-batch retry duplicated successful work"


if __name__ == "__main__":
    asyncio.run(main())
