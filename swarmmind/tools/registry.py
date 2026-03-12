"""Tool registry for SwarmMind."""

from typing import Any, Callable
import inspect

from agentscope.tool import Toolkit


class ToolRegistry:
    """Tool registry for managing tools."""

    def __init__(self):
        self._toolkit = Toolkit()
        self._funcs: dict[str, Callable] = {}

    def register(self, func: Callable, name: str | None = None, description: str | None = None) -> None:
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

    def get_tool(self, name: str) -> Any:
        """Get tool by name."""
        return self._toolkit

    def get_all_tools(self) -> list[dict[str, Any]]:
        """Get all registered tools."""
        return self._toolkit.get_json_schemas()

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

    @property
    def toolkit(self) -> Toolkit:
        """Get the underlying AgentScope toolkit."""
        return self._toolkit
