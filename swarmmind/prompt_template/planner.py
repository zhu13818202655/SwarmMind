"""Planner prompt templates."""

from __future__ import annotations

from swarmmind.models.capability import DEFAULT_STRATEGY_PROFILES, ToolGroup
from swarmmind.prompt_template.base import PromptTemplate


PLANNER_SUPPORTED_ROLES = (
    "planner",
    "coder",
    "tester",
    "reviewer",
    "researcher",
    "writer",
    "executor",
)
PLANNER_ROLE_ENUM = "|".join(PLANNER_SUPPORTED_ROLES)
PLANNER_TOOL_GROUP_ENUM = "|".join(tool_group.value for tool_group in ToolGroup)
PLANNER_STRATEGY_ENUM = "|".join(DEFAULT_STRATEGY_PROFILES)
PLANNER_EXAMPLE_JSON = """{
  \"subtasks\": [
    {
      \"name\": \"draft-release-summary\",
      \"description\": \"Research the release changes and draft a concise release summary.\",
      \"agent_profile_id\": \"writer-default\",
      \"role\": \"writer\",
      \"preferred_strategy\": \"write_report\",
      \"required_tool_groups\": [\"web_search\", \"browser_read\", \"project_write\"],
      \"sandbox_profile\": null,
      \"acceptance_criteria\": [
        \"The summary covers the requested release scope.\",
        \"The output is ready to publish without empty placeholders.\"
      ],
      \"dependencies\": []
    }
  ]
}"""


PLANNER_SYSTEM_PROMPT = PromptTemplate(
    name="planner_system_v1",
    template="""You are a planning agent that decomposes goals into executable JSON task DAGs.
Return strict JSON only.""",
)

PLANNER_TASK_DECOMPOSITION_PROMPT = PromptTemplate(
    name="planner_task_decomposition_v1",
    template=f"""Given the input, produce a plan JSON with schema:
{{
  "subtasks": [
    {{
      "name": "string-kebab-case",
      "description": "string",
      "agent_profile_id": "string|null",
      "role": "{PLANNER_ROLE_ENUM}",
      "preferred_strategy": "{PLANNER_STRATEGY_ENUM}|null",
      "required_tool_groups": ["{PLANNER_TOOL_GROUP_ENUM}"],
      "sandbox_profile": "string|null",
      "acceptance_criteria": ["string"],
      "dependencies": ["subtask-name"]
    }}
  ]
}}

Rules:
1) Subtasks must be minimal, executable, and verifiable.
2) Dependencies must be acyclic.
3) Include verification subtasks when task requests testing/validation.
4) Prefer fewer subtasks for simple goals, richer DAG for complex goals.
5) Ensure each subtask has concrete acceptance criteria.
6) Use `agent_profile_id` only when a subtask needs an explicit execution profile; otherwise omit it or set null.
7) `agent_profile_id` must come from the available profile list and should be role-compatible with the subtask.
8) Optional fields must never be empty strings. Use null or omit them.
9) `role`, `preferred_strategy`, and `agent_profile_id` must be mutually compatible.
10) `write_report` should normally use `writer` and `research` should normally use `researcher` or `writer`.
11) `research` tasks should prefer `web_search`, `browser_read`, and `project_read` when those capabilities are needed.

Valid JSON example:
{PLANNER_EXAMPLE_JSON}

Input:
- Goal: {{{{ task_goal }}}}
- Constraints JSON: {{{{ constraints_json }}}}
- Preferred Profile: {{{{ profile }}}}
- Preferred Strategy: {{{{ preferred_strategy }}}}
- Available Agent Profiles JSON: {{{{ agent_profiles_json }}}}""",
)