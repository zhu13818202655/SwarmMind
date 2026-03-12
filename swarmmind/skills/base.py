"""Base skill classes for SwarmMind."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class SkillResult:
    """Result of a skill execution."""

    success: bool
    output: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    executed_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "metadata": self.metadata,
            "executed_at": self.executed_at.isoformat(),
        }


class Skill(ABC):
    """Base class for skills."""

    name: str = "base_skill"
    description: str = "Base skill"

    def __init__(self):
        self._tools = {}

    @abstractmethod
    async def execute(self, **kwargs) -> SkillResult:
        """Execute the skill.

        Args:
            **kwargs: Skill-specific arguments

        Returns:
            SkillResult
        """
        pass

    def get_schema(self) -> dict[str, Any]:
        """Get the skill's JSON schema for LLM tool calling."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.get_parameters_schema(),
        }

    @abstractmethod
    def get_parameters_schema(self) -> dict[str, Any]:
        """Get the parameters schema."""
        pass

    def register_tool(self, name: str, tool_func):
        """Register a tool for this skill."""
        self._tools[name] = tool_func


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

    async def execute(self, skill_name: str, **kwargs) -> SkillResult:
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
