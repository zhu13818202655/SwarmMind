"""Tests for ``InMemoryDikongTokenProvider`` (login + cache + refresh)."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest
import respx

from swarmmind.config.schema import FlyReportDikongConfig
from swarmmind.domains.fly_report.dikong.token_provider import (
    InMemoryDikongTokenProvider,
    StaticDikongTokenProvider,
    build_token_provider,
)
from swarmmind.domains.fly_report.errors import DikongAuthError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeClock:
    """Manually-advanced clock for deterministic TTL tests."""

    def __init__(self, start: float = 1000.0) -> None:
        self._t = start

    def now(self) -> float:
        return self._t

    def advance(self, seconds: float) -> None:
        self._t += seconds


def _dynamic_config(**overrides: Any) -> FlyReportDikongConfig:
    base = dict(
        base_url="http://dikong.test",
        account="alice",
        password="secret",
        token_ttl_seconds=720,
        token_refresh_skew_seconds=60,
        request_timeout_seconds=2.0,
        max_retries=0,
        retry_backoff_seconds=0.0,
        max_concurrency=4,
        rate_limit_per_second=100.0,
    )
    base.update(overrides)
    return FlyReportDikongConfig(**base)


def _login_body(token: str = "tok-1", code: str | int = "200") -> dict[str, Any]:
    return {"code": code, "msg": "ok", "data": {"accessToken": token}}


# ---------------------------------------------------------------------------
# Static provider
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_static_provider_returns_token_without_login() -> None:
    p = StaticDikongTokenProvider("static-tok")
    assert await p.get_token() == "static-tok"
    assert p.supports_refresh is False


@pytest.mark.asyncio
async def test_static_provider_raises_when_unset() -> None:
    p = StaticDikongTokenProvider(None)
    with pytest.raises(DikongAuthError):
        await p.get_token()


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def test_build_token_provider_returns_in_memory_provider() -> None:
    provider = build_token_provider(_dynamic_config())
    assert isinstance(provider, InMemoryDikongTokenProvider)


def test_build_token_provider_rejects_missing_credentials() -> None:
    cfg = FlyReportDikongConfig(account=None, password=None)
    with pytest.raises(DikongAuthError):
        build_token_provider(cfg)


# ---------------------------------------------------------------------------
# Dynamic provider: login + cache + expiry + concurrency
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dynamic_provider_logs_in_then_caches() -> None:
    cfg = _dynamic_config()
    clock = FakeClock()

    with respx.mock(base_url=cfg.base_url) as router:
        route = router.post("/system/user/login").respond(200, json=_login_body("tok-1"))
        provider = InMemoryDikongTokenProvider(cfg, clock=clock)
        try:
            tok_a = await provider.get_token()
            tok_b = await provider.get_token()
        finally:
            await provider.aclose()

    assert tok_a == tok_b == "tok-1"
    assert route.call_count == 1, "second call must hit the in-memory cache"


@pytest.mark.asyncio
async def test_dynamic_provider_refreshes_after_expiry() -> None:
    cfg = _dynamic_config(token_ttl_seconds=100, token_refresh_skew_seconds=10)
    clock = FakeClock()

    with respx.mock(base_url=cfg.base_url) as router:
        route = router.post("/system/user/login").mock(
            side_effect=[
                httpx.Response(200, json=_login_body("tok-1")),
                httpx.Response(200, json=_login_body("tok-2")),
            ],
        )
        provider = InMemoryDikongTokenProvider(cfg, clock=clock)
        try:
            assert await provider.get_token() == "tok-1"
            # Token effective-TTL is 100 - 10 = 90s; jump past it.
            clock.advance(95)
            assert await provider.get_token() == "tok-2"
        finally:
            await provider.aclose()

    assert route.call_count == 2


@pytest.mark.asyncio
async def test_dynamic_provider_invalidate_forces_relogin() -> None:
    cfg = _dynamic_config()

    with respx.mock(base_url=cfg.base_url) as router:
        route = router.post("/system/user/login").mock(
            side_effect=[
                httpx.Response(200, json=_login_body("tok-1")),
                httpx.Response(200, json=_login_body("tok-2")),
            ],
        )
        provider = InMemoryDikongTokenProvider(cfg, clock=FakeClock())
        try:
            assert await provider.get_token() == "tok-1"
            await provider.invalidate()
            assert await provider.get_token() == "tok-2"
        finally:
            await provider.aclose()

    assert route.call_count == 2


@pytest.mark.asyncio
async def test_dynamic_provider_concurrent_get_token_single_flight() -> None:
    """Many concurrent ``get_token`` calls must trigger exactly one login."""

    cfg = _dynamic_config()

    async def slow_login(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0.05)
        return httpx.Response(200, json=_login_body("tok-1"))

    with respx.mock(base_url=cfg.base_url) as router:
        route = router.post("/system/user/login").mock(side_effect=slow_login)
        provider = InMemoryDikongTokenProvider(cfg, clock=FakeClock())
        try:
            results = await asyncio.gather(*[provider.get_token() for _ in range(20)])
        finally:
            await provider.aclose()

    assert all(r == "tok-1" for r in results)
    assert route.call_count == 1


# ---------------------------------------------------------------------------
# Dynamic provider: error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dynamic_provider_envelope_error_raises_auth_error() -> None:
    cfg = _dynamic_config()

    with respx.mock(base_url=cfg.base_url) as router:
        router.post("/system/user/login").respond(
            200, json={"code": "401", "msg": "bad creds", "data": None},
        )
        provider = InMemoryDikongTokenProvider(cfg, clock=FakeClock())
        try:
            with pytest.raises(DikongAuthError) as exc_info:
                await provider.get_token()
        finally:
            await provider.aclose()

    assert exc_info.value.details["code"] == "401"


@pytest.mark.asyncio
async def test_dynamic_provider_http_error_raises_auth_error() -> None:
    cfg = _dynamic_config()

    with respx.mock(base_url=cfg.base_url) as router:
        router.post("/system/user/login").respond(500, text="boom")
        provider = InMemoryDikongTokenProvider(cfg, clock=FakeClock())
        try:
            with pytest.raises(DikongAuthError) as exc_info:
                await provider.get_token()
        finally:
            await provider.aclose()

    assert exc_info.value.details["status"] == 500


@pytest.mark.asyncio
async def test_dynamic_provider_missing_access_token_raises_auth_error() -> None:
    cfg = _dynamic_config()

    with respx.mock(base_url=cfg.base_url) as router:
        router.post("/system/user/login").respond(
            200, json={"code": 0, "msg": "ok", "data": {}},
        )
        provider = InMemoryDikongTokenProvider(cfg, clock=FakeClock())
        try:
            with pytest.raises(DikongAuthError):
                await provider.get_token()
        finally:
            await provider.aclose()
