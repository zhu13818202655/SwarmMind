"""F5: ``DikongClient.get_fly_statis`` happy / business-error / retry paths."""

from __future__ import annotations

import httpx
import pytest
import respx

from swarmmind.domains.fly_report.dikong.client import DikongClient
from swarmmind.domains.fly_report.errors import DikongApiError


@pytest.mark.asyncio
async def test_get_fly_statis_happy_path(dikong_config) -> None:
    body = {
        "code": 0,
        "msg": "ok",
        "requestId": "r-1",
        "data": {"droneCount": 4, "numTotal": 12, "flyTimeTotal": 9000.0},
    }
    with respx.mock(base_url=dikong_config.base_url, assert_all_called=True) as router:
        route = router.get("/missions/getFlyStatis").respond(200, json=body)
        async with DikongClient(dikong_config) as client:
            result = await client.get_fly_statis(
                dept_id=42, startdate="2026-04-01", enddate="2026-04-07", tenant_id="ten-1"
            )

    assert result.drone_count == 4
    assert result.num_total == 12
    assert result.fly_time_total == 9000.0

    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer test-token"
    assert request.headers["X-Tenant-Id"] == "ten-1"
    assert request.url.params["deptId"] == "42"
    assert request.url.params["startdate"] == "2026-04-01"
    assert request.url.params["enddate"] == "2026-04-07"


@pytest.mark.asyncio
async def test_get_fly_statis_business_error_raises(dikong_config) -> None:
    body = {"code": 1001, "msg": "no permission", "data": None}
    with respx.mock(base_url=dikong_config.base_url) as router:
        router.get("/missions/getFlyStatis").respond(200, json=body)
        async with DikongClient(dikong_config) as client:
            with pytest.raises(DikongApiError) as exc_info:
                await client.get_fly_statis()

    assert exc_info.value.details["code"] == 1001
    assert exc_info.value.details["endpoint"] == "/missions/getFlyStatis"


@pytest.mark.asyncio
async def test_get_fly_statis_retries_on_5xx_then_succeeds(dikong_config) -> None:
    body = {"code": 0, "data": {"droneCount": 1}}
    with respx.mock(base_url=dikong_config.base_url) as router:
        route = router.get("/missions/getFlyStatis").mock(
            side_effect=[
                httpx.Response(503, text="busy"),
                httpx.Response(503, text="busy"),
                httpx.Response(200, json=body),
            ]
        )
        async with DikongClient(dikong_config) as client:
            result = await client.get_fly_statis()

    assert route.call_count == 3
    assert result.drone_count == 1


@pytest.mark.asyncio
async def test_get_fly_statis_4xx_is_not_retried(dikong_config) -> None:
    with respx.mock(base_url=dikong_config.base_url) as router:
        route = router.get("/missions/getFlyStatis").mock(
            return_value=httpx.Response(401, text="nope"),
        )
        async with DikongClient(dikong_config) as client:
            with pytest.raises(DikongApiError) as exc_info:
                await client.get_fly_statis()

    assert route.call_count == 1
    assert exc_info.value.details["status"] == 401


@pytest.mark.asyncio
async def test_get_fly_statis_transport_error_retries_then_raises(dikong_config) -> None:
    with respx.mock(base_url=dikong_config.base_url) as router:
        route = router.get("/missions/getFlyStatis").mock(
            side_effect=httpx.ConnectError("boom"),
        )
        async with DikongClient(dikong_config) as client:
            with pytest.raises(DikongApiError) as exc_info:
                await client.get_fly_statis()

    # max_retries=2 -> 3 total attempts
    assert route.call_count == 3
    assert "transport failure" in str(exc_info.value)
