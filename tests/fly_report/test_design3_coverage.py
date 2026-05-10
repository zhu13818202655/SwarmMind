"""Tests for DESIGN-3 §2.3 / §2.8 / §2.9 additions.

Covers:
- R3.1 history list keyword/state filter
- R3.2 clarify_round limit + guidance fallback
- R3.4 cleanup_old_sessions
- R8.1 fly_report.* event emission
- R8.2 FlyReportMetrics stage observations
- R9.1 input length enforcement
- R9.2 render timeout surfacing as FAILED
- R9.3 artifact path-traversal fuzz
"""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from swarmmind.domains.fly_report import FlyReportService
from swarmmind.domains.fly_report.errors import (
    InvalidStateTransition,
)
from swarmmind.domains.fly_report.observability import FlyReportMetrics
from swarmmind.domains.fly_report.schemas import DraftFilterSpec, SessionState
from swarmmind.events.in_memory_bus import InMemoryEventBus
from tests.fly_report.service_test_utils import build_fly_report_service

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


class _AmbiguousIntentParser:
    """Always produces a draft that triggers clarify (no period/indicators)."""

    async def parse(self, user_text: str, **_: Any) -> DraftFilterSpec:
        return DraftFilterSpec()


@pytest.fixture
def service(tmp_path: Path) -> FlyReportService:
    return build_fly_report_service(
        output_root=tmp_path,
        event_bus=InMemoryEventBus(),
        metrics=FlyReportMetrics(),
    )


# ---------------------------------------------------------------------------
# R9.1 input limits
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_message_rejects_empty_text(service: FlyReportService) -> None:
    sid = await service.start_session(tenant_id="t", user_id="u")
    with pytest.raises(InvalidStateTransition):
        await service.send_message(sid, "   ", user_id="u")


@pytest.mark.asyncio
async def test_send_message_rejects_too_long_text(tmp_path: Path) -> None:
    svc = build_fly_report_service(output_root=tmp_path, max_text_length=16)
    sid = await svc.start_session(tenant_id="t", user_id="u")
    with pytest.raises(InvalidStateTransition, match="exceeds max"):
        await svc.send_message(sid, "x" * 32, user_id="u")


# ---------------------------------------------------------------------------
# R8.1 / R8.2 events + metrics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_emits_fly_report_events_and_metrics(
    service: FlyReportService,
) -> None:
    sid = await service.start_session(
        tenant_id="t", user_id="u", initial_query="本周飞行报告"
    )
    bus = service._event_bus  # type: ignore[attr-defined]
    topics = {ev.topic for ev in bus.list_events()}
    assert "fly_report.intent_parsed" in topics
    assert "fly_report.data_fetched" in topics
    assert "fly_report.analyzed" in topics
    assert "fly_report.previewed" in topics
    # Every event has the session id populated.
    for ev in bus.list_events():
        if ev.topic.startswith("fly_report."):
            assert ev.session_id == sid

    metrics = service.metrics.snapshot()
    for stage in ("parsing", "fetching", "analyzing", "previewing"):
        assert metrics["stage_counts"].get(stage, 0) >= 1


@pytest.mark.asyncio
async def test_confirm_records_render_success_metric(
    service: FlyReportService,
) -> None:
    sid = await service.start_session(
        tenant_id="t", user_id="u", initial_query="本周飞行报告"
    )
    await service.confirm(sid, user_id="u", output_format="markdown")
    snap = service.metrics.snapshot()
    assert snap["render_success"] == 1
    assert snap["render_failure"] == 0
    bus = service._event_bus  # type: ignore[attr-defined]
    assert any(
        ev.topic == "fly_report.generated" for ev in bus.list_events()
    )


# ---------------------------------------------------------------------------
# R9.2 render timeout
# ---------------------------------------------------------------------------


class _SlowRouter:
    def render_markdown_to_docx(self, *args: Any, **kwargs: Any) -> Any:
        time.sleep(0.5)
        raise AssertionError("should have timed out")


