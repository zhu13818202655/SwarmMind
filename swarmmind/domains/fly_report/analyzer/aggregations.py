"""Aggregation logic for "总体飞行周报" (overall weekly flight report).

Pure functions — no I/O, no LLM calls.  Given a :class:`RawDataset` (current
+ previous period raw payloads) and a :class:`NormalizedFilter`, produces an
:class:`AnalysisResult` with:

- ``overall``: aggregated KPIs for the current period
- ``kpis``: list of individual KPI dicts (name, value, unit, change, change_pct)
- ``comparisons``: period-over-period deltas
- ``anomalies``: simple threshold-based anomaly flags

Department / pilot breakdowns are deferred to later steps (M2).
"""

from __future__ import annotations

from typing import Any

from swarmmind.domains.fly_report.schemas import (
    AnalysisResult,
    NormalizedFilter,
    RawDataset,
)


def analyze(raw: RawDataset, filt: NormalizedFilter) -> AnalysisResult:
    """Top-level analysis entry point."""

    overall: dict[str, Any] = {}
    kpis: list[dict[str, Any]] = []
    comparisons: list[dict[str, Any]] = []
    anomalies: list[dict[str, Any]] = []

    if "flight" in filt.indicators:
        flight_kpis = _flight_kpis(raw)
        kpis.extend(flight_kpis)
        overall["flight"] = {k["name"]: k["value"] for k in flight_kpis}

    if "algorithm" in filt.indicators:
        algo_kpis = _algorithm_kpis(raw)
        kpis.extend(algo_kpis)
        overall["algorithm"] = {k["name"]: k["value"] for k in algo_kpis}

    if "media_image" in filt.indicators or "media_video" in filt.indicators:
        media_kpis = _media_kpis(raw)
        kpis.extend(media_kpis)
        overall["media"] = {k["name"]: k["value"] for k in media_kpis}

    if "device_health" in filt.indicators:
        health_kpis = _device_health_kpis(raw)
        kpis.extend(health_kpis)
        overall["device_health"] = {k["name"]: k["value"] for k in health_kpis}

    # Period-over-period comparison for all numeric KPIs.
    comparisons = _period_comparisons(kpis)

    # Simple anomaly detection.
    anomalies = _detect_anomalies(kpis, comparisons)

    # Optional per-department breakdown (DESIGN-2 §13 step 8 / M2). Activated
    # whenever DataFetcher attached a ``__by_department__`` block to ``raw``.
    from swarmmind.domains.fly_report.analyzer.comparisons import (
        analyze_by_department,
    )

    by_department, dept_rank = analyze_by_department(raw, filt)
    if dept_rank:
        comparisons = comparisons + [
            {"kind": "department_rank", **row} for row in dept_rank
        ]

    return AnalysisResult(
        overall=overall,
        kpis=kpis,
        comparisons=comparisons,
        anomalies=anomalies,
        by_department=by_department,
    )


# ---------------------------------------------------------------------------
# Per-indicator KPI extraction
# ---------------------------------------------------------------------------


def _safe_get(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Nested safe dict lookup."""
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key, default)
    return current


def _flight_kpis(raw: RawDataset) -> list[dict[str, Any]]:
    cur = raw.current.get("fly_statis", {})
    prev = raw.previous.get("fly_statis", {})

    fields = [
        ("fly_count", "num_total", "次", "飞行总次数"),
        ("fly_mileage", "fly_mileage_total", "km", "飞行总里程"),
        ("fly_time", "fly_time_total", "h", "飞行总时长"),
        ("drone_count", "drone_count", "台", "无人机数量"),
        ("drone_job_count", "drone_job_count", "次", "无人机任务数"),
    ]
    return [
        _make_kpi(name, cur.get(field), prev.get(field), unit, label)
        for name, field, unit, label in fields
    ]


def _algorithm_kpis(raw: RawDataset) -> list[dict[str, Any]]:
    cur_raw = raw.current.get("warn_static", {}).get("raw", {})
    prev_raw = raw.previous.get("warn_static", {}).get("raw", {})

    # The actual field names depend on the dikong response; use generic fallback.
    total_cur = _sum_values(cur_raw)
    total_prev = _sum_values(prev_raw)
    return [
        _make_kpi("algorithm_warn_total", total_cur, total_prev, "次", "算法告警总数"),
    ]


def _media_kpis(raw: RawDataset) -> list[dict[str, Any]]:
    cur_raw = raw.current.get("media_static", {}).get("raw", {})
    prev_raw = raw.previous.get("media_static", {}).get("raw", {})

    total_cur = _sum_values(cur_raw)
    total_prev = _sum_values(prev_raw)
    return [
        _make_kpi("media_total", total_cur, total_prev, "项", "媒体成果总数"),
    ]


def _device_health_kpis(raw: RawDataset) -> list[dict[str, Any]]:
    cur_raw = raw.current.get("hms_stats", {}).get("raw", {})
    prev_raw = raw.previous.get("hms_stats", {}).get("raw", {})

    total_cur = _sum_values(cur_raw)
    total_prev = _sum_values(prev_raw)
    return [
        _make_kpi("hms_alert_total", total_cur, total_prev, "次", "设备健康告警数"),
    ]


# ---------------------------------------------------------------------------
# KPI helpers
# ---------------------------------------------------------------------------


def _make_kpi(
    name: str,
    current_val: Any,
    previous_val: Any,
    unit: str,
    label: str,
) -> dict[str, Any]:
    """Build a single KPI dict with period-over-period delta."""

    cur = _to_float(current_val)
    prev = _to_float(previous_val)
    change = cur - prev if cur is not None and prev is not None else None
    change_pct: float | None = None
    if change is not None and prev and prev != 0:
        change_pct = round(change / abs(prev) * 100, 2)

    return {
        "name": name,
        "label": label,
        "value": cur,
        "previous_value": prev,
        "unit": unit,
        "change": change,
        "change_pct": change_pct,
    }


def _to_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _sum_values(d: dict[str, Any]) -> float:
    """Sum all numeric values in a flat dict."""
    total = 0.0
    for v in d.values():
        try:
            total += float(v)
        except (ValueError, TypeError):
            continue
    return total


# ---------------------------------------------------------------------------
# Comparisons & anomalies
# ---------------------------------------------------------------------------


def _period_comparisons(kpis: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Generate period-over-period comparison records."""
    return [
        {
            "kpi": k["name"],
            "label": k["label"],
            "current": k["value"],
            "previous": k["previous_value"],
            "change": k["change"],
            "change_pct": k["change_pct"],
            "trend": _trend(k["change"]),
        }
        for k in kpis
        if k["change"] is not None
    ]


def _trend(change: float | None) -> str:
    if change is None:
        return "unknown"
    if change > 0:
        return "up"
    if change < 0:
        return "down"
    return "flat"


def _detect_anomalies(
    kpis: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
    *,
    pct_threshold: float = 50.0,
) -> list[dict[str, Any]]:
    """Flag KPIs with large period-over-period swings."""
    anomalies: list[dict[str, Any]] = []
    for comp in comparisons:
        pct = comp.get("change_pct")
        if pct is not None and abs(pct) >= pct_threshold:
            anomalies.append(
                {
                    "kpi": comp["kpi"],
                    "label": comp["label"],
                    "change_pct": pct,
                    "severity": "high" if abs(pct) >= 100 else "medium",
                    "message": f"{comp['label']}环比变化 {pct:+.1f}%",
                }
            )
    return anomalies


__all__ = ["analyze"]
