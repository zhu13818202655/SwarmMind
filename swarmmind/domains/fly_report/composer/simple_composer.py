"""Minimal :class:`AnalysisResult` -> :class:`ReportContext` composer."""

from __future__ import annotations

from typing import Any

from swarmmind.domains.fly_report.schemas import (
    AnalysisResult,
    ChartSpec,
    NormalizedFilter,
    ReportContext,
    ReportSection,
)

_TABLE_SECTIONS: tuple[tuple[str, str, str], ...] = (
    ("flight_stat_overall", "flight_stat_overall", "总体飞行统计概览"),
    ("flight_stat_day_trend", "flight_stat_day_trend", "每日飞行趋势"),
    ("flight_stat_department_share", "flight_stat_department_share", "部门飞行时长占比"),
    ("media_collection_summary", "media_collection_summary", "图片视频采集统计"),
    ("algorithm_recognition_overall", "algorithm_recognition_overall", "总的算法识别数据汇总"),
    ("algorithm_recognition_distribution", "algorithm_recognition_distribution", "算法识别统计"),
    ("algorithm_disposal_summary", "algorithm_disposal_summary", "算法处置统计"),
    ("algorithm_high_frequency_locations", "algorithm_high_frequency_locations", "高频案发点统计"),
    ("algorithm_high_frequency_time_slots", "algorithm_high_frequency_time_slots", "高频案时间段统计"),
    ("algorithm_push_events", "algorithm_push_events", "算法推送事件"),
)


class SimpleComposer:
    """Build a :class:`ReportContext` from an :class:`AnalysisResult`."""

    def compose(
        self,
        *,
        session_id: str,
        analysis: AnalysisResult,
        filt: NormalizedFilter,
        revision: int = 1,
    ) -> ReportContext:
        sections: list[ReportSection] = []
        for attr_name, section_id, fallback_title in _TABLE_SECTIONS:
            table = getattr(analysis, attr_name)
            if not table:
                continue
            title = str(table.get("title") or fallback_title)
            chart = _build_table_chart(section_id, title, table)
            sections.append(
                ReportSection(
                    id=section_id,
                    title=title,
                    summary_md=_build_table_summary(title, table),
                    tables=[table],
                    charts=[chart] if chart is not None else [],
                )
            )

        return ReportContext(
            session_id=session_id,
            filter=filt,
            sections=sections,
            revision=revision,
        )


def compose_report_context(
    *,
    session_id: str,
    analysis: AnalysisResult,
    filt: NormalizedFilter,
    revision: int = 1,
) -> ReportContext:
    """Convenience wrapper used by the API layer & tests."""

    return SimpleComposer().compose(
        session_id=session_id,
        analysis=analysis,
        filt=filt,
        revision=revision,
    )


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _build_table_summary(title: str, table: dict[str, Any]) -> str:
    rows = table.get("rows") if isinstance(table.get("rows"), list) else []
    return f"{title}：共 {len(rows)} 条数据。"


def _build_table_chart(
    section_id: str,
    title: str,
    table: dict[str, Any],
) -> ChartSpec | None:
    rows = table.get("rows")
    if not isinstance(rows, list):
        return None

    current_data: list[dict[str, Any]] = []
    previous_data: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
        current = meta.get("current_value")
        previous = meta.get("previous_value")
        if current is None and previous is None:
            continue
        label = _row_label(row)
        current_data.append({"x": label, "y": current or 0})
        previous_data.append({"x": label, "y": previous or 0})

    if not current_data and not previous_data:
        return None

    return ChartSpec(
        id=f"{section_id}-overview",
        title=f"{title} · 本期 vs 上期",
        chart_type="bar",
        series=[
            {"name": "本期", "data": current_data},
            {"name": "上期", "data": previous_data},
        ],
    )


def _row_label(row: dict[str, Any]) -> str:
    for key in (
        "metric",
        "statistic_category",
        "department_name",
        "algorithm_name",
        "scene_name",
        "date",
        "key",
    ):
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    return "数据项"
