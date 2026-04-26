from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from swarmmind.domains.fly_report.data_fetcher import DataFetcher
from swarmmind.domains.fly_report.dikong.parsers import (
    FlyJobLogResp,
    FlyJobLogRow,
    FlyStatisResp,
    MediaStaticResp,
    WarnStaticResp,
)
from swarmmind.domains.fly_report.schemas import Dimension, FilterSpec, NormalizedFilter, Period, RawDataset


class _FakeDikongClient:
    def __init__(self) -> None:
        self.job_log_calls: list[dict[str, Any]] = []

    async def get_department_name_list_by_id_list(self, dept_id_list: list[str]) -> list[str]:
        return dept_id_list

    async def get_fly_job_logs(self, **kwargs: Any) -> FlyJobLogResp:
        self.job_log_calls.append(kwargs)
        return FlyJobLogResp(
            current=1,
            size=2,
            total=2,
            pages=1,
            records=[
                FlyJobLogRow(
                    jobLogId="exception-log",
                    status=4,
                    deptidsTag="42",
                    beginTime="2026-04-14 10:00:00",
                    endTime="2026-04-14 10:02:00",
                ),
                FlyJobLogRow(
                    jobLogId="finished-log",
                    status=2,
                    deptidsTag="42",
                    beginTime="2026-04-14 11:00:00",
                    endTime="2026-04-14 11:20:00",
                ),
            ],
        )

    async def get_fly_statis(self, **kwargs: Any) -> FlyStatisResp:
        return FlyStatisResp(numTotal=2, flyTimeTotal=1320.0)

    async def get_warn_static(self, **kwargs: Any) -> WarnStaticResp:
        return WarnStaticResp()

    async def get_media_static(self, **kwargs: Any) -> MediaStaticResp:
        return MediaStaticResp()


def _filter() -> FilterSpec:
    return FilterSpec(
        period=Period(
            kind="weekly",
            start=datetime(2026, 4, 13, tzinfo=timezone.utc),
            end=datetime(2026, 4, 19, 23, 59, 59, tzinfo=timezone.utc),
        ),
        dept_ids=[42],
        dimension=Dimension(scope="department", department_ids=["42"]),
    )


@pytest.mark.asyncio
async def test_fetch_preserves_exception_job_logs_without_status_filter() -> None:
    fake_client = _FakeDikongClient()
    fetcher = DataFetcher(fake_client)  # type: ignore[arg-type]

    dataset = await fetcher.fetch(NormalizedFilter.from_filter(_filter()))

    assert isinstance(dataset, RawDataset)
    assert all(call.get("status") is None for call in fake_client.job_log_calls)
    assert all("begin_time" in call and "end_time" in call for call in fake_client.job_log_calls)
    assert fake_client.job_log_calls[0]["begin_time"] == "2026-04-13 00:00:00"
    assert fake_client.job_log_calls[0]["end_time"] == "2026-04-19 23:59:59"

    current_logs = dataset.current["fly_job_logs"]
    records = current_logs["records"]
    exception_record = next(record for record in records if str(record["status"]) == "4")
    assert exception_record["job_log_id"] == "exception-log"
    assert {str(record["status"]) for record in records} == {"2", "4"}