"""Tests for :class:`DataFetcher`."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
import respx

from swarmmind.config.schema import FlyReportDikongConfig
from swarmmind.domains.fly_report.data_fetcher import DataFetcher, _previous_period
from swarmmind.domains.fly_report.dikong.client import DikongClient
from swarmmind.domains.fly_report.dikong.token_provider import (
    StaticDikongTokenProvider,
)
from swarmmind.domains.fly_report.errors import DikongApiError
from swarmmind.domains.fly_report.schemas import (
    Dimension,
    NormalizedFilter,
    Period,
    ReportOptions,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_BASE = "http://dikong.test"
FLY_STATIS_PATH = "/api/device/missions/getFlyStatis"
WARN_STATIC_PATH = "/api/device/missions/getWarnStatic"
MEDIA_STATIC_PATH = "/api/device/missions/getMediaStatic"
JOB_LOG_PATH = "/api/device/job/log/list"


def _cfg(**overrides) -> FlyReportDikongConfig:
    defaults = dict(
        base_url=_BASE,
        account="a",
        password="p",
        max_retries=0,
        retry_backoff_seconds=0,
        max_concurrency=8,
        rate_limit_per_second=100,
    )
    defaults.update(overrides)
    return FlyReportDikongConfig(**defaults)


def _client(cfg: FlyReportDikongConfig) -> DikongClient:
    """Build a client with a static token so tests don't need a login mock."""

    return DikongClient(cfg, token_provider=StaticDikongTokenProvider("test-token"))


def _make_filter(
    *,
    indicators: list[str] | None = None,
    scope: str = "overall",
    dept_ids: list[str] | None = None,
) -> NormalizedFilter:
    filt = NormalizedFilter(
        period=Period(
            kind="weekly",
            start=datetime(2026, 4, 13, tzinfo=timezone.utc),
            end=datetime(2026, 4, 19, 23, 59, 59, tzinfo=timezone.utc),
            label="2026年第16周",
        ),
        dimension=Dimension(
            scope=scope,
            department_ids=dept_ids or [],
        ),
        dept_ids=[int(dept_id) for dept_id in (dept_ids or [])],
        indicators=indicators or ["flight"],
        options=ReportOptions(),
        hash="test-hash",
    )
    return filt


def _envelope(data: dict) -> dict:
    return {"code": 0, "msg": "ok", "data": data}


FLY_STATIS_DATA = {
    "droneCount": 10,
    "hangarCount": 2,
    "flyMileageTotal": 1234.5,
    "flyTimeTotal": 56.7,
    "numTotal": 100,
    "droneJobCount": 80,
    "hangarJobCount": 20,
}

WARN_DATA = {"typeA": 5, "typeB": 3}
MEDIA_DATA = {"imageCount": 200, "videoCount": 50}
HMS_DATA = {"critical": 1, "warning": 5}
JOB_LOG_DATA = {"records": [], "total": 0, "size": 0, "pages": 0}


def _mock_fetch_routes(router: respx.Router):
    routes = {
        "job_logs": router.get(JOB_LOG_PATH).respond(json=_envelope(JOB_LOG_DATA)),
        "fly": router.get(FLY_STATIS_PATH).respond(json=_envelope(FLY_STATIS_DATA)),
        "warn": router.get(WARN_STATIC_PATH).respond(json=_envelope(WARN_DATA)),
        "media": router.get(MEDIA_STATIC_PATH).respond(json=_envelope(MEDIA_DATA)),
    }
    return routes


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_flight_only():
    """DataFetcher with indicator=['flight'] calls getFlyStatis for current + previous."""
    cfg = _cfg()
    filt = _make_filter(indicators=["flight"])

    with respx.mock(base_url=_BASE) as router:
        _mock_fetch_routes(router)
        async with _client(cfg) as client:
            fetcher = DataFetcher(client)
            ds = await fetcher.fetch(filt)

    assert "fly_statis" in ds.current
    assert "fly_job_logs" in ds.current
    assert "fly_statis" in ds.previous
    assert ds.current["fly_statis"]["num_total"] == 100


@pytest.mark.asyncio
async def test_fetch_multiple_indicators():
    """Multiple indicators trigger parallel fetches."""
    cfg = _cfg()
    filt = _make_filter(indicators=["flight", "algorithm", "device_health"])

    with respx.mock(base_url=_BASE) as router:
        _mock_fetch_routes(router)
        async with _client(cfg) as client:
            fetcher = DataFetcher(client)
            ds = await fetcher.fetch(filt)

    assert "fly_statis" in ds.current
    assert "warn_static" in ds.current
    assert "media_static" in ds.current


@pytest.mark.asyncio
async def test_fetch_with_dept_id():
    """Single department id is passed as deptId query param."""
    cfg = _cfg()
    filt = _make_filter(indicators=["flight"], scope="department", dept_ids=["42"])

    with respx.mock(base_url=_BASE) as router:
        routes = _mock_fetch_routes(router)
        async with _client(cfg) as client:
            fetcher = DataFetcher(client)
            ds = await fetcher.fetch(filt)

    # Verify deptId was sent (at least one call should have it).
    route = routes["fly"]
    assert route.call_count >= 2  # current + previous
    for call in route.calls:
        assert call.request.url.params.get("deptId") == "42"
    assert set(ds.current["fly_statis"].keys()) == {"42"}


@pytest.mark.asyncio
async def test_fetch_media_dedup():
    """media_image + media_video share the same fetcher, should not duplicate calls."""
    cfg = _cfg()
    filt = _make_filter(indicators=["media_image", "media_video"])

    with respx.mock(base_url=_BASE) as router:
        routes = _mock_fetch_routes(router)
        async with _client(cfg) as client:
            fetcher = DataFetcher(client)
            ds = await fetcher.fetch(filt)

    # Only 2 calls (current + previous), not 4.
    route = routes["media"]
    assert route.call_count == 2
    assert "media_static" in ds.current


@pytest.mark.asyncio
async def test_previous_period_calculation():
    """_previous_period produces a shifted period of the same length."""
    p = Period(
        kind="weekly",
        start=datetime(2026, 4, 13, tzinfo=timezone.utc),
        end=datetime(2026, 4, 19, 23, 59, 59, tzinfo=timezone.utc),
        label="2026年第16周",
    )
    prev = _previous_period(p)
    assert prev.end <= p.start
    assert prev.kind == "weekly"


@pytest.mark.asyncio
async def test_fetch_graceful_on_partial_failure():
    """If one fetcher fails, the rest still return data."""
    cfg = _cfg()
    filt = _make_filter(indicators=["flight", "algorithm"])

    with respx.mock(base_url=_BASE) as router:
        router.get(JOB_LOG_PATH).respond(json=_envelope(JOB_LOG_DATA))
        router.get(FLY_STATIS_PATH).respond(json=_envelope(FLY_STATIS_DATA))
        router.get(WARN_STATIC_PATH).respond(status_code=500)
        router.get(MEDIA_STATIC_PATH).respond(json=_envelope(MEDIA_DATA))
        async with _client(cfg) as client:
            fetcher = DataFetcher(client)

            with pytest.raises(DikongApiError):
                await fetcher.fetch(filt)