@pytest.mark.asyncio
async def test_render_timeout_marks_session_failed(tmp_path: Path) -> None:
    svc = build_fly_report_service(
        output_root=tmp_path,
        renderer_router=_SlowRouter(),  # type: ignore[arg-type]
        render_timeout_seconds=0.05,
    )
    sid = await svc.start_session(
        tenant_id="t", user_id="u", initial_query="本周飞行报告"
    )
    with pytest.raises((Exception,)):
        await svc.confirm(sid, user_id="u", output_format="docx")
    snap = await svc.get_session_snapshot(sid, user_id="u")
    assert snap["state"] == SessionState.FAILED.value
    assert svc.metrics.snapshot()["render_failure"] == 1


# ---------------------------------------------------------------------------
# R3.2 clarify round limit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clarify_round_limit_returns_guidance(tmp_path: Path) -> None:
    svc = build_fly_report_service(
        output_root=tmp_path,
        intent_parser=_AmbiguousIntentParser(),
        max_clarify_rounds=2,
    )
    sid = await svc.start_session(tenant_id="t", user_id="u")
    t1 = await svc.send_message(sid, "帮我生成个报告", user_id="u")
    assert t1.payload["clarify_round"] == 1
    assert t1.payload["clarify_exhausted"] is False
    t2 = await svc.send_message(sid, "再帮我生成", user_id="u")
    assert t2.payload["clarify_round"] == 2
    assert t2.payload["clarify_exhausted"] is True
    assert "请参考以下示例" in t2.text


# ---------------------------------------------------------------------------
# R3.1 history filter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_user_sessions_keyword_and_state_filter(
    service: FlyReportService,
) -> None:
    s1 = await service.start_session(
        tenant_id="t", user_id="u", initial_query="本周飞行报告"
    )
    s2 = await service.start_session(
        tenant_id="t", user_id="u", initial_query="本月媒体统计"
    )
    # Keyword match
    payload = await service.list_user_sessions(
        tenant_id="t", user_id="u", keyword="媒体"
    )
    rows = payload["items"]
    assert {r["session_id"] for r in rows} == {s2}
    # State filter (both should be previewing after initial_query)
    payload_state = await service.list_user_sessions(
        tenant_id="t",
        user_id="u",
        state_filter=SessionState.PREVIEWING.value,
    )
    rows_state = payload_state["items"]
    assert {r["session_id"] for r in rows_state} >= {s1, s2}
    payload_none = await service.list_user_sessions(
        tenant_id="t", user_id="u", state_filter="archived"
    )
    rows_none = payload_none["items"]
    assert rows_none == []


# ---------------------------------------------------------------------------
# R3.4 cleanup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cleanup_old_sessions_removes_stale_dirs(tmp_path: Path) -> None:
    svc = build_fly_report_service(output_root=tmp_path)
    # Create 2 directories: one fresh, one aged.
    old = tmp_path / "old-session"
    old.mkdir()
    fresh = tmp_path / "fresh-session"
    fresh.mkdir()
    # Backdate the mtime on `old`.
    very_old = (datetime.now(UTC) - timedelta(days=60)).timestamp()
    os.utime(old, (very_old, very_old))

    result = await svc.cleanup_old_sessions(max_age_days=30)
    assert result["removed_dirs"] == 1
    assert not old.exists()
    assert fresh.exists()


# ---------------------------------------------------------------------------
# R9.3 path traversal fuzz
# ---------------------------------------------------------------------------


TRAVERSAL_VECTORS = [
    "../etc/passwd",
    "..\\etc\\passwd",
    "/etc/passwd",
    "\\windows\\system32",
    ".",
    "..",
    "",
    "foo/../../bar",
    "foo\x00.docx",
]


@pytest.mark.asyncio
@pytest.mark.parametrize("filename", TRAVERSAL_VECTORS)
async def test_get_artifact_path_rejects_traversal(
    service: FlyReportService, filename: str
) -> None:
    sid = await service.start_session(
        tenant_id="t", user_id="u", initial_query="本周飞行报告"
    )
    with pytest.raises(FileNotFoundError):
        await service.get_artifact_path(sid, filename, user_id="u")
