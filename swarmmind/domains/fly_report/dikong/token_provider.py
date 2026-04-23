"""Dikong access-token providers.

This module defines a small :class:`DikongTokenProvider` Protocol and a
default in-memory implementation that:

- logs in on first use via the dikong login endpoint registered in
  :class:`~swarmmind.domains.fly_report.dikong.endpoints.EndpointKey.LOGIN`
  with ``{account, password}``;
- caches the resulting ``accessToken`` for ``token_ttl_seconds`` (minus
  ``token_refresh_skew_seconds``);
- single-flights concurrent refreshes via :class:`asyncio.Lock`;
- can be ``invalidate()``-d on auth failures (e.g. HTTP 401) so the next
  caller forces a fresh login.

Future swap to a Redis-backed cache is intentionally cheap: write a second
provider that satisfies the same Protocol and inject it into
:class:`~swarmmind.domains.fly_report.dikong.client.DikongClient`.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Protocol, runtime_checkable

import httpx

from swarmmind.config.schema import FlyReportDikongConfig
from swarmmind.domains.fly_report.dikong.endpoints import EndpointKey, get_endpoint
from swarmmind.domains.fly_report.errors import DikongAuthError

logger = logging.getLogger(__name__)


#: Path of the dikong login endpoint, sourced from the central registry.
LOGIN_PATH: str = get_endpoint(EndpointKey.LOGIN).path


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class DikongTokenProvider(Protocol):
    """Async source of valid dikong access tokens."""

    async def get_token(self) -> str:
        """Return a currently-valid token, refreshing if needed."""

    async def invalidate(self) -> None:
        """Drop any cached token so the next ``get_token`` re-authenticates."""

    async def aclose(self) -> None:
        """Release any owned resources (HTTP clients, etc.)."""


# ---------------------------------------------------------------------------
# Static provider (test helper / DI escape hatch)
# ---------------------------------------------------------------------------


class StaticDikongTokenProvider:
    """Returns a fixed token; never logs in.

    Intended for tests and ad-hoc tooling where a pre-issued token is on
    hand. Production code should always go through the dynamic
    :class:`InMemoryDikongTokenProvider`.
    """

    #: Static tokens cannot be refreshed; clients should treat 401 as fatal.
    supports_refresh: bool = False

    def __init__(self, token: str | None) -> None:
        self._token = token

    async def get_token(self) -> str:
        if not self._token:
            raise DikongAuthError("static dikong token is unset")
        return self._token

    async def invalidate(self) -> None:  # pragma: no cover - no-op
        return None

    async def aclose(self) -> None:  # pragma: no cover - no-op
        return None


# ---------------------------------------------------------------------------
# In-memory dynamic provider
# ---------------------------------------------------------------------------


class InMemoryDikongTokenProvider:
    """Logs in on demand and caches the token in process memory."""

    #: Dynamic provider can re-login on demand, so 401 retries are useful.
    supports_refresh: bool = True

    def __init__(
        self,
        config: FlyReportDikongConfig,
        *,
        http_client: httpx.AsyncClient | None = None,
        clock: "Clock | None" = None,
    ) -> None:
        if not config.account or not config.password:
            raise DikongAuthError(
                "dikong dynamic token mode requires both account and password",
            )
        self._config = config
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(
            base_url=config.base_url,
            timeout=httpx.Timeout(config.request_timeout_seconds),
        )
        self._clock = clock or _MonotonicClock()

        self._lock = asyncio.Lock()
        self._token: str | None = None
        self._expires_at: float = 0.0  # monotonic seconds

    # -- DikongTokenProvider --------------------------------------------------

    async def get_token(self) -> str:
        if self._is_fresh():
            return self._token  # type: ignore[return-value]
        async with self._lock:
            # Re-check inside the lock; another coroutine may have refreshed.
            if self._is_fresh():
                return self._token  # type: ignore[return-value]
            await self._refresh_locked()
            return self._token  # type: ignore[return-value]

    async def invalidate(self) -> None:
        async with self._lock:
            self._token = None
            self._expires_at = 0.0

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    # -- internals ------------------------------------------------------------

    def _is_fresh(self) -> bool:
        if not self._token:
            return False
        return self._clock.now() < self._expires_at

    async def _refresh_locked(self) -> None:
        try:
            response = await self._client.post(
                LOGIN_PATH,
                json={
                    "account": self._config.account,
                    "password": self._config.password,
                },
                headers={"Content-Type": "application/json", "Accept": "*/*"},
            )
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            raise DikongAuthError(
                f"transport failure during dikong login: {exc}",
                details={"endpoint": LOGIN_PATH},
            ) from exc

        if response.status_code >= 400:
            raise DikongAuthError(
                f"dikong login returned HTTP {response.status_code}",
                details={
                    "endpoint": LOGIN_PATH,
                    "status": response.status_code,
                    "body_preview": response.text[:512],
                },
            )

        try:
            payload: dict[str, Any] = response.json()
        except ValueError as exc:
            raise DikongAuthError(
                "dikong login returned non-JSON body",
                details={
                    "endpoint": LOGIN_PATH,
                    "body_preview": response.text[:512],
                },
            ) from exc

        code = payload.get("code", 0)
        if code != "200":
            raise DikongAuthError(
                f"dikong login failed with envelope code {code}: {payload.get('msg')}",
                details={
                    "endpoint": LOGIN_PATH,
                    "code": code,
                    "msg": payload.get("msg"),
                },
            )

        data = payload.get("data") or {}
        token = data.get("accessToken")
        if not token:
            raise DikongAuthError(
                "dikong login envelope did not contain accessToken",
                details={"endpoint": LOGIN_PATH},
            )

        ttl = self._config.token_ttl_seconds - self._config.token_refresh_skew_seconds
        if ttl <= 0:
            ttl = max(1, self._config.token_ttl_seconds)
        self._token = token
        self._expires_at = self._clock.now() + ttl
        logger.debug(
            "dikong token refreshed (ttl=%ss, skew=%ss)",
            self._config.token_ttl_seconds,
            self._config.token_refresh_skew_seconds,
        )


# ---------------------------------------------------------------------------
# Clock indirection (so tests can fast-forward without touching wall time)
# ---------------------------------------------------------------------------


class Clock(Protocol):
    def now(self) -> float: ...  # pragma: no cover - protocol


class _MonotonicClock:
    def now(self) -> float:
        return time.monotonic()


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def build_token_provider(
    config: FlyReportDikongConfig,
    *,
    http_client: httpx.AsyncClient | None = None,
) -> DikongTokenProvider:
    """Build the production token provider.

    Always returns an :class:`InMemoryDikongTokenProvider`; ``account`` and
    ``password`` must be configured (typically via env). Tests that need a
    pre-issued token can instead inject :class:`StaticDikongTokenProvider`
    directly into :class:`DikongClient`.
    """

    return InMemoryDikongTokenProvider(config, http_client=http_client)


__all__ = [
    "Clock",
    "DikongTokenProvider",
    "InMemoryDikongTokenProvider",
    "LOGIN_PATH",
    "StaticDikongTokenProvider",
    "build_token_provider",
]
