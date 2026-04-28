"""Tests for :mod:`swarmmind.domains.fly_report.analyzer.aggregations`."""

from __future__ import annotations

from datetime import datetime, timezone

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


def _row(table: dict, key: str) -> dict:
    return next(row for row in table["rows"] if row.get("key") == key)


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
    flight_count = _row(result.flight_stat_overall, "flight_count")
    assert flight_count["meta"]["current_value"] == 120.0
    assert flight_count["meta"]["previous_value"] == 100.0
    assert flight_count["meta"]["change_value"] == 20.0
    assert flight_count["meta"]["change_pct"] == 20.0
    assert flight_count["meta"]["unit"] == "次"


def test_flight_trend_up():
    raw = RawDataset(
        current={"fly_statis": {"num_total": 150}},
        previous={"fly_statis": {"num_total": 100}},
    )
    result = analyze(raw, _filter(["flight"]))
    assert _row(result.flight_stat_overall, "flight_count")["meta"]["trend"] == "up"


def test_flight_trend_down():
    raw = RawDataset(
        current={"fly_statis": {"num_total": 80}},
        previous={"fly_statis": {"num_total": 100}},
    )
    result = analyze(raw, _filter(["flight"]))
    flight_count = _row(result.flight_stat_overall, "flight_count")
    assert flight_count["meta"]["trend"] == "down"
    assert flight_count["meta"]["change_pct"] == -20.0


def test_flight_anomaly_flagged():
    """Change ≥50% should be flagged as anomaly."""
    raw = RawDataset(
        current={"fly_statis": {"num_total": 200}},
        previous={"fly_statis": {"num_total": 100}},
    )
    result = analyze(raw, _filter(["flight"]))
    flight_count = _row(result.flight_stat_overall, "flight_count")
    assert flight_count["meta"]["change_pct"] == 100.0
    assert flight_count["change"] == "↑ 100.0%"


def test_no_anomaly_below_threshold():
    raw = RawDataset(
        current={"fly_statis": {"num_total": 110}},
        previous={"fly_statis": {"num_total": 100}},
    )
    result = analyze(raw, _filter(["flight"]))
    assert _row(result.flight_stat_overall, "flight_count")["meta"]["change_pct"] == 10.0


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

    assert result.flight_stat_overall["rows"]
    assert result.algorithm_recognition_overall["rows"]
    assert result.media_collection_summary["rows"]
    assert result.flight_stat_day_trend["rows"]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_empty_raw_dataset():
    raw = RawDataset()
    result = analyze(raw, _filter(["flight"]))
    assert isinstance(result, AnalysisResult)
    assert _row(result.flight_stat_overall, "flight_count")["meta"]["current_value"] is None


def test_missing_previous_period():
    raw = RawDataset(
        current={"fly_statis": {"num_total": 100}},
        previous={},
    )
    result = analyze(raw, _filter(["flight"]))
    flight_count = _row(result.flight_stat_overall, "flight_count")
    assert flight_count["meta"]["current_value"] == 100.0
    assert flight_count["meta"]["previous_value"] is None
    assert flight_count["meta"]["change_value"] is None
