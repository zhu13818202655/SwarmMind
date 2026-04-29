"""Markdown table helpers for FlyReport analyzer tables."""

from __future__ import annotations

from typing import Any


def dict_table_to_markdown(table: dict[str, Any], title_level: int = 0) -> str:
    """Convert an analyzer table dict to a Markdown table string."""
    title = str(table.get("title") or "").strip() if title_level >= 0 else ""

    raw_columns = table.get("columns")
    columns = raw_columns if isinstance(raw_columns, list) else []

    raw_rows = table.get("rows")
    rows = raw_rows if isinstance(raw_rows, list) else []

    if not columns:
        return _format_markdown_title(title, title_level)

    column_keys = [str(column.get("key") or "") for column in columns]
    column_labels = [
        str(column.get("label") or column.get("key") or "")
        for column in columns
    ]

    lines: list[str] = []
    if title:
        lines.append(_format_markdown_title(title, title_level))
        lines.append("")

    lines.append(
        "| "
        + " | ".join(_escape_markdown_cell(label) for label in column_labels)
        + " |"
    )
    lines.append("| " + " | ".join("---" for _ in column_labels) + " |")

    for row in rows:
        if not isinstance(row, dict):
            continue
        values = [_format_table_cell(row.get(column_key)) for column_key in column_keys]
        lines.append(
            "| "
            + " | ".join(_escape_markdown_cell(value) for value in values)
            + " |"
        )

    return "\n".join(lines)


def _format_table_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _format_markdown_title(title: str, title_level: int) -> str:
    if not title:
        return ""
    if title_level <= 0:
        return title
    level = min(title_level, 6)
    return f"{'#' * level} {title}"


def _escape_markdown_cell(value: str) -> str:
    return value.replace("\n", " ").replace("|", "\\|")
