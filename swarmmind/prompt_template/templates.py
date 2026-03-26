"""Python module-backed prompt template definitions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PromptTemplate:
    """Named prompt template content."""

    name: str
    template: str


PLANNER_SYSTEM_PROMPT = PromptTemplate(
    name="planner_system_v1",
    template="""You are a planning agent that decomposes goals into executable JSON task DAGs.
Return strict JSON only.""",
)

PLANNER_TASK_DECOMPOSITION_PROMPT = PromptTemplate(
    name="planner_task_decomposition_v1",
    template="""Given the input, produce a plan JSON with schema:
{
  "subtasks": [
    {
      "name": "string-kebab-case",
      "description": "string",
      "agent_profile_id": "string|null",
      "role": "planner|coder|tester|reviewer|researcher",
      "preferred_strategy": "string",
      "required_tool_groups": ["project_read|project_write|sandbox_exec|artifact_read|http"],
      "sandbox_profile": "string",
      "acceptance_criteria": ["string"],
      "dependencies": ["subtask-name"]
    }
  ]
}

Rules:
1) Subtasks must be minimal, executable, and verifiable.
2) Dependencies must be acyclic.
3) Include verification subtasks when task requests testing/validation.
4) Prefer fewer subtasks for simple goals, richer DAG for complex goals.
5) Ensure each subtask has concrete acceptance criteria.
6) Use `agent_profile_id` only when a subtask needs an explicit execution profile; otherwise omit it or set null.
7) `agent_profile_id` must come from the available profile list and should be role-compatible with the subtask.

Input:
- Goal: {{ task_goal }}
- Constraints JSON: {{ constraints_json }}
- Preferred Profile: {{ profile }}
- Preferred Strategy: {{ preferred_strategy }}
- Available Agent Profiles JSON: {{ agent_profiles_json }}""",
)

TASK_DECOMPOSER_LLM_PROMPT = PromptTemplate(
    name="task_decomposer_llm_v1",
    template="""You are a task decomposition assistant. Break down the user's task into clear, sequential steps.

Task: {{ goal }}

Analyze the task and break it down into subtasks. Consider:
1. What needs to be done first?
2. What information is needed?
3. What are the dependencies between steps?

Respond with a JSON array of subtasks, each with:
- name: short identifier for the step
- description: what this step should accomplish
- sandbox_profile: recommended sandbox profile (py-basic, node-basic, secure-offline)

Example output format:
[
    {"name": "research", "description": "Search for information about...", "role": "researcher", "preferred_strategy": "research", "required_tool_groups": ["web_search", "browser_read"], "sandbox_profile": "py-basic"},
    {"name": "write", "description": "Write the report based on research", "role": "writer", "preferred_strategy": "write_report", "required_tool_groups": ["project_write"], "sandbox_profile": "py-basic"}
]

Respond ONLY with the JSON array, no other text.""",
)

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

REVIEW_SUBTASK_VERIFICATION_PROMPT = PromptTemplate(
    name="review_subtask_verification_v1",
    template="""Review the subtask result.

Subtask: {{ subtask_name }}
Description: {{ subtask_description }}
Acceptance Criteria: {{ acceptance_criteria_json }}
Execution Output Preview: {{ stdout_preview }}
Artifacts: {{ artifact_list_json }}

Output format:
- Verdict: pass/fail
- Criteria Check:
  - [ ] item 1
  - [ ] item 2
- Evidence:
- Risks:
- Next Action:""",
)

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