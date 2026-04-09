"""Tool registry for SwarmMind."""

import json
from typing import Any, Callable, Sequence
import inspect

from agentscope.tool import ToolResponse, Toolkit
from swarmmind.models.capability import RuntimeKind, ToolExecutionContract, ToolGroup


class ToolRegistry:
    """Tool registry for managing tools."""

    def __init__(self):
        self._toolkit = Toolkit()
        self._funcs: dict[str, Callable] = {}
        self._registered_funcs: dict[str, Callable] = {}
        self._tool_groups: dict[str, list[ToolGroup]] = {}
        self._primary_groups: dict[str, ToolGroup] = {}
        self._descriptions: dict[str, str] = {}
        self._contracts: dict[str, ToolExecutionContract] = {}

    _GROUP_DETAILS: dict[ToolGroup, tuple[str, str | None]] = {
        ToolGroup.FILE_SYSTEM: (
            "Basic file-system operations inside the workspace such as reading, writing, listing, renaming and deleting files.",
            None,
        ),
        ToolGroup.WORKSPACE: (
            "Project-level workspace helpers such as code search, glob search and repository-aware inspection.",
            None,
        ),
        ToolGroup.WEB_SEARCH: (
            "Structured public web search for discovering external information sources.",
            None,
        ),
        ToolGroup.BROWSER: (
            "Page fetching and browser-style interaction with web content.",
            None,
        ),
        ToolGroup.CODE_EXEC: (
            "Code and command execution capabilities that may require sandbox isolation.",
            None,
        ),
        ToolGroup.MEMORY: (
            "Long-term memory lookup and persistence helpers.",
            None,
        ),
        ToolGroup.ARTIFACT: (
            "Artifact inspection and attachment-oriented access patterns.",
            None,
        ),
        ToolGroup.COMMUNICATION: (
            "Communication primitives such as email and outbound notifications.",
            None,
        ),
    }

    def register(
        self,
        func: Callable,
        name: str | None = None,
        description: str | None = None,
        groups: Sequence[ToolGroup | str] | None = None,
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
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            return self._normalize_tool_result(result)

        normalized_contract = self._normalize_contract(contract)
        normalized_groups = self._normalize_groups(groups)
        contract_target = getattr(func, "__func__", func)
        setattr(contract_target, "__swarmmind_tool_contract__", normalized_contract)
        setattr(contract_target, "__swarmmind_tool_groups__", tuple(normalized_groups))
        setattr(async_wrapper, "__swarmmind_tool_contract__", normalized_contract)
        setattr(async_wrapper, "__swarmmind_tool_groups__", tuple(normalized_groups))
        self._funcs[tool_name] = func
        self._registered_funcs[tool_name] = async_wrapper
        self._descriptions[tool_name] = description
        self._tool_groups[tool_name] = normalized_groups
        if normalized_groups:
            self._primary_groups[tool_name] = normalized_groups[0]
        elif tool_name in self._primary_groups:
            del self._primary_groups[tool_name]
        self._contracts[tool_name] = normalized_contract
        self._rebuild_internal_toolkit()

    def ensure_group(self, group: ToolGroup | str, active: bool = False) -> ToolGroup:
        """Ensure a ToolGroup exists in the underlying toolkit."""
        normalized = group if isinstance(group, ToolGroup) else ToolGroup(group)
        if normalized.value not in self._toolkit.groups:
            description, notes = self._GROUP_DETAILS[normalized]
            self._toolkit.create_tool_group(
                normalized.value,
                description=description,
                active=active,
                notes=notes,
            )
        return normalized

    def get_tool(self, name: str) -> Any:
        """Get tool by name."""
        return self._funcs.get(name)

    def get_all_tools(self) -> list[dict[str, Any]]:
        """Get all registered tools."""
        return [self._tool_schema(name) for name in self.get_tool_names()]

    def get_tools_for_groups(
        self,
        groups: Sequence[ToolGroup | str],
        *,
        runtime_kind: RuntimeKind | None = None,
        tool_names: list[str] | None = None,
        strict_tool_names: bool = False,
    ) -> list[dict[str, Any]]:
        """Get tool schemas matching any of the provided groups."""
        return [
            self._tool_schema(name)
            for name in self._select_tool_names(
                groups=groups,
                runtime_kind=runtime_kind,
                tool_names=tool_names,
                strict_tool_names=strict_tool_names,
            )
        ]

    def get_functions_for_groups(
        self,
        groups: Sequence[ToolGroup | str],
        *,
        runtime_kind: RuntimeKind | None = None,
        tool_names: list[str] | None = None,
        strict_tool_names: bool = False,
    ) -> list[Callable]:
        """Return registered tool callables matching active groups and explicit names."""
        return [
            self._funcs[name]
            for name in self._select_tool_names(
                groups=groups,
                runtime_kind=runtime_kind,
                tool_names=tool_names,
                strict_tool_names=strict_tool_names,
            )
        ]

    def get_tool_groups(self, name: str) -> list[ToolGroup]:
        """Return the tool groups associated with a tool."""
        return self._tool_groups.get(name, [])

    def get_primary_tool_group(self, name: str) -> ToolGroup | None:
        """Return the canonical primary ToolGroup for a tool."""
        return self._primary_groups.get(name)

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
                "primary_group": self._primary_groups.get(name).value if name in self._primary_groups else None,
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
        self._toolkit = Toolkit()
        self._funcs.clear()
        self._registered_funcs.clear()
        self._tool_groups.clear()
        self._primary_groups.clear()
        self._descriptions.clear()
        self._contracts.clear()

    def _rebuild_internal_toolkit(self) -> None:
        toolkit = Toolkit()
        for group in sorted({group for groups in self._tool_groups.values() for group in groups}, key=lambda item: item.value):
            description, notes = self._GROUP_DETAILS[group]
            toolkit.create_tool_group(
                group.value,
                description=description,
                active=False,
                notes=notes,
            )

        for tool_name, func in self._registered_funcs.items():
            primary_group_name = self._primary_groups.get(tool_name, ToolGroup.WORKSPACE).value if tool_name in self._primary_groups else "basic"
            toolkit.register_tool_function(
                func,
                group_name=primary_group_name,
                func_name=tool_name,
                func_description=self._descriptions[tool_name],
            )

        self._toolkit = toolkit

    def build_toolkit(
        self,
        *,
        active_groups: Sequence[ToolGroup | str] | None = None,
        active_tool_names: list[str] | None = None,
        runtime_kind: RuntimeKind | None = None,
        strict_tool_names: bool = False,
    ) -> Toolkit:
        """Build a fresh AgentScope Toolkit with group-aware activation."""
        toolkit = Toolkit()
        normalized_active_groups = [
            group if isinstance(group, ToolGroup) else ToolGroup(group)
            for group in (active_groups or [])
        ]
        selected_names = self._select_tool_names(
            groups=normalized_active_groups,
            runtime_kind=runtime_kind,
            tool_names=active_tool_names,
            strict_tool_names=strict_tool_names,
        )

        groups_to_create = {group for group in normalized_active_groups}
        for name in selected_names:
            groups_to_create.update(self._tool_groups.get(name, []))
        for group in sorted(groups_to_create, key=lambda item: item.value):
            description, notes = self._GROUP_DETAILS[group]
            toolkit.create_tool_group(group.value, description=description, active=False, notes=notes)

        for name in selected_names:
            toolkit.register_tool_function(
                self._registered_funcs[name],
                group_name=self._primary_groups[name].value if name in self._primary_groups else "basic",
                func_name=name,
                func_description=self._descriptions[name],
            )

        if normalized_active_groups:
            toolkit.update_tool_groups([group.value for group in normalized_active_groups], active=True)
        return toolkit

    def _normalize_groups(self, groups: Sequence[ToolGroup | str] | None) -> list[ToolGroup]:
        if not groups:
            return []
        normalized: list[ToolGroup] = []
        seen: set[ToolGroup] = set()
        for group in groups:
            resolved = group if isinstance(group, ToolGroup) else ToolGroup(group)
            if resolved in seen:
                continue
            normalized.append(resolved)
            seen.add(resolved)
        return normalized

    def _select_tool_names(
        self,
        *,
        groups: Sequence[ToolGroup | str] | None,
        runtime_kind: RuntimeKind | None,
        tool_names: list[str] | None,
        strict_tool_names: bool,
    ) -> list[str]:
        normalized_groups = {
            group if isinstance(group, ToolGroup) else ToolGroup(group)
            for group in (groups or [])
        }
        explicit_names = [name for name in (tool_names or []) if name in self._funcs]

        if strict_tool_names and explicit_names:
            selected: list[str] = []
            for name in explicit_names:
                contract = self._contracts.get(name)
                if runtime_kind is not None and contract is not None and runtime_kind not in contract.allowed_runtimes:
                    continue
                selected.append(name)
            return selected

        selected: list[str] = []
        seen: set[str] = set()

        for name in self._funcs:
            contract = self._contracts.get(name)
            if runtime_kind is not None and contract is not None and runtime_kind not in contract.allowed_runtimes:
                continue
            if normalized_groups and not normalized_groups.intersection(self._tool_groups.get(name, [])) and name not in explicit_names:
                continue
            if name in seen:
                continue
            selected.append(name)
            seen.add(name)

        for name in explicit_names:
            contract = self._contracts.get(name)
            if runtime_kind is not None and contract is not None and runtime_kind not in contract.allowed_runtimes:
                continue
            if name in seen:
                continue
            selected.append(name)
            seen.add(name)

        return selected

    def _tool_schema(self, name: str) -> dict[str, Any]:
        tool = self._toolkit.tools.get(name)
        if tool is None:
            raise ValueError(f"Tool not found: {name}")
        return tool.extended_json_schema

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

    @staticmethod
    def _normalize_tool_result(result: Any) -> Any:
        if isinstance(result, ToolResponse) or inspect.isasyncgen(result) or inspect.isgenerator(result):
            return result
        return ToolResponse(content=[{"type": "text", "text": ToolRegistry._stringify_tool_result(result)}])

    @staticmethod
    def _stringify_tool_result(result: Any) -> str:
        if isinstance(result, str):
            return result
        if result is None or isinstance(result, (dict, list, tuple, bool, int, float)):
            return json.dumps(result, ensure_ascii=False, indent=2)
        return str(result)

    @property
    def toolkit(self) -> Toolkit:
        """Get the underlying AgentScope toolkit."""
        return self._toolkit
