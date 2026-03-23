"""Smoke test for the first-round SwarmMind rewrite skeleton.

Run from the repository root:

    python scripts/test_first_round.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from swarmmind.app import build_container
from swarmmind.gateway import TaskSubmitRequest


async def main() -> None:
    """Submit a task and print the resulting control-plane state."""
    container = await build_container()
    identity = await container.identity_resolver.resolve()

    result = await container.gateway.submit_task(
        TaskSubmitRequest(
            goal="实现一个导出 Excel 功能并补测试",
            profile="py-basic",
            preferred_strategy="build_app",
            metadata={"source": "smoke-test"},
        ),
        identity=identity,
    )

    task_detail = await container.query_service.get_task_detail(result.task_id, identity)
    if task_detail is None:
        raise RuntimeError("task detail could not be loaded")

    event_topics = [event.topic for event in container.event_bus.list_events()]
    payload = {
        "submission": result.model_dump(mode="json"),
        "task": task_detail.task.model_dump(mode="json"),
        "session": task_detail.session.model_dump(mode="json") if task_detail.session else None,
        "runs": [run.model_dump(mode="json") for run in task_detail.runs],
        "events": event_topics,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())