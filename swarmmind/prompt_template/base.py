"""Shared prompt template types."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PromptTemplate:
    """Named prompt template content."""

    name: str
    template: str