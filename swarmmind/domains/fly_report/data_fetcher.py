"""DataFetcher: translate a :class:`NormalizedFilter` into DikongClient calls.

Responsibilities (DESIGN-2 §4.1.5 / §6):
- Map the requested dimension to the correct DikongClient methods.
- Fetch current period **and** previous period (for 同比/环比) in parallel.
- Return a :class:`RawDataset` with ``current`` and ``previous`` keyed by
  endpoint name.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel

from swarmmind.domains.fly_report.dikong.client import DikongClient
from swarmmind.domains.fly_report.schemas import (
    NormalizedFilter,
    Period,
    RawDataset,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Date formatting helpers
# ---------------------------------------------------------------------------


def _fmt_date(dt: datetime) -> str:
    """Format a datetime to ``YYYY-MM-DD`` for dikong query params."""
    return dt.strftime("%Y-%m-%d")

def _previous_period(period: Period) -> Period:
    """Compute the immediately preceding period of the same length.

    weekly  -> previous 7 days
    monthly -> previous calendar month (approximate: same delta)
    custom  -> shift back by ``(end - start)``
    """
    delta = period.end - period.start
    if delta.total_seconds() <= 0:
        delta = timedelta(days=7)
    return Period(
        kind=period.kind,
        start=period.start - delta,
        end=period.end - delta,
    )


class DataFetcher:
    """Fetch raw data from dikong based on a :class:`NormalizedFilter`.

    Parameters
    ----------
    client:
        An initialised :class:`DikongClient`.
    """

    def __init__(
        self,
        client: DikongClient,
    ) -> None:
        self._client = client

    async def get_department_name_list_by_id_list(
        self,
        dept_id_list: list[str],
    ) -> list[str]:
        """Fetch department names for a list of department ids."""
        return await self._client.get_department_name_list_by_id_list(dept_id_list)

    async def fetch(self, filt: NormalizedFilter) -> RawDataset:
        """获取飞行报告所需要的数据。"""

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
                page_num=1,
                page_size=9999999,
            )
        )
        previous_job_logs_task = asyncio.create_task(
            self._client.get_fly_job_logs(
                start_time=f"{previous_start} 00:00:00",
                end_time=f"{previous_end} 23:59:59",
                page_num=1,
                page_size=9999999,
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

        current_job_logs = self._filter_job_logs_by_dept_ids(
            self._to_plain_data(await current_job_logs_task), dept_ids
        )
        previous_job_logs = self._filter_job_logs_by_dept_ids(
            self._to_plain_data(await previous_job_logs_task), dept_ids
        )

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
        """Fetch period data that can optionally be scoped by department."""

        fly_statis, warn_static, media_static = await asyncio.gather(
            self._client.get_fly_statis(
                dept_id=dept_id,
                startdate=startdate,
                enddate=enddate,

            ),
            self._client.get_warn_static(
                dept_id=dept_id,
                startdate=startdate,
                enddate=enddate,
                page_num=1,
                page_size=9999999,
            ),
            self._client.get_media_static(
                dept_id=dept_id,
                startdate=startdate,
                enddate=enddate,
            ),
            return_exceptions=False,
        )
        return {
            "fly_statis": self._to_plain_data(fly_statis),
            "warn_static": self._to_plain_data(warn_static),
            "media_static": self._to_plain_data(media_static),
        }

    @staticmethod
    def _pivot_period_results_by_endpoint(
        by_dept: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """Turn ``{dept_id: {endpoint: payload}}`` into ``{endpoint: {dept_id: payload}}``."""
        pivoted: dict[str, dict[str, Any]] = {}
        for dept_id, result in by_dept.items():
            for endpoint, payload in result.items():
                pivoted.setdefault(endpoint, {})[dept_id] = payload
        return pivoted

    @staticmethod
    def _filter_job_logs_by_dept_ids(
        payload: Any,
        dept_ids: list[int],
    ) -> Any:
        if not dept_ids or not isinstance(payload, dict):
            return payload

        records = payload.get("records")
        if not isinstance(records, list):
            return payload

        allowed = {str(dept_id) for dept_id in dept_ids}

        def _record_dept_id(record: Any) -> str | None:
            if not isinstance(record, dict):
                return None
            for key in ("deptId", "dept_id"):
                value = record.get(key)
                if value is not None:
                    return str(value)
            return None

        filtered_records = [
            record
            for record in records
            if _record_dept_id(record) in allowed
        ]
        filtered = dict(payload)
        filtered["records"] = filtered_records
        filtered["total"] = len(filtered_records)
        filtered["size"] = len(filtered_records)
        filtered["pages"] = 1 if filtered_records else 0
        return filtered

    @staticmethod
    def _to_plain_data(value: Any) -> Any:
        """Convert pydantic payloads to plain JSON-compatible data."""
        if isinstance(value, BaseModel):
            return value.model_dump(mode="json")
        if isinstance(value, list):
            return [DataFetcher._to_plain_data(item) for item in value]
        if isinstance(value, dict):
            return {key: DataFetcher._to_plain_data(item) for key, item in value.items()}
        return value


__all__ = ["DataFetcher"]
