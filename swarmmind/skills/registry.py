"""Skill registry for SwarmMind."""

from typing import Any
from swarmmind.skills.base import Skill, SkillResult
from swarmmind.models.capability import AgentRole, DEFAULT_SKILL_PROFILES, SkillProfile


class SkillRegistry:
    """Registry for managing skills."""

    def __init__(self):
        self._skills: dict[str, Skill] = {}
        self._profiles: dict[str, SkillProfile] = dict(DEFAULT_SKILL_PROFILES)

    def register(self, skill: Skill) -> None:
        """Register a skill."""
        self._skills[skill.name] = skill

    def get(self, name: str) -> Skill | None:
        """Get a skill by name."""
        return self._skills.get(name)

    def list_skills(self) -> list[dict[str, Any]]:
        """List all registered skills."""
        return [
            {
                "name": skill.name,
                "description": skill.description,
                "schema": skill.get_schema(),
            }
            for skill in self._skills.values()
        ]

    def register_profile(self, profile: SkillProfile) -> None:
        """Register or override a structured skill profile."""
        self._profiles[profile.name] = profile

    def get_profile(self, name: str) -> SkillProfile | None:
        """Get a skill profile by name."""
        return self._profiles.get(name)

    def list_profiles(self) -> list[SkillProfile]:
        """List all known skill profiles."""
        return list(self._profiles.values())

    def list_profiles_for_role(self, role: AgentRole | str) -> list[SkillProfile]:
        """List profiles recommended for a role."""
        normalized_role = role if isinstance(role, AgentRole) else AgentRole(role)
        return [
            profile
            for profile in self._profiles.values()
            if normalized_role in profile.recommended_roles
        ]

    async def execute(self, skill_name: str, **kwargs: Any) -> SkillResult:
        """Execute a skill by name."""
        skill = self.get(skill_name)
        if skill is None:
            return SkillResult(
                success=False,
                error=f"Skill not found: {skill_name}",
            )

        try:
            return await skill.execute(**kwargs)
        except Exception as e:
            return SkillResult(
                success=False,
                error=str(e),
            )
