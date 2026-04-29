from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from swarmmind.config.settings import get_settings
from swarmmind.domains.fly_report.chart import configure_matplotlib_cjk_font
from swarmmind.domains.fly_report.lm.client import OpenAICompatibleLMClient
from swarmmind.domains.fly_report.lm.types import LMChatRequest, LMOutputFormat
from swarmmind.domains.fly_report.schemas import (
    AnalysisResult,
    NormalizedFilter,
    ParagraphBlock,
    TextRun,
)
from swarmmind.domains.fly_report.utils.markdown_table import dict_table_to_markdown

REPORT_TITLE = "武义飞行服务平台飞行统计报告"
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
CHART_OUTPUT_ROOT = Path(__file__).resolve().parents[4] / "data" / "fly_report_artifacts" / "generated_charts"
LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)")

config = get_settings()

llm_client = OpenAICompatibleLMClient(
    model_name=config.agent.model.name,
    api_key=config.agent.model.api_key,
    base_url=config.agent.model.base_url,
    temperature=1.0,
    max_tokens=16384,
    timeout_sec=100.0,
)


async def compose_report_context(
    session_id: str,
    analysis: AnalysisResult,
    filt: NormalizedFilter,
    revision: int = 1,
) -> str:

    sections: list[str] = []

    for section_title, builder in _REPORT_TEMPLATE:
        section = await builder(analysis=analysis, filt=filt, section_title=section_title)
        if section is not None:
            sections.append(section)

    return "\n\n".join(section.strip() for section in sections if section.strip())


async def build_report_meta_section(
    analysis: AnalysisResult,
    filt: NormalizedFilter,
    section_title: str,
) -> str:
    period = _format_period_text(filt)
    generated_date = _format_zh_date(datetime.now(SHANGHAI_TZ))
    data_scope = _build_data_scope_text(filt)
    heading = f"## {section_title}\n\n" if section_title else ""

    return (
        f"{heading}"
        "\\\n".join(
            [
                f"**报告周期**：{period}",
                f"**生成时间**：{generated_date}",
                f"**数据范围**：{data_scope}",
            ]
        )
    )


async def build_overview_section(
    analysis: AnalysisResult,
    filt: NormalizedFilter,
    section_title: str,
) -> str:
    summary = await llm_client.chat(
        system_prompt=(
            "你是一个简洁的助手，根据提供的数据概况生成一段简短的总结，"
            "突出关键数据点和趋势，字数控制在100字以内。"
        ),
        user_prompt=(
            f"根据以下数据概况生成总结：\n"
            f"{dict_table_to_markdown(analysis.flight_stat_overall, title_level=3)}\n"
            f"{dict_table_to_markdown(analysis.flight_stat_day_trend, title_level=3)}\n"
            f"{dict_table_to_markdown(analysis.flight_stat_department_share, title_level=3)}\n"
            f"{dict_table_to_markdown(analysis.media_collection_summary, title_level=3)}\n"
            f"{dict_table_to_markdown(analysis.algorithm_recognition_overall, title_level=3)}\n"
            f"{dict_table_to_markdown(analysis.algorithm_recognition_distribution, title_level=3)}\n"
            f"{dict_table_to_markdown(analysis.algorithm_disposal_summary, title_level=3)}\n"
            f"{dict_table_to_markdown(analysis.algorithm_high_frequency_locations, title_level=3)}\n"
            f"{dict_table_to_markdown(analysis.algorithm_high_frequency_time_slots, title_level=3)}\n"
            f"{dict_table_to_markdown(analysis.algorithm_push_events, title_level=3)}\n"
        ),
        output_format=LMOutputFormat.TEXT,
        max_tokens=512,
    )
    summary = _clean_llm_markdown(summary)
    heading = f"## {section_title}\n\n" if section_title else ""

    return (
        f"{heading}"
        "::: {.summary-box}\n"
        f"{summary}\n"
        ":::\n"
    )

