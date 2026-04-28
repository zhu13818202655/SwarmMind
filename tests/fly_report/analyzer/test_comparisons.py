"""Tests for current department-scope FlyReport analysis behavior."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from swarmmind.domains.fly_report.analyzer import analyze
from swarmmind.domains.fly_report.composer import compose_report_context
from swarmmind.domains.fly_report.dikong.parsers import (
    FlyJobLogResp,
    FlyStatisResp,
    MediaStaticResp,
    WarnStaticResp,
)
from swarmmind.domains.fly_report.schemas import (
    Dimension,
    NormalizedFilter,
    Period,
    RawDataset,
    ReportOptions,
)


def _dept_filter() -> NormalizedFilter:
    return NormalizedFilter(
        period=Period(
            kind="weekly",
            start=datetime(2026, 4, 13, tzinfo=timezone.utc),
            end=datetime(2026, 4, 19, 23, 59, 59, tzinfo=timezone.utc),
            label="2026年第16周",
        ),
        dimension=Dimension(scope="department", department_ids=["10", "20", "30"]),
        dept_ids=[10, 20, 30],
        indicators=["flight"],
        options=ReportOptions(),
        hash="h-dept",
    )


def _completed_log(dept_name: str, begin: str, end: str) -> dict:
    return {
        "status": 2,
        "deptidsTagName": dept_name,
        "begin_time": begin,
        "end_time": end,
    }


def test_analyze_builds_department_share_table() -> None:
    raw = RawDataset(
        current={
            "fly_job_logs": {
                "records": [
                    _completed_log("A大队", "2026-04-13 08:00:00", "2026-04-13 10:00:00"),
                    _completed_log("B大队", "2026-04-13 08:00:00", "2026-04-13 09:00:00"),
                    _completed_log("A大队", "2026-04-14 08:00:00", "2026-04-14 09:30:00"),
                ]
            }
        }
    )

    result = analyze(raw, _dept_filter())

    assert result.flight_stat_department_share["title"] == "部门飞行时长占比"
    rows = result.flight_stat_department_share["rows"]
    assert [row["department_name"] for row in rows] == ["A大队", "B大队"]
    assert rows[0]["flight_hours"] == 3.5
    assert rows[0]["meta"]["share_value"] > rows[1]["meta"]["share_value"]


def test_composer_emits_flight_tables_for_department_scope() -> None:
    raw = RawDataset(
        current={
            "fly_job_logs": {
                "records": [
                    _completed_log("A大队", "2026-04-13 08:00:00", "2026-04-13 10:00:00"),
                ]
            }
        }
    )
    filt = _dept_filter()
    analysis = analyze(raw, filt)

    ctx = compose_report_context(session_id="sess-x", analysis=analysis, filt=filt)

    section_ids = [section.id for section in ctx.sections]
    assert "flight_stat_department_share" in section_ids
    flight_section = next(
        section for section in ctx.sections if section.id == "flight_stat_department_share"
    )
    assert flight_section.title == "部门飞行时长占比"
    assert flight_section.tables


def test_data_fetcher_dept_fanout() -> None:
    """DataFetcher should issue one period-scoped fetch per requested dept."""

    from swarmmind.domains.fly_report.data_fetcher import DataFetcher

    client = AsyncMock()

    async def fake_fly(*args, **kwargs):
        return FlyStatisResp(num_total=10, raw={})

    client.get_fly_statis = AsyncMock(side_effect=fake_fly)
    client.get_warn_static = AsyncMock(return_value=WarnStaticResp(raw={}))
    client.get_media_static = AsyncMock(return_value=MediaStaticResp(raw={}))
    client.get_fly_job_logs = AsyncMock(
        return_value=FlyJobLogResp(records=[], total=0, size=0, pages=0)
    )

    raw = asyncio.run(DataFetcher(client).fetch(_dept_filter()))

    assert client.get_fly_statis.await_count == 6
    assert client.get_warn_static.await_count == 6
    assert client.get_media_static.await_count == 6
    assert client.get_fly_job_logs.await_count == 2
    assert set(raw.current["fly_statis"].keys()) == {"10", "20", "30"}
