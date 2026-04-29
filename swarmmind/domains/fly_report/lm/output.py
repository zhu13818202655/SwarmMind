"""Output parsing helpers for lightweight LM calls."""

from __future__ import annotations

import json
import re
from typing import Any

from swarmmind.domains.fly_report.lm.types import LMOutputFormat


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def parse_lm_output(text: str, output_format: LMOutputFormat) -> Any | None:
    """Parse optional structured output without imposing business schemas."""

    if output_format == LMOutputFormat.JSON:
        return parse_json_best_effort(text)
    return None


def parse_json_best_effort(text: str) -> Any | None:
    """Best-effort JSON extraction for model outputs."""

    if not text or not text.strip():
        return None

    candidates = [text.strip()]

    for match in _JSON_FENCE_RE.finditer(text):
        fenced = match.group(1).strip()
        if fenced:
            candidates.append(fenced)

    object_candidate = _slice_between(text, "{", "}")
    if object_candidate is not None:
        candidates.append(object_candidate)

    array_candidate = _slice_between(text, "[", "]")
    if array_candidate is not None:
        candidates.append(array_candidate)

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def _slice_between(text: str, start_char: str, end_char: str) -> str | None:
    start = text.find(start_char)
    end = text.rfind(end_char)
    if start == -1 or end <= start:
        return None
    return text[start : end + 1]