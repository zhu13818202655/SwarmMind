from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from swarmmind.domains.fly_report.schemas import (
    AnalysisResult,
    NormalizedFilter,
    RawDataset,
)
from swarmmind.models.table import DataTable, TableColumn

# TODO 怎么定义高频
_HIGH_FREQUENCY_MAX_ROWS = 5
_HIGH_FREQUENCY_MIN_OCCURRENCES = 1


def analyze(raw: RawDataset, filt: NormalizedFilter) -> AnalysisResult:

    # 总体飞行数据统计(范围内部门)
    flight_stat_overall = build_flight_stat_overall(raw, filt)
    # 每日飞行趋势
    flight_stat_day_trend = build_flight_stat_day_trend(raw, filt)
    # 部门飞行时长占比
    flight_stat_department_share = build_flight_stat_department_share(raw, filt)
    # 图片视频采集统计
    media_collection_summary = build_media_collection_summary(raw, filt)
    # 算法识别数据汇总
    algorithm_recognition_overall = build_algorithm_recognition_overall(raw, filt)
    # 算法识别分布
    algorithm_recognition_distribution = build_algorithm_recognition_distribution(raw, filt)
    # 算法处置统计
    algorithm_disposal_summary = build_algorithm_disposal_summary(raw, filt)
    # 高频案发点统计
    algorithm_high_frequency_locations = build_algorithm_high_frequency_locations(raw, filt)
    # 高频案时间段统计
    algorithm_high_frequency_time_slots = build_algorithm_high_frequency_time_slots(raw, filt)
    # 算法推送事件
    algorithm_push_events = build_algorithm_push_events(raw, filt)

    return AnalysisResult(
        flight_stat_overall=flight_stat_overall,
        flight_stat_day_trend=flight_stat_day_trend,
        flight_stat_department_share=flight_stat_department_share,
        media_collection_summary=media_collection_summary,
        algorithm_recognition_overall=algorithm_recognition_overall,
        algorithm_recognition_distribution=algorithm_recognition_distribution,
        algorithm_disposal_summary=algorithm_disposal_summary,
        algorithm_high_frequency_locations=algorithm_high_frequency_locations,
        algorithm_high_frequency_time_slots=algorithm_high_frequency_time_slots,
        algorithm_push_events=algorithm_push_events,
    )


