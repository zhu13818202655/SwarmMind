"""Persistence layer for the FlyReport domain.

Provides a thin :class:`FlyReportRepository` protocol plus an in-memory
no-op stand-in and a PostgreSQL implementation built on the existing
:class:`swarmmind.repositories.postgres.PostgresStore`.

Three tables (DESIGN-2 §10.5.2 / §14.4.1):

- ``fly_report_session``     — durable record of a conversation
- ``fly_report_chat_turn``   — full turn-by-turn history
- ``fly_report_artifact``    — generated report files

The schema follows the JSONB-payload pattern already used by other
repositories (``payload`` mirrors a Pydantic-friendly dict, plus a few
indexed columns for filtering/searching).
"""

from __future__ import annotations

import json
from typing import Any, Protocol

from psycopg.types.json import Jsonb

from swarmmind.repositories.postgres import PostgresStore


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


FLY_REPORT_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS fly_report_session (
    id              TEXT PRIMARY KEY,
    tenant_id       TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    state           TEXT NOT NULL,
    title           TEXT,
    last_user_text  TEXT,
    revision        INTEGER NOT NULL DEFAULT 0,
    payload         JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS fly_report_session_user_idx
    ON fly_report_session (tenant_id, user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS fly_report_chat_turn (
    id              BIGSERIAL PRIMARY KEY,
    session_id      TEXT NOT NULL REFERENCES fly_report_session(id) ON DELETE CASCADE,
    role            TEXT NOT NULL,
    text            TEXT NOT NULL,
    payload         JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS fly_report_chat_turn_session_idx
    ON fly_report_chat_turn (session_id, id);

CREATE TABLE IF NOT EXISTS fly_report_artifact (
    id              BIGSERIAL PRIMARY KEY,
    session_id      TEXT NOT NULL REFERENCES fly_report_session(id) ON DELETE CASCADE,
    filename        TEXT NOT NULL,
    output_format   TEXT NOT NULL,
    template_ref    TEXT,
    artifact_path   TEXT NOT NULL,
    payload         JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS fly_report_artifact_session_idx
    ON fly_report_artifact (session_id, id);
CREATE UNIQUE INDEX IF NOT EXISTS fly_report_artifact_unique_filename_idx
    ON fly_report_artifact (session_id, filename);

CREATE TABLE IF NOT EXISTS fly_report_audit (
    id              BIGSERIAL PRIMARY KEY,
    session_id      TEXT NOT NULL,
    tenant_id       TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    decision        TEXT NOT NULL,
    reason          TEXT,
    scope_required  TEXT,
    payload         JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS fly_report_audit_session_idx
    ON fly_report_audit (session_id, id);
CREATE INDEX IF NOT EXISTS fly_report_audit_user_idx
    ON fly_report_audit (tenant_id, user_id, created_at DESC);
"""


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class FlyReportRepository(Protocol):
    """Durable storage for FlyReport sessions / turns / artifacts."""

    async def initialize(self) -> None: ...

    async def upsert_session(self, session: dict[str, Any]) -> None: ...

    async def get_session(self, session_id: str) -> dict[str, Any] | None: ...

    async def list_sessions_for_user(
        self, *, tenant_id: str, user_id: str, limit: int = 50
    ) -> list[dict[str, Any]]: ...

    async def append_turn(
        self, session_id: str, turn: dict[str, Any]
    ) -> None: ...

    async def list_turns(self, session_id: str) -> list[dict[str, Any]]: ...

    async def append_artifact(
        self, session_id: str, artifact: dict[str, Any]
    ) -> None: ...

    async def list_artifacts(self, session_id: str) -> list[dict[str, Any]]: ...

    async def append_audit(
        self, session_id: str, audit: dict[str, Any]
    ) -> None: ...

    async def list_audits(
        self, session_id: str, *, limit: int = 100
    ) -> list[dict[str, Any]]: ...


# ---------------------------------------------------------------------------
# In-memory no-op (used when persistence is disabled)
# ---------------------------------------------------------------------------


class InMemoryFlyReportRepository:
    """No-op repository — used when ``settings.postgres.enabled`` is false.

    The :class:`FlyReportService` keeps its own in-memory cache, so this
    repo simply swallows writes and returns empty reads.
    """

    async def initialize(self) -> None:
        return None

    async def upsert_session(self, session: dict[str, Any]) -> None:
        return None

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        return None

    async def list_sessions_for_user(
        self, *, tenant_id: str, user_id: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        return []

    async def append_turn(self, session_id: str, turn: dict[str, Any]) -> None:
        return None

    async def list_turns(self, session_id: str) -> list[dict[str, Any]]:
        return []

    async def append_artifact(
        self, session_id: str, artifact: dict[str, Any]
    ) -> None:
        return None

    async def list_artifacts(self, session_id: str) -> list[dict[str, Any]]:
        return []

    async def append_audit(
        self, session_id: str, audit: dict[str, Any]
    ) -> None:
        return None

    async def list_audits(
        self, session_id: str, *, limit: int = 100
    ) -> list[dict[str, Any]]:
        return []


# ---------------------------------------------------------------------------
# PostgreSQL implementation
# ---------------------------------------------------------------------------


def _jsonable(value: Any) -> Any:
    """Make sure datetimes / pydantic models survive JSONB encoding."""
    return json.loads(json.dumps(value, default=str, ensure_ascii=False))


class PostgresFlyReportRepository:
    """PG-backed implementation of :class:`FlyReportRepository`."""

    def __init__(self, store: PostgresStore) -> None:
        self._store = store

    async def initialize(self) -> None:
        """Apply / verify the FlyReport schema.

        Historical behaviour was to execute ``FLY_REPORT_SCHEMA_SQL`` directly
        with ``CREATE TABLE IF NOT EXISTS``. The platform now uses Alembic
        for schema management (see ``alembic/`` + ``swarmmind.repositories.
        migrations``), so this method runs ``alembic upgrade head`` instead
        — that single revision creates *both* the core and FlyReport tables.
        Repeated invocations are idempotent (Alembic compares the
        ``alembic_version`` table).
        """
        from swarmmind.repositories.migrations import upgrade_head

        await upgrade_head(getattr(self._store, "_dsn", None))

    # ---------------- sessions ----------------

    async def upsert_session(self, session: dict[str, Any]) -> None:
        payload = _jsonable(session)
        await self._store.execute(
            """
            INSERT INTO fly_report_session (
                id, tenant_id, user_id, state, title, last_user_text,
                revision, payload, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE
              SET state          = EXCLUDED.state,
                  title          = EXCLUDED.title,
                  last_user_text = EXCLUDED.last_user_text,
                  revision       = EXCLUDED.revision,
                  payload        = EXCLUDED.payload,
                  updated_at     = EXCLUDED.updated_at
            """,
            (
                session["id"],
                session["tenant_id"],
                session["user_id"],
                session["state"],
                session.get("title"),
                session.get("last_user_text"),
                int(session.get("revision", 0)),
                Jsonb(payload),
                session["created_at"],
                session["updated_at"],
            ),
        )

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        row = await self._store.fetch_one(
            "SELECT payload FROM fly_report_session WHERE id = %s",
            (session_id,),
        )
        return None if row is None else row["payload"]

    async def list_sessions_for_user(
        self, *, tenant_id: str, user_id: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        rows = await self._store.fetch_all(
            """
            SELECT id, state, title, last_user_text, revision,
                   created_at, updated_at
              FROM fly_report_session
             WHERE tenant_id = %s AND user_id = %s
             ORDER BY updated_at DESC
             LIMIT %s
            """,
            (tenant_id, user_id, limit),
        )
        return [
            {
                "session_id": r["id"],
                "state": r["state"],
                "title": r["title"],
                "last_user_text": r["last_user_text"],
                "revision": r["revision"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            }
            for r in rows
        ]

    # ---------------- turns ----------------

    async def append_turn(
        self, session_id: str, turn: dict[str, Any]
    ) -> None:
        await self._store.execute(
            """
            INSERT INTO fly_report_chat_turn
                (session_id, role, text, payload, created_at)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                session_id,
                turn["role"],
                turn["text"],
                Jsonb(_jsonable(turn["payload"])) if turn.get("payload") else None,
                turn["created_at"],
            ),
        )

    async def list_turns(self, session_id: str) -> list[dict[str, Any]]:
        rows = await self._store.fetch_all(
            """
            SELECT role, text, payload, created_at
              FROM fly_report_chat_turn
             WHERE session_id = %s
             ORDER BY id ASC
            """,
            (session_id,),
        )
        return list(rows)

    # ---------------- artifacts ----------------

    async def append_artifact(
        self, session_id: str, artifact: dict[str, Any]
    ) -> None:
        await self._store.execute(
            """
            INSERT INTO fly_report_artifact
                (session_id, filename, output_format, template_ref,
                 artifact_path, payload, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (session_id, filename) DO UPDATE
              SET output_format = EXCLUDED.output_format,
                  template_ref  = EXCLUDED.template_ref,
                  artifact_path = EXCLUDED.artifact_path,
                  payload       = EXCLUDED.payload
            """,
            (
                session_id,
                artifact["filename"],
                artifact["output_format"],
                artifact.get("template_ref"),
                artifact["artifact_path"],
                Jsonb(_jsonable(artifact)),
                artifact["created_at"],
            ),
        )

    async def list_artifacts(self, session_id: str) -> list[dict[str, Any]]:
        rows = await self._store.fetch_all(
            """
            SELECT payload
              FROM fly_report_artifact
             WHERE session_id = %s
             ORDER BY id ASC
            """,
            (session_id,),
        )
        return [r["payload"] for r in rows]

    # ---------------- audit ----------------

    async def append_audit(
        self, session_id: str, audit: dict[str, Any]
    ) -> None:
        await self._store.execute(
            """
            INSERT INTO fly_report_audit
                (session_id, tenant_id, user_id, decision, reason,
                 scope_required, payload, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                session_id,
                audit.get("tenant_id", ""),
                audit.get("user_id", ""),
                audit["decision"],
                audit.get("reason"),
                audit.get("scope_required"),
                Jsonb(_jsonable(audit.get("payload") or {})),
                audit.get("created_at"),
            ),
        )

    async def list_audits(
        self, session_id: str, *, limit: int = 100
    ) -> list[dict[str, Any]]:
        rows = await self._store.fetch_all(
            """
            SELECT decision, reason, scope_required, payload, created_at
              FROM fly_report_audit
             WHERE session_id = %s
             ORDER BY id ASC
             LIMIT %s
            """,
            (session_id, limit),
        )
        return list(rows)


__all__ = [
    "FLY_REPORT_SCHEMA_SQL",
    "FlyReportRepository",
    "InMemoryFlyReportRepository",
    "PostgresFlyReportRepository",
]
