"""Baseline schema for SwarmMind core + FlyReport tables.

Revision ID: 20260420_0001_baseline
Revises:
Create Date: 2026-04-20

This single revision captures the schema that previously lived in:
- ``swarmmind.repositories.postgres.SCHEMA_SQL``
- ``swarmmind.domains.fly_report.repository.FLY_REPORT_SCHEMA_SQL``

All ``CREATE`` statements use ``IF NOT EXISTS`` so the migration can be
applied to a database that was already bootstrapped by the legacy
``auto_init_schema=True`` path. The downgrade drops every object created
here (destructive — only intended for tests / fresh dev databases).
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "20260420_0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

CORE_DDL = """
CREATE TABLE IF NOT EXISTS tasks (
    id      TEXT PRIMARY KEY,
    status  TEXT NOT NULL,
    payload JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id        TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    actor_id  TEXT NOT NULL,
    payload   JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id         TEXT PRIMARY KEY,
    task_id    TEXT NOT NULL,
    session_id TEXT NOT NULL,
    status     TEXT NOT NULL,
    phase      TEXT NOT NULL,
    payload    JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS runs_task_id_idx ON runs(task_id);

CREATE TABLE IF NOT EXISTS subtasks (
    id      TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    run_id  TEXT,
    status  TEXT NOT NULL,
    payload JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS subtasks_task_id_idx ON subtasks(task_id);
CREATE INDEX IF NOT EXISTS subtasks_run_id_idx  ON subtasks(run_id);

CREATE TABLE IF NOT EXISTS artifacts (
    id         TEXT PRIMARY KEY,
    task_id    TEXT NOT NULL,
    run_id     TEXT NOT NULL,
    subtask_id TEXT,
    type       TEXT NOT NULL,
    payload    JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS artifacts_run_id_idx ON artifacts(run_id);

CREATE TABLE IF NOT EXISTS replays (
    run_id  TEXT PRIMARY KEY,
    id      TEXT NOT NULL,
    task_id TEXT NOT NULL,
    payload JSONB NOT NULL
);
"""


FLY_REPORT_DDL = """
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
    id         BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES fly_report_session(id) ON DELETE CASCADE,
    role       TEXT NOT NULL,
    text       TEXT NOT NULL,
    payload    JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS fly_report_chat_turn_session_idx
    ON fly_report_chat_turn (session_id, id);

CREATE TABLE IF NOT EXISTS fly_report_artifact (
    id            BIGSERIAL PRIMARY KEY,
    session_id    TEXT NOT NULL REFERENCES fly_report_session(id) ON DELETE CASCADE,
    filename      TEXT NOT NULL,
    output_format TEXT NOT NULL,
    template_ref  TEXT,
    artifact_path TEXT NOT NULL,
    payload       JSONB NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS fly_report_artifact_session_idx
    ON fly_report_artifact (session_id, id);
CREATE UNIQUE INDEX IF NOT EXISTS fly_report_artifact_unique_filename_idx
    ON fly_report_artifact (session_id, filename);

CREATE TABLE IF NOT EXISTS fly_report_audit (
    id             BIGSERIAL PRIMARY KEY,
    session_id     TEXT NOT NULL,
    tenant_id      TEXT NOT NULL,
    user_id        TEXT NOT NULL,
    decision       TEXT NOT NULL,
    reason         TEXT,
    scope_required TEXT,
    payload        JSONB,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS fly_report_audit_session_idx
    ON fly_report_audit (session_id, id);
CREATE INDEX IF NOT EXISTS fly_report_audit_user_idx
    ON fly_report_audit (tenant_id, user_id, created_at DESC);
"""


_DROP_DDL = """
DROP TABLE IF EXISTS fly_report_audit;
DROP TABLE IF EXISTS fly_report_artifact;
DROP TABLE IF EXISTS fly_report_chat_turn;
DROP TABLE IF EXISTS fly_report_session;
DROP TABLE IF EXISTS replays;
DROP TABLE IF EXISTS artifacts;
DROP TABLE IF EXISTS subtasks;
DROP TABLE IF EXISTS runs;
DROP TABLE IF EXISTS sessions;
DROP TABLE IF EXISTS tasks;
"""


def upgrade() -> None:
    op.execute(CORE_DDL)
    op.execute(FLY_REPORT_DDL)


def downgrade() -> None:
    op.execute(_DROP_DDL)
