"""Execution profile models for equipping agents per subtask."""

from pydantic import BaseModel, Field

from swarmmind.models.capability import AgentRole, ToolGroup


class ExecutionProfile(BaseModel):
    """Resolved capability bundle for a subtask execution."""

    role: AgentRole = Field(..., description="Logical role assigned to the executor")
    preferred_skill: str | None = Field(
        default=None,
        description="Preferred skill profile for the subtask",
    )
    required_tool_groups: list[ToolGroup] = Field(
        default_factory=list,
        description="Tool groups that should be equipped for this subtask",
    )
    sandbox_profile: str | None = Field(
        default=None,
        description="Sandbox profile selected for this execution",
    )