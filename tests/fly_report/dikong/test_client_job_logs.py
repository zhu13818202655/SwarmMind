from __future__ import annotations

import pytest
import respx

from swarmmind.domains.fly_report.dikong.client import DikongClient


@pytest.mark.asyncio
async def test_get_fly_job_logs_uses_begin_end_time_params(
    dikong_config,
    static_token_provider,
) -> None:
    body = {
        "code": 0,
        "data": {
            "records": [],
            "current": 1,
            "size": 2000,
            "total": 0,
            "pages": 0,
        },
    }
    with respx.mock(base_url=dikong_config.base_url, assert_all_called=True) as router:
        route = router.get("/api/device/job/log/list").respond(200, json=body)
        async with DikongClient(dikong_config, token_provider=static_token_provider) as client:
            await client.get_fly_job_logs(
                begin_time="2026-04-01 00:00:00",
                end_time="2026-04-30 23:59:59",
                page_num=1,
                page_size=2000,
            )

    params = route.calls.last.request.url.params
    assert params["beginTime"] == "2026-04-01 00:00:00"
    assert params["endTime"] == "2026-04-30 23:59:59"
    assert params["pageNum"] == "1"
    assert params["pageSize"] == "2000"
    assert "startdate" not in params
    assert "enddate" not in params
    assert "status" not in params


@pytest.mark.asyncio
async def test_get_fly_job_log_detail_substitutes_job_log_id(
    dikong_config,
    static_token_provider,
) -> None:
    body = {"code": 0, "data": {"jobTime": "00:03:05", "jobLogNo": "log-1"}}
    with respx.mock(base_url=dikong_config.base_url, assert_all_called=True) as router:
        router.get("/api/device/job/log/log-1").respond(200, json=body)
        async with DikongClient(dikong_config, token_provider=static_token_provider) as client:
            detail = await client.get_fly_job_log_detail("log-1")

    assert detail.job_time == "00:03:05"
    assert detail.job_log_no == "log-1"