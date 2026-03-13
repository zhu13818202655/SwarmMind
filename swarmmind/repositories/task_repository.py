"""Task repository protocol."""

from __future__ import annotations

from typing import Protocol

from swarmmind.models.task import Task, TaskStatus


class TaskRepository(Protocol):
    """Persistence contract for tasks."""

    async def create(self, task: Task) -> Task:
        ...

    async def get(self, task_id: str) -> Task | None:
        ...

    async def save(self, task: Task) -> Task:
        ...

    async def list_by_status(self, status: TaskStatus | None = None) -> list[Task]:
        ...
