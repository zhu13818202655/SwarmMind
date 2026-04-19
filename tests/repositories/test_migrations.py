"""Alembic schema-migration tests."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DUMMY_DSN = "postgresql+psycopg://u:p@127.0.0.1:5432/db"


def test_alembic_offline_upgrade_emits_full_schema() -> None:
    """``alembic upgrade --sql head`` should emit DDL for every table."""
    result = subprocess.run(
        [
            "alembic",
            "-x",
            f"url={DUMMY_DSN}",
            "upgrade",
            "head",
            "--sql",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    sql = result.stdout
    expected_tables = [
        "tasks",
        "sessions",
        "runs",
        "subtasks",
        "artifacts",
        "replays",
        "fly_report_session",
        "fly_report_chat_turn",
        "fly_report_artifact",
        "fly_report_audit",
        "alembic_version",
    ]
    for name in expected_tables:
        assert f"CREATE TABLE" in sql and name in sql, (
            f"missing {name!r} in offline SQL"
        )


def test_migrations_helper_imports_clean() -> None:
    from swarmmind.repositories import migrations

    assert migrations.ALEMBIC_INI_PATH.is_file()
    assert (migrations.ALEMBIC_SCRIPT_LOCATION / "env.py").is_file()
    assert callable(migrations.upgrade_head)
    assert callable(migrations.upgrade_head_sync)
    assert callable(migrations.current_revision)


@pytest.mark.skipif(
    not os.environ.get("SWARMMIND_FLY_REPORT_PG_DSN"),
    reason="SWARMMIND_FLY_REPORT_PG_DSN not set",
)
def test_alembic_live_upgrade_round_trip() -> None:
    """upgrade head → assert revision → upgrade head again is a no-op."""
    from swarmmind.repositories.migrations import (
        current_revision_sync,
        upgrade_head_sync,
    )

    dsn = os.environ["SWARMMIND_FLY_REPORT_PG_DSN"]
    upgrade_head_sync(dsn)
    rev = current_revision_sync(dsn)
    assert rev == "20260420_0001_baseline"

    # second invocation must be idempotent (no-op)
    upgrade_head_sync(dsn)
    assert current_revision_sync(dsn) == "20260420_0001_baseline"
