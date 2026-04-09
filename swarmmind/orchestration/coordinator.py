"""First-round coordinator implementation."""

from __future__ import annotations

import json
import re

from swarmmind.agents.agent_skill import normalize_skill_profile_names
from swarmmind.agents.profile import AgentProfileStore
from swarmmind.models.agent_profile import AgentProfile
from swarmmind.models.capability import DEFAULT_ROLE_TOOL_GROUPS, RuntimeKind, ToolGroup
from swarmmind.models.execution import ExecutionProfile
from swarmmind.models.run import Run
from swarmmind.models.task import SubTask, Task


_BROWSER_PLAYWRIGHT_HINTS: tuple[str, ...] = (
    "dynamic page",
    "dynamic webpage",
    "dynamic site",
    "playwright",
    "screenshot",
    "screen shot",
    "click",
    "clicking",
    "selector",
    "interactive",
    "interaction",
    "scroll",
    "登录",
    "截图",
    "动态页面",
    "动态网页",
    "点击",
    "交互",
    "选择器",
    "滚动",
)


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
            required_tool_groups = self._resolve_required_tool_groups(subtask, agent_profile)
            candidate_runtime_kinds = self._resolve_candidate_runtime_kinds(task, subtask, agent_profile, required_tool_groups)
            skill_profiles = self._resolve_skill_profiles(subtask, agent_profile)
            resolved_runtime_kind, runtime_reason, fallback_chain = self._resolve_runtime_kind(
                task=task,
                subtask=subtask,
                agent_profile=agent_profile,
                required_tool_groups=required_tool_groups,
                candidate_runtime_kinds=candidate_runtime_kinds,
            )
            execution_profile = ExecutionProfile(
                role=subtask.role,
                agent_profile_id=agent_profile.id,
                execution_configuration=subtask.execution_configuration,
                required_tool_groups=required_tool_groups,
                resolved_runtime_kind=resolved_runtime_kind,
                runtime_resolution_reason=runtime_reason,
                runtime_fallback_chain=fallback_chain,
                allowed_tool_groups=agent_profile.allowed_tool_groups,
                allowed_tool_names=agent_profile.allowed_tool_names,
                skill_mode=agent_profile.skill_mode,
                skill_profiles=skill_profiles,
                allowed_skill_scripts=agent_profile.allowed_skill_scripts,
                sandbox_profile=self._resolve_sandbox_profile(
                    task=task,
                    subtask=subtask,
                    agent_profile=agent_profile,
                    resolved_runtime_kind=resolved_runtime_kind,
                ),
            )
            subtask.assign(execution_profile.model_dump(mode="json"), run.id)
            assigned.append(subtask)
        return assigned

    def _resolve_agent_profile(self, task: Task, subtask: SubTask) -> AgentProfile:
        explicit_profile_id = subtask.agent_profile_id or task.metadata.get("agent_profile_id")
        if explicit_profile_id:
            explicit_profile = self._agent_profile_store.get(str(explicit_profile_id))
            if explicit_profile is not None and explicit_profile.role == subtask.role:
                return explicit_profile
        return self._agent_profile_store.resolve_for_subtask(
            role=subtask.role,
        )

    @staticmethod
    def _resolve_required_tool_groups(subtask: SubTask, agent_profile: AgentProfile) -> list[ToolGroup]:
        if subtask.execution_configuration and subtask.execution_configuration.tool_requirements:
            return list(dict.fromkeys(subtask.execution_configuration.tool_requirements))
        if agent_profile.default_tool_groups:
            return list(dict.fromkeys(agent_profile.default_tool_groups))
        return list(dict.fromkeys(DEFAULT_ROLE_TOOL_GROUPS.get(subtask.role, [])))

    @staticmethod
    def _resolve_candidate_runtime_kinds(
        task: Task,
        subtask: SubTask,
        agent_profile: AgentProfile,
        required_tool_groups: list[ToolGroup],
    ) -> list[RuntimeKind]:
        candidates: list[RuntimeKind] = []
        if Coordinator._prefers_browser_playwright(task, subtask, required_tool_groups):
            candidates.append(RuntimeKind.SANDBOX)
        planner_candidate = subtask.metadata.get("planner_execution_candidate") if isinstance(subtask.metadata, dict) else None
        if isinstance(planner_candidate, dict):
            runtime_values = planner_candidate.get("runtime_kinds")
            if isinstance(runtime_values, list):
                for value in runtime_values:
                    try:
                        candidates.append(RuntimeKind(str(value).strip().lower()))
                    except ValueError:
                        continue
        if subtask.execution_configuration and subtask.execution_configuration.runtime_kind is not None:
            candidates.append(subtask.execution_configuration.runtime_kind)
            raw_fallbacks = subtask.execution_configuration.metadata.get("planner_candidate_runtime_kinds")
            if raw_fallbacks:
                try:
                    fallback_values = json.loads(raw_fallbacks)
                except json.JSONDecodeError:
                    fallback_values = []
                if isinstance(fallback_values, list):
                    for value in fallback_values:
                        try:
                            candidates.append(RuntimeKind(str(value).strip().lower()))
                        except ValueError:
                            continue
        candidates.extend(agent_profile.recommended_runtime_kinds)
        if ToolGroup.CODE_EXEC in required_tool_groups:
            candidates.extend([RuntimeKind.SANDBOX, RuntimeKind.HOST_TOOLS])
        elif required_tool_groups:
            candidates.extend([RuntimeKind.HOST_TOOLS, RuntimeKind.LLM_ONLY])
        else:
            candidates.extend([RuntimeKind.LLM_ONLY, RuntimeKind.HOST_TOOLS])
        return list(dict.fromkeys(candidates))

    @staticmethod
    def _resolve_skill_profiles(subtask: SubTask, agent_profile: AgentProfile) -> list[str]:
        if subtask.execution_configuration and subtask.execution_configuration.skill_profiles:
            return normalize_skill_profile_names(list(dict.fromkeys(subtask.execution_configuration.skill_profiles)))
        return normalize_skill_profile_names(list(dict.fromkeys(agent_profile.skill_profiles)))

    @staticmethod
    def _resolve_runtime_kind(
        *,
        task: Task,
        subtask: SubTask,
        agent_profile: AgentProfile,
        required_tool_groups: list[ToolGroup],
        candidate_runtime_kinds: list[RuntimeKind],
    ) -> tuple[RuntimeKind, str, list[RuntimeKind]]:
        fallback_chain = list(dict.fromkeys(candidate_runtime_kinds))
        required_groups = set(required_tool_groups)
        sandbox_profile = subtask.execution_configuration.sandbox_profile if subtask.execution_configuration else None
        prefers_browser_playwright = Coordinator._prefers_browser_playwright(task, subtask, required_tool_groups)

        def backup_runtimes(selected: RuntimeKind) -> list[RuntimeKind]:
            return [candidate for candidate in fallback_chain if candidate != selected]

        for runtime_kind in fallback_chain:
            if runtime_kind == RuntimeKind.SANDBOX:
                if prefers_browser_playwright:
                    return (
                        RuntimeKind.SANDBOX,
                        "Resolved to sandbox because the subtask requires browser-playwright for dynamic browsing, clicking, or screenshots.",
                        backup_runtimes(RuntimeKind.SANDBOX),
                    )
                if ToolGroup.CODE_EXEC in required_groups or sandbox_profile or agent_profile.default_sandbox_profile:
                    return (
                        RuntimeKind.SANDBOX,
                        "Resolved to sandbox because the subtask requires code execution or an explicit sandbox profile.",
                        backup_runtimes(RuntimeKind.SANDBOX),
                    )
                continue
            if runtime_kind == RuntimeKind.LLM_ONLY:
                if not required_groups.intersection({ToolGroup.FILE_SYSTEM, ToolGroup.WORKSPACE, ToolGroup.BROWSER, ToolGroup.CODE_EXEC, ToolGroup.COMMUNICATION}):
                    return (
                        RuntimeKind.LLM_ONLY,
                        "Resolved to llm_only because the subtask does not require external tool execution.",
                        backup_runtimes(RuntimeKind.LLM_ONLY),
                    )
                continue
            if runtime_kind == RuntimeKind.HOST_TOOLS:
                return (
                    RuntimeKind.HOST_TOOLS,
                    "Resolved to host_tools because the subtask requires local tools without sandbox isolation.",
                    backup_runtimes(RuntimeKind.HOST_TOOLS),
                )

        if prefers_browser_playwright:
            return (
                RuntimeKind.SANDBOX,
                "Resolved to sandbox as a safety fallback because the subtask requires browser-playwright automation.",
                backup_runtimes(RuntimeKind.SANDBOX),
            )
        if ToolGroup.CODE_EXEC in required_groups:
            return (
                RuntimeKind.SANDBOX,
                "Resolved to sandbox as a safety fallback because code execution is required.",
                backup_runtimes(RuntimeKind.SANDBOX),
            )
        return (
            RuntimeKind.HOST_TOOLS,
            "Resolved to host_tools as the default fallback runtime.",
            backup_runtimes(RuntimeKind.HOST_TOOLS),
        )

    @staticmethod
    def _resolve_sandbox_profile(
        *,
        task: Task,
        subtask: SubTask,
        agent_profile: AgentProfile,
        resolved_runtime_kind: RuntimeKind,
    ) -> str | None:
        if resolved_runtime_kind != RuntimeKind.SANDBOX:
            return None
        required_tool_groups = list(subtask.execution_configuration.tool_requirements) if subtask.execution_configuration else []
        if Coordinator._prefers_browser_playwright(task, subtask, required_tool_groups):
            return (subtask.execution_configuration.sandbox_profile if subtask.execution_configuration else None) or "browser-playwright"
        return (
            (subtask.execution_configuration.sandbox_profile if subtask.execution_configuration else None)
            or agent_profile.default_sandbox_profile
            or task.metadata.get("profile")
        )

    @staticmethod
    def _prefers_browser_playwright(task: Task, subtask: SubTask, required_tool_groups: list[ToolGroup]) -> bool:
        if ToolGroup.BROWSER not in required_tool_groups:
            return False
        text = "\n".join(
            part
            for part in [task.goal, subtask.name, subtask.description]
            if isinstance(part, str) and part.strip()
        ).lower()
        text = re.sub(r"\s+", " ", text)
        return any(keyword in text for keyword in _BROWSER_PLAYWRIGHT_HINTS)
