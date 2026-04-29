"""Shared view helpers for block-aware FlyReport exporters."""

from __future__ import annotations

from html import escape
from typing import Any

from swarmmind.domains.fly_report.schemas import ReportSection


def section_views(sections: list[ReportSection]) -> list[dict[str, Any]]:
    return [_section_view(section) for section in sections]


def _section_view(section: ReportSection) -> dict[str, Any]:
    markdown = _section_blocks_markdown(section) if section.blocks else ""
    html = _section_blocks_html(section) if section.blocks else ""
    return {
        "id": section.id,
        "title": section.title,
        "level": section.level,
        "summary_md": "" if section.blocks else section.summary_md,
        "kpis": [] if section.blocks else section.kpis,
        "tables": [] if section.blocks else [_table_view(table) for table in section.tables],
        "charts": [] if section.blocks else section.charts,
        "rendered_markdown": markdown,
        "rendered_html": html,
        "children": section_views(section.children),
    }


def _section_blocks_markdown(section: ReportSection) -> str:
    chunks: list[str] = []
    for block in section.blocks:
        rendered = _block_markdown(block)
        if rendered:
            chunks.append(rendered.rstrip())
    for child in section.children:
        child_heading = "#" * min(max(child.level + 1, 2), 6)
        child_body = _section_blocks_markdown(child) if child.blocks else _legacy_section_markdown(child)
        chunks.append(f"{child_heading} {child.title}\n\n{child_body}".rstrip())
    return "\n\n".join(chunks).strip()


def _legacy_section_markdown(section: ReportSection) -> str:
    chunks: list[str] = []
    if section.summary_md:
        chunks.append(section.summary_md)
    if section.kpis:
        chunks.append(_kpi_markdown(section.kpis))
    for table in section.tables:
        table_view = _table_view(table)
        chunks.append(f"### {table_view['title']}\n\n{table_view['markdown']}".rstrip())
    for chart in section.charts:
        chunks.append(f"### {chart.title}\n\n![{chart.title}](charts/{chart.id}.png)")
    return "\n\n".join(chunks).strip()


def _block_markdown(block: Any) -> str:
    if block.kind == "heading":
        return f"{'#' * min(max(block.level, 1), 6)} {block.text}"
    if block.kind == "paragraph":
        if block.runs:
            return "".join(_run_markdown(run) for run in block.runs)
        return block.text or ""
    if block.kind == "markdown":
        return block.markdown
    if block.kind == "list":
        lines: list[str] = []
        for index, item in enumerate(block.items, start=1):
            _list_item_markdown(lines, item, ordered=block.ordered, level=0, index=index)
        return "\n".join(lines)
    if block.kind == "table":
        table_view = _table_view(block.table)
        title = block.caption or block.title or table_view["title"]
        return f"### {title}\n\n{table_view['markdown']}".rstrip()
    if block.kind == "chart":
        caption = block.caption or block.chart.title
        return f"### {caption}\n\n![{block.chart.title}](charts/{block.chart.id}.png)"
    if block.kind == "chart_text":
        caption = block.caption or block.chart.title
        text = f"\n\n{block.text}" if block.text else ""
        return f"### {caption}\n\n![{block.chart.title}](charts/{block.chart.id}.png){text}"
    if block.kind == "image":
        alt = block.alt or block.caption or "image"
        caption = f"\n\n_{block.caption}_" if block.caption else ""
        return f"![{alt}]({block.uri}){caption}"
    if block.kind == "kpi_group":
        return _kpi_markdown(block.kpis)
    if block.kind == "callout":
        return "\n".join(f"> {line}" for line in block.markdown.splitlines() if line.strip())
    if block.kind == "page_break":
        return "<div style=\"page-break-after: always;\"></div>"
    if block.kind == "spacer":
        return "\n" * block.height
    return ""


def _run_markdown(run: Any) -> str:
    text = run.text
    if run.bold:
        text = f"**{text}**"
    if run.italic:
        text = f"_{text}_"
    if run.underline:
        text = f"<u>{text}</u>"
    return text


