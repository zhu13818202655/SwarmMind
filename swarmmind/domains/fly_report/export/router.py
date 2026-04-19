"""Routes a :class:`ReportContext` to the appropriate renderer."""

from __future__ import annotations

from pathlib import Path

from swarmmind.domains.fly_report.chart import MatplotlibChartRenderer
from swarmmind.domains.fly_report.export.base import (
    BaseRenderer,
    RenderedArtifact,
)
from swarmmind.domains.fly_report.export.docx_renderer import DocxRenderer
from swarmmind.domains.fly_report.export.markdown_renderer import (
    MarkdownRenderer,
)
from swarmmind.domains.fly_report.export.pdf_renderer import PdfRenderer
from swarmmind.domains.fly_report.export.template_loader import TemplateLoader
from swarmmind.domains.fly_report.schemas import OutputFormat, ReportContext


class RendererRouter:
    """Picks the right renderer for a given ``output_format``."""

    def __init__(
        self,
        *,
        template_loader: TemplateLoader | None = None,
        chart_renderer: MatplotlibChartRenderer | None = None,
    ) -> None:
        loader = template_loader or TemplateLoader()
        charts = chart_renderer or MatplotlibChartRenderer()
        self._renderers: dict[OutputFormat, BaseRenderer] = {
            "markdown": MarkdownRenderer(
                template_loader=loader, chart_renderer=charts
            ),
            "pdf": PdfRenderer(
                template_loader=loader, chart_renderer=charts
            ),
            "docx": DocxRenderer(
                template_loader=loader, chart_renderer=charts
            ),
        }

    def render(
        self,
        ctx: ReportContext,
        *,
        output_format: OutputFormat,
        output_dir: Path,
        template_ref: str | None = None,
    ) -> RenderedArtifact:
        try:
            renderer = self._renderers[output_format]
        except KeyError as exc:
            raise ValueError(
                f"Unsupported output_format: {output_format!r}"
            ) from exc
        return renderer.render(
            ctx,
            output_dir=output_dir,
            template_ref=template_ref,
        )
