"""Tests for M-E clarifier / conflict / followup logic."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from swarmmind.domains.fly_report.conflict_checker import (
    check_conflicts,
    merge_drafts,
)
from swarmmind.domains.fly_report.schemas import (
    Dimension,
    DraftFilterSpec,
    FilterSpec,
    Period,
)
from swarmmind.domains.fly_report.service import FlyReportService


def _period() -> Period:
    now = datetime.now(UTC)
    return Period(
        kind="weekly",
        start=now - timedelta(days=7),
        end=now,
        label="本周",
    )


def test_check_conflicts_flags_missing_period_and_indicators() -> None:
    rep = check_conflicts(FilterSpec())
    assert rep.needs_clarification
    assert "period" in rep.missing
    assert "indicators" in rep.missing


def test_check_conflicts_flags_dept_without_ids() -> None:
    rep = check_conflicts(
        FilterSpec(
            period=_period(),
            indicators=["flight"],
            dimension=Dimension(scope="department"),
        )
    )
    assert rep.needs_clarification
    assert any("department_ids" in c for c in rep.conflicts)


def test_merge_drafts_keeps_prior_period() -> None:
    base = FilterSpec(period=_period(), indicators=["flight"])
    patch = FilterSpec(
        dimension=Dimension(scope="department", department_ids=["A"]),
        indicators=["algorithm"],
    )
    merged = merge_drafts(base, patch)
    assert merged.period is not None and merged.period.label == "本周"
    assert merged.dimension.scope == "department"
    assert merged.dimension.department_ids == ["A"]
    assert merged.indicators == ["algorithm"]


@pytest.mark.asyncio
async def test_service_routes_to_clarifying_for_dept_without_ids(
    tmp_path,
) -> None:
    period = _period()

    class _ParserMissingIds:
        async def parse(self, text: str, **_) -> DraftFilterSpec:
            return DraftFilterSpec(
                period=period,
                indicators=["flight"],
                dimension=Dimension(scope="department"),
            )

    svc = FlyReportService(
        output_root=tmp_path, intent_parser=_ParserMissingIds()
    )
    sid = await svc.start_session(tenant_id="t1", user_id="u1")
    reply = await svc.send_message(sid, "请看部门数据", user_id="u1")
    assert reply.payload is not None
    assert reply.payload["state"] == "clarifying"
    assert any(
        "department_ids" in c for c in reply.payload.get("conflicts", [])
    )


@pytest.mark.asyncio
async def test_service_followup_resolves_clarification(tmp_path) -> None:
    period = _period()

    class _PatchParser:
        async def parse(self, text: str, **_) -> DraftFilterSpec:
            if "ids" in text:
                return DraftFilterSpec(
                    dimension=Dimension(
                        scope="department", department_ids=["X"]
                    ),
                )
            return DraftFilterSpec(
                period=period,
                indicators=["flight"],
                dimension=Dimension(scope="department"),
            )

    svc = FlyReportService(output_root=tmp_path, intent_parser=_PatchParser())
    sid = await svc.start_session(tenant_id="t1", user_id="u1")
    first = await svc.send_message(sid, "请看部门数据", user_id="u1")
    assert first.payload["state"] == "clarifying"

    second = await svc.send_message(sid, "department_ids=X", user_id="u1")
    assert second.payload["state"] == "previewing"
