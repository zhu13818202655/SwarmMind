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
    VERIFIER = "verifier"
    TESTER = "tester"
    REVIEWER = "reviewer"
    WRITER = "writer"


LEGACY_AGENT_ROLE_ALIASES: dict[AgentRole, AgentRole] = {
    AgentRole.EXECUTOR: AgentRole.CODER,
}


def canonicalize_agent_role(role: AgentRole) -> AgentRole:
    """Collapse legacy roles into the role-first canonical surface."""

    return LEGACY_AGENT_ROLE_ALIASES.get(role, role)


def agent_roles_match(left: AgentRole, right: AgentRole) -> bool:
    """Return whether two roles are equivalent after compatibility normalization."""

    return canonicalize_agent_role(left) == canonicalize_agent_role(right)


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


class ToolExecutionContract(BaseModel):
    """Execution metadata attached to an atomic tool function."""

    default_runtime: RuntimeKind = Field(
        default=RuntimeKind.HOST_TOOLS,
        description="Default runtime used when the agent selects this tool.",
    )
    allowed_runtimes: list[RuntimeKind] = Field(
        default_factory=list,
        description="Explicit runtimes that may execute this tool.",
    )
    read_only: bool = Field(default=False, description="Whether the tool is expected to avoid side effects.")
    expensive: bool = Field(default=False, description="Whether the tool is materially expensive in time or resources.")
    audit_required: bool = Field(default=False, description="Whether every invocation should be treated as auditable.")
    dangerous: bool = Field(default=False, description="Whether the tool can mutate state or execute untrusted actions.")
    sandbox_only: bool = Field(default=False, description="Whether the tool must run inside a sandbox runtime.")


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
        recommended_roles=[AgentRole.CODER],
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
        recommended_roles=[AgentRole.VERIFIER, AgentRole.TESTER, AgentRole.REVIEWER],
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
        recommended_roles=[AgentRole.PLANNER, AgentRole.RESEARCHER, AgentRole.WRITER, AgentRole.CODER],
        candidate_runtime_kinds=[RuntimeKind.AGENT_BACKED],
    ),
}



DEFAULT_ROLE_TOOL_GROUPS: dict[AgentRole, list[ToolGroup]] = {
    AgentRole.PLANNER: [ToolGroup.PROJECT_READ, ToolGroup.MEMORY_LOOKUP],
    AgentRole.COORDINATOR: [ToolGroup.TASK_ADMIN, ToolGroup.MEMORY_LOOKUP, ToolGroup.ARTIFACT_READ],
    AgentRole.RESEARCHER: [ToolGroup.WEB_SEARCH, ToolGroup.BROWSER_READ, ToolGroup.PROJECT_READ],
    AgentRole.CODER: [ToolGroup.PROJECT_READ, ToolGroup.PROJECT_WRITE, ToolGroup.SANDBOX_EXEC],
    AgentRole.VERIFIER: [ToolGroup.PROJECT_READ, ToolGroup.SANDBOX_EXEC, ToolGroup.ARTIFACT_READ],
    AgentRole.TESTER: [ToolGroup.PROJECT_READ, ToolGroup.SANDBOX_EXEC, ToolGroup.ARTIFACT_READ],
    AgentRole.REVIEWER: [ToolGroup.ARTIFACT_READ, ToolGroup.MEMORY_LOOKUP],
    AgentRole.WRITER: [ToolGroup.WEB_SEARCH, ToolGroup.BROWSER_READ, ToolGroup.PROJECT_WRITE],
}