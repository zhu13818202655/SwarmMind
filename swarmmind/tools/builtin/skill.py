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
        skill_name: str | None = None,
        script_path: str | None = None,
        sandbox_profile: str = DEFAULT_SANDBOX_PROFILE,
        sandbox_root: str = "/workspace/skill",
        allow_sandbox_exec: bool = False,
        environment: dict[str, str] | None = None,
        artifact_paths: list[str] | None = None,
        script_args: list[str] | None = None,
        skill: str | None = None,
        script: str | None = None,
        args: dict[str, object] | None = None,
        tenant_id: str = "system",
        session_id: str | None = None,
        task_id: str | None = None,
        run_id: str | None = None,
        subtask_id: str | None = None,
    ) -> dict[str, object]:
        """Execute a declared skill script through the formal skill service."""
        resolved_skill_name = skill_name or skill
        resolved_script_path = script_path or script
        resolved_environment = dict(environment or {})
        resolved_artifact_paths = list(artifact_paths or [])
        resolved_script_args = [str(item) for item in (script_args or [])]
        if args:
            if resolved_skill_name is None and isinstance(args.get("skill_name"), str):
                resolved_skill_name = str(args["skill_name"])
            if resolved_script_path is None and isinstance(args.get("script_path"), str):
                resolved_script_path = str(args["script_path"])
            if isinstance(args.get("sandbox_profile"), str):
                sandbox_profile = str(args["sandbox_profile"])
            if isinstance(args.get("sandbox_root"), str):
                sandbox_root = str(args["sandbox_root"])
            if isinstance(args.get("allow_sandbox_exec"), bool):
                allow_sandbox_exec = bool(args["allow_sandbox_exec"])
            environment_arg = args.get("environment")
            if isinstance(environment_arg, dict):
                resolved_environment.update({str(key): str(value) for key, value in environment_arg.items()})
            artifact_paths_arg = args.get("artifact_paths")
            if isinstance(artifact_paths_arg, list):
                resolved_artifact_paths = [str(item) for item in artifact_paths_arg]
            script_args_arg = args.get("script_args")
            if isinstance(script_args_arg, list):
                resolved_script_args = [str(item) for item in script_args_arg]
        if not resolved_skill_name or not resolved_script_path:
            raise ValueError("run_skill_script requires skill_name/script_path or skill/script aliases")
        result = await self._service.run_skill_script(
            skill_name=resolved_skill_name,
            script_path=resolved_script_path,
            policy=SkillScriptExecutionPolicy(
                allow_sandbox_exec=allow_sandbox_exec,
                sandbox_profile=sandbox_profile,
                sandbox_root=sandbox_root,
                environment=resolved_environment,
                artifact_paths=resolved_artifact_paths,
                script_args=resolved_script_args,
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
    skill_name: str | None = None,
    script_path: str | None = None,
    sandbox_profile: str = DEFAULT_SANDBOX_PROFILE,
    sandbox_root: str = "/workspace/skill",
    allow_sandbox_exec: bool = False,
    environment: dict[str, str] | None = None,
    artifact_paths: list[str] | None = None,
    script_args: list[str] | None = None,
    skill: str | None = None,
    script: str | None = None,
    args: dict[str, object] | None = None,
    tenant_id: str = "system",
    session_id: str | None = None,
    task_id: str | None = None,
    run_id: str | None = None,
    subtask_id: str | None = None,
) -> dict[str, object]:
    """Execute a declared skill script through the formal skill service."""
    raise RuntimeError("Skill tool not initialized")