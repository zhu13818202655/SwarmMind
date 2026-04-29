"""Tests for :class:`MatplotlibChartRenderer` (DESIGN-2 §13 step 6)."""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from swarmmind.domains.fly_report.chart import MatplotlibChartRenderer
from swarmmind.domains.fly_report.schemas import ChartSpec


@pytest.fixture
def renderer() -> MatplotlibChartRenderer:
    return MatplotlibChartRenderer()


def _spec(chart_type: str, *, series, chart_id: str = "chart-1"):
    return ChartSpec(
        id=chart_id,
        title=f"{chart_type} demo",
        chart_type=chart_type,  # type: ignore[arg-type]
        series=series,
    )


def test_renders_line_chart(tmp_path: Path, renderer):
    spec = _spec(
        "line",
        series=[
            {
                "name": "task",
                "data": [{"x": "Mon", "y": 5}, {"x": "Tue", "y": 7}, {"x": "Wed", "y": 4}],
            }
        ],
    )
    out = renderer.render(spec, output_dir=tmp_path)
    assert out.exists() and out.suffix == ".png" and out.stat().st_size > 0


def test_renders_bar_chart(tmp_path: Path, renderer):
    spec = _spec(
        "bar",
        series=[{"name": "flights", "data": [{"x": "A", "y": 12}, {"x": "B", "y": 8}]}],
    )
    out = renderer.render(spec, output_dir=tmp_path)
    assert out.exists() and out.stat().st_size > 0


def test_renders_stacked_bar(tmp_path: Path, renderer):
    spec = _spec(
        "stacked_bar",
        series=[
            {"name": "warn", "data": [{"x": "A", "y": 3}, {"x": "B", "y": 5}]},
            {"name": "info", "data": [{"x": "A", "y": 7}, {"x": "B", "y": 2}]},
        ],
    )
    out = renderer.render(spec, output_dir=tmp_path)
    assert out.exists() and out.stat().st_size > 0


def test_renders_pie_chart(tmp_path: Path, renderer):
    spec = _spec(
        "pie",
        series=[
            {
                "name": "share",
                "data": [
                    {"label": "Alpha", "value": 60},
                    {"label": "Beta", "value": 30},
                    {"label": "Gamma", "value": 10},
                ],
            }
        ],
    )
    out = renderer.render(spec, output_dir=tmp_path)
    assert out.exists() and out.stat().st_size > 0


def test_unsupported_type_falls_back_to_placeholder(tmp_path: Path, renderer):
    spec = ChartSpec(id="x", title="t", chart_type="heatmap", series=[])
    out = renderer.render(spec, output_dir=tmp_path)
    # Even unsupported types must produce a PNG so reports never break.
    assert out.exists() and out.stat().st_size > 0


def test_empty_series_renders_placeholder(tmp_path: Path, renderer):
    spec = _spec("line", series=[])
    out = renderer.render(spec, output_dir=tmp_path)
    assert out.exists() and out.stat().st_size > 0


def test_render_many_returns_paths_in_order(tmp_path: Path, renderer):
    specs = [
        _spec("bar", series=[{"name": "a", "data": [{"x": "A", "y": 1}]}], chart_id=f"c{i}")
        for i in range(3)
    ]
    paths = renderer.render_many(specs, output_dir=tmp_path)
    assert [p.name for p in paths] == ["c0.png", "c1.png", "c2.png"]


def test_chinese_labels_render_without_missing_glyph_warnings(tmp_path: Path, renderer):
    spec = ChartSpec(
        id="中文图表",
        title="部门飞行任务数",
        chart_type="bar",
        series=[
            {
                "name": "任务数",
                "data": [
                    {"x": "资规局", "y": 36},
                    {"x": "公安局", "y": -8},
                    {"x": "农业农村局", "y": 41},
                ],
            }
        ],
    )

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        out = renderer.render(spec, output_dir=tmp_path)

    assert out.exists() and out.stat().st_size > 0
    assert not [warning for warning in captured if "Glyph" in str(warning.message)]
