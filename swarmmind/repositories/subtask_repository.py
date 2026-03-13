"""Subtask repository protocol."""

from __future__ import annotations

from typing import Protocol

from swarmmind.models.task import SubTask


class SubTaskRepository(Protocol):
    """Persistence contract for subtasks."""

    async def create_many(self, subtasks: list[SubTask]) -> list[SubTask]:
        ...

    async def save(self, subtask: SubTask) -> SubTask:
        ...

    async def get(self, subtask_id: str) -> SubTask | None:
        ...

    async def list_for_task(self, task_id: str) -> list[SubTask]:
        ...

    async def list_for_run(self, run_id: str) -> list[SubTask]:
        ...
