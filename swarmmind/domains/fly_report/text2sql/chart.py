"""Lightweight auto-charting for Text-to-SQL results.

The pipeline tries to detect whether the query result is a *small tabular
comparison* (time series, week-over-week, per-day counts, …) and if so
renders a single PNG via Matplotlib. We deliberately keep the heuristic
small — the goal is "useful default chart" not "BI tool":

* ``rows`` must contain at least 2 records.
* Exactly one categorical / temporal x-axis column (string or datetime).
* At least one numeric y column. When the x looks like a date/time we
  draw a line chart; otherwise a bar chart.

The rendered PNG lands under :data:`CHART_OUTPUT_ROOT` (shared with the
report composer) and is exposed to clients via the static mount
``/v1/fly-reports/charts/<filename>`` configured in
``swarmmind.api.server``.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from swarmmind.domains.fly_report.chart import configure_matplotlib_cjk_font

logger = logging.getLogger(__name__)


CHART_OUTPUT_ROOT = (
    Path(__file__).resolve().parents[4]
    / "data"
    / "fly_report_artifacts"
    / "generated_charts"
)
CHART_URL_PREFIX = "/v1/fly-reports/charts"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ChartArtifact:
    """A rendered chart ready to be embedded in the assistant answer."""

    path: Path
    url: str
    chart_type: str  # "line" | "bar"
    x_column: str
    y_columns: tuple[str, ...]


def build_chart_for_text2sql(
    *,
    rows: list[dict[str, Any]],
    question: str,
    sql: str | None,
) -> ChartArtifact | None:
    """Return a rendered chart for ``rows`` if it looks chartable.

    Returns ``None`` when the result is a scalar / single row / has no
    suitable column pair, or when rendering fails for any reason.
    """
    plan = _plan_chart(rows)
    if plan is None:
        return None

    try:
        path = _render_chart(plan, question=question, sql=sql)
    except Exception:  # pragma: no cover - defensive
        logger.exception("fly_report.text2sql.chart_render_failed")
        return None

    url = f"{CHART_URL_PREFIX}/{path.name}"
    return ChartArtifact(
        path=path,
        url=url,
        chart_type=plan.chart_type,
        x_column=plan.x_column,
        y_columns=tuple(plan.y_columns),
    )


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------
_TIMELIKE_HINTS = ("date", "day", "time", "month", "week", "period", "ymd", "hour")
_CATEGORY_HINTS = (
    "name",
    "label",
    "type",
    "category",
    "department",
    "dept",
    "scene",
    "status",
    "group",
    "bucket",
)

_DATE_PATTERNS = (
    re.compile(r"^\d{4}-\d{1,2}(-\d{1,2})?$"),
    re.compile(r"^\d{4}/\d{1,2}(/\d{1,2})?$"),
    re.compile(r"^\d{4}\d{2}\d{2}$"),
    re.compile(r"^\d{4}-W\d{1,2}$"),
)


@dataclass
class _ChartPlan:
    chart_type: str
    x_column: str
    y_columns: list[str]
    x_values: list[Any]
    y_series: dict[str, list[float]]
    title: str


def _plan_chart(rows: list[dict[str, Any]]) -> _ChartPlan | None:
    if not rows or len(rows) < 2:
        return None
    columns = list(rows[0].keys())
    if len(columns) < 2:
        return None

    numeric_cols = [c for c in columns if _column_is_numeric(rows, c)]
    if not numeric_cols:
        return None

    # Pick an x column: prefer the first non-numeric column, with a bias
    # towards columns that look temporal / categorical by name.
    candidate_x = [c for c in columns if c not in numeric_cols]
    if not candidate_x:
        return None

    x_col = _pick_x_column(candidate_x)
    y_cols = [c for c in numeric_cols]
    if not y_cols:
        return None

    # Cap how many series we draw; the assistant chart is meant to be
    # glanceable, not a dashboard.
    y_cols = y_cols[:3]

    x_values = [r.get(x_col) for r in rows]
    y_series = {c: [_safe_float(r.get(c)) for r in rows] for c in y_cols}

    chart_type = "line" if _looks_temporal(x_col, x_values) else "bar"
    return _ChartPlan(
        chart_type=chart_type,
        x_column=x_col,
        y_columns=y_cols,
        x_values=x_values,
        y_series=y_series,
        title=_default_title(x_col, y_cols),
    )


def _pick_x_column(candidates: list[str]) -> str:
    for hint_group in (_TIMELIKE_HINTS, _CATEGORY_HINTS):
        for c in candidates:
            low = c.lower()
            if any(h in low for h in hint_group):
                return c
    return candidates[0]


def _column_is_numeric(rows: list[dict[str, Any]], col: str) -> bool:
    seen = 0
    for r in rows:
        v = r.get(col)
        if v is None:
            continue
        if isinstance(v, bool):
            return False
        if isinstance(v, (int, float)):
            seen += 1
            continue
        # Strings like "12" / "12.5" still count as numeric, but reject
        # date-like strings explicitly.
        if isinstance(v, str):
            s = v.strip()
            if not s or _looks_date_string(s):
                return False
            try:
                float(s)
            except ValueError:
                return False
            seen += 1
            continue
        return False
    return seen >= 1


def _looks_temporal(col: str, values: list[Any]) -> bool:
    low = col.lower()
    if any(h in low for h in _TIMELIKE_HINTS):
        return True
    for v in values:
        if isinstance(v, (_dt.date, _dt.datetime)):
            return True
        if isinstance(v, str) and _looks_date_string(v.strip()):
            return True
    return False


def _looks_date_string(s: str) -> bool:
    return any(p.match(s) for p in _DATE_PATTERNS)


def _safe_float(v: Any) -> float:
    if v is None:
        return 0.0
    if isinstance(v, bool):
        return float(v)
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return 0.0


def _default_title(x_col: str, y_cols: list[str]) -> str:
    if len(y_cols) == 1:
        return f"{y_cols[0]} by {x_col}"
    return f"{', '.join(y_cols)} by {x_col}"


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def _render_chart(
    plan: _ChartPlan, *, question: str, sql: str | None
) -> Path:
    CHART_OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    digest_payload = {
        "q": question,
        "sql": sql or "",
        "x": plan.x_column,
        "y": plan.y_columns,
        "xv": [str(v) for v in plan.x_values],
        "ys": {k: v for k, v in plan.y_series.items()},
        "t": plan.chart_type,
    }
    digest = hashlib.sha1(
        json.dumps(digest_payload, ensure_ascii=False, sort_keys=True).encode(
            "utf-8"
        )
    ).hexdigest()[:12]
    out_path = CHART_OUTPUT_ROOT / f"t2s-{digest}.png"
    if out_path.exists():
        return out_path

    configure_matplotlib_cjk_font()
    fig, ax = plt.subplots(figsize=(8.0, 4.4))
    try:
        x_labels = [_format_x(v) for v in plan.x_values]
        if plan.chart_type == "line":
            for name, ys in plan.y_series.items():
                ax.plot(x_labels, ys, marker="o", linewidth=2.0, label=name)
            ax.grid(True, linestyle="--", alpha=0.4)
        else:  # bar
            n_series = len(plan.y_series)
            if n_series == 1:
                (name, ys), = plan.y_series.items()
                ax.bar(x_labels, ys, color="#4a90d9", label=name)
            else:
                import numpy as np  # local import keeps module-load lightweight

                x_idx = np.arange(len(x_labels))
                width = 0.8 / n_series
                for i, (name, ys) in enumerate(plan.y_series.items()):
                    ax.bar(
                        x_idx + i * width - 0.4 + width / 2,
                        ys,
                        width=width,
                        label=name,
                    )
                ax.set_xticks(x_idx)
                ax.set_xticklabels(x_labels)
            ax.grid(True, axis="y", linestyle="--", alpha=0.4)

        if len(plan.y_columns) > 1:
            ax.legend(loc="best", fontsize=9, frameon=False)
        ax.set_title(plan.title, fontsize=12, pad=10)
        ax.set_xlabel(plan.x_column)
        if len(plan.y_columns) == 1:
            ax.set_ylabel(plan.y_columns[0])

        # Rotate x labels when they get crowded so dates remain readable.
        if len(x_labels) > 6:
            for label in ax.get_xticklabels():
                label.set_rotation(30)
                label.set_ha("right")

        fig.tight_layout()
        fig.savefig(out_path, dpi=160, bbox_inches="tight")
    finally:
        plt.close(fig)
    return out_path


def _format_x(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (_dt.date, _dt.datetime)):
        return value.isoformat()
    return str(value)


__all__ = [
    "CHART_OUTPUT_ROOT",
    "CHART_URL_PREFIX",
    "ChartArtifact",
    "build_chart_for_text2sql",
]
