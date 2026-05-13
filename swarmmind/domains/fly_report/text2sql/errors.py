"""Exception hierarchy for the FlyReport Text-to-SQL pipeline."""

from __future__ import annotations

from swarmmind.domains.fly_report.errors import FlyReportError


class Text2SqlError(FlyReportError):
    """Base class for Text-to-SQL failures."""


class Text2SqlConfigError(Text2SqlError):
    """Raised when the Text-to-SQL configuration is incomplete or invalid."""


class Text2SqlGenerationError(Text2SqlError):
    """Raised when the LLM fails to produce a usable SQL statement."""


class Text2SqlExecutionError(Text2SqlError):
    """Raised when generated SQL cannot be executed against PostgreSQL."""


__all__ = [
    "Text2SqlError",
    "Text2SqlConfigError",
    "Text2SqlGenerationError",
    "Text2SqlExecutionError",
]
