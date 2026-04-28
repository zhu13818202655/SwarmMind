from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from swarmmind.domains.fly_report.data_fetcher import DataFetcher
from swarmmind.domains.fly_report.dikong.fake import FakeDikongClient
from swarmmind.domains.fly_report.schemas import (
    DraftFilterSpec,
    OutputFormat,
    Period,
    ReportOptions,
)
from swarmmind.domains.fly_report.service import FlyReportService


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
    return FlyReportService(
        output_root=output_root,
        intent_parser=intent_parser or RuleBasedIntentParser(),
        data_fetcher=data_fetcher or DataFetcher(FakeDikongClient()),
        **kwargs,
    )
