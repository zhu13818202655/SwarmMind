"""Tool registry for SwarmMind."""

from typing import Any, Callable
import inspect

from agentscope.tool import Toolkit

from swarmmind.models.capability import ToolGroup


class ToolRegistry:
    """Tool registry for managing tools."""

    def __init__(self):
        self._toolkit = Toolkit()
        self._funcs: dict[str, Callable] = {}
        self._tool_groups: dict[str, list[ToolGroup]] = {}
        self._descriptions: dict[str, str] = {}

    def register(
        self,
        func: Callable,
        name: str | None = None,
        description: str | None = None,
        groups: list[ToolGroup | str] | None = None,
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

        self._toolkit.register_tool_function(
            tool_name,
            async_wrapper,
            description,
        )
        self._funcs[tool_name] = func
        self._descriptions[tool_name] = description
        self._tool_groups[tool_name] = [
            group if isinstance(group, ToolGroup) else ToolGroup(group)
            for group in (groups or [])
        ]

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

    def get_tool_metadata(self) -> list[dict[str, Any]]:
        """Return tool metadata including tool group assignments."""
        return [
            {
                "name": name,
                "description": self._descriptions.get(name, ""),
                "groups": [group.value for group in self._tool_groups.get(name, [])],
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

    @property
    def toolkit(self) -> Toolkit:
        """Get the underlying AgentScope toolkit."""
        return self._toolkit
