"""Docx renderer built directly with ``python-docx``.

We do not use docxtpl in M1: keeping templates as pure Python style dicts
(see :mod:`docx_styles`) avoids checking binary ``.docx`` files into git and
gives us full control over preset variants. The renderer assembles the
document programmatically from :class:`ReportContext`.
"""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Cm, Inches, Pt, RGBColor

from swarmmind.domains.fly_report.export.base import (
    BaseRenderer,
    RenderedArtifact,
)
from swarmmind.domains.fly_report.export.docx_styles import (
    DocxStyle,
    get_style,
)
from swarmmind.domains.fly_report.export.template_loader import LoadedTemplate
from swarmmind.domains.fly_report.schemas import OutputFormat, ReportContext


class DocxRenderer(BaseRenderer):
    output_format: OutputFormat = "docx"

    def _render(
        self,
        ctx: ReportContext,
        *,
        loaded: LoadedTemplate,
        output_dir: Path,
    ) -> RenderedArtifact:
        style = get_style(loaded.name)
        doc = Document()
        _apply_page_setup(doc, style)
        _write_title(doc, ctx, style)
        _write_meta(doc, ctx, style)
        _write_sections(doc, ctx, style, charts_dir=output_dir / "charts")
        _write_footer(doc, ctx, style)

        out_path = output_dir / f"{ctx.session_id}.docx"
        doc.save(str(out_path))
        return RenderedArtifact(
            output_format=self.output_format,
            artifact_path=str(out_path),
            template_ref=loaded.template_ref,
        )


# ---------------------------------------------------------------------- helpers


def _apply_page_setup(doc: Document, style: DocxStyle) -> None:
    for section in doc.sections:
        section.top_margin = Cm(style.page_margin_cm)
        section.bottom_margin = Cm(style.page_margin_cm)
        section.left_margin = Cm(style.page_margin_cm)
        section.right_margin = Cm(style.page_margin_cm)


def _write_title(doc: Document, ctx: ReportContext, style: DocxStyle) -> None:
    p = doc.add_paragraph()
    run = p.add_run(_title_text(ctx))
    _apply_run(run, style.title_font, style.title_size_pt, style.title_color_rgb, bold=True)


def _write_meta(doc: Document, ctx: ReportContext, style: DocxStyle) -> None:
    f = ctx.filter
    parts = [
        f"周期：{f.period.label}",
        f"范围：{_scope_label(f.dimension.scope)}",
    ]
    if f.dimension.department_ids:
        parts.append("部门：" + ", ".join(f.dimension.department_ids))
    if f.dimension.pilot_ids:
        parts.append("飞手：" + ", ".join(f.dimension.pilot_ids))
    parts.append(f"修订 v{ctx.revision}")
    p = doc.add_paragraph()
    run = p.add_run(" · ".join(parts))
    _apply_run(run, style.body_font, style.body_size_pt, (102, 102, 102))


def _write_sections(
    doc: Document,
    ctx: ReportContext,
    style: DocxStyle,
    *,
    charts_dir: Path,
) -> None:
    for index, section in enumerate(ctx.sections, start=1):
        heading = doc.add_paragraph()
        heading_text = (
            f"{style.section_prefix}{section.title}"
            if style.section_prefix
            else f"{index}. {section.title}"
        )
        run = heading.add_run(heading_text)
        _apply_run(run, style.title_font, style.heading_size_pt, style.heading_color_rgb, bold=True)

        if section.summary_md:
            p = doc.add_paragraph()
            run = p.add_run(section.summary_md)
            _apply_run(run, style.body_font, style.body_size_pt, (51, 51, 51))

        if section.kpis:
            _write_kpi_table(doc, section.kpis, style)

        for chart in section.charts:
            png = charts_dir / f"{chart.id}.png"
            if not png.exists():
                continue
            doc.add_picture(str(png), width=Inches(6.0))
            caption = doc.add_paragraph()
            run = caption.add_run(chart.title)
            _apply_run(
                run,
                style.body_font,
                max(style.body_size_pt - 1, 8),
                (119, 119, 119),
            )


def _write_kpi_table(doc: Document, kpis: list[dict[str, object]], style: DocxStyle) -> None:
    table = doc.add_table(rows=1 + len(kpis), cols=4)
    table.style = "Table Grid"

    headers = ["指标", "本期", "上期", "同比"]
    for col_index, text in enumerate(headers):
        cell = table.rows[0].cells[col_index]
        _shade_cell(cell, style.table_header_bg_hex)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        run = cell.paragraphs[0].add_run(text)
        _apply_run(run, style.title_font, style.body_size_pt, style.table_header_color_rgb, bold=True)

    for row_index, kpi in enumerate(kpis, start=1):
        row = table.rows[row_index].cells
        unit = str(kpi.get("unit") or "")
        value = kpi.get("value")
        prev = kpi.get("previous_value")
        change_pct = kpi.get("change_pct")
        cells_text = [
            str(kpi.get("label", kpi.get("name", ""))),
            f"{value}{unit}" if value is not None else "—",
            f"{prev}{unit}" if prev is not None else "—",
            f"{change_pct:+.2f}%" if isinstance(change_pct, (int, float)) else "—",
        ]
        for cell, text in zip(row, cells_text, strict=True):
            run = cell.paragraphs[0].add_run(text)
            _apply_run(run, style.body_font, style.body_size_pt, (34, 34, 34))


def _write_footer(doc: Document, ctx: ReportContext, style: DocxStyle) -> None:
    p = doc.add_paragraph()
    text = (
        f"SwarmMind FlyReport · session {ctx.session_id} · "
        f"生成于 {ctx.generated_at.strftime('%Y-%m-%d %H:%M')}"
    )
    run = p.add_run(text)
    _apply_run(run, style.body_font, max(style.body_size_pt - 2, 8), (153, 153, 153))


def _apply_run(
    run,
    font_name: str,
    size_pt: int,
    rgb: tuple[int, int, int],
    *,
    bold: bool = False,
) -> None:
    run.font.name = font_name
    # Ensure CJK characters use the same font (python-docx quirk).
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.append(rFonts)
    rFonts.set(qn("w:eastAsia"), font_name)
    run.font.size = Pt(size_pt)
    run.font.color.rgb = RGBColor(*rgb)
    run.font.bold = bold


def _shade_cell(cell, hex_color: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tc_pr.append(shd)


def _scope_label(kind: str) -> str:
    return {"overall": "总体", "department": "部门", "pilot": "飞手"}.get(kind, kind)


def _title_text(ctx: ReportContext) -> str:
    return f"{ctx.filter.period.label} {_scope_label(ctx.filter.dimension.scope)}飞行报告"