def _list_item_markdown(
    lines: list[str], item: Any, *, ordered: bool, level: int, index: int
) -> None:
    prefix = f"{index}." if ordered else "-"
    lines.append(f"{'  ' * level}{prefix} {item.text}")
    for child_index, child in enumerate(item.children, start=1):
        _list_item_markdown(
            lines, child, ordered=ordered, level=level + 1, index=child_index
        )


def _section_blocks_html(section: ReportSection) -> str:
    chunks: list[str] = []
    for block in section.blocks:
        rendered = _block_html(block)
        if rendered:
            chunks.append(rendered)
    for child in section.children:
        child_level = min(max(child.level + 1, 2), 6)
        child_body = _section_blocks_html(child) if child.blocks else _legacy_section_html(child)
        chunks.append(f"<h{child_level}>{escape(child.title)}</h{child_level}>{child_body}")
    return "\n".join(chunks)


def _legacy_section_html(section: ReportSection) -> str:
    chunks: list[str] = []
    if section.summary_md:
        chunks.append(f"<p>{escape(section.summary_md)}</p>")
    if section.kpis:
        chunks.append(_kpi_html(section.kpis))
    for table in section.tables:
        chunks.append(_table_view(table)["html"])
    for chart in section.charts:
        chunks.append(f'<h3>{escape(chart.title)}</h3><img src="charts/{escape(chart.id)}.png" alt="{escape(chart.title)}">')
    return "\n".join(chunks)


def _block_html(block: Any) -> str:
    if block.kind == "heading":
        level = min(max(block.level, 1), 6)
        return f"<h{level}>{escape(block.text)}</h{level}>"
    if block.kind == "paragraph":
        align = escape(block.style.align)
        if block.runs:
            body = "".join(_run_html(run) for run in block.runs)
        else:
            body = escape(block.text or "")
        return f'<p style="text-align:{align}">{body}</p>'
    if block.kind == "markdown":
        return _plain_markdown_html(block.markdown)
    if block.kind == "list":
        tag = "ol" if block.ordered else "ul"
        return f"<{tag}>" + "".join(_list_item_html(item, ordered=block.ordered) for item in block.items) + f"</{tag}>"
    if block.kind == "table":
        title = block.caption or block.title
        title_html = f"<h3>{escape(title)}</h3>" if title else ""
        return title_html + _table_view(block.table)["html"]
    if block.kind == "chart":
        caption = block.caption or block.chart.title
        return f'<h3>{escape(caption)}</h3><img src="charts/{escape(block.chart.id)}.png" alt="{escape(block.chart.title)}">'
    if block.kind == "chart_text":
        caption = block.caption or block.chart.title
        text = f"<p>{escape(block.text)}</p>" if block.text else ""
        return f'<h3>{escape(caption)}</h3><img src="charts/{escape(block.chart.id)}.png" alt="{escape(block.chart.title)}">{text}'
    if block.kind == "image":
        caption = f"<figcaption>{escape(block.caption)}</figcaption>" if block.caption else ""
        return f'<figure><img src="{escape(block.uri)}" alt="{escape(block.alt or block.caption or "image")}">{caption}</figure>'
    if block.kind == "kpi_group":
        return _kpi_html(block.kpis)
    if block.kind == "callout":
        return f'<blockquote class="callout-{escape(block.level)}">{_plain_markdown_html(block.markdown)}</blockquote>'
    if block.kind == "page_break":
        return '<div style="page-break-after: always;"></div>'
    if block.kind == "spacer":
        return "<br>" * block.height
    return ""


def _run_html(run: Any) -> str:
    text = escape(run.text)
    if run.bold:
        text = f"<strong>{text}</strong>"
    if run.italic:
        text = f"<em>{text}</em>"
    if run.underline:
        text = f"<u>{text}</u>"
    if run.color:
        text = f'<span style="color:{escape(run.color)}">{text}</span>'
    return text


def _list_item_html(item: Any, *, ordered: bool) -> str:
    tag = "ol" if ordered else "ul"
    children = ""
    if item.children:
        children = f"<{tag}>" + "".join(_list_item_html(child, ordered=ordered) for child in item.children) + f"</{tag}>"
    return f"<li>{escape(item.text)}{children}</li>"


