"""AgentFactory - Create agents using AgentScope."""

from __future__ import annotations

from typing import Any

from agentscope.agent import ReActAgent
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
from swarmmind.tools.builtin.file import file_exists, list_files, read_file


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
    ) -> Toolkit:
        """Create toolkit and register plain tool functions."""
        toolkit = Toolkit()
        effective_skill_profiles = list(skill_profiles or self.config.skill_profiles)

        registered_tools: list[Any] = list(tools or [])
        if effective_skill_profiles:
            registered_tools.extend([read_file, list_files, file_exists])

        seen_names: set[str] = set()
        for tool in registered_tools:
            tool_name = getattr(tool, "__name__", repr(tool))
            if tool_name in seen_names:
                continue
            toolkit.register_tool_function(tool)
            seen_names.add(tool_name)

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
    ) -> ReActAgent:
        """Create a ReActAgent."""
        return ReActAgent(
            name=self.config.name,
            sys_prompt=sys_prompt or self.config.system_prompt or "",
            model=self.create_model_client(),
            formatter=self.create_formatter(),
            toolkit=self.create_toolkit(tools, skill_profiles=skill_profiles),
            memory=self.create_memory(),
            max_iters=self.config.max_steps,
        )

    def create_main_agent(self, tools: list[Any] | None = None) -> ReActAgent:
        """Create main agent."""
        return self.create_agent(tools, sys_prompt=self.config.system_prompt)

    def create_profile_agent(
        self,
        profile: AgentProfile,
        tools: list[Any] | None = None,
        system_prompt: str | None = None,
    ) -> ReActAgent:
        """Create an agent constrained by an AgentProfile."""
        config = self.config.model_copy()
        config.name = profile.name
        prompt_parts: list[str] = []
        for part in [system_prompt, profile.system_prompt, config.system_prompt, profile.custom_prompt]:
            if part and part not in prompt_parts:
                prompt_parts.append(part)
        effective_prompt = "\n\n".join(prompt_parts)

        return ReActAgent(
            name=config.name,
            sys_prompt=effective_prompt,
            model=self.create_model_client(),
            formatter=self.create_formatter(),
            toolkit=self.create_toolkit(
                self._filter_tools_for_profile(tools or [], profile),
                skill_profiles=self._resolve_profile_skill_profiles(profile),
            ),
            memory=InMemoryMemory(),
            max_iters=config.max_steps,
        )

    def create_subagent(
        self,
        name: str,
        tools: list[Any],
        system_prompt: str | None = None,
    ) -> ReActAgent:
        """Create a sub-agent."""
        config = self.config.model_copy()
        config.name = name

        return ReActAgent(
            name=name,
            sys_prompt=system_prompt or config.system_prompt or "",
            model=self.create_model_client(),
            formatter=self.create_formatter(),
            toolkit=self.create_toolkit(tools),
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
    def _filter_tools_for_profile(tools: list[Any], profile: AgentProfile) -> list[Any]:
        if not profile.allowed_tool_names:
            return tools

        allowed = set(profile.allowed_tool_names)
        filtered: list[Any] = []
        for tool in tools:
            tool_name = getattr(tool, "__name__", None)
            if tool_name is None or tool_name in allowed:
                filtered.append(tool)
        return filtered
