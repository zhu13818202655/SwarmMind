"""DataFetcher: translate a :class:`NormalizedFilter` into DikongClient calls.

Responsibilities (DESIGN-2 §4.1.5 / §6):
- Map ``indicators × dimension`` to the correct DikongClient methods.
- Fetch current period **and** previous period (for 同比/环比) in parallel.
- Return a :class:`RawDataset` with ``current`` and ``previous`` keyed by
  endpoint name.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

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

    weekly  → previous 7 days
    monthly → previous calendar month (approximate: same delta)
    custom  → shift back by ``(end - start)``
    """
    delta = period.end - period.start
    if delta.total_seconds() <= 0:
        delta = timedelta(days=7)
    return Period(
        kind=period.kind,
        start=period.start - delta,
        end=period.end - delta,
        label=f"上一{period.kind}",
    )


# ---------------------------------------------------------------------------
# Indicator → fetch-functions mapping
# ---------------------------------------------------------------------------

# Each entry returns a dict of ``{key: pydantic_model_dump}``.

async def _fetch_flight(
    client: DikongClient,
    filt: NormalizedFilter,
    *,
    period: Period,
    dept_id: int | None,
    tenant_id: str | None,
) -> dict[str, Any]:
    """Fetch flight statistics for a single period."""
    resp = await client.get_fly_statis(
        dept_id=dept_id,
        startdate=_fmt_date(period.start),
        enddate=_fmt_date(period.end),
        tenant_id=tenant_id,
    )
    return {"fly_statis": resp.model_dump()}


async def _fetch_algorithm(
    client: DikongClient,
    filt: NormalizedFilter,
    *,
    period: Period,
    dept_id: int | None,
    tenant_id: str | None,
) -> dict[str, Any]:
    resp = await client.get_warn_static(
        dept_id=dept_id,
        startdate=_fmt_date(period.start),
        enddate=_fmt_date(period.end),
        tenant_id=tenant_id,
    )
    return {"warn_static": resp.model_dump()}


async def _fetch_media(
    client: DikongClient,
    filt: NormalizedFilter,
    *,
    period: Period,
    dept_id: int | None,
    tenant_id: str | None,
) -> dict[str, Any]:
    resp = await client.get_media_static(
        dept_id=dept_id,
        startdate=_fmt_date(period.start),
        enddate=_fmt_date(period.end),
        tenant_id=tenant_id,
    )
    return {"media_static": resp.model_dump()}


async def _fetch_device_health(
    client: DikongClient,
    filt: NormalizedFilter,
    *,
    period: Period,
    dept_id: int | None,
    tenant_id: str | None,
) -> dict[str, Any]:
    resp = await client.get_hms_stats(dept_id=dept_id, tenant_id=tenant_id)
    return {"hms_stats": resp.model_dump()}


_INDICATOR_FETCHERS = {
    "flight": _fetch_flight,
    "algorithm": _fetch_algorithm,
    "media_image": _fetch_media,
    "media_video": _fetch_media,  # same endpoint, analyzer splits later
    "device_health": _fetch_device_health,
}


# ---------------------------------------------------------------------------
# DataFetcher
# ---------------------------------------------------------------------------


class DataFetcher:
    """Fetch raw data from dikong based on a :class:`NormalizedFilter`.

    Parameters
    ----------
    client:
        An initialised :class:`DikongClient`.
    tenant_id:
        Default tenant id to pass to all dikong calls.
    """

    def __init__(
        self,
        client: DikongClient,
        *,
        tenant_id: str | None = None,
    ) -> None:
        self._client = client
        self._tenant_id = tenant_id

    async def fetch(self, filt: NormalizedFilter) -> RawDataset:
        """Fetch current + previous period data for all requested indicators."""

        prev_period = _previous_period(filt.period)

        # Determine the first department id for dept-scoped queries (overall = None).
        dept_id = self._resolve_dept_id(filt)

        # Deduplicate fetchers (media_image & media_video share the same fn).
        fetchers: dict[str, Any] = {}
        for indicator in filt.indicators:
            fn = _INDICATOR_FETCHERS.get(indicator)
            if fn is not None and fn not in fetchers.values():
                fetchers[indicator] = fn

        current_data, previous_data = await asyncio.gather(
            self._fetch_period(fetchers, filt, filt.period, dept_id),
            self._fetch_period(fetchers, filt, prev_period, dept_id),
        )

        # M2: per-department fan-out when comparing 2+ departments.
        if self._needs_dept_fanout(filt):
            cur_by_dept, prev_by_dept = await asyncio.gather(
                self._fetch_per_dept(fetchers, filt, filt.period),
                self._fetch_per_dept(fetchers, filt, prev_period),
            )
            from swarmmind.domains.fly_report.analyzer.comparisons import (
                PER_DEPT_KEY,
            )

            current_data[PER_DEPT_KEY] = cur_by_dept
            previous_data[PER_DEPT_KEY] = prev_by_dept

        return RawDataset(current=current_data, previous=previous_data)

    async def _fetch_per_dept(
        self,
        fetchers: dict[str, Any],
        filt: NormalizedFilter,
        period: Period,
    ) -> dict[str, dict[str, Any]]:
        """Run all fetchers once per department id, in parallel."""

        dept_ids = list(filt.dimension.department_ids)
        results = await asyncio.gather(
            *(
                self._fetch_period(fetchers, filt, period, self._coerce_int(d))
                for d in dept_ids
            )
        )
        return {str(dept_id): payload for dept_id, payload in zip(dept_ids, results)}

    @staticmethod
    def _needs_dept_fanout(filt: NormalizedFilter) -> bool:
        if filt.dimension.scope != "department":
            return False
        return len(filt.dimension.department_ids) >= 2

    @staticmethod
    def _coerce_int(val: Any) -> int | None:
        try:
            return int(val)
        except (ValueError, TypeError):
            return None

    async def _fetch_period(
        self,
        fetchers: dict[str, Any],
        filt: NormalizedFilter,
        period: Period,
        dept_id: int | None,
    ) -> dict[str, Any]:
        """Run all fetcher functions for one period in parallel."""

        tasks = [
            fn(
                self._client,
                filt,
                period=period,
                dept_id=dept_id,
                tenant_id=self._tenant_id,
            )
            for fn in fetchers.values()
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        merged: dict[str, Any] = {}
        for result in results:
            if isinstance(result, BaseException):
                logger.warning("fetcher failed: %s", result)
                continue
            merged.update(result)
        return merged

    @staticmethod
    def _resolve_dept_id(filt: NormalizedFilter) -> int | None:
        """Extract a single dept id for simple overall/department queries.

        If multiple departments are specified (comparison), returns None
        (the analyzer handles per-dept iteration at a higher level).
        """
        ids = filt.dimension.department_ids
        if len(ids) == 1:
            try:
                return int(ids[0])
            except (ValueError, TypeError):
                return None
        return None


__all__ = ["DataFetcher"]
