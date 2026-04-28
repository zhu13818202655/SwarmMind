"""Add FlyReport streaming interactions and messages.

Revision ID: 20260427_0002_fly_stream
Revises: 20260420_0001_baseline
Create Date: 2026-04-27
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "20260427_0002_fly_stream"
down_revision: Union[str, None] = "20260420_0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_DDL = """
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

ALTER TABLE fly_report_artifact
    ADD COLUMN IF NOT EXISTS interaction_id TEXT;
ALTER TABLE fly_report_artifact
    ADD COLUMN IF NOT EXISTS content_type TEXT;
CREATE INDEX IF NOT EXISTS fly_report_artifact_interaction_idx
    ON fly_report_artifact (interaction_id, id);
"""


DOWNGRADE_DDL = """
DROP INDEX IF EXISTS fly_report_artifact_interaction_idx;
ALTER TABLE fly_report_artifact DROP COLUMN IF EXISTS content_type;
ALTER TABLE fly_report_artifact DROP COLUMN IF EXISTS interaction_id;
DROP TABLE IF EXISTS fly_report_message;
DROP TABLE IF EXISTS fly_report_interaction;
"""


def upgrade() -> None:
    op.execute(UPGRADE_DDL)


def downgrade() -> None:
    op.execute(DOWNGRADE_DDL)
