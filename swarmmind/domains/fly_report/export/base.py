"""Renderer base class & shared artifact schema (DESIGN-2 §4.1.6)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel, Field

from swarmmind.domains.fly_report.chart import MatplotlibChartRenderer
from swarmmind.domains.fly_report.export.template_loader import (
    LoadedTemplate,
    TemplateLoader,
)
from swarmmind.domains.fly_report.schemas import OutputFormat, ReportContext


class RenderedArtifact(BaseModel):
    """Output produced by a :class:`BaseRenderer`."""

    output_format: OutputFormat
    artifact_path: str
    template_ref: str
    chart_paths: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class BaseRenderer(ABC):
    """Common protocol for the docx / pdf / markdown renderers."""

    output_format: OutputFormat

    def __init__(
        self,
        *,
        template_loader: TemplateLoader,
        chart_renderer: MatplotlibChartRenderer | None = None,
    ) -> None:
        self._template_loader = template_loader
        self._chart_renderer = chart_renderer or MatplotlibChartRenderer()

    def render(
        self,
        ctx: ReportContext,
        *,
        output_dir: Path,
        template_ref: str | None = None,
    ) -> RenderedArtifact:
        loaded = self._template_loader.load(
            output_format=self.output_format,
            template_ref=template_ref,
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        chart_paths = self._render_charts(ctx, output_dir=output_dir)
        artifact = self._render(ctx, loaded=loaded, output_dir=output_dir)
        artifact.chart_paths = [str(p) for p in chart_paths]
        return artifact

    def _render_charts(
        self, ctx: ReportContext, *, output_dir: Path
    ) -> list[Path]:
        all_charts = [c for section in ctx.sections for c in section.charts]
        if not all_charts:
            return []
        charts_dir = output_dir / "charts"
        return self._chart_renderer.render_many(
            all_charts, output_dir=charts_dir
        )

    # -------------------------------------------------------------- subclasses
    @abstractmethod
    def _render(
        self,
        ctx: ReportContext,
        *,
        loaded: LoadedTemplate,
        output_dir: Path,
    ) -> RenderedArtifact: ...
