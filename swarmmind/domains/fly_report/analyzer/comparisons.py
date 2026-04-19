"""Department / pilot dimension breakdown & cross-dimension comparisons.

DESIGN-2 §13 step 8 (M2 minimal scope):

- ``analyze_by_department(raw, filt)`` — given a :class:`RawDataset` whose
  ``current``/``previous`` dicts include a ``__by_department__`` block
  populated by :class:`DataFetcher` in fan-out mode, run the per-indicator
  KPI extraction once per department and emit:
    * ``by_department``: ``{dept_id: {"label": str, "kpis": [...]}}``
    * ``comparisons``: ranked list of dept-level comparison rows for the
      primary KPI (currently ``fly_count``), with ``rank``, ``vs_leader``
      and ``vs_previous`` fields.

Pilot-level analysis is intentionally not implemented yet — dikong does
not expose a per-pilot aggregation endpoint, so it will be added when
:mod:`data_fetcher` learns to do its own ``job/log/list`` fan-out.
"""

from __future__ import annotations

from typing import Any

from swarmmind.domains.fly_report.schemas import (
    NormalizedFilter,
    RawDataset,
)

# Key used by DataFetcher to attach per-dept payloads under raw.current /
# raw.previous without altering the schema.
PER_DEPT_KEY = "__by_department__"

# KPI name that drives department ranking (descending = best).
PRIMARY_RANK_KPI = "fly_count"


def analyze_by_department(
    raw: RawDataset,
    filt: NormalizedFilter,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Compute per-department KPIs and a ranked comparison list.

    Returns ``({}, [])`` when no per-department block is present in ``raw``.
    The aggregation logic for a single department is reused from the
    overall path so both code paths produce identical KPI rows.
    """

    # Local import avoids a circular dependency between aggregations and
    # this module (aggregations.analyze imports analyze_by_department).
    from swarmmind.domains.fly_report.analyzer.aggregations import (
        _algorithm_kpis,
        _device_health_kpis,
        _flight_kpis,
        _media_kpis,
    )

    cur_block = raw.current.get(PER_DEPT_KEY) or {}
    prev_block = raw.previous.get(PER_DEPT_KEY) or {}
    if not cur_block:
        return {}, []

    by_dept: dict[str, dict[str, Any]] = {}
    for dept_id, dept_current in cur_block.items():
        dept_id = str(dept_id)
        dept_previous = prev_block.get(dept_id, {})
        sub_raw = RawDataset(current=dept_current, previous=dept_previous)

        kpis: list[dict[str, Any]] = []
        if "flight" in filt.indicators:
            kpis.extend(_flight_kpis(sub_raw))
        if "algorithm" in filt.indicators:
            kpis.extend(_algorithm_kpis(sub_raw))
        if "media_image" in filt.indicators or "media_video" in filt.indicators:
            kpis.extend(_media_kpis(sub_raw))
        if "device_health" in filt.indicators:
            kpis.extend(_device_health_kpis(sub_raw))

        label = _dept_label(dept_current, dept_id)
        by_dept[dept_id] = {"label": label, "kpis": kpis}

    comparisons = _rank_departments(by_dept)
    return by_dept, comparisons


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _dept_label(payload: dict[str, Any], dept_id: str) -> str:
    """Best-effort dept label from the raw payload."""

    fly = payload.get("fly_statis") or {}
    name = fly.get("dept_name") or fly.get("deptName")
    return str(name) if name else f"部门 {dept_id}"


def _rank_departments(
    by_dept: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Rank departments by the primary KPI, recording diffs vs the leader."""

    rows: list[dict[str, Any]] = []
    for dept_id, info in by_dept.items():
        kpi = next(
            (k for k in info["kpis"] if k["name"] == PRIMARY_RANK_KPI),
            None,
        )
        if kpi is None or kpi.get("value") is None:
            continue
        rows.append(
            {
                "dept_id": dept_id,
                "label": info["label"],
                "kpi": PRIMARY_RANK_KPI,
                "current": kpi["value"],
                "previous": kpi.get("previous_value"),
                "change": kpi.get("change"),
                "change_pct": kpi.get("change_pct"),
            }
        )

    rows.sort(key=lambda r: r["current"], reverse=True)
    leader = rows[0]["current"] if rows else 0.0
    for idx, row in enumerate(rows, start=1):
        row["rank"] = idx
        row["vs_leader"] = round(row["current"] - leader, 4)
        row["vs_leader_pct"] = (
            round((row["current"] - leader) / leader * 100, 2)
            if leader
            else None
        )
    return rows


__all__ = ["analyze_by_department", "PER_DEPT_KEY", "PRIMARY_RANK_KPI"]
