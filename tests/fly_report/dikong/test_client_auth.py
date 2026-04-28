"""Client-level auth integration: dynamic token + 401-driven refresh."""

from __future__ import annotations

import httpx
import pytest
import respx

from swarmmind.config.schema import FlyReportDikongConfig
from swarmmind.domains.fly_report.dikong.client import DikongClient
from swarmmind.domains.fly_report.dikong.token_provider import (
    StaticDikongTokenProvider,
)
from swarmmind.domains.fly_report.errors import DikongAuthError

FLY_STATIS_PATH = "/api/device/missions/getFlyStatis"


def _dynamic_cfg(**overrides) -> FlyReportDikongConfig:
    base = dict(
        base_url="http://dikong.test",
        account="alice",
        password="secret",
        token_ttl_seconds=720,
        token_refresh_skew_seconds=60,
        request_timeout_seconds=2.0,
        max_retries=2,
        retry_backoff_seconds=0.0,
        max_concurrency=4,
        rate_limit_per_second=100.0,
    )
    base.update(overrides)
    return FlyReportDikongConfig(**base)


@pytest.mark.asyncio
async def test_back_token_header_is_set_from_dynamic_login() -> None:
    cfg = _dynamic_cfg()

    with respx.mock(base_url=cfg.base_url, assert_all_called=True) as router:
        login_route = router.post("/system/user/login").respond(
            200, json={"code": "200", "data": {"accessToken": "fresh-tok"}},
        )
        data_route = router.get(FLY_STATIS_PATH).respond(
            200, json={"code": 0, "data": {"droneCount": 1}},
        )
        async with DikongClient(cfg) as client:
            await client.get_fly_statis()

    assert login_route.call_count == 1
    request = data_route.calls.last.request
    assert request.headers["back-token"] == "fresh-tok"
    assert "Authorization" not in request.headers


@pytest.mark.asyncio
async def test_401_triggers_token_refresh_and_retry() -> None:
    """First call returns 401, provider re-logs in, second call succeeds."""

    cfg = _dynamic_cfg(max_retries=2)

    with respx.mock(base_url=cfg.base_url) as router:
        login_route = router.post("/system/user/login").mock(
            side_effect=[
                httpx.Response(200, json={"code": "200", "data": {"accessToken": "tok-1"}}),
                httpx.Response(200, json={"code": "200", "data": {"accessToken": "tok-2"}}),
            ],
        )
        data_route = router.get(FLY_STATIS_PATH).mock(
            side_effect=[
                httpx.Response(401, text="expired"),
                httpx.Response(200, json={"code": 0, "data": {"droneCount": 7}}),
            ],
        )
        async with DikongClient(cfg) as client:
            result = await client.get_fly_statis()

    assert result.drone_count == 7
    assert login_route.call_count == 2, "expected exactly one re-login on 401"
    assert data_route.call_count == 2
    # First data call carried tok-1, second carried tok-2.
    assert data_route.calls[0].request.headers["back-token"] == "tok-1"
    assert data_route.calls[1].request.headers["back-token"] == "tok-2"


@pytest.mark.asyncio
async def test_persistent_401_eventually_raises_auth_error() -> None:
    """If refresh doesn't help, the client surfaces a DikongAuthError."""

    cfg = _dynamic_cfg(max_retries=2)

    with respx.mock(base_url=cfg.base_url) as router:
        router.post("/system/user/login").respond(
            200, json={"code": "200", "data": {"accessToken": "tok-x"}},
        )
        router.get(FLY_STATIS_PATH).respond(401, text="nope")
        async with DikongClient(cfg) as client:
            with pytest.raises(DikongAuthError) as exc_info:
                await client.get_fly_statis()

    assert exc_info.value.details["status"] == 401


@pytest.mark.asyncio
async def test_static_token_mode_does_not_retry_on_401() -> None:
    """Static-token (DI) clients have nothing to refresh; 401 is fatal."""

    cfg = _dynamic_cfg()
    static = StaticDikongTokenProvider("static-tok")

    with respx.mock(base_url=cfg.base_url) as router:
        route = router.get(FLY_STATIS_PATH).respond(401, text="nope")
        async with DikongClient(cfg, token_provider=static) as client:
            with pytest.raises(DikongAuthError):
                await client.get_fly_statis()

    assert route.call_count == 1, "static-token mode must not retry on 401"


@pytest.mark.asyncio
async def test_injected_token_provider_is_used() -> None:
    """Caller-supplied provider takes precedence over config."""

    class _StubProvider:
        supports_refresh = True

        def __init__(self) -> None:
            self.calls = 0
            self.invalidations = 0

        async def get_token(self) -> str:
            self.calls += 1
            return f"stub-{self.calls}"

        async def invalidate(self) -> None:
            self.invalidations += 1

        async def aclose(self) -> None:
            return None

    cfg = _dynamic_cfg()
    stub = _StubProvider()

    with respx.mock(base_url=cfg.base_url) as router:
        route = router.get(FLY_STATIS_PATH).respond(
            200, json={"code": 0, "data": {"droneCount": 1}},
        )
        async with DikongClient(cfg, token_provider=stub) as client:
            await client.get_fly_statis()

    assert stub.calls == 1
    assert route.calls.last.request.headers["back-token"] == "stub-1"
