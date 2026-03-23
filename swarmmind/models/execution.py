"""Execution profile and structured decision models."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from swarmmind.models.capability import AgentRole, ToolGroup


class ExecutionProfile(BaseModel):
    """Resolved capability bundle for a subtask execution."""

    model_config = ConfigDict(populate_by_name=True)

    role: AgentRole = Field(..., description="Logical role assigned to the executor")
    preferred_strategy: str | None = Field(default=None, description="Preferred runtime strategy profile for the subtask")
    required_tool_groups: list[ToolGroup] = Field(
        default_factory=list,
        description="Tool groups that should be equipped for this subtask",
    )
    sandbox_profile: str | None = Field(
        default=None,
        description="Sandbox profile selected for this execution",
    )



class VerificationCriterionResult(BaseModel):
    """Per-criterion verification evidence."""

    criterion: str = Field(...)
    passed: bool = Field(...)
    evidence: str | None = Field(default=None)


class VerificationResult(BaseModel):
    """Structured verification output independent from shell exit codes."""

    passed: bool = Field(...)
    summary: str = Field(...)
    criteria_results: list[VerificationCriterionResult] = Field(default_factory=list)
    evidence_subtask_ids: list[str] = Field(default_factory=list)
    artifact_ids: list[str] = Field(default_factory=list)


class ReviewDecisionType(str, Enum):
    """Structured review outcomes."""

    ACCEPT = "accept"
    REWORK = "rework"
    ESCALATE = "escalate"


class ReviewDecision(BaseModel):
    """Structured reviewer decision."""

    decision: ReviewDecisionType = Field(...)
    summary: str = Field(...)
    rationale: str | None = Field(default=None)
    follow_up_actions: list[str] = Field(default_factory=list)