def build_flight_stat_overall(raw: RawDataset, filt: NormalizedFilter) -> dict[str, Any]:
    cur = _aggregate_department_payload(raw.current.get("fly_statis", {}))
    prev = _aggregate_department_payload(raw.previous.get("fly_statis", {}))
    cur_job_logs = raw.current.get("fly_job_logs", {})
    prev_job_logs = raw.previous.get("fly_job_logs", {})

    def records(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, dict) and isinstance(payload.get("records"), list):
            return [item for item in payload["records"] if isinstance(item, dict)]
        return []

    def number(value: Any) -> float | None:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def exception_count(log_records: list[dict[str, Any]]) -> int:
        return sum(1 for item in log_records if str(item.get("status")) == "4")

    def display(value: float | int | None, unit: str, precision: int = 1) -> str:
        if value is None:
            return ""
        if precision == 0:
            text = str(int(round(float(value))))
        else:
            text = f"{float(value):.{precision}f}".rstrip("0").rstrip(".")
        return f"{text} {unit}" if unit else text

    cur_records = records(cur_job_logs)
    prev_records = records(prev_job_logs)

    cur_completed_durations = _completed_flight_duration_minutes(cur_records)
    prev_completed_durations = _completed_flight_duration_minutes(prev_records)

    # START 2026-06-09
    # 这是之前的统计口径，直接用 fly_statis 里的 num_total 和 fly_time_total 字段。现在改成从日志记录里统计，所以注释掉了。
    # cur_flight_count = number(cur.get("num_total"))
    # prev_flight_count = number(prev.get("num_total"))
    # cur_flight_hours = number(cur.get("fly_time_total"))
    # prev_flight_hours = number(prev.get("fly_time_total"))
    # END 2026-06-09

    # Derive flight count and hours from job log records (status=2) so that
    # the totals are consistent with the per-day trend table.  Fall back to
    # the fly_statis API values only when log records yield nothing.
    cur_flight_count_from_logs = float(len(cur_completed_durations))
    prev_flight_count_from_logs = float(len(prev_completed_durations))
    cur_flight_hours_from_logs = round(sum(d / 60 for d in cur_completed_durations), 2)
    prev_flight_hours_from_logs = round(sum(d / 60 for d in prev_completed_durations), 2)

    cur_flight_count = cur_flight_count_from_logs or number(cur.get("num_total"))
    prev_flight_count = prev_flight_count_from_logs or number(prev.get("num_total"))
    cur_flight_hours = cur_flight_hours_from_logs or number(cur.get("fly_time_total"))
    prev_flight_hours = prev_flight_hours_from_logs or number(prev.get("fly_time_total"))

    values: dict[str, tuple[str, float | None, float | None, str, int]] = {
        "flight_count": ("飞行总次数", cur_flight_count, prev_flight_count, "次", 0),
        "flight_time": ("飞行总时长", cur_flight_hours, prev_flight_hours, "小时", 1),
        "avg_flight_duration": (
            "平均飞行时长",
            round(cur_flight_hours * 60 / cur_flight_count, 2)
            if cur_flight_hours is not None and cur_flight_count
            else 0,
            round(prev_flight_hours * 60 / prev_flight_count, 2)
            if prev_flight_hours is not None and prev_flight_count
            else 0,
            "分钟",
            1,
        ),
        "max_flight_duration": (
            "最长飞行时长",
            max(cur_completed_durations) if cur_completed_durations else 0,
            max(prev_completed_durations) if prev_completed_durations else 0,
            "分钟",
            1,
        ),
        "min_flight_duration": (
            "最短飞行时长",
            min(cur_completed_durations) if cur_completed_durations else 0,
            min(prev_completed_durations) if prev_completed_durations else 0,
            "分钟",
            1,
        ),
        "flight_mileage": (
            "飞行总里程",
            number(cur.get("fly_mileage_total")),
            number(prev.get("fly_mileage_total")),
            "公里",
            1,
        ),
        "route_plan_count": (
            "航线 / 航点总数",
            number(cur.get("route_plan_count")),
            number(prev.get("route_plan_count")),
            "个",
            0,
        ),
        "exception_count": (
            "异常告警次数",
            float(exception_count(cur_records)),
            float(exception_count(prev_records)),
            "次",
            0,
        ),
    }

    table = DataTable(
        title="总体飞行统计概览",
        columns=[
            TableColumn(key="metric", label="统计指标"),
            TableColumn(key="current", label=_period_table_label(filt, current=True)),
            TableColumn(key="previous", label=_period_table_label(filt, current=False)),
            TableColumn(key="change", label="环比变化"),
        ],
    )

    for key, (label, current, previous, unit, precision) in values.items():
        change_text, row_trend, change_pct = _format_change(current, previous, unit, precision)
        change_value = current - previous if current is not None and previous is not None else None
        table.add_row(
            {
                "metric": label,
                "current": display(current, unit, precision),
                "previous": display(previous, unit, precision),
                "change": change_text,
            },
            key=key,
            meta={
                "unit": unit,
                "current_value": current,
                "previous_value": previous,
                "change_value": change_value,
                "change_pct": change_pct,
                "trend": row_trend,
            },
        )

    return table.to_dict()


