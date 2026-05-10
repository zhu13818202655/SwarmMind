from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from swarmmind.domains.fly_report.data_fetcher import DataFetcher
from swarmmind.domains.fly_report.composer import simple_composer
from swarmmind.domains.fly_report.dikong.parsers import (
    FlyJobLogResp,
    FlyJobLogRow,
    FlyStatisResp,
    HmsStatsResp,
    MediaStaticResp,
    MissionQueryByPageResp,
    WarnStaticResp,
)
from swarmmind.domains.fly_report.lm.types import LMChatResponse, LMOutputFormat
from swarmmind.domains.fly_report.schemas import (
    DraftFilterSpec,
    OutputFormat,
    Period,
    ReportOptions,
)
from swarmmind.domains.fly_report.service import FlyReportService


def _seed(startdate: str | None, dept_id: int | str | None) -> int:
    base = sum(ord(char) for char in (startdate or "x")) % 40
    if dept_id is not None:
        try:
            base += int(dept_id) * 3
        except (TypeError, ValueError):
            base += sum(ord(char) for char in str(dept_id)) % 17
    return base % 60


class _FakeDikongClient:
    async def aclose(self) -> None:
        return None

    async def get_department_name_list_by_id_list(
        self, dept_id_list: list[str]
    ) -> list[str]:
        return [f"部门{dept_id}" for dept_id in dept_id_list]

    async def get_fly_statis(
        self,
        *,
        dept_id: int | str | None = None,
        startdate: str | None = None,
        enddate: str | None = None,
        tenant_id: str | None = None,
    ) -> FlyStatisResp:
        seed = _seed(startdate, dept_id)
        return FlyStatisResp(
            droneCount=8 + seed % 6,
            hangarCount=2 + seed % 3,
            routePlanCount=12 + seed,
            flyMileageTotal=300.0 + seed * 2.5,
            flyTimeTotal=40.0 + seed * 0.6,
            numTotal=80 + seed,
            droneJobCount=60 + seed,
            hangarJobCount=10 + seed % 7,
            algorithmCount=5 + seed % 4,
        )

    async def get_warn_static(
        self,
        *,
        dept_id: int | str | None = None,
        startdate: str | None = None,
        enddate: str | None = None,
        tenant_id: str | None = None,
    ) -> WarnStaticResp:
        seed = _seed(startdate, dept_id)
        return WarnStaticResp(
            raw={
                "intrusion": 5 + seed,
                "fire": 1 + seed % 3,
                "vehicle": 3 + seed % 5,
                "other": 2 + seed % 4,
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
        seed = _seed(startdate, dept_id)
        return MediaStaticResp(raw={"image": 30 + seed, "video": 5 + seed % 7})

    async def get_hms_stats(
        self,
        *,
        dept_id: int | str | None = None,
        tenant_id: str | None = None,
    ) -> HmsStatsResp:
        seed = _seed(None, dept_id)
        return HmsStatsResp(raw={"warn": 2 + seed % 5, "error": 1 + seed % 3})

    async def get_fly_job_logs(
        self,
        *,
        begin_time: str | None = None,
        end_time: str | None = None,
        page_num: int = 1,
        page_size: int = 500,
    ) -> FlyJobLogResp:
        seed = _seed(begin_time, None)
        records = [
            FlyJobLogRow(
                id=index,
                name=f"巡检任务{index}",
                jobLogId=f"test-job-{seed}-{index}",
                jobLogNo=f"FJ{seed:02d}{index:03d}",
                beginTime=begin_time,
                endTime=end_time,
                deptidsTag=str(380 + index % 5),
                deptidsTagName=f"部门{380 + index % 5}",
                deviceSn=f"SN-{index:03d}",
                operatorName="离线测试员",
                totalLength=str(3.5 + index),
                status="completed",
            )
            for index in range(1, min(page_size, 8) + 1)
        ]
        return FlyJobLogResp(
            size=len(records),
            current=page_num,
            total=len(records),
            pages=1,
            records=records,
        )

    async def query_missions_by_page(
        self,
        *,
        page_num: int = 1,
        page_size: int = 20,
        dept_id: int | str | None = None,
        tenant_id: str | None = None,
    ) -> MissionQueryByPageResp:
        return MissionQueryByPageResp(
            total=0,
            pageNum=page_num,
            pageSize=page_size,
            list=[],
        )


class _FakeLMClient:
    async def chat(self, **_: Any) -> str:
        return "测试摘要：报告数据已生成，关键指标表现稳定。"

    async def chat_response(self, request: Any) -> LMChatResponse:
        parsed = {
            "summary": "测试总结：飞行与算法数据已完成统计，整体运行平稳。",
            "suggestion": "1. 持续跟踪异常任务。\n2. 优化高频告警点位治理。",
        }
        return LMChatResponse(
            text=json.dumps(parsed, ensure_ascii=False),
            output_format=getattr(request, "output_format", LMOutputFormat.JSON),
            parsed=parsed,
            raw={"source": "test_fake_lm"},
            model_name="test-fake-lm",
        )


class RuleBasedIntentParser:
    async def parse(
        self,
        user_text: str,
        *,
        now: datetime | None = None,
        dept_names: list[str] | None = None,
        **_: Any,
    ) -> DraftFilterSpec:
        current = now or datetime.now()
        kind = "monthly" if "月" in user_text else "weekly"
        if kind == "monthly":
            start = current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            label = current.strftime("%Y-%m")
        else:
            start = current - timedelta(days=7)
            label = f"{start:%Y-%m-%d}~{current:%Y-%m-%d}"

        output_format: OutputFormat = "docx"
        lowered = user_text.lower()
        if "pdf" in lowered:
            output_format = "pdf"
        elif "markdown" in lowered or "md" in lowered:
            output_format = "markdown"

        return DraftFilterSpec(
            period=Period(kind=kind, start=start, end=current, label=label),
            dept_names=[name for name in (dept_names or []) if name in user_text],
            indicators=["flight", "algorithm", "media_image", "device_health"],
            options=ReportOptions(output_format=output_format),
        )


def build_fly_report_service(
    *,
    output_root: Path | str | None = None,
    intent_parser: Any | None = None,
    data_fetcher: DataFetcher | None = None,
    **kwargs: Any,
) -> FlyReportService:
    simple_composer.llm_client = _FakeLMClient()
    return FlyReportService(
        output_root=output_root,
        intent_parser=intent_parser or RuleBasedIntentParser(),
        data_fetcher=data_fetcher or DataFetcher(_FakeDikongClient()),
        **kwargs,
    )
