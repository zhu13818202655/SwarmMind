"""Tests for :mod:`swarmmind.domains.fly_report.analyzer.aggregations`."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from swarmmind.domains.fly_report.analyzer import analyze
from swarmmind.domains.fly_report.schemas import (
    AnalysisResult,
    Dimension,
    NormalizedFilter,
    Period,
    RawDataset,
    ReportOptions,
)


def _filter(indicators: list[str] | None = None) -> NormalizedFilter:
    return NormalizedFilter(
        period=Period(
            kind="weekly",
            start=datetime(2026, 4, 13, tzinfo=timezone.utc),
            end=datetime(2026, 4, 19, 23, 59, 59, tzinfo=timezone.utc),
            label="2026年第16周",
        ),
        dimension=Dimension(scope="overall"),
        indicators=indicators or ["flight"],
        options=ReportOptions(),
        hash="h",
    )


# ---------------------------------------------------------------------------
# Flight indicator
# ---------------------------------------------------------------------------


def test_flight_kpis_computed():
    raw = RawDataset(
        current={
            "fly_statis": {
                "num_total": 120,
                "fly_mileage_total": 500.0,
                "fly_time_total": 30.0,
                "drone_count": 10,
                "drone_job_count": 90,
            }
        },
        previous={
            "fly_statis": {
                "num_total": 100,
                "fly_mileage_total": 400.0,
                "fly_time_total": 25.0,
                "drone_count": 10,
                "drone_job_count": 80,
            }
        },
    )
    result = analyze(raw, _filter(["flight"]))

    assert isinstance(result, AnalysisResult)
    assert "flight" in result.overall
    assert result.overall["flight"]["fly_count"] == 120.0

    # Find the fly_count KPI.
    fly_count = next(k for k in result.kpis if k["name"] == "fly_count")
    assert fly_count["value"] == 120.0
    assert fly_count["previous_value"] == 100.0
    assert fly_count["change"] == 20.0
    assert fly_count["change_pct"] == 20.0
    assert fly_count["unit"] == "次"


def test_flight_trend_up():
    raw = RawDataset(
        current={"fly_statis": {"num_total": 150}},
        previous={"fly_statis": {"num_total": 100}},
    )
    result = analyze(raw, _filter(["flight"]))
    comp = next(c for c in result.comparisons if c["kpi"] == "fly_count")
    assert comp["trend"] == "up"


def test_flight_trend_down():
    raw = RawDataset(
        current={"fly_statis": {"num_total": 80}},
        previous={"fly_statis": {"num_total": 100}},
    )
    result = analyze(raw, _filter(["flight"]))
    comp = next(c for c in result.comparisons if c["kpi"] == "fly_count")
    assert comp["trend"] == "down"
    assert comp["change_pct"] == -20.0


def test_flight_anomaly_flagged():
    """Change ≥50% should be flagged as anomaly."""
    raw = RawDataset(
        current={"fly_statis": {"num_total": 200}},
        previous={"fly_statis": {"num_total": 100}},
    )
    result = analyze(raw, _filter(["flight"]))
    fly_anomalies = [a for a in result.anomalies if a["kpi"] == "fly_count"]
    assert len(fly_anomalies) == 1
    assert fly_anomalies[0]["severity"] == "high"  # 100% change


def test_no_anomaly_below_threshold():
    raw = RawDataset(
        current={"fly_statis": {"num_total": 110}},
        previous={"fly_statis": {"num_total": 100}},
    )
    result = analyze(raw, _filter(["flight"]))
    fly_anomalies = [a for a in result.anomalies if a["kpi"] == "fly_count"]
    assert fly_anomalies == []


# ---------------------------------------------------------------------------
# Multiple indicators
# ---------------------------------------------------------------------------


def test_multiple_indicators():
    raw = RawDataset(
        current={
            "fly_statis": {"num_total": 100},
            "warn_static": {"raw": {"typeA": 5}},
            "media_static": {"raw": {"images": 200}},
            "hms_stats": {"raw": {"critical": 3}},
        },
        previous={
            "fly_statis": {"num_total": 80},
            "warn_static": {"raw": {"typeA": 3}},
            "media_static": {"raw": {"images": 150}},
            "hms_stats": {"raw": {"critical": 1}},
        },
    )
    filt = _filter(["flight", "algorithm", "media_image", "device_health"])
    result = analyze(raw, filt)

    assert "flight" in result.overall
    assert "algorithm" in result.overall
    assert "media" in result.overall
    assert "device_health" in result.overall
    assert len(result.kpis) >= 4


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_empty_raw_dataset():
    raw = RawDataset()
    result = analyze(raw, _filter(["flight"]))
    assert isinstance(result, AnalysisResult)
    # KPIs exist but values are None.
    fly_count = next(k for k in result.kpis if k["name"] == "fly_count")
    assert fly_count["value"] is None


def test_missing_previous_period():
    raw = RawDataset(
        current={"fly_statis": {"num_total": 100}},
        previous={},
    )
    result = analyze(raw, _filter(["flight"]))
    fly_count = next(k for k in result.kpis if k["name"] == "fly_count")
    assert fly_count["value"] == 100.0
    assert fly_count["previous_value"] is None
    assert fly_count["change"] is None
