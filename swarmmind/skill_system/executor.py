"""Safe execution helpers for skill package scripts."""

from __future__ import annotations

import mimetypes
import os
from pathlib import Path
import shlex
import shutil

from swarmmind.sandbox.manager import SandboxManager
from swarmmind.sandbox.provider import WriteFileEntry
from swarmmind.skill_system.models import SkillEntry, SkillScriptExecutionPolicy, SkillScriptExecutionResult
from swarmmind.skill_system.resources import collect_skill_files


class SkillScriptExecutor:
    """Execute declared skill scripts inside a sandbox-managed environment."""

    def __init__(self, sandbox_manager: SandboxManager) -> None:
        self._sandbox_manager = sandbox_manager

    async def execute(
        self,
        entry: SkillEntry,
        script_path: str,
        policy: SkillScriptExecutionPolicy,
    ) -> SkillScriptExecutionResult:
        """Execute a declared script from a skill package inside a sandbox."""
        self._validate_execution_request(entry, script_path, policy)

        sandbox_root = policy.sandbox_root.rstrip("/") or "/workspace/skill"
        sandbox_skill_root = f"{sandbox_root}/{entry.name}"
        handle = await self._sandbox_manager.create(
            policy.sandbox_profile,
            metadata={"skill_name": entry.name, "script_path": script_path},
        )

        try:
            await self._sandbox_manager.write_files(
                handle.sandbox_id,
                self._build_write_entries(entry, sandbox_skill_root),
            )

            command = self._build_command(
                script_path,
                policy.environment,
                policy.artifact_paths,
                policy.script_args,
            )
            exec_result = await self._sandbox_manager.run_command(
                handle.sandbox_id,
                command,
                cwd=sandbox_skill_root,
            )

            artifacts, artifact_payloads = await self._collect_artifacts(
                handle.sandbox_id,
                sandbox_skill_root,
                policy.artifact_paths,
            )

            return SkillScriptExecutionResult(
                skill_name=entry.name,
                script_path=script_path,
                sandbox_id=handle.sandbox_id,
                command=command,
                cwd=sandbox_skill_root,
                exit_code=exec_result.exit_code,
                stdout=exec_result.stdout,
                stderr=exec_result.stderr,
                artifacts=artifacts,
                artifact_payloads=artifact_payloads,
            )
        finally:
            await self._sandbox_manager.destroy(handle.sandbox_id)

    def _validate_execution_request(
        self,
        entry: SkillEntry,
        script_path: str,
        policy: SkillScriptExecutionPolicy,
    ) -> None:
        if not policy.allow_sandbox_exec:
            raise ValueError("Skill script execution requires allow_sandbox_exec=True")

        if not entry.valid or entry.metadata.disabled:
            raise ValueError(f"Skill '{entry.name}' is not executable")

        normalized_script = script_path.strip().lstrip("/")
        if normalized_script not in entry.resources.scripts:
            raise ValueError(f"Script is not declared under scripts/: {script_path}")

        for env_name in entry.metadata.required_env:
            if env_name not in policy.environment and not os.environ.get(env_name):
                raise ValueError(f"Missing required environment variable for skill script: {env_name}")

        for binary_name in entry.metadata.required_bins:
            if shutil.which(binary_name) is None:
                raise ValueError(f"Required binary is not available for skill script: {binary_name}")

    def _build_write_entries(self, entry: SkillEntry, sandbox_skill_root: str) -> list[WriteFileEntry]:
        return [
            WriteFileEntry(path=f"{sandbox_skill_root}/{relative_path}", data=content)
            for relative_path, content in collect_skill_files(entry.root_dir)
        ]

    def _build_command(
        self,
        script_path: str,
        environment: dict[str, str],
        artifact_paths: list[str],
        script_args: list[str],
    ) -> str:
        normalized_script = script_path.strip().lstrip("/")
        env_prefix = "; ".join(
            f"export {key}={shlex.quote(value)}"
            for key, value in sorted(environment.items())
        )

        command = self._build_script_invocation(normalized_script, script_args)
        artifact_dir_preamble = self._build_artifact_dir_preamble(artifact_paths)
        if artifact_dir_preamble:
            command = f"{artifact_dir_preamble} && {command}"
        if env_prefix:
            return f"{env_prefix}; {command}"
        return command

    def _build_artifact_dir_preamble(self, artifact_paths: list[str]) -> str:
        directories = sorted(
            {
                Path(path.strip().lstrip("/")).parent.as_posix()
                for path in artifact_paths
                if Path(path.strip().lstrip("/")).parent.as_posix() not in {"", "."}
            }
        )
        if not directories:
            return ""
        quoted_dirs = " ".join(shlex.quote(directory) for directory in directories)
        return f"mkdir -p {quoted_dirs}"

    def _build_script_invocation(self, normalized_script: str, script_args: list[str]) -> str:
        quoted_script = shlex.quote(normalized_script)
        quoted_args = " ".join(shlex.quote(arg) for arg in script_args)
        arg_suffix = f" {quoted_args}" if quoted_args else ""
        extension = Path(normalized_script).suffix.lower()
        if extension == ".py":
            return f"python3 {quoted_script}{arg_suffix}"
        if extension == ".sh":
            return f"sh {quoted_script}{arg_suffix}"
        return f"./{quoted_script}{arg_suffix}"

    async def _collect_artifacts(
        self,
        sandbox_id: str,
        sandbox_skill_root: str,
        artifact_paths: list[str],
    ) -> tuple[dict[str, str], dict[str, bytes]]:
        artifacts: dict[str, str] = {}
        artifact_payloads: dict[str, bytes] = {}
        for artifact_path in artifact_paths:
            normalized_path = artifact_path.strip().lstrip("/")
            encoding = "utf-8" if self._should_read_as_text(normalized_path) else None
            try:
                content = await self._sandbox_manager.read_file(
                    sandbox_id,
                    f"{sandbox_skill_root}/{normalized_path}",
                    encoding=encoding,
                )
            except Exception:
                continue
            if isinstance(content, bytes):
                artifact_payloads[normalized_path] = content
                artifacts[normalized_path] = self._build_artifact_preview(normalized_path, content)
                continue

            if isinstance(content, bytearray):
                payload = bytes(content)
                artifact_payloads[normalized_path] = payload
                artifacts[normalized_path] = self._build_artifact_preview(normalized_path, payload)
                continue

            if isinstance(content, memoryview):
                payload = content.tobytes()
                artifact_payloads[normalized_path] = payload
                artifacts[normalized_path] = self._build_artifact_preview(normalized_path, payload)
                continue

            artifact_payloads[normalized_path] = content.encode("utf-8")
            artifacts[normalized_path] = content
        return artifacts, artifact_payloads

    def _build_artifact_preview(self, artifact_path: str, content: bytes) -> str:
        content_type, _ = mimetypes.guess_type(artifact_path)
        if content_type and content_type.startswith("text/"):
            return content.decode("utf-8", errors="replace")
        if Path(artifact_path).suffix.lower() in {".md", ".txt", ".json", ".csv", ".py", ".sh", ".yaml", ".yml", ".xml", ".html"}:
            return content.decode("utf-8", errors="replace")
        return f"[binary file: {artifact_path}]"

    def _should_read_as_text(self, artifact_path: str) -> bool:
        content_type, _ = mimetypes.guess_type(artifact_path)
        if content_type and content_type.startswith("text/"):
            return True
        return Path(artifact_path).suffix.lower() in {
            ".md",
            ".txt",
            ".json",
            ".csv",
            ".py",
            ".sh",
            ".yaml",
            ".yml",
            ".xml",
            ".html",
        }