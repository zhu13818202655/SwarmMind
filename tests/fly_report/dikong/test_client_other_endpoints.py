"""F6: smoke tests for the four other M1 endpoints."""

from __future__ import annotations

import pytest
import respx

from swarmmind.domains.fly_report.dikong.client import DikongClient


@pytest.mark.asyncio
async def test_get_warn_static(dikong_config, static_token_provider) -> None:
    raw = {"warnNum": 7, "categories": {"a": 1, "b": 2}}
    with respx.mock(base_url=dikong_config.base_url, assert_all_called=True) as router:
        router.get("/missions/getWarnStatic").respond(200, json={"code": 0, "data": raw})
        async with DikongClient(dikong_config, token_provider=static_token_provider) as client:
            resp = await client.get_warn_static(dept_id=1, startdate="2026-04-01", enddate="2026-04-07")
    assert resp.raw == raw


@pytest.mark.asyncio
async def test_get_media_static(dikong_config, static_token_provider) -> None:
    raw = {"picCount": 100, "videoCount": 5}
    with respx.mock(base_url=dikong_config.base_url, assert_all_called=True) as router:
        router.get("/missions/getMediaStatic").respond(200, json={"code": 0, "data": raw})
        async with DikongClient(dikong_config, token_provider=static_token_provider) as client:
            resp = await client.get_media_static()
    assert resp.raw == raw


@pytest.mark.asyncio
async def test_get_hms_stats(dikong_config, static_token_provider) -> None:
    raw = {"alarms": 9, "online": 3}
    with respx.mock(base_url=dikong_config.base_url, assert_all_called=True) as router:
        router.get("/devices/hms/stats").respond(200, json={"code": 0, "data": raw})
        async with DikongClient(dikong_config, token_provider=static_token_provider) as client:
            resp = await client.get_hms_stats(dept_id=2)
    assert resp.raw == raw


@pytest.mark.asyncio
async def test_query_missions_by_page(dikong_config, static_token_provider) -> None:
    body = {
        "code": 0,
        "data": {
            "total": 2,
            "pageNum": 1,
            "pageSize": 50,
            "list": [
                {"id": 1, "no": "M-1", "deptId": 9},
                {"id": 2, "no": "M-2", "deptId": 9},
            ],
        },
    }
    with respx.mock(base_url=dikong_config.base_url, assert_all_called=True) as router:
        route = router.get("/missions/queryByPage").respond(200, json=body)
        async with DikongClient(dikong_config, token_provider=static_token_provider) as client:
            resp = await client.query_missions_by_page(
                page_num=1, page_size=50, dept_id=9, extra_params={"keyword": "abc"}
            )

    assert resp.total == 2
    assert len(resp.rows) == 2
    request = route.calls.last.request
    assert request.url.params["pageNum"] == "1"
    assert request.url.params["pageSize"] == "50"
    assert request.url.params["deptId"] == "9"
    assert request.url.params["keyword"] == "abc"
