from __future__ import annotations

from swarmmind.models.agent_profile import AgentProfile, HandoffPolicy, SkillsMode
from swarmmind.models.capability import AgentRole, RuntimeKind, ToolGroup

DEFAULT_AGENT_PROFILES: dict[str, AgentProfile] = {
    "planner-default": AgentProfile(
        id="planner-default",
        name="Planner Default",
        role=AgentRole.PLANNER,
        description="Default planning profile for decomposition and requirement analysis.",
        skill_mode=SkillsMode.INCLUSIVE,
        skill_profiles=["writing-plans"],
        default_tool_groups=[ToolGroup.WORKSPACE, ToolGroup.MEMORY],
        recommended_runtime_kinds=[RuntimeKind.LLM_ONLY],
        allowed_tool_groups=[ToolGroup.WORKSPACE, ToolGroup.MEMORY],
    ),
    "researcher-default": AgentProfile(
        id="researcher-default",
        name="Researcher Default",
        role=AgentRole.RESEARCHER,
        description="Research profile for web-backed information gathering.",
        skill_mode=SkillsMode.INCLUSIVE,
        skill_profiles=["deep-research"],
        default_tool_groups=[ToolGroup.WEB_SEARCH, ToolGroup.BROWSER, ToolGroup.WORKSPACE, ToolGroup.ARTIFACT],
        recommended_runtime_kinds=[RuntimeKind.HOST_TOOLS, RuntimeKind.SANDBOX],
        allowed_tool_groups=[
            ToolGroup.WEB_SEARCH,
            ToolGroup.BROWSER,
            ToolGroup.WORKSPACE,
            ToolGroup.CODE_EXEC,
            ToolGroup.MEMORY,
            ToolGroup.ARTIFACT,
        ],
        default_sandbox_profile="research-net",
    ),
    "coder-default": AgentProfile(
        id="coder-default",
        name="Coder Default",
        role=AgentRole.CODER,
        description="Default coding profile for implementation subtasks.",
        skill_mode=SkillsMode.INCLUSIVE,
        skill_profiles=[],
        default_tool_groups=[ToolGroup.WORKSPACE, ToolGroup.CODE_EXEC, ToolGroup.MEMORY],
        recommended_runtime_kinds=[RuntimeKind.SANDBOX, RuntimeKind.HOST_TOOLS],
        allowed_tool_groups=[
            ToolGroup.WORKSPACE,
            ToolGroup.CODE_EXEC,
            ToolGroup.ARTIFACT,
            ToolGroup.MEMORY,
        ],
        default_sandbox_profile="py-basic",
    ),
    "verifier-default": AgentProfile(
        id="verifier-default",
        name="Verifier Default",
        role=AgentRole.VERIFIER,
        description="Verification-focused profile for structured acceptance checks.",
        skill_mode=SkillsMode.INCLUSIVE,
        skill_profiles=[],
        default_tool_groups=[ToolGroup.WORKSPACE, ToolGroup.CODE_EXEC, ToolGroup.ARTIFACT],
        recommended_runtime_kinds=[RuntimeKind.SANDBOX, RuntimeKind.HOST_TOOLS],
        allowed_tool_groups=[ToolGroup.WORKSPACE, ToolGroup.CODE_EXEC, ToolGroup.ARTIFACT, ToolGroup.MEMORY],
        default_sandbox_profile="py-basic",
    ),
    "tester-default": AgentProfile(
        id="tester-default",
        name="Tester Default",
        role=AgentRole.TESTER,
        description="Verification-focused profile with restricted artifact and sandbox access.",
        skill_mode=SkillsMode.INCLUSIVE,
        skill_profiles=[],
        default_tool_groups=[ToolGroup.WORKSPACE, ToolGroup.CODE_EXEC, ToolGroup.ARTIFACT],
        recommended_runtime_kinds=[RuntimeKind.SANDBOX, RuntimeKind.HOST_TOOLS],
        allowed_tool_groups=[ToolGroup.WORKSPACE, ToolGroup.CODE_EXEC, ToolGroup.ARTIFACT, ToolGroup.MEMORY],
        default_sandbox_profile="py-basic",
    ),
    "reviewer-default": AgentProfile(
        id="reviewer-default",
        name="Reviewer Default",
        role=AgentRole.REVIEWER,
        description="Review-focused profile for structured accept/rework decisions.",
        skill_mode=SkillsMode.INCLUSIVE,
        skill_profiles=[],
        default_tool_groups=[ToolGroup.ARTIFACT, ToolGroup.MEMORY, ToolGroup.WORKSPACE],
        recommended_runtime_kinds=[RuntimeKind.LLM_ONLY, RuntimeKind.HOST_TOOLS],
        allowed_tool_groups=[ToolGroup.ARTIFACT, ToolGroup.MEMORY, ToolGroup.WORKSPACE],
    ),
    "writer-default": AgentProfile(
        id="writer-default",
        name="Writer Default",
        role=AgentRole.WRITER,
        description="Writing profile for structured reports and summaries.",
        skill_mode=SkillsMode.INCLUSIVE,
        skill_profiles=[],
        default_tool_groups=[ToolGroup.WORKSPACE, ToolGroup.ARTIFACT, ToolGroup.WEB_SEARCH, ToolGroup.BROWSER],
        recommended_runtime_kinds=[RuntimeKind.HOST_TOOLS, RuntimeKind.SANDBOX],
        allowed_tool_groups=[
            ToolGroup.WEB_SEARCH,
            ToolGroup.BROWSER,
            ToolGroup.WORKSPACE,
            ToolGroup.CODE_EXEC,
            ToolGroup.MEMORY,
            ToolGroup.ARTIFACT,
        ],
    ),
}

DEFAULT_ROLE_PROFILE_IDS: dict[AgentRole, str] = {
    AgentRole.PLANNER: "planner-default",
    AgentRole.COORDINATOR: "planner-default",
    AgentRole.RESEARCHER: "researcher-default",
    AgentRole.CODER: "coder-default",
    AgentRole.VERIFIER: "verifier-default",
    AgentRole.TESTER: "tester-default",
    AgentRole.REVIEWER: "reviewer-default",
    AgentRole.WRITER: "writer-default",
}


class AgentProfileStore:
    """Simple in-memory store for built-in and runtime agent profiles."""

    def __init__(self, profiles: list[AgentProfile] | None = None) -> None:
        self._profiles: dict[str, AgentProfile] = {profile.id: profile for profile in DEFAULT_AGENT_PROFILES.values()}
        for profile in profiles or []:
            self.save(profile)

    def get(self, profile_id: str | None) -> AgentProfile | None:
        if not profile_id:
            return None
        return self._profiles.get(profile_id)

    def list_all(self) -> list[AgentProfile]:
        return list(self._profiles.values())

    def save(self, profile: AgentProfile) -> None:
        self._profiles[profile.id] = profile

    def resolve_for_subtask(
        self,
        *,
        role: AgentRole,
    ) -> AgentProfile:
        default_profile_id = DEFAULT_ROLE_PROFILE_IDS.get(role)
        profile = self.get(default_profile_id)
        if profile is None:
            raise ValueError(f"No default agent profile for role: {role}")
        return profile