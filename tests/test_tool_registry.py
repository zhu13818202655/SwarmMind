from __future__ import annotations

from swarmmind.models.capability import RuntimeKind, ToolExecutionContract, ToolGroup
from swarmmind.tools import ToolRegistry, register_builtin_tools


async def grouped_file_reader(path: str) -> str:
    return path


setattr(
    grouped_file_reader,
    "__swarmmind_tool_contract__",
    ToolExecutionContract(
        default_runtime=RuntimeKind.HOST_TOOLS,
        allowed_runtimes=[RuntimeKind.HOST_TOOLS],
        read_only=True,
    ),
)
setattr(grouped_file_reader, "__swarmmind_tool_groups__", (ToolGroup.FILE_SYSTEM, ToolGroup.WORKSPACE))


def test_registry_tracks_formal_tool_groups_and_primary_group() -> None:
    registry = ToolRegistry()
    registry.register(
        grouped_file_reader,
        name="grouped_file_reader",
        groups=[ToolGroup.FILE_SYSTEM, ToolGroup.WORKSPACE],
        contract=getattr(grouped_file_reader, "__swarmmind_tool_contract__"),
    )

    metadata = next(item for item in registry.get_tool_metadata() if item["name"] == "grouped_file_reader")

    assert metadata["groups"] == [ToolGroup.FILE_SYSTEM.value, ToolGroup.WORKSPACE.value]
    assert metadata["primary_group"] == ToolGroup.FILE_SYSTEM.value
    assert registry.get_primary_tool_group("grouped_file_reader") == ToolGroup.FILE_SYSTEM


def test_registry_build_toolkit_only_exposes_active_groups() -> None:
    registry = ToolRegistry()
    register_builtin_tools(registry)
    registry.register(
        grouped_file_reader,
        name="grouped_file_reader",
        groups=[ToolGroup.FILE_SYSTEM],
        contract=getattr(grouped_file_reader, "__swarmmind_tool_contract__"),
    )

    toolkit = registry.build_toolkit(active_groups=[ToolGroup.FILE_SYSTEM])
    exposed = {schema["function"]["name"] for schema in toolkit.get_json_schemas()}

    assert "read_file" in exposed
    assert "grouped_file_reader" in exposed
    assert "web_search" not in exposed


def test_registry_strict_tool_name_selection_overrides_group_expansion() -> None:
    registry = ToolRegistry()
    register_builtin_tools(registry)

    toolkit = registry.build_toolkit(
        active_groups=[ToolGroup.FILE_SYSTEM],
        active_tool_names=["read_file"],
        strict_tool_names=True,
    )
    exposed = {schema["function"]["name"] for schema in toolkit.get_json_schemas()}

    assert exposed == {"read_file"}