"""Tests for department-dimension analysis (DESIGN-2 §13 step 8)."""

from __future__ import annotations

from datetime import datetime, timezone

from swarmmind.domains.fly_report.analyzer import analyze
from swarmmind.domains.fly_report.analyzer.comparisons import (
    PER_DEPT_KEY,
    analyze_by_department,
)
from swarmmind.domains.fly_report.composer import compose_report_context
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
        dimension=Dimension(
            scope="department", department_ids=["10", "20", "30"]
        ),
        indicators=["flight"],
        options=ReportOptions(),
        hash="h-dept",
    )


def _per_dept_payload(num: int, dept_name: str) -> dict:
    return {"fly_statis": {"num_total": num, "dept_name": dept_name}}


def test_analyze_by_department_returns_empty_when_no_block():
    raw = RawDataset(
        current={"fly_statis": {"num_total": 100}},
        previous={"fly_statis": {"num_total": 80}},
    )
    by_dept, comparisons = analyze_by_department(raw, _dept_filter())
    assert by_dept == {}
    assert comparisons == []


def test_analyze_by_department_ranks_by_primary_kpi():
    raw = RawDataset(
        current={
            "fly_statis": {"num_total": 270},  # overall
            PER_DEPT_KEY: {
                "10": _per_dept_payload(120, "A大队"),
                "20": _per_dept_payload(60, "B大队"),
                "30": _per_dept_payload(90, "C大队"),
            },
        },
        previous={
            "fly_statis": {"num_total": 240},
            PER_DEPT_KEY: {
                "10": _per_dept_payload(100, "A大队"),
                "20": _per_dept_payload(70, "B大队"),
                "30": _per_dept_payload(70, "C大队"),
            },
        },
    )

    by_dept, comparisons = analyze_by_department(raw, _dept_filter())

    assert set(by_dept.keys()) == {"10", "20", "30"}
    assert by_dept["10"]["label"] == "A大队"
    assert {row["dept_id"] for row in comparisons} == {"10", "20", "30"}

    # Sorted descending by current.
    assert [r["dept_id"] for r in comparisons] == ["10", "30", "20"]
    assert comparisons[0]["rank"] == 1
    assert comparisons[0]["vs_leader"] == 0
    assert comparisons[2]["rank"] == 3
    assert comparisons[2]["vs_leader"] == 60 - 120  # -60


def test_analyze_merges_dept_rank_into_comparisons():
    raw = RawDataset(
        current={
            "fly_statis": {"num_total": 200},
            PER_DEPT_KEY: {
                "10": _per_dept_payload(120, "A大队"),
                "20": _per_dept_payload(80, "B大队"),
            },
        },
        previous={
            "fly_statis": {"num_total": 180},
            PER_DEPT_KEY: {
                "10": _per_dept_payload(110, "A大队"),
                "20": _per_dept_payload(70, "B大队"),
            },
        },
    )

    result = analyze(raw, _dept_filter())
    assert set(result.by_department.keys()) == {"10", "20"}

    dept_rows = [c for c in result.comparisons if c.get("kind") == "department_rank"]
    assert len(dept_rows) == 2
    assert dept_rows[0]["dept_id"] == "10"
    assert dept_rows[0]["rank"] == 1


def test_composer_emits_dept_compare_section():
    raw = RawDataset(
        current={
            "fly_statis": {"num_total": 200},
            PER_DEPT_KEY: {
                "10": _per_dept_payload(120, "A大队"),
                "20": _per_dept_payload(80, "B大队"),
            },
        },
        previous={
            "fly_statis": {"num_total": 180},
            PER_DEPT_KEY: {
                "10": _per_dept_payload(110, "A大队"),
                "20": _per_dept_payload(70, "B大队"),
            },
        },
    )
    filt = _dept_filter()
    analysis = analyze(raw, filt)

    ctx = compose_report_context(
        session_id="sess-x", analysis=analysis, filt=filt
    )
    section_ids = [s.id for s in ctx.sections]
    assert "dept_compare" in section_ids

    dept_section = next(s for s in ctx.sections if s.id == "dept_compare")
    # KPI list is one row per ranked department, in rank order.
    assert dept_section.kpis[0]["label"].startswith("#1 A大队")
    assert dept_section.charts[0].chart_type == "bar"
    assert dept_section.charts[0].series[0]["name"] == "本期"


def test_data_fetcher_dept_fanout(monkeypatch):
    """DataFetcher should issue one extra fetch per dept when scope=department."""

    from unittest.mock import AsyncMock

    from swarmmind.domains.fly_report.data_fetcher import DataFetcher

    client = AsyncMock()

    # Use a counter to vary num_total per dept call so we can assert fan-out.
    counter = {"n": 0}

    async def fake_fly(*args, **kwargs):
        counter["n"] += 1
        from swarmmind.domains.fly_report.dikong.parsers import FlyStatisResp

        return FlyStatisResp(num_total=counter["n"] * 10, raw={})

    client.get_fly_statis = AsyncMock(side_effect=fake_fly)

    filt = _dept_filter()
    fetcher = DataFetcher(client)

    import asyncio

    raw = asyncio.run(fetcher.fetch(filt))

    # 2 (overall current+previous) + 2*3 (per-dept current+previous) = 8.
    assert client.get_fly_statis.await_count == 8
    assert PER_DEPT_KEY in raw.current
    assert set(raw.current[PER_DEPT_KEY].keys()) == {"10", "20", "30"}