def build_flight_stat_day_trend(raw: RawDataset, filt: NormalizedFilter) -> dict[str, Any]:
    cur_records = _job_log_records(raw.current.get("fly_job_logs", {}))
    daily_stats = {
        day: {"flight_count": 0, "flight_hours": 0.0, "exception_count": 0}
        for day in _period_date_keys(filt)
    }

    for record in cur_records:
        start_time = _parse_dikong_datetime(record.get("start_time"))
        if start_time is None:
            continue

        date_key = start_time.strftime("%Y-%m-%d")
        if date_key not in daily_stats:
            continue

        status = str(record.get("status"))
        stat = daily_stats[date_key]
        if status == "4":
            stat["exception_count"] += 1
            continue
        if status != "2":
            continue

        stat["flight_count"] += 1
        stop_time = _parse_dikong_datetime(record.get("stop_time"))
        if stop_time is None or stop_time < start_time:
            continue
        stat["flight_hours"] += (stop_time - start_time).total_seconds() / 3600

    table = DataTable(
        title="每日飞行趋势",
        columns=[
            TableColumn(key="date", label="日期"),
            TableColumn(key="flight_count", label="飞行次数"),
            TableColumn(key="flight_hours", label="飞行时长（小时）"),
            TableColumn(key="exception_count", label="异常次数"),
        ],
    )

    for date_key in sorted(daily_stats):
        stat = daily_stats[date_key]
        flight_hours = round(float(stat["flight_hours"]), 2)
        table.add_row(
            {
                "date": datetime.strptime(date_key, "%Y-%m-%d").strftime("%m-%d"),
                "flight_count": stat["flight_count"],
                "flight_hours": flight_hours,
                "exception_count": stat["exception_count"],
            },
            key=date_key,
            meta={
                "date_value": date_key,
                "flight_count_value": stat["flight_count"],
                "flight_hours_value": flight_hours,
                "exception_count_value": stat["exception_count"],
            },
        )

    return table.to_dict()


def build_flight_stat_department_share(raw: RawDataset, filt: NormalizedFilter) -> dict[str, Any]:
    cur_records = _job_log_records(raw.current.get("fly_job_logs", {}))
    department_hours: dict[str, float] = {}

    for record in cur_records:
        if str(record.get("status")) != "2":
            continue

        duration_hours = _completed_flight_duration_hours(record)
        if duration_hours is None:
            continue

        department_names = _department_names_from_job_log(record)
        if not department_names:
            continue
        allocated_hours = duration_hours / len(department_names)
        for department_name in department_names:
            department_hours[department_name] = department_hours.get(department_name, 0.0) + allocated_hours

    total_hours = sum(department_hours.values())
    rows = sorted(department_hours.items(), key=lambda item: item[1], reverse=True)

    table = DataTable(
        title="部门飞行时长占比",
        columns=[
            TableColumn(key="department_name", label="部门名称"),
            TableColumn(key="flight_hours", label="飞行时长（小时）"),
            TableColumn(key="share", label="占比"),
        ],
    )

    for department_name, hours in rows:
        flight_hours = round(hours, 1)
        share_value = round(hours / total_hours * 100, 1) if total_hours else 0.0
        table.add_row(
            {
                "department_name": department_name,
                "flight_hours": flight_hours,
                "share": f"{share_value:.1f}%",
            },
            key=department_name,
            meta={
                "flight_hours_value": flight_hours,
                "share_value": share_value,
            },
        )

    return table.to_dict()


def build_media_collection_summary(raw: RawDataset, filt: NormalizedFilter) -> dict[str, Any]:
    cur = _media_static_payload(raw.current.get("media_static", {}))
    prev = _media_static_payload(raw.previous.get("media_static", {}))

    cur_pic_count = _number_from_keys(cur, "picCount", "pic_count", "imageCount", "image_count")
    prev_pic_count = _number_from_keys(prev, "picCount", "pic_count", "imageCount", "image_count")
    cur_labeled_pic_count = _number_from_keys(
        cur,
        "picLableCount",
        "picLabelCount",
        "pic_label_count",
        "labeledPicCount",
        "labelledPicCount",
    )
    prev_labeled_pic_count = _number_from_keys(
        prev,
        "picLableCount",
        "picLabelCount",
        "pic_label_count",
        "labeledPicCount",
        "labelledPicCount",
    )
    cur_video_count = _number_from_keys(cur, "videoCount", "video_count")
    prev_video_count = _number_from_keys(prev, "videoCount", "video_count")
    cur_video_duration = _number_from_keys(
        cur,
        "videoDurationMinute",
        "videoDurationMinutes",
        "videoTotalDurationMinute",
        "videoTotalDurationMinutes",
        "videoTimeTotalMinute",
        "videoTimeTotalMinutes",
        "videoDuration",
        "videoTotalDuration",
        "videoTimeTotal",
    )

    values: dict[str, tuple[str, float | None, float | None, str, float | None]] = {
        "image_collection_count": ("图片采集总张数", cur_pic_count, prev_pic_count, "张", None),
        "labeled_image_count": ("标注图片数量", cur_labeled_pic_count, prev_labeled_pic_count, "张", None),
        "video_collection_count": ("视频采集总数", cur_video_count, prev_video_count, "条", cur_video_duration),
    }

    table = DataTable(
        title="图片视频采集统计",
        columns=[
            TableColumn(key="statistic_category", label="统计类别"),
            TableColumn(key="count", label="数量"),
            TableColumn(key="total_duration", label="总时长"),
            TableColumn(key="average_duration", label="平均时长"),
            TableColumn(key="change", label="环比变化"),
        ],
    )

    for key, (label, current, previous, unit, total_duration) in values.items():
        change_text, row_trend, change_pct = _format_change(current, previous, unit, precision=0)
        average_duration = (
            round(total_duration / current, 1)
            if total_duration is not None and current not in (None, 0)
            else None
        )
        table.add_row(
            {
                "statistic_category": label,
                "count": _display_optional_count(current, unit),
                "total_duration": _display_optional_minutes(total_duration),
                "average_duration": _display_optional_minutes(average_duration),
                "change": change_text,
            },
            key=key,
            meta={
                "unit": unit,
                "current_value": current,
                "previous_value": previous,
                "change_value": current - previous if current is not None and previous is not None else None,
                "change_pct": change_pct,
                "trend": row_trend,
                "total_duration_minutes_value": total_duration,
                "average_duration_minutes_value": average_duration,
            },
        )

    return table.to_dict()


