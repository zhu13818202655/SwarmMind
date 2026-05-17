"""SQL-backed equivalent of :class:`DikongClient`.

Owns a PostgreSQL ``AsyncConnectionPool`` reference and a
:class:`TDengineRestClient`, exposing the same async method signatures the
HTTP client publishes (``get_fly_job_logs`` / ``get_fly_statis`` /
``get_warn_static`` / ``get_media_static`` /
``get_department_name_list_by_id_list``) so that
:class:`SqlDataFetcher` is a drop-in replacement for
:class:`DataFetcher` from the analyzer's perspective.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, AsyncIterator

import psycopg
from psycopg_pool import AsyncConnectionPool

from swarmmind.config.schema import FlyReportDikongSqlConfig
from swarmmind.domains.fly_report.dikong_sql.queries_pg import (
    SQL_DEPT_NAMES,
    SQL_FLY_JOB_LOGS,
    SQL_FLY_PERIOD_DRONE_SNS,
    SQL_FLY_STATIS_COUNTS,
    SQL_MEDIA_STATIC,
    SQL_ROUTE_PLAN_COUNT,
    SQL_WARN_STATIC,
)
from swarmmind.domains.fly_report.dikong_sql.queries_td import (
    sql_flight_overall,
)
from swarmmind.domains.fly_report.dikong_sql.td_client import (
    TDengineRestClient,
)
from swarmmind.domains.fly_report.errors import (
    DikongPgSqlError,
    DikongPgSqlTimeoutError,
)

logger = logging.getLogger(__name__)


class DikongSqlClient:
    """Async SQL client returning dikong-shaped payloads."""

    def __init__(
        self,
        pg_pool: AsyncConnectionPool,
        td_client: TDengineRestClient,
        cfg: FlyReportDikongSqlConfig,
    ) -> None:
        self._pg = pg_pool
        self._td = td_client
        self._cfg = cfg

    # ------------------------------------------------------------------
    # Public API — mirrors :class:`DikongClient`
    # ------------------------------------------------------------------

    async def get_department_name_list_by_id_list(
        self,
        id_list: list[str],
    ) -> list[str]:
        if not id_list:
            return []
        rows = await self._pg_fetch_all(
            SQL_DEPT_NAMES,
            {"dept_ids": [str(i) for i in id_list]},
        )
        return [str(r.get("dept_name")) for r in rows if r.get("dept_name")]

    async def get_fly_job_logs(
        self,
        *,
        start_time: str | None = None,
        end_time: str | None = None,
        page_num: int = 1,  # noqa: ARG002 — kept for signature parity
        page_size: int = 9999999,  # noqa: ARG002
        status: str | int | None = None,  # noqa: ARG002
        name: str | None = None,  # noqa: ARG002
        type: str | int | None = None,  # noqa: ARG002
        dept_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        if start_time is None or end_time is None:
            raise ValueError("get_fly_job_logs requires start_time and end_time")
        rows = await self._pg_fetch_all(
            SQL_FLY_JOB_LOGS,
            {
                "start_ts": start_time,
                "end_ts": end_time,
                "dept_ids": list(dept_ids) if dept_ids else None,
                "row_cap": self._cfg.postgres.fly_job_logs_row_cap,
            },
        )
        return _wrap_records(rows)

    async def get_fly_statis(
        self,
        *,
        dept_id: int | None = None,
        startdate: str | None = None,
        enddate: str | None = None,
    ) -> dict[str, Any]:
        if startdate is None or enddate is None:
            raise ValueError("get_fly_statis requires startdate and enddate")
        start_ts = f"{startdate} 00:00:00"
        end_ts = f"{enddate} 23:59:59"
        dept_ids = [dept_id] if dept_id is not None else None

        # PG: counts + route plan total + drone sn list (drives TDengine).
        counts_rows, route_rows, drone_rows = await asyncio.gather(
            self._pg_fetch_all(
                SQL_FLY_STATIS_COUNTS,
                {"start_ts": start_ts, "end_ts": end_ts, "dept_ids": dept_ids},
            ),
            self._pg_fetch_all(SQL_ROUTE_PLAN_COUNT, {}),
            self._pg_fetch_all(
                SQL_FLY_PERIOD_DRONE_SNS,
                {"start_ts": start_ts, "end_ts": end_ts, "dept_ids": dept_ids},
            ),
        )
        counts = counts_rows[0] if counts_rows else {}
        route_plan_count = (
            int(route_rows[0]["route_plan_count"]) if route_rows else 0
        )
        drone_sns = sorted(
            {str(r["device_sn"]) for r in drone_rows if r.get("device_sn")}
        )

        # TDengine: cumulative flight time / distance / sorties.
        td_total_time_sec = 0.0
        td_total_distance_m = 0.0
        if drone_sns:
            try:
                td_rows = await self._td.query(
                    sql_flight_overall(start_ts, end_ts, drone_sns)
                )
            except Exception:
                logger.exception(
                    "fly_report.dikong_sql: TDengine flight overall query failed"
                )
                td_rows = []
            if td_rows:
                first = td_rows[0]
                td_total_time_sec = _to_float(first.get("total_flight_time_sec"))
                td_total_distance_m = _to_float(
                    first.get("total_flight_distance_m")
                )

        return {
            # Snake-case keys consumed by analyzer.aggregations.
            "num_total": int(counts.get("num_total") or 0),
            "drone_job_count": int(counts.get("drone_job_count") or 0),
            "drone_count": int(counts.get("drone_count") or 0),
            "hangar_count": 0,
            "hangar_job_count": 0,
            "algorithm_count": 0,
            "route_plan_count": route_plan_count,
            "fly_time_total": round(td_total_time_sec / 3600.0, 2),
            "fly_mileage_total": round(td_total_distance_m / 1000.0, 3),
        }

    async def get_warn_static(
        self,
        *,
        dept_id: int | None = None,
        startdate: str | None = None,
        enddate: str | None = None,
        page_num: int = 1,  # noqa: ARG002
        page_size: int = 9999999,  # noqa: ARG002
    ) -> dict[str, Any]:
        if startdate is None or enddate is None:
            raise ValueError("get_warn_static requires startdate and enddate")
        rows = await self._pg_fetch_all(
            SQL_WARN_STATIC,
            {
                "start_ts": f"{startdate} 00:00:00",
                "end_ts": f"{enddate} 23:59:59",
                "dept_ids": [dept_id] if dept_id is not None else None,
            },
        )
        return _wrap_records(rows)

    async def get_media_static(
        self,
        *,
        dept_id: int | None = None,
        startdate: str | None = None,
        enddate: str | None = None,
    ) -> dict[str, Any]:
        if startdate is None or enddate is None:
            raise ValueError("get_media_static requires startdate and enddate")
        rows = await self._pg_fetch_all(
            SQL_MEDIA_STATIC,
            {
                "start_ts": f"{startdate} 00:00:00",
                "end_ts": f"{enddate} 23:59:59",
                "dept_ids": [dept_id] if dept_id is not None else None,
            },
        )
        # MediaStaticResp wraps the dikong payload under ``raw``; mirror that
        # shape so analyzer.aggregations._media_static_payload unwraps it.
        payload = rows[0] if rows else {}
        return {"raw": dict(payload)}

    # ------------------------------------------------------------------
    # PG helpers
    # ------------------------------------------------------------------

    async def _pg_fetch_all(
        self,
        sql: str,
        params: dict[str, Any],
    ) -> list[dict[str, Any]]:
        started = time.perf_counter()
        try:
            async with self._pg.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        f"SET LOCAL statement_timeout = "
                        f"{int(self._cfg.postgres.statement_timeout_ms)}"
                    )
                    await cur.execute(sql, params)
                    rows = await cur.fetchall()
        except psycopg.errors.QueryCanceled as exc:
            raise DikongPgSqlTimeoutError(
                "PostgreSQL statement_timeout fired",
                details={"sql_preview": sql.strip()[:512]},
            ) from exc
        except psycopg.Error as exc:
            raise DikongPgSqlError(
                f"PostgreSQL error: {exc}",
                details={"sql_preview": sql.strip()[:512]},
            ) from exc

        elapsed_ms = (time.perf_counter() - started) * 1000.0
        logger.info(
            "fly_report.dikong_sql.pg endpoint=? rows=%d elapsed_ms=%.1f",
            len(rows),
            elapsed_ms,
        )
        return list(rows)

    async def _pg_stream(
        self,
        sql: str,
        params: dict[str, Any],
        *,
        batch: int | None = None,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        size = batch or self._cfg.postgres.server_side_cursor_itersize
        try:
            async with self._pg.connection() as conn:
                async with conn.cursor(name="fly_report_stream") as cur:
                    await conn.execute(
                        f"SET LOCAL statement_timeout = "
                        f"{int(self._cfg.postgres.statement_timeout_ms)}"
                    )
                    cur.itersize = size  # type: ignore[attr-defined]
                    await cur.execute(sql, params)
                    while True:
                        rows = await cur.fetchmany(size)
                        if not rows:
                            break
                        yield list(rows)
        except psycopg.Error as exc:
            raise DikongPgSqlError(
                f"PostgreSQL streaming error: {exc}",
                details={"sql_preview": sql.strip()[:512]},
            ) from exc

    async def aclose(self) -> None:
        # The PG pool is shared and closed by the lifespan owner. Only the
        # TDengine client is owned per-instance here.
        await self._td.aclose()


def _wrap_records(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Mirror the dikong HTTP envelope ``{records, total, size, pages, current}``."""
    records = list(rows)
    total = len(records)
    return {
        "records": records,
        "total": total,
        "size": total,
        "pages": 1 if total else 0,
        "current": 1,
    }


def _to_float(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


__all__ = ["DikongSqlClient"]
