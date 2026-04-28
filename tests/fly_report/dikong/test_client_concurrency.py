"""F7: concurrency + rate limiter behaviour."""

from __future__ import annotations

import asyncio

import pytest
import respx

from swarmmind.config.schema import FlyReportDikongConfig
from swarmmind.domains.fly_report.dikong.client import DikongClient


@pytest.mark.asyncio
async def test_max_concurrency_caps_in_flight_requests(dikong_config, static_token_provider) -> None:
    """``max_concurrency=2`` must serialise calls into batches of <=2."""

    config = FlyReportDikongConfig(
        base_url=dikong_config.base_url,
        account="a",
        password="p",
        request_timeout_seconds=2.0,
        max_retries=0,
        retry_backoff_seconds=0.0,
        max_concurrency=2,
        rate_limit_per_second=1000.0,
    )

    in_flight = 0
    peak = 0
    lock = asyncio.Lock()

    async def handler(request):
        nonlocal in_flight, peak
        async with lock:
            in_flight += 1
            peak = max(peak, in_flight)
        await asyncio.sleep(0.05)
        async with lock:
            in_flight -= 1
        import httpx
        return httpx.Response(200, json={"code": 0, "data": {"droneCount": 1}})

    with respx.mock(base_url=config.base_url) as router:
        router.get("/api/device/missions/getFlyStatis").mock(side_effect=handler)
        async with DikongClient(config, token_provider=static_token_provider) as client:
            await asyncio.gather(*[client.get_fly_statis() for _ in range(8)])

    assert peak <= 2, f"max in-flight should be 2, was {peak}"


@pytest.mark.asyncio
async def test_rate_limiter_throttles_burst(dikong_config, static_token_provider) -> None:
    """A 4 req/s limit should keep 8 sequentially-issued requests >= ~1s."""

    config = FlyReportDikongConfig(
        base_url=dikong_config.base_url,
        account="a",
        password="p",
        request_timeout_seconds=2.0,
        max_retries=0,
        retry_backoff_seconds=0.0,
        max_concurrency=8,
        rate_limit_per_second=4.0,
    )

    with respx.mock(base_url=config.base_url) as router:
        router.get("/api/device/missions/getFlyStatis").respond(
            200, json={"code": 0, "data": {"droneCount": 1}}
        )
        async with DikongClient(config, token_provider=static_token_provider) as client:
            start = asyncio.get_event_loop().time()
            await asyncio.gather(*[client.get_fly_statis() for _ in range(8)])
            elapsed = asyncio.get_event_loop().time() - start

    # 8 requests at 4/s -> at least ~1s of throttling.
    assert elapsed >= 0.9, f"expected throttling >= 0.9s, was {elapsed:.3f}s"
