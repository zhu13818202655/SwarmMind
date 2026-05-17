"""Unit tests for the SQL-backed FlyReport data fetcher.

These tests use in-memory fakes for the PostgreSQL pool and the TDengine
REST client so they run without any external services. They focus on
verifying the data-flow contract between :class:`SqlDataFetcher` and
:class:`DikongSqlClient`:

* envelope shape returned by ``get_*`` methods,
* per-department pivoting (``fly_statis``/``warn_static``/``media_static``),
* ``fly_job_logs`` is *not* pivoted,
* the previous-period window is shifted symmetrically,
* TDengine flight totals are converted from seconds → hours and metres → km,
* the strict identifier validators in ``td_client`` reject bad input.
"""

from __future__ import annotations

import re
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

import pytest

from swarmmind.config.schema import (
    FlyReportDikongSqlConfig,
    FlyReportPostgresConfig,
    FlyReportTDengineConfig,
)
from swarmmind.domains.fly_report.dikong_sql.client import DikongSqlClient
from swarmmind.domains.fly_report.dikong_sql.data_fetcher import SqlDataFetcher
from swarmmind.domains.fly_report.dikong_sql.td_client import (
    quote_drone_sn,
    quote_ts,
)
from swarmmind.domains.fly_report.errors import DikongTdError
from swarmmind.domains.fly_report.schemas import NormalizedFilter, Period


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeCursor:
    def __init__(self, pool: "_FakePgPool") -> None:
        self._pool = pool
        self._rows: list[dict[str, Any]] = []
        self._executed: list[tuple[str, dict[str, Any] | None]] = []

    async def execute(self, sql: str, params: dict[str, Any] | None = None) -> None:
        # Skip the SET LOCAL preamble.
        if sql.strip().lower().startswith("set local"):
            return
        self._executed.append((sql, params))
        self._pool.queries.append((sql, params))
        self._rows = self._pool.respond(sql, params)

    async def fetchall(self) -> list[dict[str, Any]]:
        return list(self._rows)

    async def __aenter__(self) -> "_FakeCursor":
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        return None


class _FakeConn:
    def __init__(self, pool: "_FakePgPool") -> None:
        self._pool = pool

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self._pool)

    async def __aenter__(self) -> "_FakeConn":
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        return None


class _FakePgPool:
    """Minimal stand-in for :class:`psycopg_pool.AsyncConnectionPool`."""

    def __init__(self) -> None:
        self.queries: list[tuple[str, dict[str, Any] | None]] = []
        self._responses: list[tuple[re.Pattern[str], list[dict[str, Any]]]] = []

    def add_response(self, sql_pattern: str, rows: list[dict[str, Any]]) -> None:
        self._responses.append((re.compile(sql_pattern, re.IGNORECASE | re.DOTALL), rows))

    def respond(self, sql: str, _params: dict[str, Any] | None) -> list[dict[str, Any]]:
        for pattern, rows in self._responses:
            if pattern.search(sql):
                return list(rows)
        return []

    @asynccontextmanager
    async def connection(self):
        yield _FakeConn(self)


class _FakeTdClient:
    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = rows or []
        self.queries: list[str] = []

    async def query(self, sql: str, database: str | None = None) -> list[dict[str, Any]]:
        self.queries.append(sql)
        return list(self.rows)

    async def aclose(self) -> None:
        return None


def _make_cfg() -> FlyReportDikongSqlConfig:
    return FlyReportDikongSqlConfig(
        postgres=FlyReportPostgresConfig(
            dsn="postgresql://stub", statement_timeout_ms=1000
        ),
        tdengine=FlyReportTDengineConfig(password="x"),
    )


# ---------------------------------------------------------------------------
# Validator tests (no IO)
# ---------------------------------------------------------------------------


class TestQuoting:
    def test_quote_drone_sn_accepts_valid(self) -> None:
        assert quote_drone_sn("ABC-123_45") == "'ABC-123_45'"

    @pytest.mark.parametrize(
        "bad",
        ["", "abc def", "abc;DROP", "x" * 65, "你好", "abc'or'1"],
    )
    def test_quote_drone_sn_rejects_invalid(self, bad: str) -> None:
        with pytest.raises(DikongTdError):
            quote_drone_sn(bad)

    def test_quote_ts_accepts_valid(self) -> None:
        assert quote_ts("2026-04-20 10:00:00") == "'2026-04-20 10:00:00'"
        assert quote_ts("2026-04-20") == "'2026-04-20'"

    @pytest.mark.parametrize(
        "bad",
        ["2026/04/20", "abc", "2026-04-20 10:00:00; DROP TABLE x", ""],
    )
    def test_quote_ts_rejects_invalid(self, bad: str) -> None:
        with pytest.raises(DikongTdError):
            quote_ts(bad)