def build_algorithm_recognition_overall(raw: RawDataset, filt: NormalizedFilter) -> dict[str, Any]:
    cur_records = [item["record"] for item in _warn_static_records(raw.current.get("warn_static", {}), filt)]
    prev_records = [item["record"] for item in _warn_static_records(raw.previous.get("warn_static", {}), filt)]

    values: dict[str, tuple[str, float, float, str, int]] = {
        "recognition_count": (
            "识别总次数",
            float(len(cur_records)),
            float(len(prev_records)),
            "次",
            0,
        ),
        "recognized_target_count": (
            "识别目标总数",
            _recognized_target_count(cur_records),
            _recognized_target_count(prev_records),
            "个",
            0,
        ),
    }

    table = DataTable(
        title="总的算法识别数据汇总",
        columns=[
            TableColumn(key="metric", label="统计指标"),
            TableColumn(key="current", label=_period_table_label(filt, current=True)),
            TableColumn(key="previous", label=_period_table_label(filt, current=False)),
            TableColumn(key="change", label="环比变化"),
        ],
    )

    for key, (label, current, previous, unit, precision) in values.items():
        change_text, row_trend, change_pct = _format_change(current, previous, unit, precision)
        table.add_row(
            {
                "metric": label,
                "current": _display_number(current, unit, precision),
                "previous": _display_number(previous, unit, precision),
                "change": change_text,
            },
            key=key,
            meta={
                "unit": unit,
                "current_value": current,
                "previous_value": previous,
                "change_value": current - previous,
                "change_pct": change_pct,
                "trend": row_trend,
            },
        )

    return table.to_dict()


def build_algorithm_recognition_distribution(raw: RawDataset, filt: NormalizedFilter) -> dict[str, Any]:
    records = _warn_static_records(raw.current.get("warn_static", {}), filt)
    by_algorithm_department: dict[tuple[str, str], dict[str, Any]] = {}

    for item in records:
        record = item["record"]
        algorithm_name = _algorithm_name(record)
        if not algorithm_name:
            continue
        department_name = item["department_name"]
        key = (algorithm_name, department_name)
        bucket = by_algorithm_department.setdefault(
            key,
            {"recognized_count": 0.0},
        )
        bucket["recognized_count"] += _recognized_target_count([record])

    total_count = sum(float(item["recognized_count"]) for item in by_algorithm_department.values())
    rows = sorted(
        by_algorithm_department.items(),
        key=lambda item: float(item[1]["recognized_count"]),
        reverse=True,
    )

    table = DataTable(
        title="算法识别统计",
        columns=[
            TableColumn(key="algorithm_name", label="算法名称"),
            TableColumn(key="recognized_count", label="识别数量"),
            TableColumn(key="share", label="占比"),
            TableColumn(key="department_name", label="使用部门"),
        ],
    )

    for (algorithm_name, department_name), bucket in rows:
        recognized_count = int(bucket["recognized_count"])
        share_value = round(recognized_count / total_count * 100, 1) if total_count else 0.0
        table.add_row(
            {
                "algorithm_name": algorithm_name,
                "department_name": department_name,
                "recognized_count": recognized_count,
                "share": f"{share_value:.1f}%",
            },
            key=f"{algorithm_name}:{department_name}",
            meta={
                "recognized_count_value": recognized_count,
                "share_value": share_value,
            },
        )

    return table.to_dict()


