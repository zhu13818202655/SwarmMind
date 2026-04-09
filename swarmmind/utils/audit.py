"""Audit serialization helpers for replay and artifact traces."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def sanitize_audit_value(
    value: Any,
    *,
    max_string_length: int = 100_000,
    max_items: int = 50,
    max_depth: int = 6,
) -> Any:
    """Convert runtime values into bounded JSON-friendly audit payloads."""
    if max_depth <= 0:
        return _truncate_string(repr(value), max_string_length)

    if value is None or isinstance(value, (bool, int, float)):
        return value

    if isinstance(value, str):
        return _truncate_string(value, max_string_length)

    if isinstance(value, bytes):
        return {
            "type": "bytes",
            "length": len(value),
            "preview": _truncate_string(value.decode("utf-8", errors="replace"), max_string_length),
        }

    try:
        model_dump = getattr(value, "model_dump")
    except Exception:
        model_dump = None
    if callable(model_dump):
        try:
            return sanitize_audit_value(
                model_dump(mode="json"),
                max_string_length=max_string_length,
                max_items=max_items,
                max_depth=max_depth - 1,
            )
        except Exception:
            return _truncate_string(repr(value), max_string_length)

    try:
        to_dict = getattr(value, "to_dict")
    except Exception:
        to_dict = None
    if callable(to_dict):
        try:
            return sanitize_audit_value(
                to_dict(),
                max_string_length=max_string_length,
                max_items=max_items,
                max_depth=max_depth - 1,
            )
        except Exception:
            return _truncate_string(repr(value), max_string_length)

    if isinstance(value, Mapping):
        items = list(value.items())
        sanitized = {
            str(key): sanitize_audit_value(
                item,
                max_string_length=max_string_length,
                max_items=max_items,
                max_depth=max_depth - 1,
            )
            for key, item in items[:max_items]
        }
        if len(items) > max_items:
            sanitized["_truncated_keys"] = len(items) - max_items
        return sanitized

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        items = list(value)
        sanitized_items = [
            sanitize_audit_value(
                item,
                max_string_length=max_string_length,
                max_items=max_items,
                max_depth=max_depth - 1,
            )
            for item in items[:max_items]
        ]
        if len(items) > max_items:
            sanitized_items.append({"_truncated_items": len(items) - max_items})
        return sanitized_items

    return _truncate_string(repr(value), max_string_length)


def extract_text_preview(value: Any, *, limit: int = 2_000) -> str:
    """Best-effort compact text preview for audit summaries."""
    sanitized = sanitize_audit_value(value, max_string_length=limit, max_items=8, max_depth=4)
    if isinstance(sanitized, str):
        return sanitized
    return _truncate_string(str(sanitized), limit)


def _truncate_string(value: str, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    remaining = len(value) - max_length
    return f"{value[:max_length]}\n...[truncated {remaining} chars]"