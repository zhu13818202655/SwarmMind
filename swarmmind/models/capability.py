"""Capability models for agent roles, strategy profiles, and tool groups."""

from enum import Enum

from pydantic import BaseModel, Field


class AgentRole(str, Enum):
    """Logical roles used by the orchestrator."""

    PLANNER = "planner"
    COORDINATOR = "coordinator"
    RESEARCHER = "researcher"
    EXECUTOR = "executor"
    CODER = "coder"
    TESTER = "tester"
    REVIEWER = "reviewer"
    WRITER = "writer"


class ToolGroup(str, Enum):
    """Groups of atomic tools equipped per subtask."""

    PROJECT_READ = "project_read"
    PROJECT_WRITE = "project_write"
    WEB_SEARCH = "web_search"
    BROWSER_READ = "browser_read"
    SANDBOX_EXEC = "sandbox_exec"
    ARTIFACT_READ = "artifact_read"
    MEMORY_LOOKUP = "memory_lookup"
    TASK_ADMIN = "task_admin"
    MAIL = "mail"
    PRESENTATION = "presentation"


class RuntimeKind(str, Enum):
    """Execution backends available to a subtask attempt."""

    LLM_ONLY = "llm_only"
    HOST_TOOLS = "host_tools"
    SANDBOX = "sandbox"
    BROWSER_AUTOMATION = "browser_automation"
    AGENT_BACKED = "agent_backed"


class StrategyProfile(BaseModel):
    """Structured runtime strategy profile used to equip a subtask."""

    name: str = Field(..., description="Unique skill profile name")
    description: str = Field(..., description="What this profile is for")
    tool_groups: list[ToolGroup] = Field(
        default_factory=list,
        description="Tool groups required by the skill profile",
    )
    recommended_roles: list[AgentRole] = Field(
        default_factory=list,
        description="Roles that commonly use this profile",
    )
    candidate_runtime_kinds: list[RuntimeKind] = Field(
        default_factory=list,
        description="Candidate execution backends that may satisfy the workflow",
    )
    default_skill_profiles: list[str] = Field(
        default_factory=list,
        description="Reusable skill packages commonly attached to the workflow",
    )
    sandbox_profile: str | None = Field(
        default=None,
        description="Preferred sandbox profile for this skill profile",
    )


