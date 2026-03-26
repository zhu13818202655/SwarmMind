"""Planner prompt templates."""

from __future__ import annotations

from swarmmind.prompt_template.base import PromptTemplate


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