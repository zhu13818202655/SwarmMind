"""Matplotlib-based chart renderer (DESIGN-2 §13 step 6).

Produces PNG images from :class:`ChartSpec` objects so the docx / pdf /
markdown renderers can embed them via plain ``<img>`` / docx pictures.

The renderer intentionally takes only the *minimal* fields it needs from
each ``ChartSpec`` so we can iterate on the upstream composer without
breaking exports:

- ``id``           — used as the output filename (``<id>.png``)
- ``title``        — drawn as the chart title
- ``chart_type``   — one of ``line``, ``bar``, ``stacked_bar``, ``pie``
- ``series``       — a list of ``{"name": str, "data": [{"x": ..., "y": ...}]}``
                     dicts. ``pie`` uses a single series of ``{"label", "value"}``.

Anything missing or unsupported is rendered as a placeholder chart so the
report still produces a usable artifact instead of crashing.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Any

import matplotlib

# Use a non-GUI backend; rendering happens in worker processes.
matplotlib.use("Agg")
import matplotlib.font_manager as _fm  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

from swarmmind.domains.fly_report.schemas import ChartSpec  # noqa: E402

# Best-effort CJK font detection so Chinese labels render instead of boxes.
# Matplotlib's own font cache can miss fonts that fontconfig sees, so we ask
# fontconfig for the actual file and register it explicitly when possible.
_CJK_CANDIDATES = (
    "Noto Sans CJK SC",
    "SimHei",
    "WenQuanYi Micro Hei",
    "WenQuanYi Zen Hei",
    "Source Han Sans CN",
    "Microsoft YaHei",
    "PingFang SC",
    "Droid Sans Fallback",
    "Arial Unicode MS",
)


def configure_matplotlib_cjk_font() -> str | None:
    """Configure Matplotlib to use an installed CJK-capable sans font.

    Returns the font family name when a candidate is found. The function is
    idempotent and safe to call from scripts before creating figures.
    """

    current = list(plt.rcParams.get("font.sans-serif", []))
    available = {font.name for font in _fm.fontManager.ttflist}
    for candidate in _CJK_CANDIDATES:
        if candidate in available:
            plt.rcParams["font.sans-serif"] = _prepend_unique(candidate, current)
            plt.rcParams["axes.unicode_minus"] = False
            return candidate

    for candidate in _CJK_CANDIDATES:
        font_path = _fontconfig_match(candidate)
        if font_path is None:
            continue
        try:
            _fm.fontManager.addfont(str(font_path))
        except Exception:
            continue
        family = _fm.FontProperties(fname=str(font_path)).get_name()
        plt.rcParams["font.sans-serif"] = _prepend_unique(family, current)
        plt.rcParams["axes.unicode_minus"] = False
        return family
    return None


def _fontconfig_match(family: str) -> Path | None:
    try:
        result = subprocess.run(
            ["fc-match", "-f", "%{file}", family],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    path = Path(result.stdout.strip())
    if result.returncode != 0 or not path.is_file():
        return None
    return path


def _prepend_unique(value: str, values: list[str]) -> list[str]:
    return [value, *[item for item in values if item != value]]


_CONFIGURED_CJK_FONT = configure_matplotlib_cjk_font()


SUPPORTED_TYPES = ("line", "bar", "stacked_bar", "pie")


class MatplotlibChartRenderer:
    """Render :class:`ChartSpec` objects to PNG files."""

    def __init__(self, *, dpi: int = 150) -> None:
        self._dpi = dpi

    def render(self, chart: ChartSpec, *, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / f"{chart.id}.png"

        fig, ax = plt.subplots(figsize=(8, 4.5))
        try:
            self._draw(ax, chart)
            ax.set_title(chart.title, fontsize=12)
            fig.tight_layout()
            fig.savefig(out_path, dpi=self._dpi, bbox_inches="tight")
        finally:
            plt.close(fig)
        return out_path

    def render_many(
        self, charts: list[ChartSpec], *, output_dir: Path
    ) -> list[Path]:
        return [self.render(c, output_dir=output_dir) for c in charts]

    # ------------------------------------------------------------------
    # internal
    # ------------------------------------------------------------------

    def _draw(self, ax, chart: ChartSpec) -> None:
        kind = chart.chart_type
        if kind not in SUPPORTED_TYPES:
            self._draw_placeholder(ax, f"unsupported chart_type: {kind}")
            return
        if not chart.series:
            self._draw_placeholder(ax, "no data")
            return

        if kind == "line":
            self._draw_line(ax, chart.series)
        elif kind == "bar":
            self._draw_bar(ax, chart.series)
        elif kind == "stacked_bar":
            self._draw_stacked_bar(ax, chart.series)
        elif kind == "pie":
            self._draw_pie(ax, chart.series[0])

    def _draw_line(self, ax, series: list[dict[str, Any]]) -> None:
        for s in series:
            xs, ys = _xy(s.get("data", []))
            ax.plot(xs, ys, marker="o", label=s.get("name", ""))
        ax.legend(loc="best", fontsize=9)
        ax.grid(True, linestyle="--", alpha=0.4)

    def _draw_bar(self, ax, series: list[dict[str, Any]]) -> None:
        # Single-series bar (most common KPI case).
        first = series[0]
        xs, ys = _xy(first.get("data", []))
        ax.bar(xs, ys, color="#4a90d9")
        ax.grid(True, axis="y", linestyle="--", alpha=0.4)

    def _draw_stacked_bar(self, ax, series: list[dict[str, Any]]) -> None:
        # Build a unified x axis from the first series.
        if not series:
            self._draw_placeholder(ax, "no data")
            return
        xs0, _ = _xy(series[0].get("data", []))
        bottom = [0.0] * len(xs0)
        for s in series:
            _, ys = _xy(s.get("data", []))
            ys = (ys + [0.0] * len(xs0))[: len(xs0)]
            ax.bar(xs0, ys, bottom=bottom, label=s.get("name", ""))
            bottom = [b + y for b, y in zip(bottom, ys, strict=True)]
        ax.legend(loc="best", fontsize=9)
        ax.grid(True, axis="y", linestyle="--", alpha=0.4)

    def _draw_pie(self, ax, series: dict[str, Any]) -> None:
        data = series.get("data", [])
        labels = [str(d.get("label", "")) for d in data]
        values = [_to_float(d.get("value")) for d in data]
        # Drop zero / negative entries silently to avoid matplotlib warnings.
        cleaned = [(l, v) for l, v in zip(labels, values, strict=True) if v > 0]
        if not cleaned:
            self._draw_placeholder(ax, "no positive values")
            return
        labels, values = zip(*cleaned, strict=True)
        ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=90)
        ax.set_aspect("equal")

    def _draw_placeholder(self, ax, message: str) -> None:
        ax.text(
            0.5, 0.5, message,
            ha="center", va="center", transform=ax.transAxes,
            fontsize=11, color="#999",
        )
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _xy(points: list[dict[str, Any]]) -> tuple[list[Any], list[float]]:
    xs: list[Any] = []
    ys: list[float] = []
    for p in points:
        xs.append(p.get("x"))
        ys.append(_to_float(p.get("y")))
    return xs, ys


def _to_float(val: Any) -> float:
    if val is None:
        return 0.0
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


__all__ = ["MatplotlibChartRenderer", "SUPPORTED_TYPES", "configure_matplotlib_cjk_font"]
