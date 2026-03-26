"""Prompt template registry."""

from __future__ import annotations

from swarmmind.prompt_template.execution import (
    EXECUTION_FALLBACK_CONTENT_PROMPT,
    EXECUTION_SUBTASK_MARKDOWN_PROMPT,
    EXECUTION_SYSTEM_PROMPT,
)
from swarmmind.prompt_template.planner import (
    PLANNER_SYSTEM_PROMPT,
    PLANNER_TASK_DECOMPOSITION_PROMPT,
)
from swarmmind.prompt_template.review import REVIEW_SUBTASK_VERIFICATION_PROMPT
from swarmmind.prompt_template.task_decomposer import TASK_DECOMPOSER_LLM_PROMPT


PROMPT_TEMPLATES = {
    template.name: template
    for template in (
        PLANNER_SYSTEM_PROMPT,
        PLANNER_TASK_DECOMPOSITION_PROMPT,
        TASK_DECOMPOSER_LLM_PROMPT,
        EXECUTION_SYSTEM_PROMPT,
        EXECUTION_SUBTASK_MARKDOWN_PROMPT,
        EXECUTION_FALLBACK_CONTENT_PROMPT,
        REVIEW_SUBTASK_VERIFICATION_PROMPT,
    )
}