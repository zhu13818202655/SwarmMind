"""FlyReport prompt templates.

Prompts live as Python modules exposing :class:`PromptTemplate` constants,
matching the convention of other ``swarmmind/prompt_template/*.py`` files
(e.g. :mod:`swarmmind.prompt_template.planner`).
"""

from __future__ import annotations

from swarmmind.prompt_template.fly_report.clarify import CLARIFY_SYSTEM_PROMPT
from swarmmind.prompt_template.fly_report.followup_patch import (
    FOLLOWUP_PATCH_SYSTEM_PROMPT,
)
from swarmmind.prompt_template.fly_report.intent_parse import (
    INTENT_PARSE_SYSTEM_PROMPT,
    INTENT_PARSE_USER_PROMPT,
)


__all__ = [
    "INTENT_PARSE_SYSTEM_PROMPT",
    "INTENT_PARSE_USER_PROMPT",
    "CLARIFY_SYSTEM_PROMPT",
    "FOLLOWUP_PATCH_SYSTEM_PROMPT",
]
