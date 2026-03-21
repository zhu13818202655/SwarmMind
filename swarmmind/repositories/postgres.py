"""PostgreSQL-backed repository implementations."""

from __future__ import annotations

from typing import Any, TypeVar

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import BaseModel

from swarmmind.models.artifact import Artifact
from swarmmind.models.replay import ReplayRoot
from swarmmind.models.run import Run
from swarmmind.models.session import Session
from swarmmind.models.task import SubTask, Task, TaskStatus


ModelT = TypeVar("ModelT", bound=BaseModel)


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    payload JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    payload JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    status TEXT NOT NULL,
    phase TEXT NOT NULL,
    payload JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS runs_task_id_idx ON runs(task_id);

CREATE TABLE IF NOT EXISTS subtasks (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    run_id TEXT,
    status TEXT NOT NULL,
    payload JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS subtasks_task_id_idx ON subtasks(task_id);
CREATE INDEX IF NOT EXISTS subtasks_run_id_idx ON subtasks(run_id);

CREATE TABLE IF NOT EXISTS artifacts (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    subtask_id TEXT,
    type TEXT NOT NULL,
    payload JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS artifacts_run_id_idx ON artifacts(run_id);

CREATE TABLE IF NOT EXISTS replays (
    run_id TEXT PRIMARY KEY,
    id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    payload JSONB NOT NULL
);
"""


class PostgresStore:
    """Shared PostgreSQL storage helper."""

    def __init__(self, dsn: str):
        self._dsn = dsn

    async def initialize(self) -> None:
        async with await self._connect() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(SCHEMA_SQL)
            await connection.commit()

    async def fetch_one(self, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        async with await self._connect() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(query, params)
                return await cursor.fetchone()

    async def fetch_all(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        async with await self._connect() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(query, params)
                return list(await cursor.fetchall())

    async def execute(self, query: str, params: tuple[Any, ...] = ()) -> None:
        async with await self._connect() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(query, params)
            await connection.commit()

    async def _connect(self) -> AsyncConnection[Any]:
        return await AsyncConnection.connect(self._dsn, row_factory=dict_row)


def _dump(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json")


def _load(model_type: type[ModelT], row: dict[str, Any] | None) -> ModelT | None:
    if row is None:
        return None
    return model_type.model_validate(row["payload"])


class PostgresTaskRepository:
    """PostgreSQL task repository."""

    def __init__(self, store: PostgresStore):
        self._store = store

    async def create(self, task: Task) -> Task:
        return await self.save(task)

    async def get(self, task_id: str) -> Task | None:
        row = await self._store.fetch_one("SELECT payload FROM tasks WHERE id = %s", (task_id,))
        return _load(Task, row)

    async def save(self, task: Task) -> Task:
        await self._store.execute(
            """
            INSERT INTO tasks (id, status, payload)
            VALUES (%s, %s, %s)
            ON CONFLICT (id) DO UPDATE
            SET status = EXCLUDED.status, payload = EXCLUDED.payload
            """,
            (task.id, task.status.value, Jsonb(_dump(task))),
        )
        return task

    async def list_by_status(self, status: TaskStatus | None = None) -> list[Task]:
        if status is None:
            rows = await self._store.fetch_all("SELECT payload FROM tasks ORDER BY id")
        else:
            rows = await self._store.fetch_all(
                "SELECT payload FROM tasks WHERE status = %s ORDER BY id",
                (status.value,),
            )
        return [Task.model_validate(row["payload"]) for row in rows]


class PostgresSessionRepository:
    """PostgreSQL session repository."""

    def __init__(self, store: PostgresStore):
        self._store = store

    async def create(self, session: Session) -> Session:
        return await self.save(session)

    async def get(self, session_id: str) -> Session | None:
        row = await self._store.fetch_one("SELECT payload FROM sessions WHERE id = %s", (session_id,))
        return _load(Session, row)

    async def save(self, session: Session) -> Session:
        await self._store.execute(
            """
            INSERT INTO sessions (id, tenant_id, actor_id, payload)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE
            SET tenant_id = EXCLUDED.tenant_id,
                actor_id = EXCLUDED.actor_id,
                payload = EXCLUDED.payload
            """,
            (session.id, session.tenant_id, session.actor_id, Jsonb(_dump(session))),
        )
        return session


class PostgresRunRepository:
    """PostgreSQL run repository."""

    def __init__(self, store: PostgresStore):
        self._store = store

    async def create(self, run: Run) -> Run:
        return await self.save(run)

    async def get(self, run_id: str) -> Run | None:
        row = await self._store.fetch_one("SELECT payload FROM runs WHERE id = %s", (run_id,))
        return _load(Run, row)

    async def save(self, run: Run) -> Run:
        await self._store.execute(
            """
            INSERT INTO runs (id, task_id, session_id, status, phase, payload)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE
            SET task_id = EXCLUDED.task_id,
                session_id = EXCLUDED.session_id,
                status = EXCLUDED.status,
                phase = EXCLUDED.phase,
                payload = EXCLUDED.payload
            """,
            (run.id, run.task_id, run.session_id, run.status.value, run.phase.value, Jsonb(_dump(run))),
        )
        return run

    async def list_for_task(self, task_id: str) -> list[Run]:
        rows = await self._store.fetch_all(
            "SELECT payload FROM runs WHERE task_id = %s ORDER BY id",
            (task_id,),
        )
        return [Run.model_validate(row["payload"]) for row in rows]


class PostgresSubTaskRepository:
    """PostgreSQL subtask repository."""

    def __init__(self, store: PostgresStore):
        self._store = store

    async def create_many(self, subtasks: list[SubTask]) -> list[SubTask]:
        for subtask in subtasks:
            await self.save(subtask)
        return subtasks

    async def save(self, subtask: SubTask) -> SubTask:
        await self._store.execute(
            """
            INSERT INTO subtasks (id, task_id, run_id, status, payload)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE
            SET task_id = EXCLUDED.task_id,
                run_id = EXCLUDED.run_id,
                status = EXCLUDED.status,
                payload = EXCLUDED.payload
            """,
            (
                subtask.id,
                subtask.task_id,
                subtask.metadata.get("run_id"),
                subtask.status.value,
                Jsonb(_dump(subtask)),
            ),
        )
        return subtask

    async def get(self, subtask_id: str) -> SubTask | None:
        row = await self._store.fetch_one("SELECT payload FROM subtasks WHERE id = %s", (subtask_id,))
        return _load(SubTask, row)

    async def list_for_task(self, task_id: str) -> list[SubTask]:
        rows = await self._store.fetch_all(
            "SELECT payload FROM subtasks WHERE task_id = %s ORDER BY id",
            (task_id,),
        )
        return [SubTask.model_validate(row["payload"]) for row in rows]

    async def list_for_run(self, run_id: str) -> list[SubTask]:
        rows = await self._store.fetch_all(
            "SELECT payload FROM subtasks WHERE run_id = %s ORDER BY id",
            (run_id,),
        )
        return [SubTask.model_validate(row["payload"]) for row in rows]


class PostgresArtifactRepository:
    """PostgreSQL artifact repository."""

    def __init__(self, store: PostgresStore):
        self._store = store

    async def create(self, artifact: Artifact) -> Artifact:
        await self._store.execute(
            """
            INSERT INTO artifacts (id, task_id, run_id, subtask_id, type, payload)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE
            SET task_id = EXCLUDED.task_id,
                run_id = EXCLUDED.run_id,
                subtask_id = EXCLUDED.subtask_id,
                type = EXCLUDED.type,
                payload = EXCLUDED.payload
            """,
            (
                artifact.id,
                artifact.task_id,
                artifact.run_id,
                artifact.subtask_id,
                artifact.type.value,
                Jsonb(_dump(artifact)),
            ),
        )
        return artifact

    async def list_for_run(self, run_id: str) -> list[Artifact]:
        rows = await self._store.fetch_all(
            "SELECT payload FROM artifacts WHERE run_id = %s ORDER BY id",
            (run_id,),
        )
        return [Artifact.model_validate(row["payload"]) for row in rows]


class PostgresReplayRepository:
    """PostgreSQL replay repository."""

    def __init__(self, store: PostgresStore):
        self._store = store

    async def create(self, replay: ReplayRoot) -> ReplayRoot:
        return await self.save(replay)

    async def get_by_run(self, run_id: str) -> ReplayRoot | None:
        row = await self._store.fetch_one("SELECT payload FROM replays WHERE run_id = %s", (run_id,))
        return _load(ReplayRoot, row)

    async def save(self, replay: ReplayRoot) -> ReplayRoot:
        await self._store.execute(
            """
            INSERT INTO replays (run_id, id, task_id, payload)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (run_id) DO UPDATE
            SET id = EXCLUDED.id,
                task_id = EXCLUDED.task_id,
                payload = EXCLUDED.payload
            """,
            (replay.run_id, replay.id, replay.task_id, Jsonb(_dump(replay))),
        )
        return replay


__all__ = [
    "PostgresArtifactRepository",
    "PostgresReplayRepository",
    "PostgresRunRepository",
    "PostgresSessionRepository",
    "PostgresStore",
    "PostgresSubTaskRepository",
    "PostgresTaskRepository",
]