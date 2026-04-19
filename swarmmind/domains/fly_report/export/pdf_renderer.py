"""PDF renderer powered by Jinja2 + WeasyPrint.

If WeasyPrint is not installed (it has heavy native deps: cairo, pango, ...),
the renderer gracefully falls back to writing a standalone ``.html`` artifact
and records a warning. This keeps the FlyReport pipeline runnable in
minimal CI environments while still producing a meaningful preview.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from swarmmind.domains.fly_report.export.base import (
    BaseRenderer,
    RenderedArtifact,
)
from swarmmind.domains.fly_report.export.template_loader import LoadedTemplate
from swarmmind.domains.fly_report.schemas import OutputFormat, ReportContext


class PdfRenderer(BaseRenderer):
    output_format: OutputFormat = "pdf"

    def _render(
        self,
        ctx: ReportContext,
        *,
        loaded: LoadedTemplate,
        output_dir: Path,
    ) -> RenderedArtifact:
        env = Environment(
            loader=FileSystemLoader(loaded.format_root),
            undefined=StrictUndefined,
            autoescape=True,
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
        )
        template = env.get_template(loaded.template_name)
        html = template.render(
            report=_report_view(ctx),
            sections=ctx.sections,
        )

        warnings: list[str] = []
        try:
            from weasyprint import HTML  # type: ignore[import-not-found]
        except ImportError:
            html_path = output_dir / f"{ctx.session_id}.html"
            html_path.write_text(html, encoding="utf-8")
            warnings.append(
                "WeasyPrint not installed; emitted standalone HTML instead "
                "of PDF. Install ``weasyprint`` to enable PDF rendering."
            )
            return RenderedArtifact(
                output_format=self.output_format,
                artifact_path=str(html_path),
                template_ref=loaded.template_ref,
                warnings=warnings,
            )

        pdf_path = output_dir / f"{ctx.session_id}.pdf"
        HTML(string=html, base_url=str(loaded.format_root)).write_pdf(
            str(pdf_path)
        )
        return RenderedArtifact(
            output_format=self.output_format,
            artifact_path=str(pdf_path),
            template_ref=loaded.template_ref,
            warnings=warnings,
        )


def _report_view(ctx: ReportContext) -> dict[str, object]:
    f = ctx.filter
    scope_label = {
        "overall": "总体",
        "department": "部门",
        "pilot": "飞手",
    }.get(f.dimension.scope, f.dimension.scope)
    return {
        "title": f"{f.period.label} {scope_label}飞行报告",
        "period_label": f.period.label,
        "scope_kind": f.dimension.scope,
        "scope_label": scope_label,
        "department_ids": list(f.dimension.department_ids),
        "pilot_ids": list(f.dimension.pilot_ids),
        "indicators": list(f.indicators),
        "session_id": ctx.session_id,
        "revision": ctx.revision,
        "generated_at": ctx.generated_at.strftime("%Y-%m-%d %H:%M"),
    }
