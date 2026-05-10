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

CREATE TABLE IF NOT EXISTS fly_report_interaction (
    id              TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL REFERENCES fly_report_session(id) ON DELETE CASCADE,
    tenant_id       TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    status          TEXT NOT NULL,
    phase           TEXT NOT NULL DEFAULT 'intake',
    input_text      TEXT NOT NULL,
    output_format   TEXT,
    template_ref    TEXT,
    error           TEXT,
    message_count   INTEGER NOT NULL DEFAULT 0,
    artifact_count  INTEGER NOT NULL DEFAULT 0,
    payload         JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS fly_report_interaction_session_idx
    ON fly_report_interaction (session_id, created_at ASC);
CREATE INDEX IF NOT EXISTS fly_report_interaction_user_idx
    ON fly_report_interaction (tenant_id, user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS fly_report_interaction_status_idx
    ON fly_report_interaction (status, updated_at DESC);

CREATE TABLE IF NOT EXISTS fly_report_message (
    id              TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL REFERENCES fly_report_session(id) ON DELETE CASCADE,
    interaction_id  TEXT NOT NULL REFERENCES fly_report_interaction(id) ON DELETE CASCADE,
    tenant_id       TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    role            TEXT NOT NULL,
    message_type    TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'completed',
    title           TEXT,
    text            TEXT NOT NULL DEFAULT '',
    sequence        INTEGER NOT NULL,
    payload         JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS fly_report_message_session_idx
    ON fly_report_message (session_id, created_at ASC, sequence ASC);
CREATE INDEX IF NOT EXISTS fly_report_message_interaction_idx
    ON fly_report_message (interaction_id, sequence ASC);
CREATE INDEX IF NOT EXISTS fly_report_message_user_idx
    ON fly_report_message (tenant_id, user_id, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS fly_report_message_interaction_sequence_idx
    ON fly_report_message (interaction_id, sequence);

CREATE TABLE IF NOT EXISTS fly_report_artifact (
    id              BIGSERIAL PRIMARY KEY,
    session_id      TEXT NOT NULL REFERENCES fly_report_session(id) ON DELETE CASCADE,
    interaction_id  TEXT REFERENCES fly_report_interaction(id) ON DELETE SET NULL,
    filename        TEXT NOT NULL,
    output_format   TEXT NOT NULL,
    template_ref    TEXT,
    content_type    TEXT,
    artifact_path   TEXT NOT NULL,
    payload         JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS fly_report_artifact_session_idx
    ON fly_report_artifact (session_id, id);
CREATE INDEX IF NOT EXISTS fly_report_artifact_interaction_idx
    ON fly_report_artifact (interaction_id, id);
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
        self,
        *,
        tenant_id: str,
        user_id: str,
        limit: int | None = 50,
        keyword: str | None = None,
        state_filter: str | None = None,
        before_session_id: str | None = None,
    ) -> list[dict[str, Any]]: ...

    async def append_turn(
        self, session_id: str, turn: dict[str, Any]
    ) -> None: ...

    async def list_turns(self, session_id: str) -> list[dict[str, Any]]: ...

    async def upsert_interaction(
        self, interaction: dict[str, Any]
    ) -> None: ...

    async def get_interaction(
        self, interaction_id: str
    ) -> dict[str, Any] | None: ...

    async def append_message(self, message: dict[str, Any]) -> None: ...

    async def list_messages(
        self,
        session_id: str,
        *,
        user_id: str,
        limit: int = 100,
        before_message_id: str | None = None,
    ) -> list[dict[str, Any]]: ...

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
        self,
        *,
        tenant_id: str,
        user_id: str,
        limit: int | None = 50,
        keyword: str | None = None,
        state_filter: str | None = None,
        before_session_id: str | None = None,
    ) -> list[dict[str, Any]]:
        return []

    async def append_turn(self, session_id: str, turn: dict[str, Any]) -> None:
        return None

    async def list_turns(self, session_id: str) -> list[dict[str, Any]]:
        return []

    async def upsert_interaction(
        self, interaction: dict[str, Any]
    ) -> None:
        return None

    async def get_interaction(
        self, interaction_id: str
    ) -> dict[str, Any] | None:
        return None

    async def append_message(self, message: dict[str, Any]) -> None:
        return None

    async def list_messages(
        self,
        session_id: str,
        *,
        user_id: str,
        limit: int = 100,
        before_message_id: str | None = None,
    ) -> list[dict[str, Any]]:
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
        self,
        *,
        tenant_id: str,
        user_id: str,
        limit: int | None = 50,
        keyword: str | None = None,
        state_filter: str | None = None,
        before_session_id: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses = ["tenant_id = %s", "user_id = %s"]
        params: list[Any] = [tenant_id, user_id]
        if state_filter:
            clauses.append("state = %s")
            params.append(state_filter)
        if keyword:
            clauses.append(
                "LOWER(COALESCE(title, '') || ' ' || COALESCE(last_user_text, '')) LIKE %s"
            )
            params.append(f"%{keyword.lower()}%")
        if before_session_id:
            clauses.append(
                """
                (updated_at, id) < (
                    SELECT updated_at, id
                      FROM fly_report_session
                     WHERE tenant_id = %s AND user_id = %s AND id = %s
                )
                """
            )
            params.extend([tenant_id, user_id, before_session_id])
        query = f"""
            SELECT id, state, title, last_user_text, revision,
                   created_at, updated_at
              FROM fly_report_session
             WHERE {' AND '.join(clauses)}
             ORDER BY updated_at DESC, id DESC
        """
        if limit is not None:
            query += " LIMIT %s"
            params.append(limit)
        rows = await self._store.fetch_all(query, tuple(params))
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

    # ---------------- interactions / messages ----------------

    async def upsert_interaction(
        self, interaction: dict[str, Any]
    ) -> None:
        await self._store.execute(
            """
            INSERT INTO fly_report_interaction (
                id, session_id, tenant_id, user_id, status, phase,
                input_text, output_format, template_ref, error,
                message_count, artifact_count, payload, created_at,
                started_at, completed_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE
              SET status         = EXCLUDED.status,
                  phase          = EXCLUDED.phase,
                  error          = EXCLUDED.error,
                  message_count  = EXCLUDED.message_count,
                  artifact_count = EXCLUDED.artifact_count,
                  payload        = EXCLUDED.payload,
                  started_at     = EXCLUDED.started_at,
                  completed_at   = EXCLUDED.completed_at,
                  updated_at     = EXCLUDED.updated_at
            """,
            (
                interaction["id"],
                interaction["session_id"],
                interaction["tenant_id"],
                interaction["user_id"],
                interaction["status"],
                interaction.get("phase", "intake"),
                interaction["input_text"],
                interaction.get("output_format"),
                interaction.get("template_ref"),
                interaction.get("error"),
                int(interaction.get("message_count", 0)),
                int(interaction.get("artifact_count", 0)),
                Jsonb(_jsonable(interaction.get("payload") or {})),
                interaction["created_at"],
                interaction.get("started_at"),
                interaction.get("completed_at"),
                interaction["updated_at"],
            ),
        )

    async def get_interaction(
        self, interaction_id: str
    ) -> dict[str, Any] | None:
        row = await self._store.fetch_one(
            """
            SELECT id, session_id, tenant_id, user_id, status, phase,
                   input_text, output_format, template_ref, error,
                   message_count, artifact_count, payload, created_at,
                   started_at, completed_at, updated_at
              FROM fly_report_interaction
             WHERE id = %s
            """,
            (interaction_id,),
        )
        return None if row is None else dict(row)

    async def append_message(self, message: dict[str, Any]) -> None:
        await self._store.execute(
            """
            INSERT INTO fly_report_message (
                id, session_id, interaction_id, tenant_id, user_id,
                role, message_type, status, title, text, sequence,
                payload, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE
              SET status     = EXCLUDED.status,
                  title      = EXCLUDED.title,
                  text       = EXCLUDED.text,
                  payload    = EXCLUDED.payload,
                  updated_at = EXCLUDED.updated_at
            """,
            (
                message["id"],
                message["session_id"],
                message["interaction_id"],
                message["tenant_id"],
                message["user_id"],
                message["role"],
                message["message_type"],
                message.get("status", "completed"),
                message.get("title"),
                message.get("text", ""),
                int(message["sequence"]),
                Jsonb(_jsonable(message.get("payload") or {})),
                message["created_at"],
                message["updated_at"],
            ),
        )

    async def list_messages(
        self,
        session_id: str,
        *,
        user_id: str,
        limit: int = 100,
        before_message_id: str | None = None,
    ) -> list[dict[str, Any]]:
        params: list[Any] = [session_id, user_id]
        before_clause = ""
        if before_message_id:
            before_clause = """
              AND created_at < (
                    SELECT created_at FROM fly_report_message WHERE id = %s
                  )
            """
            params.append(before_message_id)
        params.append(limit)
        rows = await self._store.fetch_all(
            f"""
            SELECT id, session_id, interaction_id, tenant_id, user_id,
                   role, message_type, status, title, text, sequence,
                   payload, created_at, updated_at
              FROM fly_report_message
             WHERE session_id = %s AND user_id = %s
             {before_clause}
             ORDER BY created_at ASC, sequence ASC
             LIMIT %s
            """,
            tuple(params),
        )
        return [dict(r) for r in rows]

    # ---------------- artifacts ----------------

    async def append_artifact(
        self, session_id: str, artifact: dict[str, Any]
    ) -> None:
        await self._store.execute(
            """
            INSERT INTO fly_report_artifact
                (session_id, interaction_id, filename, output_format,
                 template_ref, content_type, artifact_path, payload, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (session_id, filename) DO UPDATE
              SET output_format = EXCLUDED.output_format,
                                    interaction_id = EXCLUDED.interaction_id,
                  template_ref  = EXCLUDED.template_ref,
                                    content_type   = EXCLUDED.content_type,
                  artifact_path = EXCLUDED.artifact_path,
                  payload       = EXCLUDED.payload
            """,
            (
                session_id,
                artifact.get("interaction_id"),
                artifact["filename"],
                artifact["output_format"],
                artifact.get("template_ref"),
                artifact.get("content_type"),
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
