"""TDengine REST client for the FlyReport SQL data fetcher.

Wraps a single ``httpx.AsyncClient`` (one per process) targeting taosAdapter
on port 6041. The REST protocol exposes:

    POST {base_url}/rest/sql/{database}
    Content-Type: text/plain
    Authorization: Basic base64(user:pwd)

with a JSON response of the form::

    {"code": 0, "column_meta": [["ts", "TIMESTAMP", 8], ...],
     "data": [[...], ...], "rows": N}

This module pivots ``column_meta + data`` into ``list[dict[str, Any]]`` so
callers see the same row shape as ``psycopg`` with ``dict_row``.

⚠️ Security: TDengine REST does **not** support parameter binding. Any
identifier or literal interpolated into a SQL string MUST be validated by
:func:`quote_drone_sn` / :func:`quote_ts` first. Never feed unvalidated
user input into queries — see ``02_sql_fetcher_plan.md §5.2'``.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import re
from typing import Any

import httpx

from swarmmind.config.schema import FlyReportTDengineConfig
from swarmmind.domains.fly_report.errors import (
    DikongTdError,
    DikongTdTimeoutError,
)

logger = logging.getLogger(__name__)


_DRONE_SN_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")
_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}:\d{2}(\.\d+)?)?$")


def quote_drone_sn(value: str) -> str:
    """Validate a ``drone_sn`` identifier and return ``'<value>'``.

    Rejects anything outside ``[A-Za-z0-9_-]`` (no quotes, no whitespace).
    """
    if not isinstance(value, str) or not _DRONE_SN_RE.match(value):
        raise DikongTdError(
            f"invalid drone_sn for TDengine SQL: {value!r}",
        )
    return f"'{value}'"


def quote_ts(value: str) -> str:
    """Validate a TDengine timestamp literal and return ``'<value>'``.

    Accepts ``YYYY-MM-DD`` or ``YYYY-MM-DD HH:MM:SS[.fff]``.
    """
    if not isinstance(value, str) or not _TS_RE.match(value):
        raise DikongTdError(
            f"invalid timestamp for TDengine SQL: {value!r}",
        )
    return f"'{value}'"


class TDengineRestClient:
    """Thin async REST client for TDengine's taosAdapter."""

    def __init__(
        self,
        cfg: FlyReportTDengineConfig,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._cfg = cfg
        self._owns_http = http_client is None
        if cfg.password is None:
            raise RuntimeError(
                "FlyReport SQL data fetcher requires "
                "fly_report.dikong_sql.tdengine.password (env: "
                "FLY_REPORT_DIKONG_TDENGINE_PASSWORD) to be set."
            )
        token = base64.b64encode(
            f"{cfg.username}:{cfg.password}".encode()
        ).decode()
        self._http = http_client or httpx.AsyncClient(
            timeout=httpx.Timeout(cfg.timeout_seconds),
            limits=httpx.Limits(
                max_connections=cfg.max_connections,
                max_keepalive_connections=cfg.max_keepalive_connections,
            ),
            headers={
                "Authorization": f"Basic {token}",
                "Content-Type": "text/plain",
            },
            verify=cfg.verify_tls,
        )

    @property
    def database(self) -> str:
        return self._cfg.database

    def _url_for(self, database: str | None) -> str:
        base = self._cfg.base_url.rstrip("/")
        db = database if database is not None else self._cfg.database
        return f"{base}/rest/sql/{db}" if db else f"{base}/rest/sql"

    async def query(
        self,
        sql: str,
        *,
        database: str | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a SQL string and return rows as ``list[dict]``.

        Network errors / 5xx are retried up to ``cfg.max_retries`` times
        with exponential backoff. Business errors (``code != 0``) are NOT
        retried and surface as :class:`DikongTdError`.
        """

        url = self._url_for(database)
        attempts = max(self._cfg.max_retries, 0) + 1
        last_exc: Exception | None = None
        for attempt in range(attempts):
            try:
                resp = await self._http.post(url, content=sql.encode("utf-8"))
            except httpx.TimeoutException as exc:
                last_exc = exc
                if attempt + 1 >= attempts:
                    raise DikongTdTimeoutError(
                        f"TDengine REST timeout after {attempt + 1} attempts",
                        sql=sql,
                    ) from exc
                await asyncio.sleep(self._backoff(attempt))
                continue
            except httpx.TransportError as exc:
                last_exc = exc
                if attempt + 1 >= attempts:
                    raise DikongTdError(
                        f"TDengine REST transport error: {exc}",
                        sql=sql,
                    ) from exc
                await asyncio.sleep(self._backoff(attempt))
                continue

            if resp.status_code >= 500 and attempt + 1 < attempts:
                await asyncio.sleep(self._backoff(attempt))
                continue
            if resp.status_code >= 400:
                raise DikongTdError(
                    f"TDengine REST HTTP {resp.status_code}: "
                    f"{resp.text[:512]}",
                    sql=sql,
                )

            try:
                body = resp.json()
            except ValueError as exc:
                raise DikongTdError(
                    "TDengine REST returned non-JSON body",
                    sql=sql,
                ) from exc

            code = int(body.get("code", 0)) if isinstance(body, dict) else 0
            if code != 0:
                raise DikongTdError(
                    f"TDengine error code={code}",
                    td_code=code,
                    desc=str(body.get("desc")) if isinstance(body, dict) else None,
                    sql=sql,
                )

            cols = [c[0] for c in body.get("column_meta", [])]
            data = body.get("data", []) or []
            return [dict(zip(cols, row)) for row in data]

        # Unreachable in normal flow.
        raise DikongTdError(
            f"TDengine REST exhausted retries: {last_exc}",
            sql=sql,
        )

    async def chunked_query(
        self,
        sql_template: str,
        sn_chunks: list[list[str]],
        *,
        database: str | None = None,
    ) -> list[dict[str, Any]]:
        """Run ``sql_template.format(sn_in=...)`` once per drone-sn chunk.

        Used when the IN-list grows too large for a single REST request.
        Caller is responsible for crafting an ``{sn_in}`` placeholder that
        accepts a comma-separated list of already-quoted SNs.
        """
        out: list[dict[str, Any]] = []
        for chunk in sn_chunks:
            sn_list = ", ".join(quote_drone_sn(sn) for sn in chunk)
            sql = sql_template.format(sn_in=sn_list)
            out.extend(await self.query(sql, database=database))
        return out

    def _backoff(self, attempt: int) -> float:
        return self._cfg.retry_backoff_seconds * (2**attempt)

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()


_td_client: TDengineRestClient | None = None


async def get_td_client(cfg: FlyReportTDengineConfig) -> TDengineRestClient:
    """Return the process-wide TDengine REST client."""

    global _td_client
    if _td_client is None:
        _td_client = TDengineRestClient(cfg)
        logger.info(
            "fly_report.dikong_sql: created TDengine REST client base_url=%s db=%s",
            cfg.base_url,
            cfg.database,
        )
    return _td_client


async def close_td_client() -> None:
    """Close the process-wide TDengine REST client (if any)."""

    global _td_client
    if _td_client is None:
        return
    client = _td_client
    _td_client = None
    await client.aclose()
    logger.info("fly_report.dikong_sql: TDengine REST client closed")


def reset_td_client_for_testing() -> None:
    global _td_client
    _td_client = None


__all__ = [
    "TDengineRestClient",
    "get_td_client",
    "close_td_client",
    "reset_td_client_for_testing",
    "quote_drone_sn",
    "quote_ts",
]
