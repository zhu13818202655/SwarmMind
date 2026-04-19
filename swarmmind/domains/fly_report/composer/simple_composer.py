"""Minimal :class:`AnalysisResult` → :class:`ReportContext` composer.

Groups KPIs by their indicator domain (flight / algorithm / media /
device_health) into sections, attaches a generated bar chart per section
showing current-vs-previous values, and produces a one-paragraph
summary that is good enough to render a usable report without any LLM.

This is intentionally **not** the full §4.1.5 composer: there is no
SectionSummarizerAgent here, no anomaly narratives, no comparisons table.
It exists to unblock end-to-end exports today; richer composition lands
in M2+.
"""

from __future__ import annotations

from typing import Any

from swarmmind.domains.fly_report.schemas import (
    AnalysisResult,
    ChartSpec,
    NormalizedFilter,
    ReportContext,
    ReportSection,
)

# Mapping from KPI ``name`` prefix → (section_id, section_title, indicator).
_GROUPS: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    (
        "flight",
        "飞行概览",
        "flight",
        ("fly_count", "fly_mileage", "fly_time", "drone_count", "drone_job_count"),
    ),
    (
        "algorithm",
        "算法告警",
        "algorithm",
        ("algorithm_warn_total",),
    ),
    (
        "media",
        "媒体成果",
        "media",
        ("media_total",),
    ),
    (
        "device_health",
        "设备健康",
        "device_health",
        ("hms_alert_total",),
    ),
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
        kpis_by_name = {k["name"]: k for k in analysis.kpis}

        for section_id, title, _indicator, kpi_names in _GROUPS:
            section_kpis = [
                kpis_by_name[name]
                for name in kpi_names
                if name in kpis_by_name
            ]
            if not section_kpis:
                continue
            sections.append(
                ReportSection(
                    id=section_id,
                    title=title,
                    summary_md=_build_summary(title, section_kpis),
                    kpis=section_kpis,
                    charts=[_build_chart(section_id, title, section_kpis)],
                )
            )

        # Department comparison section (DESIGN-2 §13 step 8).
        dept_section = _build_dept_compare_section(analysis)
        if dept_section is not None:
            sections.append(dept_section)

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


def _build_summary(title: str, kpis: list[dict[str, Any]]) -> str:
    """Plain-language one-liner derived purely from KPI deltas."""

    movers: list[str] = []
    for k in kpis:
        change_pct = k.get("change_pct")
        if change_pct is None:
            continue
        direction = "上升" if change_pct >= 0 else "下降"
        movers.append(f"{k.get('label', k['name'])}{direction} {abs(change_pct):.1f}%")
    if not movers:
        return f"{title}：本期暂无环比数据。"
    return f"{title}：" + "；".join(movers[:3]) + "。"


def _build_chart(
    section_id: str, title: str, kpis: list[dict[str, Any]]
) -> ChartSpec:
    """One bar chart per section comparing current vs previous values."""

    current = {
        "name": "本期",
        "data": [
            {
                "x": k.get("label", k["name"]),
                "y": k.get("value") if k.get("value") is not None else 0,
            }
            for k in kpis
        ],
    }
    previous = {
        "name": "上期",
        "data": [
            {
                "x": k.get("label", k["name"]),
                "y": k.get("previous_value") if k.get("previous_value") is not None else 0,
            }
            for k in kpis
        ],
    }
    return ChartSpec(
        id=f"{section_id}-overview",
        title=f"{title} · 本期 vs 上期",
        chart_type="bar",
        series=[current, previous],
    )


def _build_dept_compare_section(analysis: AnalysisResult) -> ReportSection | None:
    """Build the "部门对比" section if per-department data is present."""

    by_dept = analysis.by_department or {}
    if not by_dept:
        return None

    rank_rows = [
        c for c in analysis.comparisons if c.get("kind") == "department_rank"
    ]
    if not rank_rows:
        return None

    summary_parts: list[str] = []
    leader = rank_rows[0]
    summary_parts.append(f"领先部门：{leader['label']}（{leader['current']:.0f} 次）")
    if len(rank_rows) > 1:
        tail = rank_rows[-1]
        summary_parts.append(
            f"末位部门：{tail['label']}（{tail['current']:.0f} 次，"
            f"较领先 {tail['vs_leader']:+.0f} 次）"
        )

    chart = ChartSpec(
        id="dept-compare-overview",
        title="部门飞行次数对比",
        chart_type="bar",
        series=[
            {
                "name": "本期",
                "data": [
                    {"x": r["label"], "y": r["current"]} for r in rank_rows
                ],
            },
            {
                "name": "上期",
                "data": [
                    {"x": r["label"], "y": r.get("previous") or 0}
                    for r in rank_rows
                ],
            },
        ],
    )

    return ReportSection(
        id="dept_compare",
        title="部门对比",
        summary_md="部门对比：" + "；".join(summary_parts) + "。",
        kpis=[
            {
                "name": f"dept_rank_{r['rank']}",
                "label": f"#{r['rank']} {r['label']}",
                "value": r["current"],
                "previous_value": r.get("previous"),
                "unit": "次",
                "change": r.get("change"),
                "change_pct": r.get("change_pct"),
            }
            for r in rank_rows
        ],
        charts=[chart],
    )
