"""Agent profile store and built-in runtime profile defaults."""

from __future__ import annotations

from swarmmind.models.agent_profile import AgentProfile, HandoffPolicy, SkillsMode
from swarmmind.models.capability import AgentRole, ToolGroup, agent_roles_match, canonicalize_agent_role


DEFAULT_AGENT_PROFILES: dict[str, AgentProfile] = {
    "planner-default": AgentProfile(
        id="planner-default",
        name="Planner Default",
        role=AgentRole.PLANNER,
        description="Default planning profile for decomposition and requirement analysis.",
        skill_mode=SkillsMode.INCLUSIVE,
        skill_profiles=["task_planning"],
        allowed_tool_groups=[ToolGroup.PROJECT_READ, ToolGroup.MEMORY_LOOKUP, ToolGroup.SANDBOX_EXEC],
        default_strategy="task_planning",
    ),
    "coder-default": AgentProfile(
        id="coder-default",
        name="Coder Default",
        role=AgentRole.CODER,
        description="Default coding profile for implementation subtasks.",
        skill_mode=SkillsMode.INCLUSIVE,
        skill_profiles=["build_app"],
        allowed_tool_groups=[
            ToolGroup.PROJECT_READ,
            ToolGroup.PROJECT_WRITE,
            ToolGroup.SANDBOX_EXEC,
            ToolGroup.ARTIFACT_READ,
            ToolGroup.MEMORY_LOOKUP,
        ],
        default_strategy="build_app",
        default_sandbox_profile="py-basic",
    ),
    "verifier-default": AgentProfile(
        id="verifier-default",
        name="Verifier Default",
        role=AgentRole.VERIFIER,
        description="Verification-focused profile for structured acceptance checks.",
        skill_mode=SkillsMode.INCLUSIVE,
        skill_profiles=["verification"],
        allowed_tool_groups=[ToolGroup.PROJECT_READ, ToolGroup.SANDBOX_EXEC, ToolGroup.ARTIFACT_READ],
        default_strategy="verification",
        default_sandbox_profile="py-basic",
    ),
    "tester-default": AgentProfile(
        id="tester-default",
        name="Tester Default",
        role=AgentRole.TESTER,
        description="Verification-focused profile with restricted artifact and sandbox access.",
        skill_mode=SkillsMode.INCLUSIVE,
        skill_profiles=["verification"],
        allowed_tool_groups=[ToolGroup.PROJECT_READ, ToolGroup.SANDBOX_EXEC, ToolGroup.ARTIFACT_READ],
        default_strategy="verification",
        default_sandbox_profile="py-basic",
    ),
    "reviewer-default": AgentProfile(
        id="reviewer-default",
        name="Reviewer Default",
        role=AgentRole.REVIEWER,
        description="Review-focused profile for structured accept/rework decisions.",
        skill_mode=SkillsMode.INCLUSIVE,
        skill_profiles=["review"],
        allowed_tool_groups=[ToolGroup.ARTIFACT_READ, ToolGroup.MEMORY_LOOKUP],
        default_strategy="review",
    ),
    "researcher-default": AgentProfile(
        id="researcher-default",
        name="Researcher Default",
        role=AgentRole.RESEARCHER,
        description="Research profile for web-backed information gathering.",
        skill_mode=SkillsMode.INCLUSIVE,
        skill_profiles=["research"],
        allowed_tool_groups=[
            ToolGroup.WEB_SEARCH,
            ToolGroup.BROWSER_READ,
            ToolGroup.PROJECT_READ,
            ToolGroup.SANDBOX_EXEC,
            ToolGroup.MEMORY_LOOKUP,
        ],
        default_strategy="research",
        default_sandbox_profile="research-net",
    ),
    "writer-default": AgentProfile(
        id="writer-default",
        name="Writer Default",
        role=AgentRole.WRITER,
        description="Writing profile for structured reports and summaries.",
        skill_mode=SkillsMode.INCLUSIVE,
        skill_profiles=["write_report"],
        allowed_tool_groups=[
            ToolGroup.WEB_SEARCH,
            ToolGroup.BROWSER_READ,
            ToolGroup.PROJECT_WRITE,
            ToolGroup.SANDBOX_EXEC,
            ToolGroup.MEMORY_LOOKUP,
        ],
        default_strategy="write_report",
    ),
    "agent-backed-default": AgentProfile(
        id="agent-backed-default",
        name="Agent Backed Default",
        role=AgentRole.CODER,
        description="Controlled profile for the reserved agent-backed execution strategy.",
        skill_mode=SkillsMode.ALL,
        allowed_tool_groups=[ToolGroup.PROJECT_READ, ToolGroup.MEMORY_LOOKUP],
        default_strategy="agent_backed",
        handoff_policy=HandoffPolicy(allow_handoff=False, max_depth=0),
    ),
}

DEFAULT_ROLE_PROFILE_IDS: dict[AgentRole, str] = {
    AgentRole.PLANNER: "planner-default",
    AgentRole.COORDINATOR: "planner-default",
    AgentRole.RESEARCHER: "researcher-default",
    AgentRole.EXECUTOR: "coder-default",
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
        profile_id: str | None,
        role: AgentRole,
        preferred_strategy: str | None = None,
    ) -> AgentProfile:
        canonical_role = canonicalize_agent_role(role)
        if profile_id:
            profile = self.get(profile_id)
            if profile is None:
                raise ValueError(f"Agent profile not found: {profile_id}")
            if agent_roles_match(profile.role, canonical_role):
                if profile.role == canonical_role:
                    return profile
                return profile.model_copy(update={"role": canonical_role})

        if preferred_strategy == "agent_backed":
            profile = self.get("agent-backed-default")
            if profile is not None:
                return profile.model_copy(update={"role": canonical_role})

        default_profile_id = DEFAULT_ROLE_PROFILE_IDS.get(canonical_role)
        profile = self.get(default_profile_id)
        if profile is None:
            raise ValueError(f"No default agent profile for role: {canonical_role}")
        return profile