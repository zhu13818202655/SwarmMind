"""Process-wide async PostgreSQL connection pool for the SQL data fetcher.

Single ``psycopg_pool.AsyncConnectionPool`` instance shared across the
domain. The FastAPI ``lifespan`` hook is responsible for
:func:`get_pg_pool` (open) and :func:`close_pg_pool` (close); ad-hoc
scripts may also call them directly.
"""

from __future__ import annotations

import logging

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from swarmmind.config.schema import FlyReportPostgresConfig

logger = logging.getLogger(__name__)


_pg_pool: AsyncConnectionPool | None = None


async def get_pg_pool(cfg: FlyReportPostgresConfig) -> AsyncConnectionPool:
    """Return the shared async PG pool, opening it on first call.

    The pool is keyed by process – callers that need an isolated pool
    (e.g. tests) should construct :class:`AsyncConnectionPool` directly.
    """

    global _pg_pool
    if _pg_pool is not None:
        return _pg_pool

    if not cfg.dsn:
        raise RuntimeError(
            "FlyReport SQL data fetcher requires fly_report.dikong_sql."
            "postgres.dsn (env: FLY_REPORT_DIKONG_PG_DSN) to be set."
        )

    pool = AsyncConnectionPool(
        conninfo=cfg.dsn,
        min_size=cfg.pool_min_size,
        max_size=cfg.pool_max_size,
        timeout=cfg.pool_timeout_seconds,
        kwargs={
            "row_factory": dict_row,
            "application_name": cfg.application_name,
            "autocommit": True,
        },
        open=False,
    )
    await pool.open()
    logger.info(
        "fly_report.dikong_sql: opened PG pool min=%d max=%d app=%s",
        cfg.pool_min_size,
        cfg.pool_max_size,
        cfg.application_name,
    )
    _pg_pool = pool
    return pool


async def close_pg_pool() -> None:
    """Close the shared PG pool if it has been opened."""

    global _pg_pool
    if _pg_pool is None:
        return
    pool = _pg_pool
    _pg_pool = None
    await pool.close()
    logger.info("fly_report.dikong_sql: PG pool closed")


def reset_pg_pool_for_testing() -> None:
    """Drop the cached pool reference (test-only helper)."""

    global _pg_pool
    _pg_pool = None


__all__ = ["get_pg_pool", "close_pg_pool", "reset_pg_pool_for_testing"]
