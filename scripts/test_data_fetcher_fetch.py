"""Zero-arg smoke test for DataFetcher.fetch and analyze.

The script still performs a real fetch first to verify login/connectivity, then
replaces the sparse live payload with richer realistic mock data before analysis.

Usage:
    python scripts/test_data_fetcher_fetch.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


_load_dotenv(ROOT / ".env")

from swarmmind.config.schema import FlyReportDikongConfig
from swarmmind.domains.fly_report.analyzer.aggregations import analyze
from swarmmind.domains.fly_report.composer import compose_report_context
from swarmmind.domains.fly_report.data_fetcher import DataFetcher
from swarmmind.domains.fly_report.dikong.client import DikongClient
from swarmmind.domains.fly_report.export import RendererRouter
from swarmmind.domains.fly_report.schemas import (
    AnalysisResult,
    Dimension,
    FilterSpec,
    NormalizedFilter,
    Period,
    RawDataset,
)


DEPT_NAMES = [
    "武义县资规局",
    "武义县公安局",
    "武义县交通运输局",
    "武义县建设局",
    "金华市生态环境局武义分局",
    "武义县综合行政执法局（城市管理局）",
    "武义县农业农村局",
    "县创建办",
]

DEPT_IDS = [375, 382, 381, 395, 394, 384, 217]


def _build_filter() -> NormalizedFilter:
    now = datetime.now(UTC)
    period = Period(
        kind="weekly",
        start=now - timedelta(days=7),
        end=now,
    )
    spec = FilterSpec(
        period=period,
        dept_names=DEPT_NAMES,
        dept_ids=DEPT_IDS,
        dimension=Dimension(scope="department"),
    )
    print(
        "Testing with filter spec:",
        period.start.strftime("%Y-%m-%d"),
        "to",
        period.end.strftime("%Y-%m-%d"),
        "with departments",
        spec.dept_ids,
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

    live = await fetcher.fetch(filt)
    _write_json("test_data_fetcher_live_output.json", live.model_dump(mode="json"))

    # mocked = replace_fetched_data_with_mock(live, filt)
    # _write_json("test_data_fetcher_fetch_output.json", mocked.model_dump(mode="json"))
    return live, filt


def replace_fetched_data_with_mock(raw: RawDataset, filt: NormalizedFilter) -> RawDataset:
    """Replace sparse live data with richer realistic mock data.

    The live fetch still runs first, then this function returns a normal
    RawDataset. Downstream analysis remains unaware of the replacement.
    """

    print(
        "Fetched live dataset keys:",
        {
            "current": sorted(raw.current.keys()),
            "previous": sorted(raw.previous.keys()),
        },
    )
    mocked = RawDataset(
        current=_build_mock_period_data(filt, previous=False),
        previous=_build_mock_period_data(filt, previous=True),
    )
    print(
        "Replaced with mock dataset:",
        {
            "current_job_logs": len(mocked.current["fly_job_logs"]["records"]),
            "previous_job_logs": len(mocked.previous["fly_job_logs"]["records"]),
            "current_warn_records": _count_warn_records(mocked.current["warn_static"]),
            "previous_warn_records": _count_warn_records(mocked.previous["warn_static"]),
        },
    )
    return mocked


def _build_mock_period_data(filt: NormalizedFilter, *, previous: bool) -> dict[str, Any]:
    scale = 0.72 if previous else 1.0
    period_shift = filt.period.end - filt.period.start if previous else timedelta(0)
    period_start = filt.period.start - period_shift
    dept_ids = filt.dept_ids or DEPT_IDS
    dept_names = filt.dept_names or DEPT_NAMES

    fly_statis: dict[str, dict[str, Any]] = {}
    media_static: dict[str, dict[str, Any]] = {}
    warn_static: dict[str, dict[str, Any]] = {}
    job_logs: list[dict[str, Any]] = []

    for index, dept_id in enumerate(dept_ids):
        dept_name = dept_names[index] if index < len(dept_names) else f"部门{dept_id}"
        weight = index + 1
        completed_count = max(8, int(round((16 + weight * 4) * scale)))
        exception_count = max(1, int(round((weight % 3 + 1) * scale)))
        total_count = completed_count + exception_count
        flight_hours = round((completed_count * (0.34 + weight * 0.025)) * scale, 2)

        fly_statis[str(dept_id)] = {
            "num_total": total_count,
            "fly_time_total": flight_hours,
            "fly_mileage_total": round(flight_hours * (7.6 + weight), 2),
            "route_plan_count": int(round((24 + weight * 5) * scale)),
        }
        media_static[str(dept_id)] = {
            "picCount": int(round((180 + weight * 42) * scale)),
            "picLableCount": int(round((96 + weight * 25) * scale)),
            "picLabelCount": int(round((96 + weight * 25) * scale)),
            "videoCount": int(round((18 + weight * 3) * scale)),
            "videoDurationMinute": round((260 + weight * 38) * scale, 1),
        }
        warn_static[str(dept_id)] = {
            "records": _build_mock_warn_records(
                dept_id=dept_id,
                dept_name=dept_name,
                period_start=period_start,
                count=max(4, int(round((6 + weight * 2) * scale))),
                previous=previous,
            ),
            "total": max(4, int(round((6 + weight * 2) * scale))),
        }
        job_logs.extend(
            _build_mock_job_logs(
                dept_id=dept_id,
                dept_name=dept_name,
                period_start=period_start,
                completed_count=completed_count,
                exception_count=exception_count,
                previous=previous,
            )
        )

    return {
        "fly_statis": fly_statis,
        "media_static": media_static,
        "warn_static": warn_static,
        "fly_job_logs": {
            "records": job_logs,
            "total": len(job_logs),
            "size": len(job_logs),
            "current": 1,
            "pages": 1,
        },
    }


def _build_mock_job_logs(
    *,
    dept_id: int,
    dept_name: str,
    period_start: datetime,
    completed_count: int,
    exception_count: int,
    previous: bool,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index in range(completed_count):
        begin = period_start + timedelta(
            days=index % 7,
            hours=8 + (index * 3) % 10,
            minutes=(index * 7 + dept_id) % 60,
        )
        duration_minutes = 18 + (index % 6) * 7 + (dept_id % 5)
        end = begin + timedelta(minutes=duration_minutes)
        records.append(
            {
                "id": f"job-{dept_id}-{index}-{'prev' if previous else 'cur'}",
                "status": "2",
                "begin_time": begin.strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": end.strftime("%Y-%m-%d %H:%M:%S"),
                "deptids_tag": str(dept_id),
                "deptidsTagName": dept_name,
                "mission_name": f"{dept_name}巡查任务{index + 1}",
                "drone_name": f"无人机-{dept_id % 100}-{index % 4 + 1}",
                "pilot_name": f"飞手-{dept_id % 100}-{index % 5 + 1}",
            }
        )

    for index in range(exception_count):
        begin = period_start + timedelta(days=(index * 2 + dept_id) % 7, hours=15, minutes=index * 8)
        records.append(
            {
                "id": f"job-exception-{dept_id}-{index}-{'prev' if previous else 'cur'}",
                "status": "4",
                "begin_time": begin.strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": "",
                "deptids_tag": str(dept_id),
                "deptidsTagName": dept_name,
                "mission_name": f"{dept_name}异常中断任务{index + 1}",
                "drone_name": f"无人机-{dept_id % 100}-异常",
                "pilot_name": f"飞手-{dept_id % 100}-异常{index + 1}",
            }
        )
    return records


def _build_mock_warn_records(
    *,
    dept_id: int,
    dept_name: str,
    period_start: datetime,
    count: int,
    previous: bool,
) -> list[dict[str, Any]]:
    algorithms = ["违停识别", "裸土识别", "河道漂浮物", "违建识别", "烟火识别"]
    locations = ["武阳路", "熟溪街道", "壶山公园", "白洋街道", "王宅镇", "泉溪镇"]
    records: list[dict[str, Any]] = []
    for index in range(count):
        created = period_start + timedelta(
            days=index % 7,
            hours=7 + (index * 2) % 14,
            minutes=(index * 9 + dept_id) % 60,
        )
        target_count = 1 + index % 4
        records.append(
            {
                "id": f"warn-{dept_id}-{index}-{'prev' if previous else 'cur'}",
                "deptName": dept_name,
                "dept_name": dept_name,
                "algorithmName": algorithms[index % len(algorithms)],
                "workOrderName": algorithms[index % len(algorithms)],
                "status": "2" if index % 3 else "1",
                "pushStatus": "1" if index % 2 == 0 else "0",
                "createTime": created.strftime("%Y-%m-%d %H:%M:%S"),
                "pushTime": (created + timedelta(minutes=6 + index % 8)).strftime("%Y-%m-%d %H:%M:%S"),
                "location": f"{locations[index % len(locations)]}{20 + index}号附近",
                "extraResult": json.dumps(
                    {"targets": [f"target-{dept_id}-{index}-{num}" for num in range(target_count)]},
                    ensure_ascii=False,
                ),
            }
        )
    return records


def _count_warn_records(payload: Any) -> int:
    if not isinstance(payload, dict):
        return 0
    total = 0
    for item in payload.values():
        if isinstance(item, dict) and isinstance(item.get("records"), list):
            total += len(item["records"])
    return total


def analyze_data(raw: RawDataset, filt: NormalizedFilter) -> AnalysisResult:
    result = analyze(raw, filt)
    _write_json("test_data_fetcher_analysis_output.json", result.model_dump(mode="json"))
    return result


async def compose_data(analysis: AnalysisResult, filt: NormalizedFilter) -> str:
    markdown = await compose_report_context(
        session_id="test-data-fetcher-session",
        analysis=analysis,
        filt=filt,
        revision=1,
    )
    Path("test_data_fetcher_context_output.md").write_text(markdown, encoding="utf-8")
    return markdown


def render_docx_report(markdown: str) -> Path:
    output_dir = ROOT / "data" / "fly_report_artifacts" / "test-data-fetcher-session" / "docx"
    artifact = RendererRouter().render_markdown_to_docx(
        markdown,
        output_dir=output_dir,
        filename="test-data-fetcher-session.docx",
        title="武义飞行服务平台飞行统计报告",
    )
    artifact_path = Path(artifact.artifact_path).resolve()
    if not artifact_path.is_file():
        raise FileNotFoundError(artifact_path)
    return artifact_path


def _write_json(path: str, payload: Any) -> None:
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


async def _main() -> None:
    raw, filt = await fetch_data()
    analysis = analyze_data(raw, filt)
    markdown = await compose_data(analysis, filt)
    docx_path = render_docx_report(markdown)
    print("Analysis table count:", len(analysis.model_dump()))
    print("Markdown length:", len(markdown))
    print("DOCX artifact path:", docx_path)


if __name__ == "__main__":
    asyncio.run(_main())