def build_algorithm_disposal_summary(raw: RawDataset, filt: NormalizedFilter) -> dict[str, Any]:
    records = _warn_static_records(raw.current.get("warn_static", {}), filt)
    by_scene: dict[tuple[str, str], dict[str, int]] = {}

    for item in records:
        record = item["record"]
        scene_name = _algorithm_name(record)
        department_name = item["department_name"]
        if not scene_name:
            continue
        key = (scene_name, department_name)
        bucket = by_scene.setdefault(key, {"occurrence_count": 0, "disposal_count": 0})
        bucket["occurrence_count"] += 1
        if str(record.get("status")) == "2":  # 0已识别 1已复核  2已处理
            bucket["disposal_count"] += 1

    rows = sorted(by_scene.items(), key=lambda item: item[1]["occurrence_count"], reverse=True)
    table = DataTable(
        title="算法处置统计",
        columns=[
            TableColumn(key="scene_name", label="场景名称"),
            TableColumn(key="department_name", label="使用部门"),
            TableColumn(key="occurrence_count", label="发生次数"),
            TableColumn(key="disposal_count", label="处置次数"),
            TableColumn(key="disposal_share", label="处置占比"),
        ],
    )

    for (scene_name, department_name), bucket in rows:
        occurrence_count = bucket["occurrence_count"]
        disposal_count = bucket["disposal_count"]
        disposal_share_value = round(disposal_count / occurrence_count * 100, 1) if occurrence_count else 0.0
        table.add_row(
            {
                "scene_name": scene_name,
                "department_name": department_name,
                "occurrence_count": occurrence_count,
                "disposal_count": disposal_count,
                "disposal_share": _format_percent(disposal_share_value),
            },
            key=f"{scene_name}:{department_name}",
            meta={
                "occurrence_count_value": occurrence_count,
                "disposal_count_value": disposal_count,
                "disposal_share_value": disposal_share_value,
            },
        )

    return table.to_dict()


def build_algorithm_high_frequency_locations(raw: RawDataset, filt: NormalizedFilter) -> dict[str, Any]:
    records = _warn_static_records(raw.current.get("warn_static", {}), filt)
    by_scene_department_location: dict[tuple[str, str, str], int] = {}

    for item in records:
        record = item["record"]
        scene_name = _algorithm_name(record)
        if not scene_name:
            continue
        department_name = item["department_name"]
        location = _location_from_record(record)
        key = (scene_name, department_name, location)
        by_scene_department_location[key] = by_scene_department_location.get(key, 0) + 1

    rows = _top_high_frequency_rows(by_scene_department_location.items())
    table = DataTable(
        title="高频案发点统计",
        columns=[
            TableColumn(key="scene_name", label="场景名称"),
            TableColumn(key="department_name", label="使用部门"),
            TableColumn(key="location", label="地点"),
            TableColumn(key="occurrence_count", label="发生次数"),
        ],
    )

    for (scene_name, department_name, location), occurrence_count in rows:
        table.add_row(
            {
                "scene_name": scene_name,
                "department_name": department_name,
                "location": location,
                "occurrence_count": occurrence_count,
            },
            key=f"{scene_name}:{department_name}:{location}",
            meta={"occurrence_count_value": occurrence_count},
        )

    return table.to_dict()


