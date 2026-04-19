"""Async dikong HTTP client used by the FlyReport domain.

Design notes (DESIGN-2 §4.1.4 / §10.6.2):
- thin ``httpx.AsyncClient`` wrapper, *no* business logic
- one ``DikongClient`` instance per process or per worker (cheap to share);
  it manages a single ``aiolimiter.AsyncLimiter`` and a connection pool
- retries are bounded and only fire on transient transport errors / 5xx;
  a non-zero ``code`` in the envelope is a *business* error and is **not**
  retried (it is raised as :class:`DikongApiError`)
- per-request tenant id can be passed in to override the default header
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any

import httpx
from aiolimiter import AsyncLimiter
from pydantic import BaseModel

from swarmmind.config.schema import FlyReportDikongConfig
from swarmmind.domains.fly_report.dikong.auth import build_headers
from swarmmind.domains.fly_report.dikong.endpoints import (
    EndpointKey,
    EndpointSpec,
    HttpMethod,
    get_endpoint,
)
from swarmmind.domains.fly_report.dikong.parsers import (
    DikongEnvelope,
    FlyStatisResp,
    HmsStatsResp,
    MediaStaticResp,
    MissionQueryByPageResp,
    WarnStaticResp,
    parse_envelope,
)
from swarmmind.domains.fly_report.errors import DikongApiError

logger = logging.getLogger(__name__)


# Transient HTTP status codes worth retrying.
_RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}


class DikongClient:
    """Async client over dikong's REST API."""

    def __init__(
        self,
        config: FlyReportDikongConfig,
        *,
        http_client: httpx.AsyncClient | None = None,
        limiter: AsyncLimiter | None = None,
    ) -> None:
        self._config = config
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(
            base_url=config.base_url,
            timeout=httpx.Timeout(config.request_timeout_seconds),
        )
        # aiolimiter token-bucket; one second window keeps semantics obvious.
        self._limiter = limiter or AsyncLimiter(
            max_rate=config.rate_limit_per_second,
            time_period=1.0,
        )
        self._semaphore = asyncio.Semaphore(config.max_concurrency)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> "DikongClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

    # ------------------------------------------------------------------
    # Core request helper
    # ------------------------------------------------------------------

    async def _request(
        self,
        endpoint: EndpointKey,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        tenant_id: str | None = None,
        data_model: type[BaseModel] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> DikongEnvelope[Any]:
        spec: EndpointSpec = get_endpoint(endpoint)
        headers = build_headers(
            token=self._config.token,
            tenant_id=tenant_id,
            tenant_header=self._config.tenant_header,
            extra=extra_headers,
        )

        cleaned_params = _drop_none(params) if params else None
        attempts = self._config.max_retries + 1
        last_exc: Exception | None = None

        for attempt in range(attempts):
            try:
                async with self._semaphore, self._limiter:
                    response = await self._client.request(
                        spec.method.value,
                        spec.path,
                        params=cleaned_params,
                        json=json_body,
                        headers=headers,
                    )
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_exc = exc
                if attempt + 1 >= attempts:
                    raise DikongApiError(
                        f"transport failure calling {spec.path}: {exc}",
                        details={"endpoint": spec.path, "attempt": attempt + 1},
                    ) from exc
                await asyncio.sleep(self._backoff(attempt))
                continue

            if response.status_code in _RETRYABLE_STATUS and attempt + 1 < attempts:
                await asyncio.sleep(self._backoff(attempt))
                continue
            if response.status_code >= 400:
                raise DikongApiError(
                    f"dikong returned HTTP {response.status_code} for {spec.path}",
                    details={
                        "endpoint": spec.path,
                        "status": response.status_code,
                        "body_preview": response.text[:512],
                    },
                )

            try:
                payload = response.json()
            except ValueError as exc:
                raise DikongApiError(
                    f"dikong returned non-JSON body for {spec.path}",
                    details={"endpoint": spec.path, "body_preview": response.text[:512]},
                ) from exc

            return parse_envelope(payload, endpoint=spec.path, data_model=data_model)

        # Loop exited without returning - exhaustion path.
        raise DikongApiError(
            f"exhausted retries calling {spec.path}",
            details={"endpoint": spec.path, "last_error": str(last_exc)},
        )

    def _backoff(self, attempt: int) -> float:
        return self._config.retry_backoff_seconds * (2**attempt)

    # ------------------------------------------------------------------
    # Typed accessors for the 5 core M1 endpoints
    # ------------------------------------------------------------------

    async def get_fly_statis(
        self,
        *,
        dept_id: int | None = None,
        startdate: str | None = None,
        enddate: str | None = None,
        tenant_id: str | None = None,
    ) -> FlyStatisResp:
        envelope = await self._request(
            EndpointKey.GET_FLY_STATIS,
            params={"deptId": dept_id, "startdate": startdate, "enddate": enddate},
            tenant_id=tenant_id,
            data_model=FlyStatisResp,
        )
        return envelope.data or FlyStatisResp()

    async def get_warn_static(
        self,
        *,
        dept_id: int | None = None,
        startdate: str | None = None,
        enddate: str | None = None,
        tenant_id: str | None = None,
    ) -> WarnStaticResp:
        envelope = await self._request(
            EndpointKey.GET_WARN_STATIC,
            params={"deptId": dept_id, "startdate": startdate, "enddate": enddate},
            tenant_id=tenant_id,
            data_model=WarnStaticResp,
        )
        return envelope.data or WarnStaticResp()

    async def get_media_static(
        self,
        *,
        dept_id: int | None = None,
        startdate: str | None = None,
        enddate: str | None = None,
        tenant_id: str | None = None,
    ) -> MediaStaticResp:
        envelope = await self._request(
            EndpointKey.GET_MEDIA_STATIC,
            params={"deptId": dept_id, "startdate": startdate, "enddate": enddate},
            tenant_id=tenant_id,
            data_model=MediaStaticResp,
        )
        return envelope.data or MediaStaticResp()

    async def get_hms_stats(
        self,
        *,
        dept_id: int | None = None,
        tenant_id: str | None = None,
    ) -> HmsStatsResp:
        envelope = await self._request(
            EndpointKey.HMS_STATS,
            params={"deptId": dept_id},
            tenant_id=tenant_id,
            data_model=HmsStatsResp,
        )
        return envelope.data or HmsStatsResp()

    async def query_missions_by_page(
        self,
        *,
        page_num: int = 1,
        page_size: int = 20,
        dept_id: int | None = None,
        startdate: str | None = None,
        enddate: str | None = None,
        tenant_id: str | None = None,
        extra_params: dict[str, Any] | None = None,
    ) -> MissionQueryByPageResp:
        params: dict[str, Any] = {
            "pageNum": page_num,
            "pageSize": page_size,
            "deptId": dept_id,
            "startdate": startdate,
            "enddate": enddate,
        }
        if extra_params:
            params.update(extra_params)
        envelope = await self._request(
            EndpointKey.MISSION_QUERY_BY_PAGE,
            params=params,
            tenant_id=tenant_id,
            data_model=MissionQueryByPageResp,
        )
        return envelope.data or MissionQueryByPageResp()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _drop_none(params: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in params.items() if v is not None}


@asynccontextmanager
async def open_dikong_client(config: FlyReportDikongConfig):
    """Convenience async context manager for ad-hoc usage in scripts/tests."""

    client = DikongClient(config)
    try:
        yield client
    finally:
        await client.aclose()


__all__ = ["DikongClient", "open_dikong_client"]
