"""Helpers for loading and rendering prompt templates."""

from __future__ import annotations

from pathlib import Path


_PROMPT_TEMPLATE_DIR = Path(__file__).resolve().parent


def load_prompt_template(file_name: str) -> str:
    """Load a prompt template from the prompt_template directory."""
    path = _PROMPT_TEMPLATE_DIR / file_name
    return path.read_text(encoding="utf-8")


def render_prompt_template(file_name: str, values: dict[str, str]) -> str:
    """Render a template by replacing {{key}} placeholders."""
    template = load_prompt_template(file_name)
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value)
    return rendered
