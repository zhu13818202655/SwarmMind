"""Zero-arg smoke test for DataFetcher.fetch and analyze.

Usage:
    python scripts/test_data_fetcher_fetch.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from swarmmind.config.schema import FlyReportDikongConfig
from swarmmind.domains.fly_report.analyzer.aggregations import analyze
from swarmmind.domains.fly_report.data_fetcher import DataFetcher
from swarmmind.domains.fly_report.dikong.client import DikongClient
from swarmmind.domains.fly_report.schemas import (
    AnalysisResult,
    Dimension,
    FilterSpec,
    NormalizedFilter,
    Period,
    RawDataset,
)


def _build_filter() -> NormalizedFilter:
    now = datetime.now(UTC)
    period = Period(
        kind="weekly",
        start=now - timedelta(days=7),
        end=now,
    )
    spec = FilterSpec(
        period=period,
        dept_names=["武义县资规局", "武义县公安局", "武义县交通运输局", "武义县建设局", "金华市生态环境局武义分局", "武义县综合行政执法局（城市管理局）", "武义县农业农村局", "县创建办"],
        dept_ids=[375,382, 381, 395, 394, 384, 217],
        dimension=Dimension(
            scope="department"
        ),
    )
    print(
        "Testing with filter spec:",
        now.fromtimestamp(period.start.timestamp()).strftime("%Y-%m-%d"),
        "to",
        now.fromtimestamp(period.end.timestamp()).strftime("%Y-%m-%d"),
        "with departments",
        spec.dimension.department_ids,
    )
    return NormalizedFilter.from_filter(spec)


async def fetch_data() -> tuple[RawDataset, NormalizedFilter]:
    filt = _build_filter()
    fetcher = DataFetcher(
        client=DikongClient(
            config=FlyReportDikongConfig(
                base_url="http://61.169.171.82:50001",
                account="admin",
                password="1qazXSW@4321",
                token_ttl_seconds=720,
                token_refresh_skew_seconds=60,
                request_timeout_seconds=15.0,
                max_retries=2,
                retry_backoff_seconds=0.5,
                max_concurrency=8,
                rate_limit_per_second=10.0,
                department_id_list=[],
            )
        )
    )

    result = await fetcher.fetch(filt)
    with open("test_data_fetcher_fetch_output.json", "w", encoding="utf-8") as f:
        json.dump(result.model_dump(mode="json"), f, ensure_ascii=False, indent=2)
    return result, filt


def analyze_data(raw: RawDataset, filt: NormalizedFilter) -> AnalysisResult:
    result = analyze(raw, filt)
    with open("test_data_fetcher_analysis_output.json", "w", encoding="utf-8") as f:
        json.dump(result.model_dump(mode="json"), f, ensure_ascii=False, indent=2)
    return result


async def _main() -> None:
    raw, filt = await fetch_data()
    analysis = analyze_data(raw, filt)
    print("Analysis table count:", len(analysis.model_dump()))


if __name__ == "__main__":
    asyncio.run(_main())
