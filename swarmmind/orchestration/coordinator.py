"""First-round coordinator implementation."""

from __future__ import annotations

from swarmmind.agents.profile import AgentProfileStore
from swarmmind.models.agent_profile import AgentProfile
from swarmmind.models.capability import DEFAULT_STRATEGY_PROFILES, RuntimeKind, ToolGroup
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
            candidate_runtime_kinds = self._resolve_candidate_runtime_kinds(subtask, effective_strategy)
            preferred_skill_profiles = self._resolve_skill_profiles(subtask, agent_profile, effective_strategy)
            resolved_runtime_kind, runtime_reason, fallback_chain = self._resolve_runtime_kind(
                task=task,
                subtask=subtask,
                agent_profile=agent_profile,
                effective_strategy=effective_strategy,
                candidate_runtime_kinds=candidate_runtime_kinds,
            )
            execution_profile = ExecutionProfile(
                role=subtask.role,
                agent_profile_id=agent_profile.id,
                preferred_strategy=effective_strategy,
                required_tool_groups=subtask.required_tool_groups,
                candidate_runtime_kinds=candidate_runtime_kinds,
                resolved_runtime_kind=resolved_runtime_kind,
                runtime_resolution_reason=runtime_reason,
                runtime_fallback_chain=fallback_chain,
                allowed_tool_groups=agent_profile.allowed_tool_groups,
                allowed_tool_names=agent_profile.allowed_tool_names,
                skill_mode=agent_profile.skill_mode,
                preferred_skill_profiles=preferred_skill_profiles,
                skill_profiles=preferred_skill_profiles,
                allowed_skill_scripts=agent_profile.allowed_skill_scripts,
                sandbox_profile=self._resolve_sandbox_profile(
                    task=task,
                    subtask=subtask,
                    agent_profile=agent_profile,
                    resolved_runtime_kind=resolved_runtime_kind,
                    effective_strategy=effective_strategy,
                ),
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

    @staticmethod
    def _resolve_candidate_runtime_kinds(subtask: SubTask, effective_strategy: str | None) -> list[RuntimeKind]:
        if subtask.candidate_runtime_kinds:
            return list(dict.fromkeys(subtask.candidate_runtime_kinds))
        strategy_profile = DEFAULT_STRATEGY_PROFILES.get(effective_strategy or "")
        if strategy_profile and strategy_profile.candidate_runtime_kinds:
            return list(dict.fromkeys(strategy_profile.candidate_runtime_kinds))
        if ToolGroup.SANDBOX_EXEC in subtask.required_tool_groups:
            return [RuntimeKind.SANDBOX, RuntimeKind.HOST_TOOLS]
        if any(group in subtask.required_tool_groups for group in {ToolGroup.WEB_SEARCH, ToolGroup.BROWSER_READ}):
            return [RuntimeKind.HOST_TOOLS, RuntimeKind.BROWSER_AUTOMATION]
        return [RuntimeKind.LLM_ONLY, RuntimeKind.HOST_TOOLS]

    @staticmethod
    def _resolve_skill_profiles(subtask: SubTask, agent_profile: AgentProfile, effective_strategy: str | None) -> list[str]:
        if subtask.preferred_skill_profiles:
            return list(dict.fromkeys(subtask.preferred_skill_profiles))
        strategy_profile = DEFAULT_STRATEGY_PROFILES.get(effective_strategy or "")
        if strategy_profile and strategy_profile.default_skill_profiles:
            return list(dict.fromkeys(strategy_profile.default_skill_profiles))
        return list(dict.fromkeys(agent_profile.skill_profiles))

    @staticmethod
    def _resolve_runtime_kind(
        *,
        task: Task,
        subtask: SubTask,
        agent_profile: AgentProfile,
        effective_strategy: str | None,
        candidate_runtime_kinds: list[RuntimeKind],
    ) -> tuple[RuntimeKind, str, list[RuntimeKind]]:
        fallback_chain = list(dict.fromkeys(candidate_runtime_kinds))
        required_groups = set(subtask.required_tool_groups)

        if effective_strategy == "agent_backed" or agent_profile.default_strategy == "agent_backed":
            return (
                RuntimeKind.AGENT_BACKED,
                "Resolved to agent_backed because the workflow explicitly requested the agent-backed executor.",
                fallback_chain or [RuntimeKind.AGENT_BACKED],
            )

        for runtime_kind in fallback_chain:
            if runtime_kind == RuntimeKind.SANDBOX:
                if ToolGroup.SANDBOX_EXEC in required_groups or subtask.sandbox_profile:
                    return (
                        RuntimeKind.SANDBOX,
                        "Resolved to sandbox because the subtask requires sandbox execution or an explicit sandbox profile.",
                        fallback_chain,
                    )
                continue
            if runtime_kind == RuntimeKind.BROWSER_AUTOMATION:
                continue
            if runtime_kind == RuntimeKind.LLM_ONLY:
                if not required_groups.intersection({ToolGroup.SANDBOX_EXEC, ToolGroup.PRESENTATION, ToolGroup.PROJECT_WRITE}):
                    return (
                        RuntimeKind.LLM_ONLY,
                        "Resolved to llm_only because the subtask does not require sandbox, presentation generation, or project writes.",
                        fallback_chain,
                    )
                continue
            if runtime_kind == RuntimeKind.HOST_TOOLS:
                if RuntimeKind.BROWSER_AUTOMATION in fallback_chain and any(
                    group in required_groups for group in {ToolGroup.WEB_SEARCH, ToolGroup.BROWSER_READ}
                ):
                    return (
                        RuntimeKind.HOST_TOOLS,
                        "Resolved to host_tools after considering browser_automation first; the current runtime only exposes browser-like host tools, not a dedicated browser automation executor.",
                        fallback_chain,
                    )
                return (
                    RuntimeKind.HOST_TOOLS,
                    "Resolved to host_tools because the subtask requires local tools without sandbox isolation.",
                    fallback_chain,
                )
            if runtime_kind == RuntimeKind.AGENT_BACKED:
                return (
                    RuntimeKind.AGENT_BACKED,
                    "Resolved to agent_backed because it is the only remaining compatible runtime candidate.",
                    fallback_chain,
                )

        if ToolGroup.SANDBOX_EXEC in required_groups:
            return (
                RuntimeKind.SANDBOX,
                "Resolved to sandbox as a safety fallback because sandbox_exec is required.",
                fallback_chain or [RuntimeKind.SANDBOX],
            )
        return (
            RuntimeKind.HOST_TOOLS,
            "Resolved to host_tools as the default fallback runtime.",
            fallback_chain or [RuntimeKind.HOST_TOOLS],
        )

    @staticmethod
    def _resolve_sandbox_profile(
        *,
        task: Task,
        subtask: SubTask,
        agent_profile: AgentProfile,
        resolved_runtime_kind: RuntimeKind,
        effective_strategy: str | None,
    ) -> str | None:
        if resolved_runtime_kind != RuntimeKind.SANDBOX:
            return None
        strategy_profile = DEFAULT_STRATEGY_PROFILES.get(effective_strategy or "")
        return (
            subtask.sandbox_profile
            or agent_profile.default_sandbox_profile
            or (strategy_profile.sandbox_profile if strategy_profile else None)
            or task.metadata.get("profile")
        )
