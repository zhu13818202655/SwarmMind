"""Bash tool for executing commands in sandbox."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from swarmmind.sandbox.manager import SandboxManager


class BashTool:
    """Tool for executing bash commands in sandbox."""

    def __init__(self, sandbox_manager: "SandboxManager"):
        self._sandbox = sandbox_manager

    async def execute(
        self,
        command: str,
        sandbox_id: str | None = None,
        cwd: str = "/tmp",
    ) -> str:
        """Execute a bash command.

        Args:
            command: The command to execute
            sandbox_id: Existing sandbox ID (optional)
            cwd: Working directory

        Returns:
            Command output (stdout/stderr)
        """
        if sandbox_id:
            result = await self._sandbox.run_command(sandbox_id, command, cwd)
        else:
            # Create temporary sandbox
            handle = await self._sandbox.create("py-basic")
            try:
                result = await self._sandbox.run_command(handle.sandbox_id, command, cwd)
            finally:
                await self._sandbox.destroy(handle.sandbox_id)

        if result.exit_code != 0:
            return f"Error (exit {result.exit_code}):\n{result.stderr}\n{result.stdout}"

        return result.stdout or result.stderr or "Command executed successfully"


# Tool function for AgentScope
async def bash(
    command: str,
    sandbox_id: str | None = None,
    cwd: str = "/tmp",
) -> str:
    """Execute a bash command in sandbox.

    Args:
        command: The command to execute
        sandbox_id: Existing sandbox ID (optional)
        cwd: Working directory in sandbox

    Returns:
        Command output
    """
    # This will be injected by the tool registry with sandbox manager
    return "Bash tool not initialized"
