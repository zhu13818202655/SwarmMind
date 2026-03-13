"""Capability models for agent roles, skills, and tool groups."""

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


class SkillProfile(BaseModel):
    """Structured skill profile used to equip an agent for a subtask."""

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
    sandbox_profile: str | None = Field(
        default=None,
        description="Preferred sandbox profile for this skill profile",
    )


DEFAULT_SKILL_PROFILES: dict[str, SkillProfile] = {
    "task_planning": SkillProfile(
        name="task_planning",
        description="Decompose user goals into executable task graphs.",
        tool_groups=[ToolGroup.PROJECT_READ, ToolGroup.MEMORY_LOOKUP],
        recommended_roles=[AgentRole.PLANNER, AgentRole.COORDINATOR],
    ),
    "research": SkillProfile(
        name="research",
        description="Research external information and summarize findings.",
        tool_groups=[ToolGroup.WEB_SEARCH, ToolGroup.BROWSER_READ, ToolGroup.PROJECT_READ],
        recommended_roles=[AgentRole.RESEARCHER, AgentRole.WRITER],
        sandbox_profile="research-net",
    ),
    "build_app": SkillProfile(
        name="build_app",
        description="Implement application code, write files, and run local validation.",
        tool_groups=[
            ToolGroup.PROJECT_READ,
            ToolGroup.PROJECT_WRITE,
            ToolGroup.SANDBOX_EXEC,
            ToolGroup.ARTIFACT_READ,
        ],
        recommended_roles=[AgentRole.CODER, AgentRole.EXECUTOR],
        sandbox_profile="py-basic",
    ),
    "verification": SkillProfile(
        name="verification",
        description="Run tests and verify outputs against acceptance criteria.",
        tool_groups=[
            ToolGroup.PROJECT_READ,
            ToolGroup.SANDBOX_EXEC,
            ToolGroup.ARTIFACT_READ,
        ],
        recommended_roles=[AgentRole.TESTER, AgentRole.REVIEWER],
        sandbox_profile="py-basic",
    ),
    "review": SkillProfile(
        name="review",
        description="Review results and decide whether to accept or rework.",
        tool_groups=[ToolGroup.ARTIFACT_READ, ToolGroup.MEMORY_LOOKUP],
        recommended_roles=[AgentRole.REVIEWER, AgentRole.COORDINATOR],
    ),
    "write_report": SkillProfile(
        name="write_report",
        description="Research, draft, and save a structured report.",
        tool_groups=[
            ToolGroup.WEB_SEARCH,
            ToolGroup.BROWSER_READ,
            ToolGroup.PROJECT_WRITE,
        ],
        recommended_roles=[AgentRole.WRITER, AgentRole.RESEARCHER],
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