def _plain_markdown_html(markdown: str) -> str:
    chunks: list[str] = []
    in_list = False
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line:
            if in_list:
                chunks.append("</ul>")
                in_list = False
            continue
        if line.startswith("### "):
            if in_list:
                chunks.append("</ul>")
                in_list = False
            chunks.append(f"<h3>{escape(line[4:])}</h3>")
        elif line.startswith("## "):
            if in_list:
                chunks.append("</ul>")
                in_list = False
            chunks.append(f"<h2>{escape(line[3:])}</h2>")
        elif line.startswith("# "):
            if in_list:
                chunks.append("</ul>")
                in_list = False
            chunks.append(f"<h1>{escape(line[2:])}</h1>")
        elif line.startswith("- "):
            if not in_list:
                chunks.append("<ul>")
                in_list = True
            chunks.append(f"<li>{escape(line[2:])}</li>")
        else:
            if in_list:
                chunks.append("</ul>")
                in_list = False
            chunks.append(f"<p>{escape(line)}</p>")
    if in_list:
        chunks.append("</ul>")
    return "\n".join(chunks)


def _table_view(table: dict[str, Any]) -> dict[str, str]:
    title = str(table.get("title") or "数据表")
    columns = table.get("columns") if isinstance(table, dict) else []
    rows = table.get("rows") if isinstance(table, dict) else []
    if not isinstance(columns, list) or not isinstance(rows, list):
        return {"title": title, "markdown": str(table.get("markdown") or ""), "html": str(table.get("html") or "")}
    keys = [str(col.get("key") if isinstance(col, dict) else col) for col in columns]
    labels = [str(col.get("label") if isinstance(col, dict) else col) for col in columns]
    markdown_lines = ["| " + " | ".join(labels) + " |", "|" + "|".join(["---"] * len(labels)) + "|"]
    html_parts = ["<table><thead><tr>"]
    html_parts.extend(f"<th>{escape(label)}</th>" for label in labels)
    html_parts.append("</tr></thead><tbody>")
    for row in rows:
        row_values = []
        if isinstance(row, dict):
            row_values = [row.get(key, "") for key in keys]
        markdown_lines.append("| " + " | ".join(str(value if value is not None else "") for value in row_values) + " |")
        html_parts.append("<tr>")
        html_parts.extend(f"<td>{escape(str(value if value is not None else ''))}</td>" for value in row_values)
        html_parts.append("</tr>")
    html_parts.append("</tbody></table>")
    return {"title": title, "markdown": "\n".join(markdown_lines), "html": "".join(html_parts)}


def _kpi_markdown(kpis: list[dict[str, Any]]) -> str:
    lines = ["| 指标 | 本期 | 上期 | 同比 |", "|---|---|---|---|"]
    for item in kpis:
        lines.append(
            "| {label} | {value}{unit} | {previous}{unit} | {change} |".format(
                label=item.get("label") or item.get("name") or "指标",
                value=_dash(item.get("value")),
                previous=_dash(item.get("previous_value")),
                unit=item.get("unit") or "",
                change=_change_pct(item.get("change_pct")),
            )
        )
    return "\n".join(lines)


def _kpi_html(kpis: list[dict[str, Any]]) -> str:
    rows = []
    for item in kpis:
        rows.append(
            "<tr><td>{label}</td><td>{value}{unit}</td><td>{previous}{unit}</td><td>{change}</td></tr>".format(
                label=escape(str(item.get("label") or item.get("name") or "指标")),
                value=escape(_dash(item.get("value"))),
                previous=escape(_dash(item.get("previous_value"))),
                unit=escape(str(item.get("unit") or "")),
                change=escape(_change_pct(item.get("change_pct"))),
            )
        )
    return "<table><thead><tr><th>指标</th><th>本期</th><th>上期</th><th>同比</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"


def _dash(value: Any) -> str:
    return "—" if value is None else str(value)


def _change_pct(value: Any) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):+.2f}%"
    except (TypeError, ValueError):
        return str(value)
