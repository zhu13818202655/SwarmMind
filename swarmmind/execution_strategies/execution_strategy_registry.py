"""Registry for runtime execution strategies and related profiles."""

from typing import Any

from swarmmind.execution_strategies.strategy import ExecutionStrategy, StrategyResult
from swarmmind.models.capability import AgentRole, DEFAULT_STRATEGY_PROFILES, StrategyProfile


class ExecutionStrategyRegistry:
    """Registry for runtime execution strategies and related profiles."""

    def __init__(self):
        self._strategies: dict[str, ExecutionStrategy] = {}
        self._profiles: dict[str, StrategyProfile] = dict(DEFAULT_STRATEGY_PROFILES)

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

    def register_profile(self, profile: StrategyProfile) -> None:
        """Register or override a structured strategy profile."""
        self._profiles[profile.name] = profile

    def get_profile(self, name: str) -> StrategyProfile | None:
        """Get a structured strategy profile."""
        return self._profiles.get(name)

    def list_profiles(self) -> list[StrategyProfile]:
        """List all known strategy profiles."""
        return list(self._profiles.values())

    def list_profiles_for_role(self, role: AgentRole | str) -> list[StrategyProfile]:
        """List strategy profiles recommended for a role."""
        normalized_role = role if isinstance(role, AgentRole) else AgentRole(role)
        return [
            profile
            for profile in self._profiles.values()
            if normalized_role in profile.recommended_roles
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