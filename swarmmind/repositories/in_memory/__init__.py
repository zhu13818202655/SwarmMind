"""In-memory repository implementations for the first rewrite round."""

from __future__ import annotations

from swarmmind.models.artifact import Artifact
from swarmmind.models.replay import ReplayRoot
from swarmmind.models.run import Run
from swarmmind.models.session import Session
from swarmmind.models.task import SubTask, Task, TaskStatus


class InMemoryTaskRepository:
    """In-memory task store."""

    def __init__(self):
        self._items: dict[str, Task] = {}

    async def create(self, task: Task) -> Task:
        self._items[task.id] = task
        return task

    async def get(self, task_id: str) -> Task | None:
        return self._items.get(task_id)

    async def save(self, task: Task) -> Task:
        self._items[task.id] = task
        return task

    async def list_by_status(self, status: TaskStatus | None = None) -> list[Task]:
        tasks = list(self._items.values())
        if status is None:
            return tasks
        return [task for task in tasks if task.status == status]


class InMemorySessionRepository:
    """In-memory session store."""

    def __init__(self):
        self._items: dict[str, Session] = {}

    async def create(self, session: Session) -> Session:
        self._items[session.id] = session
        return session

    async def get(self, session_id: str) -> Session | None:
        return self._items.get(session_id)

    async def save(self, session: Session) -> Session:
        self._items[session.id] = session
        return session


class InMemoryRunRepository:
    """In-memory run store."""

    def __init__(self):
        self._items: dict[str, Run] = {}

    async def create(self, run: Run) -> Run:
        self._items[run.id] = run
        return run

    async def get(self, run_id: str) -> Run | None:
        return self._items.get(run_id)

    async def save(self, run: Run) -> Run:
        self._items[run.id] = run
        return run

    async def list_for_task(self, task_id: str) -> list[Run]:
        return [run for run in self._items.values() if run.task_id == task_id]


class InMemorySubTaskRepository:
    """In-memory subtask store."""

    def __init__(self):
        self._items: dict[str, SubTask] = {}

    async def create_many(self, subtasks: list[SubTask]) -> list[SubTask]:
        for subtask in subtasks:
            self._items[subtask.id] = subtask
        return subtasks

    async def save(self, subtask: SubTask) -> SubTask:
        self._items[subtask.id] = subtask
        return subtask

    async def get(self, subtask_id: str) -> SubTask | None:
        return self._items.get(subtask_id)

    async def list_for_task(self, task_id: str) -> list[SubTask]:
        return [subtask for subtask in self._items.values() if subtask.task_id == task_id]

    async def list_for_run(self, run_id: str) -> list[SubTask]:
        return [subtask for subtask in self._items.values() if subtask.metadata.get("run_id") == run_id]


class InMemoryArtifactRepository:
    """In-memory artifact store."""

    def __init__(self):
        self._items: dict[str, Artifact] = {}

    async def create(self, artifact: Artifact) -> Artifact:
        self._items[artifact.id] = artifact
        return artifact

    async def list_for_run(self, run_id: str) -> list[Artifact]:
        return [artifact for artifact in self._items.values() if artifact.run_id == run_id]


class InMemoryReplayRepository:
    """In-memory replay store."""

    def __init__(self):
        self._items: dict[str, ReplayRoot] = {}

    async def create(self, replay: ReplayRoot) -> ReplayRoot:
        self._items[replay.run_id] = replay
        return replay

    async def get_by_run(self, run_id: str) -> ReplayRoot | None:
        return self._items.get(run_id)

    async def save(self, replay: ReplayRoot) -> ReplayRoot:
        self._items[replay.run_id] = replay
        return replay


__all__ = [
    "InMemoryArtifactRepository",
    "InMemoryReplayRepository",
    "InMemoryRunRepository",
    "InMemorySessionRepository",
    "InMemorySubTaskRepository",
    "InMemoryTaskRepository",
]
