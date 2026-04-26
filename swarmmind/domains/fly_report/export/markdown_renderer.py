"""Markdown renderer powered by Jinja2."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from swarmmind.domains.fly_report.export.base import (
    BaseRenderer,
    RenderedArtifact,
)
from swarmmind.domains.fly_report.export.template_loader import LoadedTemplate
from swarmmind.domains.fly_report.schemas import OutputFormat, ReportContext


class MarkdownRenderer(BaseRenderer):
    output_format: OutputFormat = "markdown"

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
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
        )
        template = env.get_template(loaded.template_name)
        rendered = template.render(
            report=_report_view(ctx),
            sections=ctx.sections,
            generated_at=ctx.generated_at,
        )
        out_path = output_dir / f"{ctx.session_id}.md"
        out_path.write_text(rendered, encoding="utf-8")
        return RenderedArtifact(
            output_format=self.output_format,
            artifact_path=str(out_path),
            template_ref=loaded.template_ref,
        )


def _report_view(ctx: ReportContext) -> dict[str, object]:
    f = ctx.filter
    return {
        "title": _title(ctx),
        "period_label": f.period.label,
        "scope_kind": f.dimension.scope,
        "department_ids": list(f.dimension.department_ids),
        "pilot_ids": list(f.dimension.pilot_ids),
        "session_id": ctx.session_id,
        "revision": ctx.revision,
        "generated_at": ctx.generated_at.strftime("%Y-%m-%d %H:%M"),
    }


def _title(ctx: ReportContext) -> str:
    period = ctx.filter.period.label
    scope = {
        "overall": "总体",
        "department": "部门",
        "pilot": "飞手",
    }.get(ctx.filter.dimension.scope, ctx.filter.dimension.scope)
    return f"{period} {scope}飞行报告"


# Keep ``datetime`` referenced so static analysers know we use it indirectly.
_ = datetime
