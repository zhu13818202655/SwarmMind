"""First-round coordinator implementation."""

from __future__ import annotations

from swarmmind.agents.profile import AgentProfileStore
from swarmmind.models.agent_profile import AgentProfile
from swarmmind.models.execution import ExecutionProfile
from swarmmind.models.run import Run
from swarmmind.models.task import SubTask, Task


class Coordinator:
    """Attach execution metadata to ready subtasks."""

    def __init__(self, agent_profile_store: AgentProfileStore):
        self._agent_profile_store = agent_profile_store

    async def assign(self, task: Task, run: Run, subtasks: list[SubTask]) -> list[SubTask]:
        """Assign an execution profile to each ready subtask."""
        assigned: list[SubTask] = []
        for subtask in subtasks:
            agent_profile = self._resolve_agent_profile(task, subtask)
            subtask.agent_profile_id = agent_profile.id
            effective_strategy = subtask.preferred_strategy or agent_profile.default_strategy
            if effective_strategy:
                subtask.preferred_strategy = effective_strategy
            execution_profile = ExecutionProfile(
                role=subtask.role,
                agent_profile_id=agent_profile.id,
                preferred_strategy=effective_strategy,
                required_tool_groups=subtask.required_tool_groups,
                allowed_tool_groups=agent_profile.allowed_tool_groups,
                allowed_tool_names=agent_profile.allowed_tool_names,
                skill_mode=agent_profile.skill_mode,
                skill_profiles=agent_profile.skill_profiles,
                allowed_skill_scripts=agent_profile.allowed_skill_scripts,
                sandbox_profile=subtask.sandbox_profile or agent_profile.default_sandbox_profile or task.metadata.get("profile"),
                handoff_policy=agent_profile.handoff_policy,
            )
            subtask.assign(execution_profile.model_dump(mode="json"), run.id)
            assigned.append(subtask)
        return assigned

    def _resolve_agent_profile(self, task: Task, subtask: SubTask) -> AgentProfile:
        requested_profile_id = subtask.agent_profile_id or task.metadata.get("agent_profile_id")
        return self._agent_profile_store.resolve_for_subtask(
            profile_id=requested_profile_id,
            role=subtask.role,
            preferred_strategy=subtask.preferred_strategy,
        )
