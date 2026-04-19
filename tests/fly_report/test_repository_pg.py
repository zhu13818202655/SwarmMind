"""Live PG round-trip for the FlyReport repository.

Skipped unless ``SWARMMIND_FLY_REPORT_PG_DSN`` is set, e.g.::

    SWARMMIND_FLY_REPORT_PG_DSN=postgresql://swarmmind:swarmmind@127.0.0.1:2360/swarmmind \\
        pytest tests/fly_report/test_repository_pg.py -x
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

import pytest

DSN = os.environ.get("SWARMMIND_FLY_REPORT_PG_DSN")

pytestmark = pytest.mark.skipif(
    not DSN, reason="SWARMMIND_FLY_REPORT_PG_DSN not set"
)


@pytest.mark.asyncio
async def test_postgres_fly_report_repository_roundtrip() -> None:
    from swarmmind.domains.fly_report.repository import (
        PostgresFlyReportRepository,
    )
    from swarmmind.repositories.postgres import PostgresStore

    repo = PostgresFlyReportRepository(PostgresStore(DSN))
    await repo.initialize()

    sid = str(uuid.uuid4())
    now = datetime.now(UTC)
    await repo.upsert_session(
        {
            "id": sid,
            "tenant_id": "t1",
            "user_id": "u1",
            "state": "parsing",
            "title": "test",
            "last_user_text": "hi",
            "revision": 0,
            "created_at": now,
            "updated_at": now,
            "filter_spec": {},
            "state_history": [],
            "turn_count": 0,
            "artifacts": [],
        }
    )
    snap = await repo.get_session(sid)
    assert snap is not None
    assert snap["user_id"] == "u1"

    await repo.append_turn(
        sid,
        {
            "role": "user",
            "text": "hello",
            "payload": {"k": 1},
            "created_at": now,
        },
    )
    turns = await repo.list_turns(sid)
    assert len(turns) == 1
    assert turns[0]["text"] == "hello"

    await repo.append_artifact(
        sid,
        {
            "filename": "demo.md",
            "output_format": "markdown",
            "template_ref": "default",
            "artifact_path": "/tmp/demo.md",
            "created_at": now,
        },
    )
    artifacts = await repo.list_artifacts(sid)
    assert len(artifacts) == 1
    assert artifacts[0]["filename"] == "demo.md"

    listed = await repo.list_sessions_for_user(tenant_id="t1", user_id="u1")
    assert any(s["session_id"] == sid for s in listed)
