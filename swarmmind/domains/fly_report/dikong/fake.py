"""In-process deterministic stand-in for :class:`DikongClient`.

Implements the same async signatures that :class:`DataFetcher` uses, so
the FlyReport pipeline can run end-to-end without a reachable dikong
upstream (local development, CI, demo). All numbers are derived from a
small hash of ``(startdate, dept_id)`` so behaviour is reproducible.

This is **not** a subclass of :class:`DikongClient`; the real client is a
heavy ``httpx``-backed object. We just duck-type the 5 core methods.
"""

from __future__ import annotations

from swarmmind.domains.fly_report.dikong.parsers import (
    FlyJobLogResp,
    FlyJobLogRow,
    FlyStatisResp,
    HmsStatsResp,
    MediaStaticResp,
    MissionQueryByPageResp,
    WarnStaticResp,
)


def _seed(startdate: str | None, dept_id: int | str | None) -> int:
    base = sum(ord(c) for c in (startdate or "x")) % 40
    if dept_id is not None:
        try:
            base += int(dept_id) * 3
        except (TypeError, ValueError):
            base += sum(ord(c) for c in str(dept_id)) % 17
    return base % 60


class FakeDikongClient:
    """Drop-in replacement for :class:`DikongClient` (5 core endpoints)."""

    async def aclose(self) -> None:  # noqa: D401 - parity with real client
        return None

    async def __aenter__(self) -> "FakeDikongClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

    async def get_fly_statis(
        self,
        *,
        dept_id: int | str | None = None,
        startdate: str | None = None,
        enddate: str | None = None,
        tenant_id: str | None = None,
    ) -> FlyStatisResp:
        s = _seed(startdate, dept_id)
        return FlyStatisResp(
            droneCount=8 + s % 6,
            hangarCount=2 + s % 3,
            routePlanCount=12 + s,
            flyMileageTotal=300.0 + s * 2.5,
            flyTimeTotal=40.0 + s * 0.6,
            numTotal=80 + s,
            droneJobCount=60 + s,
            hangarJobCount=10 + s % 7,
            algorithmCount=5 + s % 4,
        )

    async def get_warn_static(
        self,
        *,
        dept_id: int | str | None = None,
        startdate: str | None = None,
        enddate: str | None = None,
        tenant_id: str | None = None,
    ) -> WarnStaticResp:
        s = _seed(startdate, dept_id)
        return WarnStaticResp(
            raw={
                "intrusion": 5 + s,
                "fire": 1 + s % 3,
                "vehicle": 3 + s % 5,
                "other": 2 + s % 4,
            }
        )

    async def get_media_static(
        self,
        *,
        dept_id: int | str | None = None,
        startdate: str | None = None,
        enddate: str | None = None,
        tenant_id: str | None = None,
    ) -> MediaStaticResp:
        s = _seed(startdate, dept_id)
        return MediaStaticResp(raw={"image": 30 + s, "video": 5 + s % 7})

    async def get_hms_stats(
        self,
        *,
        dept_id: int | str | None = None,
        tenant_id: str | None = None,
    ) -> HmsStatsResp:
        s = _seed(None, dept_id)
        return HmsStatsResp(raw={"warn": 2 + s % 5, "error": 1 + s % 3})

    async def get_department_name_list_by_id_list(
        self, dept_id_list: list[str]
    ) -> list[str]:
        return [f"部门{dept_id}" for dept_id in dept_id_list]

    async def get_fly_job_logs(
        self,
        *,
        begin_time: str | None = None,
        end_time: str | None = None,
        page_num: int = 1,
        page_size: int = 500,
    ) -> FlyJobLogResp:
        s = _seed(begin_time, None)
        records = [
            FlyJobLogRow(
                id=i,
                name=f"巡检任务{i}",
                jobLogId=f"fake-job-{s}-{i}",
                jobLogNo=f"FJ{s:02d}{i:03d}",
                beginTime=begin_time,
                endTime=end_time,
                deptidsTag=str(380 + i % 5),
                deptidsTagName=f"部门{380 + i % 5}",
                deviceSn=f"SN-{i:03d}",
                operatorName="离线演示员",
                totalLength=str(3.5 + i),
                status="completed",
            )
            for i in range(1, min(page_size, 8) + 1)
        ]
        return FlyJobLogResp(
            size=len(records), current=page_num, total=len(records), pages=1, records=records
        )

    async def query_missions_by_page(
        self,
        *,
        page_num: int = 1,
        page_size: int = 20,
        dept_id: int | str | None = None,
        tenant_id: str | None = None,
    ) -> MissionQueryByPageResp:
        return MissionQueryByPageResp(total=0, pageNum=page_num, pageSize=page_size, list=[])


__all__ = ["FakeDikongClient"]