async def build_flight_stat_overall_section(
    analysis: AnalysisResult,
    filt: NormalizedFilter,
    section_title: str,
) -> str:
    table = dict_table_to_markdown(analysis.flight_stat_overall, title_level=-1)
    summary = await llm_client.chat(
        system_prompt=(
            "你是一个擅长数据分析和总结的助手，根据提供的数据概况生成一段简短的总结，"
            "按照数字序号分点给出结论，不要超过5点，每一点不要太长，保持在一句话左右"
        ),
        user_prompt=(
            f"根据以下数据概况生成总结，需要对比趋势。然后在每一个有显著变化的地方给出结论。\n"
            f"{table}\n"
        ),
        output_format=LMOutputFormat.MARKDOWN,
        max_tokens=512,
    )
    summary = _clean_llm_markdown(summary)
    heading = f"## {section_title}\n\n" if section_title else ""
    return (
        f"{heading}"
        "::: {align=center}\n"
        f"{table}\n"
        ":::\n\n"
        f"**关键结论**：\n\n"
        f"{summary}\n"
    )


async def build_flight_stat_day_trend_section(
    analysis: AnalysisResult,
    filt: NormalizedFilter,
    section_title: str,
) -> str:
    table = dict_table_to_markdown(analysis.flight_stat_day_trend, title_level=-1)
    chart = _build_day_trend_line_chart_markdown(analysis.flight_stat_day_trend)
    summary = await llm_client.chat(
        system_prompt=(
            "你是一个擅长飞行数据趋势分析的助手，根据每日飞行趋势数据生成简短总结，"
            "按照数字序号分点给出结论，不要超过5点，每一点保持在一句话左右。"
        ),
        user_prompt=(
            "根据以下每日飞行趋势数据生成总结，需要说明飞行次数、飞行时长和异常次数的变化。\n"
            f"{table}\n"
        ),
        output_format=LMOutputFormat.MARKDOWN,
        max_tokens=512,
    )
    summary = _clean_llm_markdown(summary)
    heading = f"## {section_title}\n\n" if section_title else ""

    return (
        f"{heading}"
        f"{chart}\n\n"
        "**趋势说明**：\n\n"
        "::: {align=center}\n"
        f"{table}\n"
        ":::\n\n"
        "**关键结论**：\n\n"
        f"{summary}\n"
    )


def _build_day_trend_line_chart_markdown(table: dict[str, Any]) -> str:
    raw_rows = table.get("rows")
    rows = raw_rows if isinstance(raw_rows, list) else []
    dates = [
        _format_chart_date_label(str(row.get("date") or ""))
        for row in rows
        if isinstance(row, dict)
    ]
    flight_counts = [
        _to_number(row.get("flight_count")) for row in rows if isinstance(row, dict)
    ]
    flight_hours = [
        _to_number(row.get("flight_hours")) for row in rows if isinstance(row, dict)
    ]
    option = {
        "title": {"text": "飞行趋势"},
        "tooltip": {"trigger": "axis"},
        "legend": {"bottom": 0, "data": ["飞行次数", "飞行时长"]},
        "grid": {"left": "8%", "right": "8%", "bottom": "18%", "containLabel": True},
        "xAxis": {
            "type": "category",
            "data": dates,
            "axisLabel": _build_date_axis_label(dates),
        },
        "yAxis": [
            _build_value_axis("次数", flight_counts),
            _build_value_axis("小时", flight_hours),
        ],
        "series": [
            {
                "name": "飞行次数",
                "type": "line",
                "smooth": True,
                "yAxisIndex": 0,
                "itemStyle": {"color": "#d62728"},
                "lineStyle": {"color": "#d62728", "width": 2},
                "data": flight_counts,
            },
            {
                "name": "飞行时长",
                "type": "line",
                "smooth": True,
                "yAxisIndex": 1,
                "itemStyle": {"color": "#1f77b4"},
                "lineStyle": {"color": "#1f77b4", "width": 2},
                "data": flight_hours,
            },
        ],
    }
    chart_path = _render_day_trend_line_chart_png(
        dates=dates,
        flight_counts=flight_counts,
        flight_hours=flight_hours,
        option=option,
    )
    return f"![]({chart_path}){{width=14cm align=center}}"


