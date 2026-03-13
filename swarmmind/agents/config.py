"""Agent configuration."""

from typing import Any
from pydantic import BaseModel, Field

from swarmmind.models.capability import AgentRole, ToolGroup


class AgentScopeConfig(BaseModel):
    """AgentScope configuration."""

    model_type: str = Field(default="openai", description="Model type")
    model_name: str = Field(default="gpt-4o", description="Model name")
    api_key: str | None = Field(default=None, description="API key")
    base_url: str | None = Field(default=None, description="Base URL")
    temperature: float = Field(default=0.7, description="Temperature")
    max_tokens: int = Field(default=4096, description="Max tokens")


class AgentConfig(BaseModel):
    """Agent configuration."""

    name: str = Field(default="main", description="Agent name")
    role: AgentRole = Field(default=AgentRole.EXECUTOR, description="Logical agent role")
    scope_config: AgentScopeConfig = Field(default_factory=AgentScopeConfig)
    max_steps: int = Field(default=100, description="Max steps")
    memory_config: dict[str, Any] = Field(
        default_factory=lambda: {"max_session_blocks": 10},
        description="Memory configuration",
    )
    system_prompt: str | None = Field(default=None, description="System prompt")
    skill_profiles: list[str] = Field(
        default_factory=list,
        description="Skill profiles equipped on this agent",
    )
    tool_groups: list[ToolGroup] = Field(
        default_factory=list,
        description="Tool groups equipped on this agent",
    )