DEFAULT_STRATEGY_PROFILES: dict[str, StrategyProfile] = {
    "task_planning": StrategyProfile(
        name="task_planning",
        description="Decompose user goals into executable task graphs.",
        tool_groups=[ToolGroup.PROJECT_READ, ToolGroup.MEMORY_LOOKUP],
        recommended_roles=[AgentRole.PLANNER, AgentRole.COORDINATOR],
        candidate_runtime_kinds=[RuntimeKind.LLM_ONLY, RuntimeKind.HOST_TOOLS],
        default_skill_profiles=["task_planning"],
    ),
    "research": StrategyProfile(
        name="research",
        description="Research external information and summarize findings.",
        tool_groups=[ToolGroup.WEB_SEARCH, ToolGroup.BROWSER_READ, ToolGroup.PROJECT_READ],
        recommended_roles=[AgentRole.RESEARCHER, AgentRole.WRITER],
        candidate_runtime_kinds=[RuntimeKind.HOST_TOOLS, RuntimeKind.BROWSER_AUTOMATION],
    ),
    "build_app": StrategyProfile(
        name="build_app",
        description="Implement application code, write files, and run local validation.",
        tool_groups=[
            ToolGroup.PROJECT_READ,
            ToolGroup.PROJECT_WRITE,
            ToolGroup.SANDBOX_EXEC,
            ToolGroup.ARTIFACT_READ,
        ],
        recommended_roles=[AgentRole.CODER, AgentRole.EXECUTOR],
        candidate_runtime_kinds=[RuntimeKind.SANDBOX, RuntimeKind.HOST_TOOLS],
        default_skill_profiles=["build_app"],
        sandbox_profile="py-basic",
    ),
    "verification": StrategyProfile(
        name="verification",
        description="Run tests and verify outputs against acceptance criteria.",
        tool_groups=[
            ToolGroup.PROJECT_READ,
            ToolGroup.SANDBOX_EXEC,
            ToolGroup.ARTIFACT_READ,
        ],
        recommended_roles=[AgentRole.TESTER, AgentRole.REVIEWER],
        candidate_runtime_kinds=[RuntimeKind.HOST_TOOLS],
        default_skill_profiles=["verification"],
    ),
    "review": StrategyProfile(
        name="review",
        description="Review results and decide whether to accept or rework.",
        tool_groups=[ToolGroup.ARTIFACT_READ, ToolGroup.MEMORY_LOOKUP],
        recommended_roles=[AgentRole.REVIEWER, AgentRole.COORDINATOR],
        candidate_runtime_kinds=[RuntimeKind.LLM_ONLY, RuntimeKind.HOST_TOOLS],
        default_skill_profiles=["review"],
    ),
    "write_report": StrategyProfile(
        name="write_report",
        description="Research, draft, and save a structured report.",
        tool_groups=[
            ToolGroup.WEB_SEARCH,
            ToolGroup.BROWSER_READ,
            ToolGroup.PROJECT_WRITE,
        ],
        recommended_roles=[AgentRole.WRITER, AgentRole.RESEARCHER],
        candidate_runtime_kinds=[RuntimeKind.LLM_ONLY, RuntimeKind.HOST_TOOLS],
        default_skill_profiles=["write_report"],
    ),
    "presentation_delivery": StrategyProfile(
        name="presentation_delivery",
        description="Turn researched material into a presentation delivery artifact.",
        tool_groups=[ToolGroup.PRESENTATION, ToolGroup.ARTIFACT_READ, ToolGroup.PROJECT_WRITE],
        recommended_roles=[AgentRole.WRITER, AgentRole.REVIEWER],
        candidate_runtime_kinds=[RuntimeKind.HOST_TOOLS, RuntimeKind.SANDBOX],
        default_skill_profiles=["pptx"],
        sandbox_profile="py-basic",
    ),
    "agent_backed": StrategyProfile(
        name="agent_backed",
        description="Run a controlled agent runtime backend instead of the default sandbox strategy.",
        tool_groups=[ToolGroup.PROJECT_READ, ToolGroup.MEMORY_LOOKUP],
        recommended_roles=[AgentRole.PLANNER, AgentRole.RESEARCHER, AgentRole.WRITER, AgentRole.EXECUTOR],
        candidate_runtime_kinds=[RuntimeKind.AGENT_BACKED],
    ),
}



DEFAULT_ROLE_TOOL_GROUPS: dict[AgentRole, list[ToolGroup]] = {
    AgentRole.PLANNER: [ToolGroup.PROJECT_READ, ToolGroup.MEMORY_LOOKUP],
    AgentRole.COORDINATOR: [ToolGroup.TASK_ADMIN, ToolGroup.MEMORY_LOOKUP, ToolGroup.ARTIFACT_READ],
    AgentRole.RESEARCHER: [ToolGroup.WEB_SEARCH, ToolGroup.BROWSER_READ, ToolGroup.PROJECT_READ],
    AgentRole.EXECUTOR: [ToolGroup.PROJECT_READ, ToolGroup.PROJECT_WRITE, ToolGroup.SANDBOX_EXEC],
    AgentRole.CODER: [ToolGroup.PROJECT_READ, ToolGroup.PROJECT_WRITE, ToolGroup.SANDBOX_EXEC],
    AgentRole.TESTER: [ToolGroup.PROJECT_READ, ToolGroup.SANDBOX_EXEC, ToolGroup.ARTIFACT_READ],
    AgentRole.REVIEWER: [ToolGroup.ARTIFACT_READ, ToolGroup.MEMORY_LOOKUP],
    AgentRole.WRITER: [ToolGroup.WEB_SEARCH, ToolGroup.BROWSER_READ, ToolGroup.PROJECT_WRITE],
}