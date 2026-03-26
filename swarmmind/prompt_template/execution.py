"""Execution prompt templates."""

from __future__ import annotations

from swarmmind.prompt_template.base import PromptTemplate


EXECUTION_SYSTEM_PROMPT = PromptTemplate(
    name="execution_system_v1",
    template="""You are a precise task execution assistant.
Return only actionable markdown for this single subtask.""",
)

EXECUTION_SUBTASK_MARKDOWN_PROMPT = PromptTemplate(
    name="execution_subtask_markdown_v1",
    template="""Execute the following subtask and produce the deliverable in markdown.

Task Goal: {{ task_goal }}
Subtask Name: {{ subtask_name }}
Subtask Description: {{ subtask_description }}
Acceptance Criteria: {{ acceptance_criteria_json }}
Constraints: {{ constraints_json }}
Tool Groups: {{ tool_groups_json }}

Output requirements:
1) Use concise markdown.
2) Include a clear completion checklist.
3) Include verification notes for acceptance criteria.""",
)

EXECUTION_FALLBACK_CONTENT_PROMPT = PromptTemplate(
    name="execution_fallback_content_v1",
    template="""# {{ subtask_name }}

## Goal
{{ subtask_description }}

## Parent Task
{{ task_goal }}

## Acceptance Criteria
{{ acceptance_criteria_lines }}

## Execution Notes
- Completed by real subtask runner in sandbox.
- Output persisted as artifact source for replay and query APIs.

## Constraints Snapshot
```json
{{ constraints_json_pretty }}
```""",
)