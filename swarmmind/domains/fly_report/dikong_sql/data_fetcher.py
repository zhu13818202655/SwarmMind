"""SQL-backed equivalent of :class:`swarmmind.domains.fly_report.data_fetcher.DataFetcher`.

The output :class:`RawDataset` is structurally identical to the HTTP version
so the analyzer / composer / service code paths require no changes.
Selection between the two is driven by ``fly_report.source`` in config.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from swarmmind.domains.fly_report.dikong_sql.client import DikongSqlClient
from swarmmind.domains.fly_report.schemas import (
    NormalizedFilter,
    Period,
    RawDataset,
)

logger = logging.getLogger(__name__)


def _fmt_date(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def _previous_period(period: Period) -> Period:
    delta = period.end - period.start
    if delta.total_seconds() <= 0:
        delta = timedelta(days=7)
    return Period(
        kind=period.kind,
        start=period.start - delta,
        end=period.end - delta,
    )


class SqlDataFetcher:
    """Translate a :class:`NormalizedFilter` into SQL queries.

    Returns the same :class:`RawDataset` shape as the HTTP-backed
    :class:`swarmmind.domains.fly_report.data_fetcher.DataFetcher` so the
    downstream analyzer/composer code requires no changes.
    """

    def __init__(self, client: DikongSqlClient) -> None:
        self._client = client

    async def get_department_name_list_by_id_list(
        self,
        dept_id_list: list[str],
    ) -> list[str]:
        return await self._client.get_department_name_list_by_id_list(dept_id_list)

    async def fetch(self, filt: NormalizedFilter) -> RawDataset:
        prev_period = _previous_period(filt.period)
        dept_ids = filt.dept_ids
        current_start = _fmt_date(filt.period.start)
        current_end = _fmt_date(filt.period.end)
        previous_start = _fmt_date(prev_period.start)
        previous_end = _fmt_date(prev_period.end)

        current_job_logs_task = asyncio.create_task(
            self._client.get_fly_job_logs(
                start_time=f"{current_start} 00:00:00",
                end_time=f"{current_end} 23:59:59",
                dept_ids=list(dept_ids) if dept_ids else None,
            )
        )
        previous_job_logs_task = asyncio.create_task(
            self._client.get_fly_job_logs(
                start_time=f"{previous_start} 00:00:00",
                end_time=f"{previous_end} 23:59:59",
                dept_ids=list(dept_ids) if dept_ids else None,
            )
        )

        target_dept_ids: list[int | None] = list(dept_ids) if dept_ids else [None]
        current_dept_tasks = {
            dept_id: asyncio.create_task(
                self._fetch_period_scoped_data(
                    dept_id=dept_id,
                    startdate=current_start,
                    enddate=current_end,
                )
            )
            for dept_id in target_dept_ids
        }
        previous_dept_tasks = {
            dept_id: asyncio.create_task(
                self._fetch_period_scoped_data(
                    dept_id=dept_id,
                    startdate=previous_start,
                    enddate=previous_end,
                )
            )
            for dept_id in target_dept_ids
        }

        current_job_logs = await current_job_logs_task
        previous_job_logs = await previous_job_logs_task

        current_data: dict[str, Any] = {"fly_job_logs": current_job_logs}
        previous_data: dict[str, Any] = {"fly_job_logs": previous_job_logs}

        if dept_ids:
            current_by_dept = {
                str(dept_id): await task
                for dept_id, task in current_dept_tasks.items()
                if dept_id is not None
            }
            previous_by_dept = {
                str(dept_id): await task
                for dept_id, task in previous_dept_tasks.items()
                if dept_id is not None
            }
            current_data.update(self._pivot_period_results_by_endpoint(current_by_dept))
            previous_data.update(self._pivot_period_results_by_endpoint(previous_by_dept))
        else:
            current_data.update(await current_dept_tasks[None])
            previous_data.update(await previous_dept_tasks[None])

        return RawDataset(current=current_data, previous=previous_data)

    async def _fetch_period_scoped_data(
        self,
        *,
        dept_id: int | None,
        startdate: str,
        enddate: str,
    ) -> dict[str, Any]:
        fly_statis, warn_static, media_static = await asyncio.gather(
            self._client.get_fly_statis(
                dept_id=dept_id, startdate=startdate, enddate=enddate
            ),
            self._client.get_warn_static(
                dept_id=dept_id, startdate=startdate, enddate=enddate
            ),
            self._client.get_media_static(
                dept_id=dept_id, startdate=startdate, enddate=enddate
            ),
            return_exceptions=False,
        )
        return {
            "fly_statis": fly_statis,
            "warn_static": warn_static,
            "media_static": media_static,
        }

    @staticmethod
    def _pivot_period_results_by_endpoint(
        by_dept: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        pivoted: dict[str, dict[str, Any]] = {}
        for dept_id, result in by_dept.items():
            for endpoint, payload in result.items():
                pivoted.setdefault(endpoint, {})[dept_id] = payload
        return pivoted


__all__ = ["SqlDataFetcher"]