def _render_day_trend_line_chart_png(
    *,
    dates: list[str],
    flight_counts: list[float],
    flight_hours: list[float],
    option: dict[str, Any],
) -> Path:
    CHART_OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(
        json.dumps(option, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:12]
    output_path = CHART_OUTPUT_ROOT / f"flight-day-trend-{digest}.png"
    if output_path.exists():
        return output_path

    configure_matplotlib_cjk_font()
    fig, left_ax = plt.subplots(figsize=(8.2, 4.4))
    right_ax = left_ax.twinx()
    count_axis, hour_axis = option["yAxis"]

    left_line = left_ax.plot(
        dates,
        flight_counts,
        color="#d62728",
        linewidth=2.2,
        marker="o",
        markersize=4,
        label="飞行次数",
    )[0]
    hour_line = right_ax.plot(
        dates,
        flight_hours,
        color="#1f77b4",
        linewidth=2.2,
        marker="o",
        markersize=4,
        label="飞行时长",
    )[0]

    left_ax.set_title(str(option["title"]["text"]), fontsize=13, pad=12)
    left_ax.set_ylabel("次数", color="#d62728")
    right_ax.set_ylabel("小时", color="#1f77b4")
    left_ax.set_ylim(count_axis["min"], count_axis["max"])
    right_ax.set_ylim(hour_axis["min"], hour_axis["max"])
    left_ax.set_yticks(_axis_ticks(count_axis))
    right_ax.set_yticks(_axis_ticks(hour_axis))
    left_ax.grid(True, axis="y", linestyle="--", alpha=0.35)

    label_style = option["xAxis"].get("axisLabel", {})
    interval = int(label_style.get("interval", 0))
    visible_indexes = [index for index in range(len(dates)) if index % (interval + 1) == 0]
    left_ax.set_xticks(visible_indexes)
    left_ax.set_xticklabels(
        [dates[index] for index in visible_indexes],
        rotation=int(label_style.get("rotate", 0)),
        ha="right" if label_style.get("rotate", 0) else "center",
    )
    left_ax.legend(handles=[left_line, hour_line], loc="upper center", ncol=2, frameon=False)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return output_path


def _axis_ticks(axis: dict[str, Any]) -> list[float | int]:
    axis_min = _to_number(axis.get("min"))
    axis_max = _to_number(axis.get("max"))
    interval = _to_number(axis.get("interval")) or 1
    ticks: list[float | int] = []
    value = axis_min
    while value <= axis_max + interval / 10:
        ticks.append(_compact_number(value))
        value += interval
    return ticks


def _format_chart_date_label(value: str) -> str:
    for fmt in ("%Y-%m-%d", "%m-%d"):
        try:
            parsed = datetime.strptime(value, fmt)
            return f"{parsed.month}月{parsed.day}日"
        except ValueError:
            continue
    return value


def _build_date_axis_label(dates: list[str]) -> dict[str, Any]:
    count = len(dates)
    if count <= 7:
        return {"interval": 0, "rotate": 0}
    if count <= 15:
        return {"interval": 0, "rotate": 30}
    if count <= 31:
        return {"interval": 1, "rotate": 30}
    return {"interval": 6, "rotate": 30}


def _build_value_axis(name: str, values: list[float]) -> dict[str, Any]:
    axis_min, axis_max, step = _nice_axis_bounds(values)
    return {
        "type": "value",
        "name": name,
        "min": axis_min,
        "max": axis_max,
        "interval": step,
        "splitLine": {"lineStyle": {"type": "dashed", "color": "#d9d9d9"}},
    }


def _nice_axis_bounds(
    values: list[float], split_count: int = 5
) -> tuple[float | int, float | int, float | int]:
    min_value = min(values or [0])
    max_value = max(values or [0])
    if max_value <= 0:
        return 0, 1, 1

    spread = max_value - min_value
    use_narrow_axis = min_value >= 100 and spread / max_value <= 0.25
    axis_range = spread if use_narrow_axis and spread > 0 else max_value
    rough_step = axis_range / split_count
    magnitude = 10 ** int(math.floor(math.log10(rough_step)))
    normalized = rough_step / magnitude
    if normalized <= 1:
        step = magnitude
    elif normalized <= 2:
        step = 2 * magnitude
    elif normalized <= 5:
        step = 5 * magnitude
    else:
        step = 10 * magnitude

    if use_narrow_axis:
        axis_min = max(0, math.floor((min_value - step) / step) * step)
    else:
        axis_min = 0
    axis_max = math.ceil(max_value / step) * step
    if axis_max <= axis_min:
        axis_max = axis_min + step
    return _compact_number(axis_min), _compact_number(axis_max), _compact_number(step)


def _to_number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0


def _compact_number(value: float) -> float | int:
    if float(value).is_integer():
        return int(value)
    return round(value, 2)


async def build_department_share_section(
    analysis: AnalysisResult,
    filt: NormalizedFilter,
    section_title: str,
) -> str:
    table = dict_table_to_markdown(analysis.flight_stat_department_share, title_level=-1)
    chart = _build_table_pie_chart_markdown(
        table=analysis.flight_stat_department_share,
        label_key="department_name",
        value_meta_key="flight_hours_value",
        value_key="flight_hours",
        title="部门飞行时长占比",
        filename_prefix="flight-department-share",
    )
    summary = await llm_client.chat(
        system_prompt=(
            "你是一个擅长飞行业务数据分析的助手，根据部门飞行时长占比数据生成简短分析，"
            "突出占比最高部门、部门间差异和资源投入特征，按照数字序号分点，不超过3点。"
        ),
        user_prompt=f"根据以下部门飞行占比数据生成分析：\n{table}\n",
        output_format=LMOutputFormat.MARKDOWN,
        max_tokens=512,
    )
    summary = _clean_llm_markdown(summary)
    heading = f"## {section_title}\n\n" if section_title else ""

    return (
        f"{heading}"
        f"{chart}\n\n"
        "::: {align=center}\n"
        f"{table}\n"
        ":::\n\n"
        "**分析**：\n\n"
        f"{summary}\n"
    )


async def build_algorithm_stat_overall_section(
    analysis: AnalysisResult,
    filt: NormalizedFilter,
    section_title: str,
) -> str:
    overall_table = dict_table_to_markdown(analysis.algorithm_recognition_overall, title_level=-1)
    distribution_table = dict_table_to_markdown(
        analysis.algorithm_recognition_distribution,
        title_level=-1,
    )
    chart = _build_table_pie_chart_markdown(
        table=analysis.algorithm_recognition_distribution,
        label_key="algorithm_name",
        value_meta_key="recognized_count_value",
        value_key="recognized_count",
        title="各场景算法调用次数",
        filename_prefix="algorithm-recognition-distribution",
        aggregate_by_label=True,
    )
    heading = f"## {section_title}\n\n" if section_title else ""

    return (
        f"{heading}"
        "::: {align=center}\n"
        f"{overall_table}\n"
        ":::\n\n"
        "**各场景算法调用次数**\n\n"
        f"{chart}\n\n"
        "::: {align=center}\n"
        f"{distribution_table}\n"
        ":::\n"
    )


async def build_disposal_rate_section(
    analysis: AnalysisResult,
    filt: NormalizedFilter,
    section_title: str,
) -> str:
    occurrence_total, disposal_total = _sum_disposal_totals(analysis.algorithm_disposal_summary)
    disposal_table = dict_table_to_markdown(analysis.algorithm_disposal_summary, title_level=-1)
    push_table = dict_table_to_markdown(analysis.algorithm_push_events, title_level=-1)
    chart = _build_disposal_rate_line_chart_markdown(analysis.algorithm_disposal_summary)
    heading = f"## {section_title}\n\n" if section_title else ""

    return (
        f"{heading}"
        f"本周期共监测事件{occurrence_total:g}件，处置{disposal_total:g}件，处置统计如下：\n\n"
        f"{chart}\n\n"
        "::: {align=center}\n"
        f"{disposal_table}\n"
        ":::\n\n"
        "已推送事件如下：\n\n"
        "::: {align=center}\n"
        f"{push_table}\n"
        ":::\n"
    )


async def build_hotspot_section(
    analysis: AnalysisResult,
    filt: NormalizedFilter,
    section_title: str,
) -> str:
    location_table = dict_table_to_markdown(
        analysis.algorithm_high_frequency_locations,
        title_level=-1,
    )
    time_slot_table = dict_table_to_markdown(
        analysis.algorithm_high_frequency_time_slots,
        title_level=-1,
    )
    heading = f"## {section_title}\n\n" if section_title else ""

    return (
        f"{heading}"
        "高频案发点统计如下：\n\n"
        "::: {align=center}\n"
        f"{location_table}\n"
        ":::\n\n"
        "高频案发时间段统计如下：\n\n"
        "::: {align=center}\n"
        f"{time_slot_table}\n"
        ":::\n"
    )


async def build_media_section(
    analysis: AnalysisResult,
    filt: NormalizedFilter,
    section_title: str,
) -> str:
    table = dict_table_to_markdown(analysis.media_collection_summary, title_level=-1)
    heading = f"## {section_title}\n\n" if section_title else ""

    return (
        f"{heading}"
        "图片与视频采集统计如下：\n\n"
        "::: {align=center}\n"
        f"{table}\n"
        ":::\n"
    )


async def build_summary_section(
    analysis: AnalysisResult,
    filt: NormalizedFilter,
    section_title: str,
) -> str:
    data_markdown = _analysis_tables_markdown(analysis)
    response = await llm_client.chat_response(
        LMChatRequest(
            system_prompt=(
                "你是一个政务飞行统计报告撰写助手和无人机治理顾问。"
                "请基于全部统计数据同时生成报告总结和后续工作建议，"
                "语言正式、简洁，建议应具体、可执行。只返回 JSON 对象，"
                "不要返回 Markdown 代码块或额外解释。"
            ),
            user_prompt=(
                "请基于以下全部数据生成总结和建议。返回 JSON 对象，字段固定为："
                "summary（字符串，200字以内），suggestion（字符串，按数字序号分点，不超过5点）。\n"
                f"{data_markdown}"
            ),
            output_format=LMOutputFormat.JSON,
            response_format={"type": "json_object"},
            max_tokens=1024,
        )
    )
    summary = _json_field_text(response.parsed, "summary")
    suggestion = _json_field_text(response.parsed, "suggestion")
    summary = _clean_llm_markdown(summary)
    suggestion = _clean_llm_markdown(suggestion)
    heading = f"## {section_title}\n\n" if section_title else ""

    return (
        f"{heading}"
        "**总结**：\n\n"
        f"{summary}\n\n"
        "**建议**：\n\n"
        f"{suggestion}\n"
    )


def _json_field_text(payload: Any, field_name: str) -> str:
    if not isinstance(payload, dict):
        return ""
    value = payload.get(field_name)
    if isinstance(value, list):
        return "\n".join(str(item).strip() for item in value if str(item).strip())
    if value is None:
        return ""
    return str(value).strip()


def _clean_llm_markdown(value: str) -> str:
    raw_lines = value.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    lines: list[str] = []
    for index, raw_line in enumerate(raw_lines):
        line = raw_line.rstrip()
        if not line.strip():
            next_line = _next_nonblank_line(raw_lines[index + 1 :])
            if lines and _is_markdown_list_item(lines[-1]) and _is_markdown_list_item(next_line):
                continue
            if lines and lines[-1]:
                lines.append("")
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def _next_nonblank_line(lines: list[str]) -> str:
    for line in lines:
        if line.strip():
            return line.rstrip()
    return ""


def _is_markdown_list_item(line: str) -> bool:
    return bool(LIST_ITEM_RE.match(line))


def _build_table_pie_chart_markdown(
    *,
    table: dict[str, Any],
    label_key: str,
    value_meta_key: str,
    value_key: str,
    title: str,
    filename_prefix: str,
    aggregate_by_label: bool = False,
) -> str:
    slices = _table_numeric_slices(
        table,
        label_key,
        value_meta_key,
        value_key,
        aggregate_by_label=aggregate_by_label,
    )
    chart_path = _render_pie_chart_png(
        slices=slices,
        title=title,
        filename_prefix=filename_prefix,
    )
    return f"![]({chart_path}){{width=12cm align=center}}"


def _table_numeric_slices(
    table: dict[str, Any],
    label_key: str,
    value_meta_key: str,
    value_key: str,
    *,
    aggregate_by_label: bool = False,
) -> list[tuple[str, float]]:
    rows = _table_rows(table)
    if aggregate_by_label:
        values_by_label: dict[str, float] = {}
    else:
        slices: list[tuple[str, float]] = []
    for row in rows:
        label = str(row.get(label_key) or "未命名")
        value = _row_meta_number(row, value_meta_key)
        if value == 0:
            value = _to_number(row.get(value_key))
        if value <= 0:
            continue
        if aggregate_by_label:
            values_by_label[label] = values_by_label.get(label, 0.0) + value
        else:
            slices.append((label, value))
    if aggregate_by_label:
        return sorted(values_by_label.items(), key=lambda item: item[1], reverse=True)
    return slices


def _render_pie_chart_png(
    *,
    slices: list[tuple[str, float]],
    title: str,
    filename_prefix: str,
) -> Path:
    CHART_OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    payload = {"title": title, "slices": slices}
    digest = hashlib.sha1(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:12]
    output_path = CHART_OUTPUT_ROOT / f"{filename_prefix}-{digest}.png"
    if output_path.exists():
        return output_path

    configure_matplotlib_cjk_font()
    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    if slices:
        labels = [label for label, _ in slices]
        values = [value for _, value in slices]
        ax.pie(
            values,
            labels=labels,
            autopct="%1.1f%%",
            startangle=90,
            counterclock=False,
            textprops={"fontsize": 9},
        )
    else:
        ax.text(0.5, 0.5, "暂无数据", ha="center", va="center", fontsize=12)
    ax.set_title(title, fontsize=13, pad=12)
    ax.axis("equal")
    fig.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return output_path


def _build_disposal_rate_line_chart_markdown(table: dict[str, Any]) -> str:
    rows = _aggregate_disposal_rows_by_scene(table)
    scenes = [row["scene_name"] for row in rows]
    disposal_counts = [row["disposal_count"] for row in rows]
    disposal_shares = [row["disposal_share"] for row in rows]
    option = {
        "title": {"text": "处置率统计"},
        "xAxis": {"data": scenes, "axisLabel": _build_category_axis_label(scenes)},
        "yAxis": [
            _build_value_axis("处置次数", disposal_counts),
            _build_value_axis("处置占比", disposal_shares),
        ],
        "series": [
            {"name": "处置次数", "data": disposal_counts, "color": "#d62728"},
            {"name": "处置占比", "data": disposal_shares, "color": "#1f77b4"},
        ],
    }
    chart_path = _render_disposal_rate_line_chart_png(
        scenes=scenes,
        disposal_counts=disposal_counts,
        disposal_shares=disposal_shares,
        option=option,
    )
    return f"![]({chart_path}){{width=14cm align=center}}"


def _aggregate_disposal_rows_by_scene(table: dict[str, Any]) -> list[dict[str, Any]]:
    by_scene: dict[str, dict[str, float]] = {}
    for row in _table_rows(table):
        scene_name = str(row.get("scene_name") or "未命名")
        bucket = by_scene.setdefault(
            scene_name,
            {"occurrence_count": 0.0, "disposal_count": 0.0},
        )
        bucket["occurrence_count"] += _row_meta_number(
            row,
            "occurrence_count_value",
            fallback_key="occurrence_count",
        )
        bucket["disposal_count"] += _row_meta_number(
            row,
            "disposal_count_value",
            fallback_key="disposal_count",
        )

    aggregated: list[dict[str, Any]] = []
    for scene_name, bucket in by_scene.items():
        occurrence_count = bucket["occurrence_count"]
        disposal_count = bucket["disposal_count"]
        disposal_share = round(disposal_count / occurrence_count * 100, 1) if occurrence_count else 0.0
        aggregated.append(
            {
                "scene_name": scene_name,
                "occurrence_count": _compact_number(occurrence_count),
                "disposal_count": _compact_number(disposal_count),
                "disposal_share": _compact_number(disposal_share),
            }
        )
    aggregated.sort(key=lambda row: float(row["occurrence_count"]), reverse=True)
    return aggregated


def _render_disposal_rate_line_chart_png(
    *,
    scenes: list[str],
    disposal_counts: list[float],
    disposal_shares: list[float],
    option: dict[str, Any],
) -> Path:
    CHART_OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(
        json.dumps(option, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:12]
    output_path = CHART_OUTPUT_ROOT / f"algorithm-disposal-rate-{digest}.png"
    if output_path.exists():
        return output_path

    configure_matplotlib_cjk_font()
    fig, left_ax = plt.subplots(figsize=(8.2, 4.4))
    right_ax = left_ax.twinx()
    count_axis, share_axis = option["yAxis"]
    x_indexes = list(range(len(scenes)))

    if scenes:
        count_line = left_ax.plot(
            x_indexes,
            disposal_counts,
            color="#d62728",
            linewidth=2.2,
            marker="o",
            markersize=4,
            label="处置次数",
        )[0]
        share_line = right_ax.plot(
            x_indexes,
            disposal_shares,
            color="#1f77b4",
            linewidth=2.2,
            marker="o",
            markersize=4,
            label="处置占比",
        )[0]
        left_ax.legend(handles=[count_line, share_line], loc="upper center", ncol=2, frameon=False)
    else:
        left_ax.text(0.5, 0.5, "暂无数据", ha="center", va="center", fontsize=12)

    left_ax.set_title(str(option["title"]["text"]), fontsize=13, pad=12)
    left_ax.set_ylabel("处置次数", color="#d62728")
    right_ax.set_ylabel("处置占比（%）", color="#1f77b4")
    left_ax.set_ylim(count_axis["min"], count_axis["max"])
    right_ax.set_ylim(share_axis["min"], share_axis["max"])
    left_ax.set_yticks(_axis_ticks(count_axis))
    right_ax.set_yticks(_axis_ticks(share_axis))
    left_ax.grid(True, axis="y", linestyle="--", alpha=0.35)

    label_style = option["xAxis"].get("axisLabel", {})
    interval = int(label_style.get("interval", 0))
    visible_indexes = [index for index in x_indexes if index % (interval + 1) == 0]
    left_ax.set_xticks(visible_indexes)
    left_ax.set_xticklabels(
        [scenes[index] for index in visible_indexes],
        rotation=int(label_style.get("rotate", 0)),
        ha="right" if label_style.get("rotate", 0) else "center",
    )
    fig.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return output_path


def _build_category_axis_label(labels: list[str]) -> dict[str, Any]:
    count = len(labels)
    if count <= 5:
        return {"interval": 0, "rotate": 0}
    if count <= 10:
        return {"interval": 0, "rotate": 30}
    return {"interval": 1, "rotate": 30}


def _sum_disposal_totals(table: dict[str, Any]) -> tuple[float | int, float | int]:
    occurrence_total = 0.0
    disposal_total = 0.0
    for row in _table_rows(table):
        occurrence_total += _row_meta_number(
            row,
            "occurrence_count_value",
            fallback_key="occurrence_count",
        )
        disposal_total += _row_meta_number(
            row,
            "disposal_count_value",
            fallback_key="disposal_count",
        )
    return _compact_number(occurrence_total), _compact_number(disposal_total)


def _table_rows(table: dict[str, Any]) -> list[dict[str, Any]]:
    rows = table.get("rows")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _row_meta_number(row: dict[str, Any], key: str, fallback_key: str | None = None) -> float:
    meta = row.get("meta")
    if isinstance(meta, dict):
        value = _to_number(meta.get(key))
        if value != 0:
            return value
    if fallback_key is not None:
        return _to_number(row.get(fallback_key))
    return 0.0


def _analysis_tables_markdown(analysis: AnalysisResult) -> str:
    tables = [
        analysis.flight_stat_overall,
        analysis.flight_stat_day_trend,
        analysis.flight_stat_department_share,
        analysis.media_collection_summary,
        analysis.algorithm_recognition_overall,
        analysis.algorithm_recognition_distribution,
        analysis.algorithm_disposal_summary,
        analysis.algorithm_high_frequency_locations,
        analysis.algorithm_high_frequency_time_slots,
        analysis.algorithm_push_events,
    ]
    return "\n\n".join(
        dict_table_to_markdown(table, title_level=3)
        for table in tables
        if table
    )

_REPORT_TEMPLATE = (
    ("", build_report_meta_section),
    ("一、总体概况", build_overview_section),
    ("二、总体飞行数据统计", build_flight_stat_overall_section),
    ("三、每日飞行趋势", build_flight_stat_day_trend_section),
    ("四、部门飞行占比", build_department_share_section),
    ("五、算法识别数据统计", build_algorithm_stat_overall_section),
    ("六、处置率统计", build_disposal_rate_section),
    ("七、高频案发点和高频案发时间段统计", build_hotspot_section),
    ("八、图片与视频采集数据", build_media_section),
    ("九、总结与建议", build_summary_section),
)


def _meta_line_block(block_id: str, label: str, value: str) -> ParagraphBlock:
    return ParagraphBlock(
        id=block_id,
        runs=[
            TextRun(text=label, bold=True),
            TextRun(text=value),
        ],
    )


def _format_zh_date(value: datetime) -> str:
    return f"{value.year:04d} 年 {value.month:02d} 月 {value.day:02d} 日"


def _format_period_text(filt: NormalizedFilter) -> str:
    if filt.period is None:
        return ""
    return f"{_format_zh_date(filt.period.start)} — {_format_zh_date(filt.period.end)}"


def _build_data_scope_text(filt: NormalizedFilter) -> str:
    if filt.dimension.scope == "department" and filt.dept_names:
        scope = "、".join(filt.dept_names)
        return f"{scope}权限内无人机飞行、算法识别、图片 / 视频采集全量数据"
    if filt.dimension.scope == "pilot" and filt.dimension.pilot_ids:
        pilots = "、".join(str(pilot_id) for pilot_id in filt.dimension.pilot_ids)
        return f"飞手 {pilots} 权限内无人机飞行、算法识别、图片 / 视频采集全量数据"
    return "全县权限内无人机飞行、算法识别、图片 / 视频采集全量数据"
