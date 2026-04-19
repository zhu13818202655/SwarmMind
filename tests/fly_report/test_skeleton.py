"""Skeleton-level smoke tests for the FlyReport domain (Step 1).

These tests intentionally do **not** call any LLM, dikong API or renderer.
They only verify that the package imports cleanly, the schemas validate as
expected, and the in-memory service stub keeps a consistent state.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from swarmmind.domains.fly_report import FlyReportService
from swarmmind.domains.fly_report.errors import (
    InvalidStateTransition,
    SessionNotFound,
)
from swarmmind.domains.fly_report.schemas import (
    Dimension,
    FilterSpec,
    NormalizedFilter,
    Period,
    ReportOptions,
    SessionState,
)
from swarmmind.domains.fly_report.state_machine import (
    assert_transition,
    can_transition,
    is_terminal,
)
from swarmmind.prompt_template.fly_report import (
    CLARIFY_SYSTEM_PROMPT,
    FOLLOWUP_PATCH_SYSTEM_PROMPT,
    INTENT_PARSE_SYSTEM_PROMPT,
)


def test_load_prompts() -> None:
    for tmpl in (
        INTENT_PARSE_SYSTEM_PROMPT,
        CLARIFY_SYSTEM_PROMPT,
        FOLLOWUP_PATCH_SYSTEM_PROMPT,
    ):
        assert tmpl.template.strip(), f"prompt {tmpl.name} should not be empty"


def test_normalized_filter_hash_is_deterministic() -> None:
    period = Period(
        kind="weekly",
        start=datetime(2026, 4, 6),
        end=datetime(2026, 4, 12),
        label="2026年第15周",
    )
    spec = FilterSpec(
        period=period,
        dimension=Dimension(scope="overall"),
        indicators=["flight"],
        options=ReportOptions(),
    )
    a = NormalizedFilter.from_filter(spec)
    b = NormalizedFilter.from_filter(spec)
    assert a.hash == b.hash
    assert len(a.hash) == 64  # sha256 hex


def test_normalized_filter_requires_period_and_indicators() -> None:
    with pytest.raises(ValueError):
        NormalizedFilter.from_filter(FilterSpec(indicators=["flight"]))
    with pytest.raises(ValueError):
        NormalizedFilter.from_filter(
            FilterSpec(
                period=Period(
                    kind="weekly",
                    start=datetime.utcnow(),
                    end=datetime.utcnow() + timedelta(days=7),
                    label="x",
                ),
            )
        )


def test_state_machine_allows_documented_path() -> None:
    path = [
        SessionState.PARSING,
        SessionState.AUTHORIZING,
        SessionState.FETCHING,
        SessionState.ANALYZING,
        SessionState.PREVIEWING,
        SessionState.RENDERING,
        SessionState.ARCHIVED,
    ]
    for src, dst in zip(path, path[1:]):
        assert can_transition(src, dst), f"{src} -> {dst} should be allowed"
        assert_transition(src, dst)
    assert is_terminal(SessionState.ARCHIVED)


def test_state_machine_rejects_illegal_jump() -> None:
    with pytest.raises(InvalidStateTransition):
        assert_transition(SessionState.PARSING, SessionState.RENDERING)


def test_failed_state_reachable_from_active_states() -> None:
    for state in (
        SessionState.PARSING,
        SessionState.FETCHING,
        SessionState.PREVIEWING,
    ):
        assert can_transition(state, SessionState.FAILED)
    # but not from terminal states
    assert not can_transition(SessionState.ARCHIVED, SessionState.FAILED)


@pytest.mark.asyncio
async def test_service_pipeline_runs_end_to_end(tmp_path) -> None:
    """Service should drive the full PARSING → ARCHIVED pipeline.

    Uses the default :class:`RuleBasedIntentParser` + :class:`FakeDikongClient`,
    so no LLM/dikong access is required.
    """
    service = FlyReportService(output_root=tmp_path)
    sid = await service.start_session(tenant_id="t1", user_id="u1")
    assert sid

    reply = await service.send_message(sid, "生成农业局上周飞行周报", user_id="u1")
    assert reply.role == "assistant"
    assert reply.payload is not None
    # The pipeline must have walked through every stage at least once.
    stages = {s["stage"] for s in reply.payload["stages"]}
    assert {"parsing", "authorizing", "fetching", "analyzing", "previewing"} <= stages
    assert reply.payload["state"] == SessionState.PREVIEWING.value

    snap = await service.get_session_snapshot(sid, user_id="u1")
    assert snap["session_id"] == sid
    assert snap["state"] == SessionState.PREVIEWING.value
    assert snap["turn_count"] >= 2
    assert snap["last_user_text"].startswith("生成农业局")

    confirm = await service.confirm(
        sid, user_id="u1", output_format="markdown"
    )
    assert confirm.payload is not None
    assert confirm.payload["output_format"] == "markdown"
    artifact_path = confirm.payload["artifact_path"]
    assert Path(artifact_path).is_file()
    assert confirm.payload["download_url"].startswith(
        f"/v1/fly-reports/sessions/{sid}/artifacts/"
    )

    # After ARCHIVED the session is terminal.
    snap = await service.get_session_snapshot(sid, user_id="u1")
    assert snap["state"] == SessionState.ARCHIVED.value
    with pytest.raises(InvalidStateTransition):
        await service.send_message(sid, "再来一次", user_id="u1")


@pytest.mark.asyncio
async def test_service_artifact_download_path(tmp_path) -> None:
    service = FlyReportService(output_root=tmp_path)
    sid = await service.start_session(
        tenant_id="t1", user_id="u1", initial_query="飞行周报"
    )
    confirm = await service.confirm(sid, user_id="u1", output_format="markdown")
    filename = confirm.payload["filename"]
    path = await service.get_artifact_path(sid, filename, user_id="u1")
    assert path.is_file()
    assert path.suffix == ".md"

    with pytest.raises(FileNotFoundError):
        await service.get_artifact_path(sid, "../etc/passwd", user_id="u1")
    with pytest.raises(FileNotFoundError):
        await service.get_artifact_path(sid, "nope.docx", user_id="u1")


@pytest.mark.asyncio
async def test_service_isolates_users() -> None:
    service = FlyReportService()
    sid = await service.start_session(tenant_id="t1", user_id="u1")
    with pytest.raises(SessionNotFound):
        await service.get_session_snapshot(sid, user_id="someone-else")


def test_agent_factory_imports() -> None:
    """Agents must at least import without instantiating an LLM client."""

    from swarmmind.domains.fly_report.agents import (  # noqa: F401
        FlyReportSessionHub,
        build_clarifier_agent,
        build_followup_router_agent,
        build_intent_agent,
    )
