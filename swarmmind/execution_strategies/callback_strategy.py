"""Runtime execution strategy adapters used by the orchestration layer."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from swarmmind.execution_strategies.strategy import ExecutionStrategy, StrategyResult


class CallbackStrategy(ExecutionStrategy):
    """Adapt an async callback into a runtime execution strategy."""

    def __init__(
        self,
        name: str,
        description: str,
        handler: Callable[..., Awaitable[StrategyResult]],
    ) -> None:
        super().__init__()
        self.name = name
        self.description = description
        self._handler = handler

    async def execute(self, **kwargs: Any) -> StrategyResult:
        return await self._handler(**kwargs)

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {"type": "object"},
                "run": {"type": "object"},
                "subtask": {"type": "object"},
            },
            "required": ["task", "run", "subtask"],
        }