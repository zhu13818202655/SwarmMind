"""Lightweight HTML preview renderer for ``ReportContext``.

Used by the M3 ``GET /sessions/{id}/preview`` endpoint to render a
human-readable view of the current draft *without* generating the final
DOCX/PDF artifact (DESIGN-2 §14.4.5).

The output is plain self-contained HTML — no external assets, no JS —
so it can be embedded in any chat UI iframe.
"""

from __future__ import annotations

import html
import json
from typing import Any

from swarmmind.domains.fly_report.schemas import ReportBlock, ReportContext, ReportSection


def render_preview_html(ctx: ReportContext) -> str:
    """Render ``ctx`` as a single self-contained HTML document."""
    sections_html = "\n".join(_render_section(s) for s in ctx.sections)
    title = html.escape(
        f"FlyReport 预览 (rev {ctx.revision}) — {ctx.filter.period.label}"
    )
    return _PREVIEW_TEMPLATE.format(
        title=title,
        meta=_render_meta(ctx),
        sections=sections_html or "<p><em>暂无章节</em></p>",
    )


def _render_meta(ctx: ReportContext) -> str:
    rows = [
        ("Session", ctx.session_id),
        ("Revision", str(ctx.revision)),
        ("Period", ctx.filter.period.label),
        ("Generated", ctx.generated_at.isoformat()),
    ]
    inner = "".join(
        f"<tr><th>{html.escape(k)}</th><td>{html.escape(v)}</td></tr>"
        for k, v in rows
    )
    return f"<table class='meta'>{inner}</table>"


def _render_section(section: ReportSection) -> str:
    level = min(max(section.level + 1, 2), 6)
    parts: list[str] = [
        f"<section><h{level}>{html.escape(section.title)}</h{level}>"
    ]
    if section.blocks:
        parts.extend(_render_block(block) for block in section.blocks)
    else:
        parts.append(_render_legacy_section_body(section))
    parts.extend(_render_section(child) for child in section.children)
    parts.append("</section>")
    return "".join(parts)


def _render_legacy_section_body(section: ReportSection) -> str:
    parts: list[str] = []
    if section.summary_md:
        parts.append(f"<p class='summary'>{html.escape(section.summary_md)}</p>")
    if section.kpis:
        parts.append(_render_kpis(section.kpis))
    if section.tables:
        parts.append(_render_tables(section.tables))
    if section.charts:
        parts.append(_render_charts(section.charts))
    return "".join(parts)


def _render_block(block: ReportBlock) -> str:
    if block.kind == "heading":
        level = min(max(block.level, 1), 6)
        return f"<h{level}>{html.escape(block.text)}</h{level}>"
    if block.kind == "paragraph":
        text = block.text or "".join(run.text for run in block.runs)
        return f"<p>{html.escape(text)}</p>"
    if block.kind == "markdown":
        return f"<div class='markdown'>{_render_markdown_text(block.markdown)}</div>"
    if block.kind == "list":
        tag = "ol" if block.ordered else "ul"
        items = "".join(_render_list_item(item, block.ordered) for item in block.items)
        return f"<{tag}>{items}</{tag}>"
    if block.kind == "table":
        return _render_tables([block.table])
    if block.kind == "chart":
        return _render_charts([block.chart]) + _render_caption(block.caption)
    if block.kind == "chart_text":
        return (
            "<div class='chart-text'>"
            f"{_render_charts([block.chart])}"
            f"<p>{html.escape(block.text or '')}</p>"
            f"{_render_caption(block.caption)}"
            "</div>"
        )
    if block.kind == "image":
        return (
            "<figure>"
            f"<img src='{html.escape(block.uri)}' alt='{html.escape(block.alt or '')}'>"
            f"{_render_caption(block.caption)}"
            "</figure>"
        )
    if block.kind == "kpi_group":
        return _render_kpis(block.kpis)
    if block.kind == "callout":
        return f"<div class='callout {html.escape(block.level)}'>{_render_markdown_text(block.markdown)}</div>"
    if block.kind == "page_break":
        return "<hr class='page-break'>"
    if block.kind == "spacer":
        return f"<div style='height:{block.height}em'></div>"
    return ""


def _render_markdown_text(value: str) -> str:
    paragraphs = [line.strip() for line in value.splitlines() if line.strip()]
    return "".join(f"<p>{html.escape(line)}</p>" for line in paragraphs)


