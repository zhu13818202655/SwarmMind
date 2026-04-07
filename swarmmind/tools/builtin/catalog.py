"""Canonical builtin tool registration for SwarmMind."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from swarmmind.models.capability import RuntimeKind, ToolExecutionContract, ToolGroup
from swarmmind.tools.builtin.browser import browser_get, browser_screenshot
from swarmmind.tools.builtin.file import (
    delete_file,
    file_exists,
    list_files,
    make_directory,
    read_file,
    rename_file,
    write_file,
)
from swarmmind.tools.builtin.mail import send_mail
from swarmmind.tools.builtin.search import search
from swarmmind.tools.builtin.skill import SkillTool
from swarmmind.tools.builtin.workspace import glob_search, grep_search

if TYPE_CHECKING:
    from swarmmind.skill_system import SkillExecutionService
    from swarmmind.tools.registry import ToolRegistry


def register_builtin_tools(
    registry: "ToolRegistry",
    *,
    skill_execution_service: "SkillExecutionService | None" = None,
) -> None:
    """Register canonical builtin tools grouped by ToolGroup."""
    existing = set(registry.get_tool_names())

    def register(
        func: Any,
        *,
        name: str,
        description: str,
        groups: list[ToolGroup],
        contract: ToolExecutionContract,
    ) -> None:
        if name in existing:
            return
        registry.register(
            func,
            name=name,
            description=description,
            groups=groups,
            contract=contract,
        )

    host_read_only = ToolExecutionContract(
        default_runtime=RuntimeKind.HOST_TOOLS,
        allowed_runtimes=[RuntimeKind.HOST_TOOLS],
        read_only=True,
    )
    host_mutating = ToolExecutionContract(
        default_runtime=RuntimeKind.HOST_TOOLS,
        allowed_runtimes=[RuntimeKind.HOST_TOOLS, RuntimeKind.SANDBOX],
        audit_required=True,
    )

    register(
        read_file,
        name="read_file",
        description="Read a file from the workspace.",
        groups=[ToolGroup.FILE_SYSTEM],
        contract=host_read_only,
    )
    register(
        write_file,
        name="write_file",
        description="Write a file in the workspace.",
        groups=[ToolGroup.FILE_SYSTEM],
        contract=host_mutating,
    )
    register(
        list_files,
        name="list_files",
        description="List files in a workspace directory.",
        groups=[ToolGroup.FILE_SYSTEM],
        contract=host_read_only,
    )
    register(
        file_exists,
        name="file_exists",
        description="Check whether a workspace path exists.",
        groups=[ToolGroup.FILE_SYSTEM],
        contract=host_read_only,
    )
    register(
        delete_file,
        name="delete_file",
        description="Delete a file or directory in the workspace.",
        groups=[ToolGroup.FILE_SYSTEM],
        contract=host_mutating,
    )
    register(
        rename_file,
        name="rename_file",
        description="Rename or move a file or directory in the workspace.",
        groups=[ToolGroup.FILE_SYSTEM],
        contract=host_mutating,
    )
    register(
        make_directory,
        name="make_directory",
        description="Create a directory recursively in the workspace.",
        groups=[ToolGroup.FILE_SYSTEM],
        contract=host_mutating,
    )
    register(
        glob_search,
        name="glob_search",
        description="Find workspace files matching a glob pattern.",
        groups=[ToolGroup.WORKSPACE],
        contract=host_read_only,
    )
    register(
        grep_search,
        name="grep_search",
        description="Search text content inside workspace files.",
        groups=[ToolGroup.WORKSPACE],
        contract=host_read_only,
    )
    register(
        search,
        name="web_search",
        description="Search the public web for information.",
        groups=[ToolGroup.WEB_SEARCH],
        contract=ToolExecutionContract(
            default_runtime=RuntimeKind.HOST_TOOLS,
            allowed_runtimes=[RuntimeKind.HOST_TOOLS],
            read_only=True,
            expensive=True,
        ),
    )
    register(
        browser_get,
        name="browser_get",
        description="Fetch and extract text content from a web page.",
        groups=[ToolGroup.BROWSER],
        contract=ToolExecutionContract(
            default_runtime=RuntimeKind.HOST_TOOLS,
            allowed_runtimes=[RuntimeKind.HOST_TOOLS],
            read_only=True,
            expensive=True,
        ),
    )
    register(
        browser_screenshot,
        name="browser_screenshot",
        description="Capture a screenshot placeholder for a web page.",
        groups=[ToolGroup.BROWSER],
        contract=ToolExecutionContract(
            default_runtime=RuntimeKind.HOST_TOOLS,
            allowed_runtimes=[RuntimeKind.HOST_TOOLS],
            read_only=True,
            expensive=True,
        ),
    )
    register(
        send_mail,
        name="send_mail",
        description="Send an email using configured SMTP credentials.",
        groups=[ToolGroup.COMMUNICATION],
        contract=ToolExecutionContract(
            default_runtime=RuntimeKind.HOST_TOOLS,
            allowed_runtimes=[RuntimeKind.HOST_TOOLS],
            audit_required=True,
            dangerous=True,
        ),
    )

    if skill_execution_service is not None:
        skill_tool = SkillTool(skill_execution_service)
        register(
            skill_tool.list_skill_scripts,
            name="list_skill_scripts",
            description="List declared scripts for a skill package.",
            groups=[ToolGroup.WORKSPACE],
            contract=host_read_only,
        )
        register(
            skill_tool.get_skill_details,
            name="get_skill_details",
            description="Inspect expanded metadata and resources for a skill package.",
            groups=[ToolGroup.WORKSPACE],
            contract=host_read_only,
        )
        register(
            skill_tool.run_skill_script,
            name="run_skill_script",
            description="Execute a declared skill script inside a sandbox with audit context.",
            groups=[ToolGroup.CODE_EXEC],
            contract=ToolExecutionContract(
                default_runtime=RuntimeKind.SANDBOX,
                allowed_runtimes=[RuntimeKind.SANDBOX],
                audit_required=True,
                dangerous=True,
                expensive=True,
                sandbox_only=True,
            ),
        )