def build_algorithm_high_frequency_time_slots(raw: RawDataset, filt: NormalizedFilter) -> dict[str, Any]:
    records = _warn_static_records(raw.current.get("warn_static", {}), filt)
    by_scene_department_slot: dict[tuple[str, str, str], int] = {}

    for item in records:
        record = item["record"]
        scene_name = _algorithm_name(record)
        if not scene_name:
            continue
        occurrence_time = _parse_dikong_datetime(_occurrence_time_text(record))
        if occurrence_time is None:
            continue
        department_name = item["department_name"]
        time_slot = _high_frequency_time_slot(occurrence_time)
        key = (scene_name, department_name, time_slot)
        by_scene_department_slot[key] = by_scene_department_slot.get(key, 0) + 1

    rows = _top_high_frequency_rows(by_scene_department_slot.items())
    table = DataTable(
        title="高频案时间段统计",
        columns=[
            TableColumn(key="scene_name", label="场景名称"),
            TableColumn(key="department_name", label="使用部门"),
            TableColumn(key="time_slot", label="时间段"),
            TableColumn(key="occurrence_count", label="发生次数"),
        ],
    )

    for (scene_name, department_name, time_slot), occurrence_count in rows:
        table.add_row(
            {
                "scene_name": scene_name,
                "department_name": department_name,
                "time_slot": time_slot,
                "occurrence_count": occurrence_count,
            },
            key=f"{scene_name}:{department_name}:{time_slot}",
            meta={"occurrence_count_value": occurrence_count},
        )

    return table.to_dict()


def build_algorithm_push_events(raw: RawDataset, filt: NormalizedFilter) -> dict[str, Any]:
    # TODO 推送时间需要确认
    records = _warn_static_records(raw.current.get("warn_static", {}), filt)
    table = DataTable(
        title="算法推送事件",
        columns=[
            TableColumn(key="scene_name", label="场景名称"),
            TableColumn(key="department_name", label="使用部门"),
            TableColumn(key="occurrence_time", label="发生时间"),
            TableColumn(key="push_time", label="推送时间"),
        ],
    )

    pushed_records = [item for item in records if str(item["record"].get("push_status") or item["record"].get("pushStatus")) in {"1", "2"}]
    pushed_records.sort(key=lambda item: _occurrence_time_text(item["record"]), reverse=True)

    for item in pushed_records:
        record = item["record"]
        scene_name = _algorithm_name(record)
        if not scene_name:
            continue
        occurrence_time = _occurrence_time_text(record)
        push_time = _push_time_text(record) or occurrence_time
        table.add_row(
            {
                "scene_name": scene_name,
                "department_name": item["department_name"],
                "occurrence_time": occurrence_time,
                "push_time": push_time,
            },
            key=str(record.get("id") or f"{scene_name}:{occurrence_time}"),
        )

    return table.to_dict()


def _job_log_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict) and isinstance(payload.get("records"), list):
        return [item for item in payload["records"] if isinstance(item, dict)]
    return []


def _top_high_frequency_rows(
    rows: Any,
    *,
    min_occurrences: int = _HIGH_FREQUENCY_MIN_OCCURRENCES,
    max_rows: int = _HIGH_FREQUENCY_MAX_ROWS,
) -> list[Any]:
    sorted_rows = sorted(rows, key=lambda item: item[1], reverse=True)
    return [item for item in sorted_rows if item[1] >= min_occurrences][:max_rows]


def _warn_static_records(payload: Any, filt: NormalizedFilter) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []

    direct_records = payload.get("records")
    if isinstance(direct_records, list):
        return [
            {"record": item, "department_name": _department_name_from_record(item)}
            for item in direct_records
            if isinstance(item, dict)
        ]

    dept_name_by_id = {str(dept_id): name for dept_id, name in zip(filt.dept_ids, filt.dept_names)}
    rows: list[dict[str, Any]] = []
    for dept_id, dept_payload in payload.items():
        if not isinstance(dept_payload, dict):
            continue
        records = dept_payload.get("records")
        if not isinstance(records, list):
            continue
        department_name = dept_name_by_id.get(str(dept_id), str(dept_id))
        for record in records:
            if not isinstance(record, dict):
                continue
            rows.append(
                {
                    "record": record,
                    "department_name": _department_name_from_record(record) or department_name,
                }
            )
    return rows


def _department_name_from_record(record: dict[str, Any]) -> str:
    value = (
        record.get("dept_name")
        or record.get("deptName")
        or record.get("deptids_tag_name")
        or record.get("deptidsTagName")
    )
    return str(value).strip() if value else ""


def _algorithm_name(record: dict[str, Any]) -> str:
    value = (
        record.get("algorithm_name")
        or record.get("work_order_name")
    )
    return str(value).strip() if value else ""


