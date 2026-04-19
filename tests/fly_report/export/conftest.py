"""Shared fixtures for FlyReport renderer tests."""

from __future__ import annotations

from datetime import UTC, datetime

from swarmmind.domains.fly_report.schemas import (
    Dimension,
    FilterSpec,
    NormalizedFilter,
    Period,
    ReportContext,
    ReportSection,
)


def make_filter(*, scope: str = "overall") -> NormalizedFilter:
    spec = FilterSpec(
        period=Period(
            kind="weekly",
            start=datetime(2026, 4, 6, tzinfo=UTC),
            end=datetime(2026, 4, 13, tzinfo=UTC),
            label="2026-W15",
        ),
        dimension=Dimension(
            scope=scope,  # type: ignore[arg-type]
            department_ids=["dept-1"] if scope != "overall" else [],
        ),
        indicators=["flight", "algorithm"],
    )
    return NormalizedFilter.from_filter(spec)


def make_context(*, session_id: str = "sess-test") -> ReportContext:
    return ReportContext(
        session_id=session_id,
        filter=make_filter(),
        sections=[
            ReportSection(
                id="flight-overview",
                title="飞行概览",
                summary_md="本周飞行任务整体平稳，告警数量较上周下降 12%。",
                kpis=[
                    {
                        "name": "flight_total",
                        "label": "飞行任务数",
                        "value": 128.0,
                        "previous_value": 102.0,
                        "unit": "次",
                        "change": 26.0,
                        "change_pct": 25.49,
                    },
                    {
                        "name": "flight_hours",
                        "label": "飞行小时数",
                        "value": 64.5,
                        "previous_value": 70.0,
                        "unit": "h",
                        "change": -5.5,
                        "change_pct": -7.86,
                    },
                ],
            ),
            ReportSection(
                id="algo",
                title="算法告警",
                summary_md="",
                kpis=[
                    {
                        "name": "algo_warn",
                        "label": "算法告警",
                        "value": 18.0,
                        "previous_value": None,
                        "unit": "次",
                        "change": None,
                        "change_pct": None,
                    },
                ],
            ),
        ],
    )
