"""AgentFactory - Create agents using AgentScope."""

from typing import Any
from agentscope.agent import ReActAgent
from agentscope.formatter import OpenAIChatFormatter
from agentscope.memory import InMemoryMemory
from agentscope.model import OpenAIChatModel
from agentscope.tool import Toolkit

from swarmmind.agents.config import AgentConfig


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

    def create_toolkit(self, tools: list[Any] | None = None) -> Toolkit:
        """Create toolkit and register plain tool functions."""
        toolkit = Toolkit()

        for tool in tools or []:
            toolkit.register_tool_function(tool)

        return toolkit

    def create_agent(
        self,
        tools: list[Any] | None = None,
        sys_prompt: str | None = None,
    ) -> ReActAgent:
        """Create a ReActAgent."""
        return ReActAgent(
            name=self.config.name,
            sys_prompt=sys_prompt or self.config.system_prompt or "",
            model=self.create_model_client(),
            formatter=self.create_formatter(),
            toolkit=self.create_toolkit(tools),
            memory=self.create_memory(),
            max_iters=self.config.max_steps,
        )

    def create_main_agent(self, tools: list[Any] | None = None) -> ReActAgent:
        """Create main agent."""
        return self.create_agent(tools, sys_prompt=self.config.system_prompt)

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