# ---------------------------------------------------------------------------
# Client tests
# ---------------------------------------------------------------------------


class TestDikongSqlClient:
    @pytest.mark.asyncio
    async def test_get_fly_job_logs_envelope(self) -> None:
        pool = _FakePgPool()
        pool.add_response(
            "from sys_job_log",
            [
                {
                    "start_time": "2026-04-20 10:00:00",
                    "stop_time": "2026-04-20 10:30:00",
                    "status": "2",
                    "deptids_tag": "380",
                    "deptids_tag_name": "测绘部",
                }
            ],
        )
        td = _FakeTdClient()
        client = DikongSqlClient(pool, td, _make_cfg())  # type: ignore[arg-type]

        out = await client.get_fly_job_logs(
            start_time="2026-04-20 00:00:00",
            end_time="2026-04-20 23:59:59",
            dept_ids=[380],
        )
        assert out["records"][0]["status"] == "2"
        assert out["total"] == 1
        assert out["size"] == 1
        assert out["pages"] == 1
        assert out["current"] == 1

    @pytest.mark.asyncio
    async def test_get_fly_statis_converts_units(self) -> None:
        pool = _FakePgPool()
        pool.add_response(
            r"select[\s\S]+num_total",
            [
                {
                    "num_total": 12,
                    "drone_job_count": 8,
                    "drone_count": 5,
                }
            ],
        )
        pool.add_response(
            r"select[\s\S]+route_plan_count",
            [{"route_plan_count": 3}],
        )
        pool.add_response(
            r"select[\s\S]+device_sn",
            [{"device_sn": "DRONE-1"}, {"device_sn": "DRONE-2"}],
        )
        td = _FakeTdClient(
            rows=[
                {
                    "total_flight_time_sec": 7200,  # 2 hours
                    "total_flight_distance_m": 1500,  # 1.5 km
                }
            ]
        )
        client = DikongSqlClient(pool, td, _make_cfg())  # type: ignore[arg-type]

        out = await client.get_fly_statis(
            dept_id=380, startdate="2026-04-20", enddate="2026-04-26"
        )
        assert out["num_total"] == 12
        assert out["drone_count"] == 5
        assert out["drone_job_count"] == 8
        assert out["route_plan_count"] == 3
        assert out["fly_time_total"] == 2.0
        assert out["fly_mileage_total"] == 1.5
        # Two drone SNs were sent into a single TDengine call.
        assert len(td.queries) == 1
        assert "DRONE-1" in td.queries[0]
        assert "DRONE-2" in td.queries[0]

    @pytest.mark.asyncio
    async def test_get_warn_static_envelope(self) -> None:
        pool = _FakePgPool()
        pool.add_response(
            "from t_algorithm_record",
            [
                {
                    "algorithm_name": "person",
                    "extra_result": "{}",
                    "status": "2",
                    "push_status": "1",
                    "create_time": "2026-04-20 10:00:00",
                    "address": "Site A",
                    "dept_name": "Dept A",
                    "deptids_tag_name": "Dept A",
                }
            ],
        )
        client = DikongSqlClient(pool, _FakeTdClient(), _make_cfg())  # type: ignore[arg-type]
        out = await client.get_warn_static(
            dept_id=380, startdate="2026-04-20", enddate="2026-04-26"
        )
        assert out["total"] == 1
        assert out["records"][0]["algorithm_name"] == "person"

    @pytest.mark.asyncio
    async def test_get_media_static_wraps_under_raw(self) -> None:
        pool = _FakePgPool()
        pool.add_response(
            "from t_media_file",
            [
                {
                    "picCount": 100,
                    "picLableCount": 80,
                    "videoCount": 5,
                    "videoDurationMinute": 12.5,
                }
            ],
        )
        client = DikongSqlClient(pool, _FakeTdClient(), _make_cfg())  # type: ignore[arg-type]
        out = await client.get_media_static(
            dept_id=380, startdate="2026-04-20", enddate="2026-04-26"
        )
        assert "raw" in out
        assert out["raw"]["picCount"] == 100
        assert out["raw"]["videoDurationMinute"] == 12.5

    @pytest.mark.asyncio
    async def test_get_department_name_list(self) -> None:
        pool = _FakePgPool()
        pool.add_response(
            "from sys_dept",
            [{"dept_name": "测绘部"}, {"dept_name": "运维部"}],
        )
        client = DikongSqlClient(pool, _FakeTdClient(), _make_cfg())  # type: ignore[arg-type]
        names = await client.get_department_name_list_by_id_list(["380", "381"])
        assert names == ["测绘部", "运维部"]


