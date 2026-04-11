"""Built-in tools backed by the skill execution service."""

from __future__ import annotations

from swarmmind.defaults import DEFAULT_SANDBOX_PROFILE
from swarmmind.skill_system import SkillExecutionContext, SkillExecutionService, SkillScriptExecutionPolicy


class SkillTool:
    """Tool wrapper around the skill execution service."""

    def __init__(self, service: SkillExecutionService) -> None:
        self._service = service

    async def list_skill_scripts(self, skill_name: str) -> list[str]:
        """List declared scripts for a skill package."""
        return self._service.list_skill_scripts(skill_name)

    async def get_skill_details(self, skill_name: str) -> dict[str, object]:
        """Return expanded metadata and resources for a skill package."""
        return self._service.get_skill_details(skill_name)

    async def run_skill_script(
        self,
        skill_name: str,
        script_path: str,
        sandbox_profile: str = DEFAULT_SANDBOX_PROFILE,
        sandbox_root: str = "/workspace/skill",
        allow_sandbox_exec: bool = False,
        environment: dict[str, str] | None = None,
        artifact_paths: list[str] | None = None,
        tenant_id: str = "system",
        session_id: str | None = None,
        task_id: str | None = None,
        run_id: str | None = None,
        subtask_id: str | None = None,
    ) -> dict[str, object]:
        """Execute a declared skill script through the formal skill service."""
        result = await self._service.run_skill_script(
            skill_name=skill_name,
            script_path=script_path,
            policy=SkillScriptExecutionPolicy(
                allow_sandbox_exec=allow_sandbox_exec,
                sandbox_profile=sandbox_profile,
                sandbox_root=sandbox_root,
                environment=environment or {},
                artifact_paths=artifact_paths or [],
            ),
            context=SkillExecutionContext(
                tenant_id=tenant_id,
                session_id=session_id,
                task_id=task_id,
                run_id=run_id,
                subtask_id=subtask_id,
            ),
        )
        return result.model_dump(mode="json")


async def list_skill_scripts(skill_name: str) -> list[str]:
    """List declared scripts for a skill package."""
    raise RuntimeError("Skill tool not initialized")


async def get_skill_details(skill_name: str) -> dict[str, object]:
    """Return expanded metadata and resources for a skill package."""
    raise RuntimeError("Skill tool not initialized")


async def run_skill_script(
    skill_name: str,
    script_path: str,
    sandbox_profile: str = DEFAULT_SANDBOX_PROFILE,
    sandbox_root: str = "/workspace/skill",
    allow_sandbox_exec: bool = False,
    environment: dict[str, str] | None = None,
    artifact_paths: list[str] | None = None,
    tenant_id: str = "system",
    session_id: str | None = None,
    task_id: str | None = None,
    run_id: str | None = None,
    subtask_id: str | None = None,
) -> dict[str, object]:
    """Execute a declared skill script through the formal skill service."""
    raise RuntimeError("Skill tool not initialized")