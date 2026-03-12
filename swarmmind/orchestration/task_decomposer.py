"""Task decomposer for breaking down tasks using LLM."""

import json
import uuid
from typing import Any
from swarmmind.models.task import SubTask


LLM_DECOMPOSE_PROMPT = """You are a task decomposition assistant. Break down the user's task into clear, sequential steps.

Task: {goal}

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
  {{"name": "research", "description": "Search for information about...", "sandbox_profile": "py-basic"}},
  {{"name": "write", "description": "Write the report based on research", "sandbox_profile": "py-basic"}}
]

Respond ONLY with the JSON array, no other text."""


class TaskDecomposer:
    """Decompose a task into subtasks using LLM or patterns."""

    # Fallback patterns when LLM is not available
    TASK_PATTERNS = {
        "write_email": ["compose", "review", "send"],
        "write_report": ["research", "outline", "write", "review"],
        "build_app": ["analyze", "design", "implement", "test"],
        "monitor_stock": ["fetch_data", "analyze", "alert"],
        "search": ["search"],
        "code": ["implement", "test"],
    }

    def __init__(self, model_client=None):
        """Initialize with optional LLM client for intelligent decomposition."""
        self._model_client = model_client

    def set_model_client(self, model_client) -> None:
        """Set the LLM model client."""
        self._model_client = model_client

    async def decompose(self, goal: str) -> list[SubTask]:
        """Decompose a goal into subtasks.

        Uses LLM if available, otherwise falls back to pattern matching.
        """
        task_id = str(uuid.uuid4())

        # Try LLM-based decomposition
        if self._model_client:
            try:
                subtasks = await self._decompose_with_llm(goal, task_id)
                if subtasks:
                    return subtasks
            except Exception:
                pass  # Fall back to pattern matching

        # Fallback to pattern matching
        return self._decompose_with_patterns(goal, task_id)

    async def _decompose_with_llm(self, goal: str, task_id: str) -> list[SubTask] | None:
        """Decompose using LLM."""
        prompt = LLM_DECOMPOSE_PROMPT.format(goal=goal)

        # Call LLM (simplified - actual implementation depends on model client)
        response = await self._model_client.chat(
            messages=[{"role": "user", "content": prompt}]
        )

        content = response.content if hasattr(response, 'content') else str(response)

        # Parse JSON response
        try:
            # Extract JSON from response
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            subtask_data = json.loads(content.strip())

            # Convert to SubTask objects
            subtasks = []
            for item in subtask_data:
                subtask = SubTask(
                    id=str(uuid.uuid4()),
                    task_id=task_id,
                    name=item.get("name", "step"),
                    description=item.get("description", ""),
                    sandbox_profile=item.get("sandbox_profile", "py-basic"),
                )
                subtasks.append(subtask)

            return subtasks

        except (json.JSONDecodeError, KeyError):
            return None

    def _decompose_with_patterns(self, goal: str, task_id: str) -> list[SubTask]:
        """Decompose using pattern matching (fallback)."""
        goal_lower = goal.lower()

        # Determine pattern
        if "email" in goal_lower or "邮件" in goal_lower:
            pattern = "write_email"
        elif "report" in goal_lower or "报告" in goal_lower:
            pattern = "write_report"
        elif any(k in goal_lower for k in ["app", "应用", "程序", "build"]):
            pattern = "build_app"
        elif any(k in goal_lower for k in ["stock", "股票", "监控", "monitor"]):
            pattern = "monitor_stock"
        elif any(k in goal_lower for k in ["search", "搜索", "find"]):
            pattern = "search"
        elif any(k in goal_lower for k in ["code", "代码", "implement"]):
            pattern = "code"
        else:
            pattern = None

        # Create subtasks
        if pattern and pattern in self.TASK_PATTERNS:
            steps = self.TASK_PATTERNS[pattern]
            return [
                SubTask(
                    id=str(uuid.uuid4()),
                    task_id=task_id,
                    name=step,
                    description=f"Step: {step} for task: {goal}",
                    sandbox_profile="py-basic",
                )
                for step in steps
            ]
        else:
            # Default: single task
            return [
                SubTask(
                    id=str(uuid.uuid4()),
                    task_id=task_id,
                    name="main",
                    description=goal,
                    sandbox_profile="py-basic",
                )
            ]
