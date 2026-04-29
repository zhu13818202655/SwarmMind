"""Shared fixtures for FlyReport renderer tests."""

from __future__ import annotations

from datetime import UTC, datetime

from swarmmind.domains.fly_report.schemas import (
    ChartBlock,
    ChartSpec,
    Dimension,
    FilterSpec,
    KpiGroupBlock,
    ListBlock,
    ListItem,
    MarkdownBlock,
    NormalizedFilter,
    ParagraphBlock,
    Period,
    ReportContext,
    ReportSection,
    TableBlock,
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


def make_block_context(*, session_id: str = "sess-block") -> ReportContext:
    chart = ChartSpec(
        id="flight-trend",
        title="飞行趋势",
        chart_type="line",
        series=[
            {
                "name": "任务数",
                "data": [
                    {"x": "周一", "y": 12},
                    {"x": "周二", "y": 18},
                    {"x": "周三", "y": 15},
                ],
            }
        ],
    )
    return ReportContext(
        session_id=session_id,
        title="自定义飞行报告",
        filter=make_filter(),
        sections=[
            ReportSection(
                id="rich-overview",
                title="综合概览",
                blocks=[
                    MarkdownBlock(
                        id="summary",
                        markdown="本周飞行任务整体稳定，重点关注夜间任务波动。",
                    ),
                    KpiGroupBlock(
                        id="kpis",
                        kpis=[
                            {
                                "name": "flight_total",
                                "label": "飞行任务数",
                                "value": 128.0,
                                "previous_value": 102.0,
                                "unit": "次",
                                "change_pct": 25.49,
                            }
                        ],
                    ),
                    ChartBlock(id="trend-chart", chart=chart, caption="任务趋势"),
                    TableBlock(
                        id="dept-table",
                        caption="部门明细",
                        table={
                            "columns": [
                                {"key": "dept", "label": "部门"},
                                {"key": "count", "label": "任务数"},
                            ],
                            "rows": [
                                {"dept": "一中队", "count": 64},
                                {"dept": "二中队", "count": 42},
                            ],
                        },
                    ),
                    ListBlock(
                        id="actions",
                        items=[
                            ListItem(text="复盘夜间航线"),
                            ListItem(text="补充设备巡检记录"),
                        ],
                    ),
                    ParagraphBlock(id="closing", text="建议下周继续观察高频点位。"),
                ],
            )
        ],
    )
