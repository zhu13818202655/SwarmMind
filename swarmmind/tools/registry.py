"""Tool registry for SwarmMind."""

from typing import Any, Callable
import inspect

from agentscope.tool import Toolkit

from swarmmind.models.capability import RuntimeKind, ToolExecutionContract, ToolGroup


class ToolRegistry:
    """Tool registry for managing tools."""

    def __init__(self):
        self._toolkit = Toolkit()
        self._funcs: dict[str, Callable] = {}
        self._tool_groups: dict[str, list[ToolGroup]] = {}
        self._descriptions: dict[str, str] = {}
        self._contracts: dict[str, ToolExecutionContract] = {}

    def register(
        self,
        func: Callable,
        name: str | None = None,
        description: str | None = None,
        groups: list[ToolGroup | str] | None = None,
        contract: ToolExecutionContract | dict[str, Any] | None = None,
    ) -> None:
        """Register a function as a tool."""
        tool_name = name or func.__name__

        # Get description from docstring if not provided
        if description is None:
            description = func.__doc__ or "No description"

        # Wrap async function for sync use
        async def async_wrapper(*args, **kwargs):
            if inspect.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            return func(*args, **kwargs)

        normalized_contract = self._normalize_contract(contract)
        contract_target = getattr(func, "__func__", func)
        setattr(contract_target, "__swarmmind_tool_contract__", normalized_contract)
        setattr(async_wrapper, "__swarmmind_tool_contract__", normalized_contract)

        self._toolkit.register_tool_function(
            async_wrapper,
            func_name=tool_name,
            func_description=description,
        )
        self._funcs[tool_name] = func
        self._descriptions[tool_name] = description
        self._tool_groups[tool_name] = [
            group if isinstance(group, ToolGroup) else ToolGroup(group)
            for group in (groups or [])
        ]
        self._contracts[tool_name] = normalized_contract

    def get_tool(self, name: str) -> Any:
        """Get tool by name."""
        return self._toolkit

    def get_all_tools(self) -> list[dict[str, Any]]:
        """Get all registered tools."""
        return self._toolkit.get_json_schemas()

    def get_tools_for_groups(self, groups: list[ToolGroup | str]) -> list[dict[str, Any]]:
        """Get tool schemas matching any of the provided groups."""
        normalized_groups = {
            group if isinstance(group, ToolGroup) else ToolGroup(group)
            for group in groups
        }
        selected_names = {
            name
            for name, tool_groups in self._tool_groups.items()
            if normalized_groups.intersection(tool_groups)
        }
        return [
            schema
            for schema in self._toolkit.get_json_schemas()
            if schema.get("name") in selected_names
        ]

    def get_tool_groups(self, name: str) -> list[ToolGroup]:
        """Return the tool groups associated with a tool."""
        return self._tool_groups.get(name, [])

    def get_tool_contract(self, name: str) -> ToolExecutionContract | None:
        """Return execution metadata associated with a tool."""
        return self._contracts.get(name)

    def get_tool_metadata(self) -> list[dict[str, Any]]:
        """Return tool metadata including tool group assignments."""
        return [
            {
                "name": name,
                "description": self._descriptions.get(name, ""),
                "groups": [group.value for group in self._tool_groups.get(name, [])],
                "contract": self._contracts.get(name, ToolExecutionContract()).model_dump(mode="json"),
            }
            for name in self._funcs
        ]

    def get_tool_names(self) -> list[str]:
        """Get all tool names."""
        return list(self._funcs.keys())

    async def execute(self, tool_name: str, **kwargs: Any) -> Any:
        """Execute a tool by name."""
        func = self._funcs.get(tool_name)
        if func is None:
            raise ValueError(f"Tool not found: {tool_name}")

        # Check if function is async
        if inspect.iscoroutinefunction(func):
            return await func(**kwargs)
        else:
            return func(**kwargs)

    def clear(self) -> None:
        """Clear all registered tools."""
        self._toolkit.clear()
        self._funcs.clear()
        self._tool_groups.clear()
        self._descriptions.clear()
        self._contracts.clear()

    @staticmethod
    def _normalize_contract(
        contract: ToolExecutionContract | dict[str, Any] | None,
    ) -> ToolExecutionContract:
        if isinstance(contract, ToolExecutionContract):
            normalized = contract.model_copy(deep=True)
        elif isinstance(contract, dict):
            normalized = ToolExecutionContract(**contract)
        else:
            normalized = ToolExecutionContract()

        allowed_runtimes = list(normalized.allowed_runtimes)
        if normalized.sandbox_only:
            normalized = normalized.model_copy(update={"default_runtime": RuntimeKind.SANDBOX})
            allowed_runtimes = [RuntimeKind.SANDBOX]
        elif not allowed_runtimes:
            allowed_runtimes = [normalized.default_runtime]

        return normalized.model_copy(update={"allowed_runtimes": allowed_runtimes})

    @property
    def toolkit(self) -> Toolkit:
        """Get the underlying AgentScope toolkit."""
        return self._toolkit
