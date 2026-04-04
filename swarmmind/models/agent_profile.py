"""Agent profile models for runtime capability boundaries."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from swarmmind.models.capability import AgentRole, ToolGroup


class SkillsMode(str, Enum):
    """How an agent profile should interpret its declared skill profiles."""

    ALL = "all"
    INCLUSIVE = "inclusive"
    EXCLUSIVE = "exclusive"


class HandoffContextMode(str, Enum):
    """How much context a future delegated execution may inherit."""

    NONE = "none"
    SUMMARY = "summary"
    ARTIFACTS = "artifacts"
    FULL = "full"


class HandoffPolicy(BaseModel):
    """Controlled handoff policy attached to an execution-capable profile."""

    allow_handoff: bool = Field(default=False)
    allowed_targets: list[str] = Field(default_factory=list)
    max_depth: int = Field(default=0, ge=0)
    context_mode: HandoffContextMode = Field(default=HandoffContextMode.SUMMARY)


class AgentProfile(BaseModel):
    """Explicit agent boundary contract inspired by OpenAkita profiles."""

    id: str = Field(..., description="Unique profile identifier")
    name: str = Field(..., description="Human-friendly display name")
    role: AgentRole = Field(..., description="Primary logical role served by this profile")
    description: str = Field(default="", description="Short profile description")
    system_prompt: str | None = Field(default=None, description="Optional system prompt override")
    custom_prompt: str | None = Field(default=None, description="Prompt suffix injected for this profile")
    skill_mode: SkillsMode = Field(default=SkillsMode.ALL)
    skill_profiles: list[str] = Field(default_factory=list, description="Native AgentScope skill profiles")
    allowed_tool_groups: list[ToolGroup] = Field(default_factory=list)
    allowed_tool_names: list[str] = Field(default_factory=list)
    allowed_skill_scripts: list[str] = Field(default_factory=list)
    default_strategy: str | None = Field(default=None)
    default_sandbox_profile: str | None = Field(default=None)
    preferred_model: str | None = Field(default=None)
    preferred_endpoint: str | None = Field(default=None)
    handoff_policy: HandoffPolicy = Field(default_factory=HandoffPolicy)
    ephemeral: bool = Field(default=False)
    inherit_from: str | None = Field(default=None)
    metadata: dict[str, Any] = Field(default_factory=dict)