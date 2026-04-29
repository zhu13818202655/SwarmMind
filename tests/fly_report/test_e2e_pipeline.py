"""End-to-end test for the FlyReport pipeline (DESIGN-2 §13 step 6).

Path covered: mock ``DikongClient`` → ``DataFetcher`` → ``analyze`` →
``compose_report_context`` → all three renderers (markdown / pdf / docx).

No LLM is called at this step. The "real LLM" hook documented in §13 step 6
will be added once the SectionSummarizerAgent is wired in M2+; for now the
``compose_report_context`` fills section summaries deterministically.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from swarmmind.domains.fly_report.analyzer import analyze
from swarmmind.domains.fly_report.composer import compose_report_context
from swarmmind.domains.fly_report.data_fetcher import DataFetcher
from swarmmind.domains.fly_report.dikong.parsers import (
    FlyJobLogResp,
    FlyStatisResp,
    HmsStatsResp,
    MediaStaticResp,
    WarnStaticResp,
)
from swarmmind.domains.fly_report.export import RendererRouter
from swarmmind.domains.fly_report.schemas import (
    Dimension,
    FilterSpec,
    NormalizedFilter,
    Period,
)


@pytest.fixture
def mock_dikong_client():
    """A DikongClient stub that returns deterministic typed payloads."""

    client = AsyncMock()

    # Current period > previous period so we get visible deltas.
    def fly(*, dept_id, startdate, enddate, tenant_id=None):
        is_current = startdate == "2026-04-06"
        return FlyStatisResp(
            droneCount=12 if is_current else 10,
            numTotal=128 if is_current else 102,
            flyMileageTotal=420.5 if is_current else 380.0,
            flyTimeTotal=64.5 if is_current else 70.0,
            droneJobCount=98 if is_current else 75,
        )

    def warn(*, dept_id, startdate, enddate, tenant_id=None):
        is_current = startdate == "2026-04-06"
        return WarnStaticResp(
            raw={"total": 18 if is_current else 32}
        )

    def media(*, dept_id, startdate, enddate, tenant_id=None):
        is_current = startdate == "2026-04-06"
        return MediaStaticResp(
            raw={"total": 56 if is_current else 41}
        )

    def hms(*, dept_id, tenant_id=None):
        # HMS endpoint has no period; same payload for both periods.
        return HmsStatsResp(raw={"total": 4})

    def job_logs(*, begin_time, end_time, dept_id=None, status=None, tenant_id=None):
        return FlyJobLogResp(records=[], total=0, size=0, pages=0)

    client.get_fly_statis.side_effect = fly
    client.get_warn_static.side_effect = warn
    client.get_media_static.side_effect = media
    client.get_hms_stats.side_effect = hms
    client.get_fly_job_logs.side_effect = job_logs
    return client


@pytest.fixture
def filter_spec() -> NormalizedFilter:
    spec = FilterSpec(
        period=Period(
            kind="weekly",
            start=datetime(2026, 4, 6, tzinfo=UTC),
            end=datetime(2026, 4, 13, tzinfo=UTC),
            label="2026-W15",
        ),
        dimension=Dimension(scope="overall"),
        indicators=["flight", "algorithm", "media_image", "device_health"],
    )
    return NormalizedFilter.from_filter(spec)


@pytest.mark.asyncio
async def test_e2e_renders_all_three_formats(
    tmp_path: Path, mock_dikong_client, filter_spec
):
    # 1. Fetch
    fetcher = DataFetcher(mock_dikong_client)
    raw = await fetcher.fetch(filter_spec)
    assert raw.current and raw.previous

    # Sanity-check the dikong stub fired for both periods.
    assert mock_dikong_client.get_fly_statis.await_count == 2

    # 2. Analyze
    analysis = analyze(raw, filter_spec)
    assert analysis.flight_stat_overall["rows"]
    flight_count = next(
        row
        for row in analysis.flight_stat_overall["rows"]
        if row.get("key") == "flight_count"
    )
    assert flight_count["meta"]["current_value"] == 128.0

    # 3. Compose into a renderable ReportContext
    ctx = compose_report_context(
        session_id="e2e-sess",
        analysis=analysis,
        filt=filter_spec,
    )
    assert ctx.sections, "composer should produce at least one section"
    assert any(section.charts for section in ctx.sections), (
        "composer should attach a chart per section"
    )

    # 4. Render all three formats with different presets.
    router = RendererRouter()

    md = router.render(
        ctx, output_format="markdown",
        output_dir=tmp_path / "md",
        template_ref="preset:default_zh",
    )
    assert md.artifact_path.endswith(".md")
    assert md.template_ref == "preset:default_zh"
    assert md.chart_paths and all(p.endswith(".png") for p in md.chart_paths)
    md_content = Path(md.artifact_path).read_text(encoding="utf-8")
    assert "武义飞行服务平台" in md_content
    assert "飞行统计" in md_content
    assert "总体飞行统计概览" in md_content

    pdf = router.render(
        ctx, output_format="pdf",
        output_dir=tmp_path / "pdf",
        template_ref="preset:gov_formal",
    )
    # PDF falls back to .html when WeasyPrint is unavailable in CI; both fine.
    assert pdf.artifact_path.endswith((".pdf", ".html"))
    assert pdf.template_ref == "preset:gov_formal"
    assert pdf.chart_paths

    docx = router.render(
        ctx, output_format="docx",
        output_dir=tmp_path / "docx",
        template_ref="preset:dashboard",
    )
    assert docx.artifact_path.endswith(".docx")
    assert docx.template_ref == "preset:dashboard"
    assert Path(docx.artifact_path).stat().st_size > 0
    assert docx.chart_paths

    # The PNG files referenced by the markdown report must exist on disk.
    for png in md.chart_paths:
        assert Path(png).exists() and Path(png).stat().st_size > 0
