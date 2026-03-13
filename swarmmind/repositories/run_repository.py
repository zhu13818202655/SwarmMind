"""Run repository protocol."""

from __future__ import annotations

from typing import Protocol

from swarmmind.models.run import Run


class RunRepository(Protocol):
    """Persistence contract for runs."""

    async def create(self, run: Run) -> Run:
        ...

    async def get(self, run_id: str) -> Run | None:
        ...

    async def save(self, run: Run) -> Run:
        ...

    async def list_for_task(self, task_id: str) -> list[Run]:
        ...
