"""AgentFactory - Create agents using AgentScope."""

from __future__ import annotations

from typing import Any, List

from agentscope.formatter import OpenAIChatFormatter
from agentscope.memory import InMemoryMemory
from agentscope.model import OpenAIChatModel
from agentscope.tool import Toolkit

from swarmmind.models.agent_profile import AgentProfile, SkillsMode
from swarmmind.agents.agent_skill import (
    build_agent_skill_catalog,
    build_agent_skill_details,
    resolve_agent_skill_entries,
)
from swarmmind.agents.config import AgentConfig
from swarmmind.agents.omni_agent import CapabilityResolver, OmniAgent
from swarmmind.models.capability import DEFAULT_ROLE_TOOL_GROUPS, ToolExecutionContract, ToolGroup
from swarmmind.models.execution import ExecutionProfile
from swarmmind.tools import ToolRegistry, register_builtin_tools


class AgentFactory:
    """Factory for creating AgentScope agents."""

    def __init__(self, config: AgentConfig):
        self.config = config

    def create_model_client(self):
        """Create model client from config."""
        config = self.config.scope_config
        return OpenAIChatModel(
            model_name=config.model_name,
            api_key=config.api_key,
            generate_kwargs={
                "temperature": config.temperature,
                "max_tokens": config.max_tokens,
            },
            client_kwargs={
                "base_url": config.base_url,
            },
        )

    def create_formatter(self) -> OpenAIChatFormatter:
        """Create message formatter for the configured model family."""
        return OpenAIChatFormatter(max_tokens=self.config.scope_config.max_tokens)

    def create_memory(self):
        """Create memory from config."""
        return InMemoryMemory()

    def create_toolkit(
        self,
        tools: list[Any] | None = None,
        skill_profiles: list[str] | None = None,
        tool_groups: list[ToolGroup] | None = None,
        active_tool_names: list[str] | None = None,
        runtime_kind: Any | None = None,
    ) -> Toolkit:
        """Create a group-aware toolkit assembled from a ToolRegistry."""
        effective_skill_profiles = list(skill_profiles or self.config.skill_profiles)
        equipped_tool_groups = list(tool_groups or self.config.tool_groups)
        strict_tool_names = bool(active_tool_names)
        registry = self._build_tool_registry(tools or [], fallback_groups=equipped_tool_groups)
        toolkit = registry.build_toolkit(
            active_groups=equipped_tool_groups,
            active_tool_names=active_tool_names,
            runtime_kind=runtime_kind,
            strict_tool_names=strict_tool_names,
        )
        equipped_tools = registry.get_functions_for_groups(
            equipped_tool_groups,
            runtime_kind=runtime_kind,
            tool_names=active_tool_names,
            strict_tool_names=strict_tool_names,
        )
        seen_names = {getattr(tool, "__name__", repr(tool)) for tool in equipped_tools}

        skill_entries = resolve_agent_skill_entries(effective_skill_profiles, seen_names)
        for entry in skill_entries:
            toolkit.register_agent_skill(str(entry.root_dir))

        # Keep a structured catalog on the toolkit instance for future profile-driven selection.
        toolkit._swarmmind_skill_catalog = build_agent_skill_catalog(  # type: ignore[attr-defined]
            effective_skill_profiles,
            seen_names,
        )
        toolkit._swarmmind_skill_details = build_agent_skill_details(  # type: ignore[attr-defined]
            effective_skill_profiles,
            seen_names,
        )

        return toolkit

    def create_agent(
        self,
        tools: list[Any] | None = None,
        sys_prompt: str | None = None,
        skill_profiles: list[str] | None = None,
        event_publisher: Any = None,
        execution_profile: ExecutionProfile | None = None,
    ) -> OmniAgent:
        """Create an OmniAgent."""
        effective_prompt = sys_prompt or self.config.system_prompt or ""
        equipped_tool_groups = self._resolve_equipped_tool_groups(execution_profile=execution_profile)
        active_tool_names = self._resolve_active_tool_names(execution_profile=execution_profile)
        effective_skill_profiles = self._resolve_effective_skill_profiles(
            explicit_skill_profiles=skill_profiles,
            fallback_skill_profiles=self.config.skill_profiles,
            execution_profile=execution_profile,
        )
        toolkit, effective_tools = self._assemble_tooling(
            tools=tools or [],
            skill_profiles=effective_skill_profiles,
            tool_groups=equipped_tool_groups,
            active_tool_names=active_tool_names,
            runtime_kind=execution_profile.resolved_runtime_kind if execution_profile is not None else None,
        )
        capability_bundle = CapabilityResolver.resolve(
            role=execution_profile.role if execution_profile is not None else self.config.role,
            system_prompt=effective_prompt,
            tool_functions=effective_tools,
            skill_profiles=effective_skill_profiles,
            execution_profile=execution_profile,
        )
        return OmniAgent(
            capability_bundle=capability_bundle,
            event_publisher=event_publisher,
            name=self.config.name,
            sys_prompt=effective_prompt,
            model=self.create_model_client(),
            formatter=self.create_formatter(),
            toolkit=toolkit,
            memory=self.create_memory(),
            max_iters=self.config.max_steps,
        )

    def create_main_agent(
        self,
        tools: list[Any] | None = None,
        event_publisher: Any = None,
        execution_profile: ExecutionProfile | None = None,
    ) -> OmniAgent:
        """Create main agent."""
        return self.create_agent(
            tools,
            sys_prompt=self.config.system_prompt,
            event_publisher=event_publisher,
            execution_profile=execution_profile,
        )

    def create_profile_agent(
        self,
        profile: AgentProfile,
        tools: list[Any] | None = None,
        system_prompt: str | None = None,
        event_publisher: Any = None,
        execution_profile: ExecutionProfile | None = None,
    ) -> OmniAgent:
        """Create an agent constrained by an AgentProfile."""
        config = self.config.model_copy()
        config.name = profile.name
        prompt_parts: list[str] = []
        for part in [system_prompt, profile.system_prompt, config.system_prompt, profile.custom_prompt]:
            if part and part not in prompt_parts:
                prompt_parts.append(part)
        effective_prompt = "\n\n".join(prompt_parts)
        equipped_tool_groups = self._resolve_equipped_tool_groups(profile=profile, execution_profile=execution_profile)
        active_tool_names = self._resolve_active_tool_names(profile=profile, execution_profile=execution_profile)
        effective_skill_profiles = self._resolve_effective_skill_profiles(
            explicit_skill_profiles=None,
            fallback_skill_profiles=self._resolve_profile_skill_profiles(profile),
            execution_profile=execution_profile,
        )
        toolkit, capability_tools = self._assemble_tooling(
            tools=tools or [],
            skill_profiles=effective_skill_profiles,
            tool_groups=equipped_tool_groups,
            active_tool_names=active_tool_names,
            runtime_kind=execution_profile.resolved_runtime_kind if execution_profile is not None else None,
        )
        capability_bundle = CapabilityResolver.resolve(
            role=execution_profile.role if execution_profile is not None else profile.role,
            system_prompt=effective_prompt,
            tool_functions=capability_tools,
            skill_profiles=effective_skill_profiles,
            agent_profile=profile,
            execution_profile=execution_profile,
        )

        return OmniAgent(
            capability_bundle=capability_bundle,
            event_publisher=event_publisher,
            name=config.name,
            sys_prompt=effective_prompt,
            model=self.create_model_client(),
            formatter=self.create_formatter(),
            toolkit=toolkit,
            memory=InMemoryMemory(),
            max_iters=config.max_steps,
        )

    def create_subagent(  # TODO 考虑删除
        self,
        name: str,
        tools: list[Any],
        system_prompt: str | None = None,
        event_publisher: Any = None,
        execution_profile: ExecutionProfile | None = None,
    ) -> OmniAgent:
        """Create a sub-agent."""
        config = self.config.model_copy()
        config.name = name
        effective_prompt = system_prompt or config.system_prompt or ""
        equipped_tool_groups = self._resolve_equipped_tool_groups(execution_profile=execution_profile)
        active_tool_names = self._resolve_active_tool_names(execution_profile=execution_profile)
        effective_skill_profiles = self._resolve_effective_skill_profiles(
            explicit_skill_profiles=None,
            fallback_skill_profiles=config.skill_profiles,
            execution_profile=execution_profile,
        )
        toolkit, effective_tools = self._assemble_tooling(
            tools=tools,
            skill_profiles=effective_skill_profiles,
            tool_groups=equipped_tool_groups,
            active_tool_names=active_tool_names,
            runtime_kind=execution_profile.resolved_runtime_kind if execution_profile is not None else None,
        )
        capability_bundle = CapabilityResolver.resolve(
            role=execution_profile.role if execution_profile is not None else config.role,
            system_prompt=effective_prompt,
            tool_functions=effective_tools,
            skill_profiles=effective_skill_profiles,
            execution_profile=execution_profile,
        )

        return OmniAgent(
            capability_bundle=capability_bundle,
            event_publisher=event_publisher,
            name=name,
            sys_prompt=effective_prompt,
            model=self.create_model_client(),
            formatter=self.create_formatter(),
            toolkit=toolkit,
            memory=InMemoryMemory(),
            max_iters=config.max_steps,
        )

    @staticmethod
    def _resolve_profile_skill_profiles(profile: AgentProfile) -> list[str]:
        if profile.skill_mode == SkillsMode.ALL:
            return list(profile.skill_profiles)
        if profile.skill_mode == SkillsMode.INCLUSIVE:
            return list(profile.skill_profiles)
        return []

    @staticmethod
    def _resolve_effective_skill_profiles(
        *,
        explicit_skill_profiles: list[str] | None,
        fallback_skill_profiles: list[str] | None,
        execution_profile: ExecutionProfile | None,
    ) -> list[str]:
        if explicit_skill_profiles:
            return list(explicit_skill_profiles)
        if execution_profile is not None and execution_profile.skill_profiles:
            return list(execution_profile.skill_profiles)
        return list(fallback_skill_profiles or [])

    def _assemble_tooling(
        self,
        *,
        tools: list[Any],
        skill_profiles: list[str],
        tool_groups: list[ToolGroup],
        active_tool_names: list[str],
        runtime_kind: Any | None,
    ) -> tuple[Toolkit, list[Any]]:
        registry = self._build_tool_registry(tools, fallback_groups=tool_groups)
        strict_tool_names = bool(active_tool_names)
        toolkit = registry.build_toolkit(
            active_groups=tool_groups,
            active_tool_names=active_tool_names,
            runtime_kind=runtime_kind,
            strict_tool_names=strict_tool_names,
        )
        effective_tools = registry.get_functions_for_groups(
            tool_groups,
            tool_names=active_tool_names,
            runtime_kind=runtime_kind,
            strict_tool_names=strict_tool_names,
        )
        seen_names = {getattr(tool, "__name__", repr(tool)) for tool in effective_tools}
        skill_entries = resolve_agent_skill_entries(skill_profiles, seen_names)
        for entry in skill_entries:
            toolkit.register_agent_skill(str(entry.root_dir))
        toolkit._swarmmind_skill_catalog = build_agent_skill_catalog(  # type: ignore[attr-defined]
            skill_profiles,
            seen_names,
        )
        toolkit._swarmmind_skill_details = build_agent_skill_details(  # type: ignore[attr-defined]
            skill_profiles,
            seen_names,
        )
        return toolkit, effective_tools

    @staticmethod
    def _build_tool_registry(tools: list[Any], fallback_groups: list[ToolGroup]) -> ToolRegistry:
        registry = ToolRegistry()
        register_builtin_tools(registry)
        for tool in tools:
            tool_name = getattr(tool, "__name__", repr(tool))
            contract = getattr(tool, "__swarmmind_tool_contract__", None)
            if isinstance(contract, dict):
                contract = ToolExecutionContract(**contract)
            registry.register(
                tool,
                name=tool_name,
                description=getattr(tool, "__doc__", None) or "No description",
                groups=AgentFactory._resolve_tool_groups(tool, fallback_groups),
                contract=contract,
            )
        return registry

    @staticmethod
    def _resolve_tool_groups(tool: Any, fallback_groups: list[ToolGroup]) -> List[ToolGroup]:
        raw_groups = getattr(tool, "__swarmmind_tool_groups__", None)
        if raw_groups:
            return [group if isinstance(group, ToolGroup) else ToolGroup(group) for group in raw_groups]
        tool_name = getattr(tool, "__name__", "")
        if tool_name in {"run_skill_script", "sandbox_exec"}:
            return [ToolGroup.CODE_EXEC]
        return list(fallback_groups or [ToolGroup.WORKSPACE])

    def _resolve_equipped_tool_groups(
        self,
        *,
        profile: AgentProfile | None = None,
        execution_profile: ExecutionProfile | None = None,
    ) -> list[ToolGroup]:
        if execution_profile is not None and execution_profile.required_tool_groups:
            return list(execution_profile.required_tool_groups)
        if profile is not None and profile.default_tool_groups:
            return list(profile.default_tool_groups)
        if self.config.tool_groups:
            return list(self.config.tool_groups)
        role = (
            execution_profile.role
            if execution_profile is not None
            else profile.role
            if profile is not None
            else self.config.role
        )
        return list(DEFAULT_ROLE_TOOL_GROUPS.get(role, [ToolGroup.WORKSPACE]))

    @staticmethod
    def _resolve_active_tool_names(
        *,
        profile: AgentProfile | None = None,
        execution_profile: ExecutionProfile | None = None,
    ) -> list[str]:
        if execution_profile is not None and execution_profile.allowed_tool_names:
            return list(execution_profile.allowed_tool_names)
        if profile is not None and profile.allowed_tool_names:
            return list(profile.allowed_tool_names)
        return []
