"""Skill registry for SwarmMind."""

from typing import Any
from swarmmind.skills.base import Skill, SkillResult


class SkillRegistry:
    """Registry for managing skills."""

    def __init__(self):
        self._skills: dict[str, Skill] = {}

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
