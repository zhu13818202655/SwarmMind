"""Execution profile and structured decision models."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from swarmmind.models.agent_profile import SkillsMode
from swarmmind.models.capability import AgentRole, RuntimeKind, ToolGroup


class ExecutionConfiguration(BaseModel):
    """Planner-provided execution configuration for a subtask."""

    runtime_kind: RuntimeKind | None = Field(default=None)
    tool_requirements: list[ToolGroup] = Field(default_factory=list)
    sandbox_profile: str | None = Field(default=None)
    skill_profiles: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)


class ExecutionProfile(BaseModel):
    """Resolved capability bundle for a subtask execution."""

    model_config = ConfigDict(populate_by_name=True)

    role: AgentRole = Field(..., description="Logical role assigned to the executor")
    agent_profile_id: str | None = Field(default=None, description="Resolved agent profile identifier")
    execution_configuration: ExecutionConfiguration | None = Field(default=None)
    required_tool_groups: list[ToolGroup] = Field(
        default_factory=list,
        description="Tool groups that should be equipped for this subtask",
    )
    resolved_runtime_kind: RuntimeKind | None = Field(
        default=None,
        description="Resolved runtime kind selected for this execution attempt",
    )
    runtime_resolution_reason: str | None = Field(
        default=None,
        description="Human-readable explanation for the resolved runtime choice",
    )
    runtime_fallback_chain: list[RuntimeKind] = Field(
        default_factory=list,
        description="Ordered backup runtimes kept after the resolved runtime is selected",
    )
    allowed_tool_groups: list[ToolGroup] = Field(
        default_factory=list,
        description="Tool groups allowed by the resolved agent profile",
    )
    allowed_tool_names: list[str] = Field(
        default_factory=list,
        description="Explicit tool allowlist enforced at runtime",
    )
    skill_mode: SkillsMode = Field(default=SkillsMode.ALL, description="How agent skill profiles should be interpreted")
    skill_profiles: list[str] = Field(
        default_factory=list,
        description="Skill packages selected for the subtask",
    )
    allowed_skill_scripts: list[str] = Field(
        default_factory=list,
        description="Allowlisted skill script specifiers such as skill_name:script.py",
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