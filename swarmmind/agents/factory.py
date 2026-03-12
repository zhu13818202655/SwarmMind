"""AgentFactory - Create agents using AgentScope."""

from typing import Any
from agentscope.agent import ReActAgent
from agentscope.memory import InMemoryMemory
from agentscope.model import OpenAIChatModel

from swarmmind.agents.config import AgentConfig


class AgentFactory:
    """Factory for creating AgentScope agents."""

    def __init__(self, config: AgentConfig):
        self.config = config

    def create_model_client(self):
        """Create model client from config."""
        config = self.config.scope_config
        return OpenAIChatModel(
            model=config.model_name,
            api_key=config.api_key,
            base_url=config.base_url,
        )

    def create_memory(self):
        """Create memory from config."""
        return InMemoryMemory(memory_config=self.config.memory_config)

    def create_agent(self, tools: list[Any] | None = None) -> ReActAgent:
        """Create a ReActAgent."""
        return ReActAgent(
            name=self.config.name,
            model=self.create_model_client(),
            tools=tools or [],
            memory=self.create_memory(),
            max_steps=self.config.max_steps,
        )

    def create_main_agent(self, tools: list[Any] | None = None) -> ReActAgent:
        """Create main agent."""
        agent = self.create_agent(tools)
        if self.config.system_prompt:
            # Add system prompt as first message
            from agentscope.message import Msg
            agent.memory.add(Msg(name="system", content=self.config.system_prompt, role="system"))
        return agent

    def create_subagent(
        self,
        name: str,
        tools: list[Any],
        system_prompt: str | None = None,
    ) -> ReActAgent:
        """Create a sub-agent."""
        config = self.config.model_copy()
        config.name = name

        agent = ReActAgent(
            name=name,
            model=self.create_model_client(),
            tools=tools,
            memory=InMemoryMemory(memory_config=config.memory_config),
            max_steps=config.max_steps,
        )

        if system_prompt:
            from agentscope.message import Msg
            agent.memory.add(Msg(name="system", content=system_prompt, role="system"))

        return agent
