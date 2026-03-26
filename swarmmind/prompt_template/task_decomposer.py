"""Task decomposer prompt templates."""

from __future__ import annotations

from swarmmind.prompt_template.base import PromptTemplate


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