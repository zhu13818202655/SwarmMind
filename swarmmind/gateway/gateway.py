"""Gateway for routing tasks to agents."""

import uuid
from typing import Any
from swarmmind.models.task import Task, TaskRequest, TaskResponse, TaskStatus
from swarmmind.memory.transcript import Transcript


class Gateway:
    """Gateway for routing tasks."""

    def __init__(self):
        self._tasks: dict[str, Task] = {}
        self._sessions: dict[str, dict[str, Any]] = {}

    async def create_task(self, request: TaskRequest) -> Task:
        """Create a new task."""
        task = Task(
            id=str(uuid.uuid4()),
            goal=request.goal,
            constraints=request.constraints,
            priority=request.priority,
        )
        self._tasks[task.id] = task
        return task

    async def get_task(self, task_id: str) -> Task | None:
        """Get task by ID."""
        return self._tasks.get(task_id)

    async def update_task(self, task: Task) -> None:
        """Update task."""
        self._tasks[task.id] = task

    async def list_tasks(self, status: TaskStatus | None = None) -> list[Task]:
        """List tasks, optionally filtered by status."""
        tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        return tasks

    def create_session(self, task_id: str) -> dict[str, Any]:
        """Create a session for a task."""
        session = {
            "task_id": task_id,
            "transcript": Transcript(task_id),
            "context": {},
        }
        self._sessions[task_id] = session
        return session

    def get_session(self, task_id: str) -> dict[str, Any] | None:
        """Get session by task ID."""
        return self._sessions.get(task_id)

    async def close_session(self, task_id: str) -> None:
        """Close a session."""
        self._sessions.pop(task_id, None)