def _location_from_record(record: dict[str, Any]) -> str:
    value = (
        record.get("address")
        or record.get("place")
        or record.get("road")
        or record.get("streetName")
        or record.get("street_name")
        or record.get("operLocation")
        or record.get("oper_location")
    )
    return str(value).strip() if value else ""


def _occurrence_time_text(record: dict[str, Any]) -> str:
    return str(record.get("create_time") or record.get("createTime") or "")


def _push_time_text(record: dict[str, Any]) -> str:
    value = (
        record.get("push_time")
        or record.get("pushTime")
        or record.get("approval_time")
        or record.get("approvalTime")
        or record.get("dispose_time")
        or record.get("disposeTime")
    )
    return str(value) if value else ""


def _media_static_payload(value: Any) -> dict[str, Any]:
    payload = _aggregate_department_payload(value)
    if isinstance(payload.get("raw"), dict):
        return payload["raw"]
    return payload


def _number_from_keys(payload: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        if key not in payload:
            continue
        value = payload.get(key)
        if value in (None, ""):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _percent_change_optional(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return round((current - previous) / abs(previous) * 100, 1)


def _display_optional_count(value: float | None, unit: str) -> str:
    if value is None:
        return "—"
    text = str(int(round(value))) if float(value).is_integer() else f"{value:.1f}".rstrip("0").rstrip(".")
    return f"{text} {unit}" if unit else text


def _display_optional_minutes(value: float | None) -> str:
    if value is None:
        return "—"
    text = str(int(round(value))) if float(value).is_integer() else f"{value:.1f}".rstrip("0").rstrip(".")
    return f"{text} 分钟"


def _high_frequency_time_slot(value: datetime) -> str:
    day_kind = "工作日" if value.weekday() < 5 else "休息日"
    hour = value.hour
    if 6 <= hour < 9:
        period = "早高峰"
    elif 9 <= hour < 12:
        period = "上午"
    elif 12 <= hour < 14:
        period = "中午"
    elif 14 <= hour < 18:
        period = "下午"
    elif 18 <= hour < 21:
        period = "晚高峰"
    elif 21 <= hour < 24:
        period = "夜间"
    else:
        period = "凌晨"
    return f"{day_kind}{period}"


def _recognized_target_count(records: list[dict[str, Any]]) -> float:
    return sum(_extra_result_value_sum(record.get("extra_result") or record.get("extraResult")) for record in records)


def _extra_result_value_sum(value: Any) -> float:
    if not value:
        return 0.0
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return 0.0
    if isinstance(value, dict):
        total = 0.0
        for item in value.values():
            if isinstance(item, list):
                total += len(item)
                continue
            try:
                total += float(item)
            except (TypeError, ValueError):
                continue
        return total
    return 0.0


def _percent_change(current: float, previous: float) -> float | None:
    if previous == 0:
        return None
    return round((current - previous) / abs(previous) * 100, 1)


def _display_number(value: float, unit: str, precision: int) -> str:
    if precision == 0:
        text = str(int(round(value)))
    else:
        text = f"{value:.{precision}f}".rstrip("0").rstrip(".")
    return f"{text} {unit}" if unit else text


def _change_display(change_pct: float | None, row_trend: str) -> str:
    if change_pct is None:
        return ""
    marker = {"up": "↑", "down": "↓", "flat": "-"}.get(row_trend, "")
    return f"{marker} {abs(change_pct):.1f}%" if marker else f"{change_pct:.1f}%"


def _format_value(value: float, precision: int) -> str:
    if precision == 0:
        return str(int(round(value)))
    return f"{value:.{precision}f}".rstrip("0").rstrip(".")


def _format_change(
    current: float | None,
    previous: float | None,
    unit: str = "",
    precision: int = 0,
) -> tuple[str, str, float | None]:
    """Compute QoQ change display, trend tag, and percent value.

    When ``previous == 0`` the percentage is undefined, so we fall back to
    showing the absolute delta with a 新增 / 减少 / 持平 prefix (方案 B+D).
    Returns ``(display_text, trend, change_pct)`` where ``trend`` is one of
    ``up`` / ``down`` / ``flat`` / ``new`` / ``unknown`` and ``change_pct``
    is ``None`` when not applicable.
    """
    if current is None or previous is None:
        return "", "unknown", None
    if previous == 0:
        if current == 0:
            return "持平", "flat", 0.0
        prefix = "新增" if current > 0 else "减少"
        sign = "+" if current > 0 else "-"
        unit_suffix = f" {unit}" if unit else ""
        return (
            f"{prefix} {sign}{_format_value(abs(current), precision)}{unit_suffix}",
            "new",
            None,
        )
    change_pct = round((current - previous) / abs(previous) * 100, 1)
    if current > previous:
        row_trend, marker = "up", "↑"
    elif current < previous:
        row_trend, marker = "down", "↓"
    else:
        row_trend, marker = "flat", "-"
    return f"{marker} {abs(change_pct):.1f}%", row_trend, change_pct


def _format_percent(value: float) -> str:
    if float(value).is_integer():
        return f"{int(value)}%"
    return f"{value:.1f}%"


def _period_date_keys(filt: NormalizedFilter) -> list[str]:
    start = filt.period.start.date()
    end = filt.period.end.date()
    if end < start:
        return []
    days = (end - start).days
    return [(start + timedelta(days=offset)).isoformat() for offset in range(days + 1)]


def  _department_names_from_job_log(record: dict[str, Any]) -> list[str]:
    # "deptidsTag": "22,23", "deptidsTagName": "垂直部门（单位）,经济实体",
    raw_names = record.get("deptids_tag_name", "")
    if not raw_names:
        return []
    names = [part.strip() for part in str(raw_names).split(",") if part.strip()]
    return names


def _completed_flight_duration_hours(record: dict[str, Any]) -> float | None:
    start_time = _parse_dikong_datetime(record.get("start_time"))
    stop_time = _parse_dikong_datetime(record.get("stop_time"))
    if start_time is None or stop_time is None or stop_time < start_time:
        return None
    return (stop_time - start_time).total_seconds() / 3600


def _period_table_label(filt: NormalizedFilter, *, current: bool) -> str:
    period_kind = getattr(getattr(filt, "period", None), "kind", None)
    if period_kind == "weekly":
        return "本周数据" if current else "上周数据"
    if period_kind == "monthly":
        return "本月数据" if current else "上月数据"
    return "本期数据" if current else "上期数据"


def _completed_flight_duration_minutes(records: list[dict[str, Any]]) -> list[float]:
    durations: list[float] = []
    for record in records:
        if str(record.get("status")) != "2":
            continue
        start_time = _parse_dikong_datetime(record.get("start_time"))
        stop_time = _parse_dikong_datetime(record.get("stop_time"))
        if start_time is None or stop_time is None or stop_time < start_time:
            continue
        durations.append(round((stop_time - start_time).total_seconds() / 60, 2))
    return durations


def _parse_dikong_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    if "." in normalized:
        normalized = normalized.split(".", 1)[0]
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(normalized, fmt)
        except ValueError:
            continue
    return None


def _aggregate_department_payload(value: Any) -> dict[str, Any]:
    """Aggregate endpoint payloads shaped as ``{dept_id: payload}`` for KPI extraction."""
    if not _is_department_payload_map(value):
        return value if isinstance(value, dict) else {}

    aggregate: dict[str, Any] = {}
    for payload in value.values():
        if isinstance(payload, dict):
            _merge_numeric_payload(aggregate, payload)
    return aggregate


def _is_department_payload_map(value: Any) -> bool:
    return isinstance(value, dict) and bool(value) and all(
        str(key).isdigit() and isinstance(payload, dict)
        for key, payload in value.items()
    )


def _merge_numeric_payload(target: dict[str, Any], payload: dict[str, Any]) -> None:
    for key, value in payload.items():
        if isinstance(value, dict):
            nested = target.setdefault(key, {})
            if isinstance(nested, dict):
                _merge_numeric_payload(nested, value)
            continue
        try:
            target[key] = float(target.get(key, 0) or 0) + float(value)
        except (ValueError, TypeError):
            target.setdefault(key, value)


def _to_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _trend(change: float | None) -> str:
    if change is None:
        return "unknown"
    if change > 0:
        return "up"
    if change < 0:
        return "down"
    return "flat"


__all__ = ["analyze"]
