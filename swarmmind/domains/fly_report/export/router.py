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
        docx_renderer = DocxRenderer(
            template_loader=loader, chart_renderer=charts
        )
        self._docx_renderer = docx_renderer
        self._renderers: dict[OutputFormat, BaseRenderer] = {
            "markdown": MarkdownRenderer(
                template_loader=loader, chart_renderer=charts
            ),
            "pdf": PdfRenderer(
                template_loader=loader, chart_renderer=charts
            ),
            "docx": docx_renderer,
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

    def render_markdown_to_docx(
        self,
        markdown: str,
        *,
        output_dir: Path,
        filename: str = "markdown-report.docx",
        template_ref: str | None = None,
        title: str | None = None,
    ) -> RenderedArtifact:
        """Render a Markdown document directly to ``.docx``.

        This path is intentionally separate from :meth:`render`: callers can
        pass a complete Markdown report without first reshaping it into a
        :class:`ReportContext` template tree.
        """

        return self._docx_renderer.render_markdown(
            markdown,
            output_dir=output_dir,
            filename=filename,
            template_ref=template_ref,
            title=title,
        )