# ---------------------------------------------------------------------------
# SqlDataFetcher (high-level shape)
# ---------------------------------------------------------------------------


class _StubClient:
    """High-fidelity stub used to verify pivoting + period shifting."""

    def __init__(self) -> None:
        self.fly_job_logs_calls: list[dict[str, Any]] = []
        self.fly_statis_calls: list[dict[str, Any]] = []
        self.warn_static_calls: list[dict[str, Any]] = []
        self.media_static_calls: list[dict[str, Any]] = []

    async def get_fly_job_logs(self, **kwargs: Any) -> dict[str, Any]:
        self.fly_job_logs_calls.append(kwargs)
        return {"records": [], "total": 0, "size": 0, "pages": 0, "current": 1}

    async def get_fly_statis(self, **kwargs: Any) -> dict[str, Any]:
        self.fly_statis_calls.append(kwargs)
        return {"num_total": 1, "fly_time_total": 0.0, "fly_mileage_total": 0.0}

    async def get_warn_static(self, **kwargs: Any) -> dict[str, Any]:
        self.warn_static_calls.append(kwargs)
        return {"records": [], "total": 0}

    async def get_media_static(self, **kwargs: Any) -> dict[str, Any]:
        self.media_static_calls.append(kwargs)
        return {"raw": {}}


class TestSqlDataFetcher:
    @pytest.mark.asyncio
    async def test_fetch_pivots_per_dept_and_shifts_period(self) -> None:
        client = _StubClient()
        fetcher = SqlDataFetcher(client)  # type: ignore[arg-type]

        period = Period(
            kind="weekly",
            start=datetime(2026, 4, 20),
            end=datetime(2026, 4, 26, 23, 59, 59),
        )
        filt = NormalizedFilter(period=period, dept_ids=[380, 381], hash="x")

        ds = await fetcher.fetch(filt)

        # fly_job_logs is shared (no per-dept dict).
        assert "fly_job_logs" in ds.current
        assert isinstance(ds.current["fly_job_logs"], dict)
        assert "records" in ds.current["fly_job_logs"]

        # Pivoted endpoints map dept_id -> payload.
        for endpoint in ("fly_statis", "warn_static", "media_static"):
            assert endpoint in ds.current
            assert set(ds.current[endpoint].keys()) == {"380", "381"}

        # Two job-log fetches (current + previous), 4 dept-scoped fetches each.
        assert len(client.fly_job_logs_calls) == 2
        assert len(client.fly_statis_calls) == 4  # 2 dept × 2 period
        assert len(client.warn_static_calls) == 4
        assert len(client.media_static_calls) == 4

        # Previous period mirrors current span (7 days).
        starts = sorted({c["start_time"] for c in client.fly_job_logs_calls})
        assert starts == ["2026-04-13 00:00:00", "2026-04-20 00:00:00"]

    @pytest.mark.asyncio
    async def test_fetch_without_dept_does_not_pivot(self) -> None:
        client = _StubClient()
        fetcher = SqlDataFetcher(client)  # type: ignore[arg-type]
        period = Period(
            kind="weekly",
            start=datetime(2026, 4, 20),
            end=datetime(2026, 4, 26, 23, 59, 59),
        )
        filt = NormalizedFilter(period=period, dept_ids=[], hash="x")

        ds = await fetcher.fetch(filt)

        # No pivoting -> values are direct payloads (not dept-keyed dicts).
        assert "num_total" in ds.current["fly_statis"]
        assert ds.current["fly_statis"]["num_total"] == 1
        assert ds.current["warn_static"]["total"] == 0
        assert ds.current["media_static"] == {"raw": {}}
