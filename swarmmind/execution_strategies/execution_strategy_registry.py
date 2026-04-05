"""Registry for runtime execution strategies and related profiles."""

from typing import Any

from swarmmind.execution_strategies.strategy import ExecutionStrategy, StrategyResult


class ExecutionStrategyRegistry:
    """Registry for runtime execution strategies and related profiles."""

    def __init__(self):
        self._strategies: dict[str, ExecutionStrategy] = {}

    def register(self, strategy: ExecutionStrategy) -> None:
        """Register a runtime execution strategy."""
        self._strategies[strategy.name] = strategy

    def get(self, name: str) -> ExecutionStrategy | None:
        """Get a runtime execution strategy by name."""
        return self._strategies.get(name)

    def list_strategies(self) -> list[dict[str, Any]]:
        """List all registered runtime execution strategies."""
        return [
            {
                "name": strategy.name,
                "description": strategy.description,
                "schema": strategy.get_schema(),
            }
            for strategy in self._strategies.values()
        ]

    async def execute(self, strategy_name: str, **kwargs: Any) -> StrategyResult:
        """Execute a runtime strategy by name."""
        strategy = self.get(strategy_name)
        if strategy is None:
            return StrategyResult(
                success=False,
                error=f"Runtime strategy not found: {strategy_name}",
            )

        try:
            return await strategy.execute(**kwargs)
        except Exception as exc:
            return StrategyResult(
                success=False,
                error=str(exc),
            )