def _render_list_item(item: Any, ordered: bool) -> str:
    tag = "ol" if ordered else "ul"
    children = "".join(_render_list_item(child, ordered) for child in item.children)
    nested = f"<{tag}>{children}</{tag}>" if children else ""
    return f"<li>{html.escape(item.text)}{nested}</li>"


def _render_caption(value: str | None) -> str:
    return f"<figcaption>{html.escape(value)}</figcaption>" if value else ""


def _render_kpis(kpis: list[dict[str, Any]]) -> str:
    cards = "".join(
        (
            "<div class='kpi'>"
            f"<div class='kpi-label'>{html.escape(str(k.get('label') or k.get('name') or '')) }</div>"
            f"<div class='kpi-value'>{html.escape(str(k.get('value') or ''))}</div>"
            f"<div class='kpi-unit'>{html.escape(str(k.get('unit') or ''))}</div>"
            "</div>"
        )
        for k in kpis
    )
    return f"<div class='kpis'>{cards}</div>"


def _render_tables(tables: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for tbl in tables:
        cols = tbl.get("columns") or []
        rows = tbl.get("rows") or []
        col_keys = [c.get("key") if isinstance(c, dict) else c for c in cols]
        col_labels = [c.get("label") if isinstance(c, dict) else c for c in cols]
        thead = "".join(f"<th>{html.escape(str(c))}</th>" for c in col_labels)
        body_rows: list[str] = []
        for row in rows:
            if isinstance(row, dict):
                values = [row.get(c) for c in col_keys]
            else:
                values = list(row)
            tds = "".join(f"<td>{html.escape(str(v))}</td>" for v in values)
            body_rows.append(f"<tr>{tds}</tr>")
        parts.append(
            f"<table class='data'><thead><tr>{thead}</tr></thead>"
            f"<tbody>{''.join(body_rows)}</tbody></table>"
        )
    return "".join(parts)


def _render_charts(charts: list[Any]) -> str:
    parts: list[str] = []
    for chart in charts:
        opt = getattr(chart, "echarts_option", None) or {}
        parts.append(
            "<div class='chart'>"
            f"<h3>{html.escape(getattr(chart, 'title', '') or '')}</h3>"
            f"<pre>{html.escape(json.dumps(opt, ensure_ascii=False, indent=2))}</pre>"
            "</div>"
        )
    return "".join(parts)


_PREVIEW_TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
     max-width:960px;margin:24px auto;padding:0 16px;color:#222;line-height:1.5;}}
h1{{margin:0 0 12px;font-size:24px}}
h2{{margin:24px 0 8px;font-size:18px;border-bottom:1px solid #eee;padding-bottom:4px}}
h3{{margin:12px 0 4px;font-size:14px;color:#555}}
table.meta{{border-collapse:collapse;margin-bottom:16px}}
table.meta th{{text-align:left;background:#f7f7f9;padding:4px 8px;border:1px solid #eee}}
table.meta td{{padding:4px 8px;border:1px solid #eee}}
table.data{{border-collapse:collapse;width:100%;margin:8px 0}}
table.data th,table.data td{{border:1px solid #ddd;padding:4px 8px;font-size:13px}}
.kpis{{display:flex;flex-wrap:wrap;gap:12px;margin:8px 0}}
.kpi{{background:#f4f7fb;border:1px solid #e3eaf3;border-radius:6px;padding:8px 12px;min-width:120px}}
.kpi-label{{font-size:12px;color:#666}}
.kpi-value{{font-size:20px;font-weight:600;color:#1a73e8}}
.kpi-unit{{font-size:12px;color:#999}}
.chart pre{{background:#f7f7f9;padding:8px;font-size:11px;overflow:auto;border-radius:4px}}
.summary{{color:#444;background:#fafafa;padding:8px 12px;border-left:3px solid #1a73e8;margin:8px 0}}
.callout{{padding:8px 12px;border-left:3px solid #888;background:#fafafa;margin:8px 0}}
.callout.warning{{border-color:#c77700;background:#fff8ed}}
figure{{margin:8px 0}}
figcaption{{font-size:12px;color:#777;text-align:center;margin-top:4px}}
img{{max-width:100%}}
.page-break{{border:0;border-top:1px dashed #bbb;margin:24px 0}}
</style>
</head>
<body>
<h1>{title}</h1>
{meta}
{sections}
</body>
</html>
"""


__all__ = ["render_preview_html"]
