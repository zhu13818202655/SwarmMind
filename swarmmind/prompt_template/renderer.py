"""Jinja-backed prompt rendering helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from jinja2 import Environment, StrictUndefined

from swarmmind.prompt_template.templates import PromptTemplate


_JINJA_ENV = Environment(undefined=StrictUndefined, autoescape=False)


def render_prompt(template: PromptTemplate, values: Mapping[str, Any] | None = None) -> str:
    """Render a named prompt template and fail fast on missing variables."""

    compiled = _JINJA_ENV.from_string(template.template)
    rendered = compiled.render(**dict(values or {}))
    return str(rendered)