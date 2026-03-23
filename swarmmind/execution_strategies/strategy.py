"""Execution strategy abstractions for the runtime orchestration layer."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from swarmmind.utils import utc_now


@dataclass
class StrategyResult:
    """Result of runtime strategy execution."""

    success: bool
    output: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    executed_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "metadata": self.metadata,
            "executed_at": self.executed_at.isoformat(),
        }


class ExecutionStrategy(ABC):
    """Base class for runtime execution strategies."""

    name: str = "base_strategy"
    description: str = "Base execution strategy"

    def __init__(self):
        self._tools = {}

    @abstractmethod
    async def execute(self, **kwargs) -> StrategyResult:
        """Execute the strategy."""

    def get_schema(self) -> dict[str, Any]:
        """Get the strategy's JSON schema for inspection."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.get_parameters_schema(),
        }

    @abstractmethod
    def get_parameters_schema(self) -> dict[str, Any]:
        """Get the parameters schema."""

    def register_tool(self, name: str, tool_func):
        """Register a tool for this strategy."""
        self._tools[name] = tool_func