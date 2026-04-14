"""Safe execution helpers for skill package scripts."""

from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
import os
from pathlib import Path
import shlex
import shutil
from typing import Any

from swarmmind.defaults import DEFAULT_SKILL_NPM_REGISTRY_URL, DEFAULT_SKILL_PIP_INDEX_URL
from swarmmind.sandbox.manager import SandboxManager
from swarmmind.sandbox.provider import WriteFileEntry
from swarmmind.skill_system.models import (
    SkillEntry,
    SkillRuntimeRequirements,
    SkillScriptExecutionPolicy,
    SkillScriptExecutionResult,
    SkillScriptSpec,
)
from swarmmind.skill_system.resources import collect_skill_files


logger = logging.getLogger(__name__)


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
        normalized_script = script_path.strip().lstrip("/")
        script_spec = self._resolve_script_spec(entry, normalized_script)
        effective_policy, applied_defaults = self._resolve_execution_policy(policy, script_spec)
        self._validate_execution_request(entry, normalized_script, effective_policy)

        sandbox_root = effective_policy.sandbox_root.rstrip("/") or "/workspace/skill"
        sandbox_skill_root = f"{sandbox_root}/{entry.name}"
        handle = await self._sandbox_manager.create(
            effective_policy.sandbox_profile,
            metadata={"skill_name": entry.name, "script_path": script_path},
        )

        try:
            await self._sandbox_manager.write_files(
                handle.sandbox_id,
                self._build_write_entries(entry, sandbox_skill_root),
            )

            command = self._build_command(
                entry.metadata.runtime_requirements,
                script_spec,
                normalized_script,
                effective_policy.environment,
                effective_policy.artifact_paths,
                effective_policy.script_args,
            )
            exec_result = await self._sandbox_manager.run_command(
                handle.sandbox_id,
                command,
                cwd=sandbox_skill_root,
            )

            artifacts, artifact_payloads = await self._collect_artifacts(
                handle.sandbox_id,
                sandbox_skill_root,
                effective_policy.artifact_paths,
            )

            await self._debug_hold_before_cleanup(
                sandbox_id=handle.sandbox_id,
                sandbox_skill_root=sandbox_skill_root,
                expected_artifact_paths=effective_policy.artifact_paths,
                collected_artifact_paths=list(artifacts.keys()),
                command=command,
                exit_code=exec_result.exit_code,
            )

            return SkillScriptExecutionResult(
                skill_name=entry.name,
                script_path=normalized_script,
                sandbox_id=handle.sandbox_id,
                command=command,
                cwd=sandbox_skill_root,
                exit_code=exec_result.exit_code,
                stdout=exec_result.stdout,
                stderr=exec_result.stderr,
                resolved_artifact_paths=list(effective_policy.artifact_paths),
                applied_defaults=applied_defaults,
                artifacts=artifacts,
                artifact_payloads=artifact_payloads,
            )
        finally:
            await self._sandbox_manager.destroy(handle.sandbox_id)

    async def _debug_hold_before_cleanup(
        self,
        *,
        sandbox_id: str,
        sandbox_skill_root: str,
        expected_artifact_paths: list[str],
        collected_artifact_paths: list[str],
        command: str,
        exit_code: int,
    ) -> None:
        missing_artifact_paths = [
            artifact_path
            for artifact_path in expected_artifact_paths
            if artifact_path not in collected_artifact_paths
        ]
        if not self._should_hold_debug_sandbox(missing_artifact_paths):
            return

        release_file = self._build_debug_release_file_path(sandbox_id)
        timeout_seconds = self._get_debug_hold_timeout_seconds()
        logger.warning(
            "Holding skill sandbox before cleanup for inspection",
            extra={
                "sandbox_id": sandbox_id,
                "sandbox_skill_root": sandbox_skill_root,
                "expected_artifact_paths": list(expected_artifact_paths),
                "collected_artifact_paths": list(collected_artifact_paths),
                "missing_artifact_paths": missing_artifact_paths,
                "release_file": str(release_file),
                "timeout_seconds": timeout_seconds,
                "command": command,
                "exit_code": exit_code,
            },
        )
        await self._wait_for_debug_release(release_file, timeout_seconds)
        logger.warning(
            "Resuming skill sandbox cleanup",
            extra={
                "sandbox_id": sandbox_id,
                "release_file": str(release_file),
            },
        )

    def _should_hold_debug_sandbox(self, missing_artifact_paths: list[str]) -> bool:
        if self._read_debug_flag("SWARMMIND_DEBUG_HOLD_SANDBOX"):
            return True
        return bool(missing_artifact_paths) and self._read_debug_flag("SWARMMIND_DEBUG_HOLD_ON_MISSING_ARTIFACTS")

    @staticmethod
    def _read_debug_flag(env_name: str) -> bool:
        value = os.environ.get(env_name, "").strip().lower()
        return value in {"1", "true", "yes", "on"}

    @staticmethod
    def _get_debug_hold_timeout_seconds() -> int:
        raw_value = os.environ.get("SWARMMIND_DEBUG_HOLD_TIMEOUT_SECONDS", "900").strip()
        try:
            return max(0, int(raw_value))
        except ValueError:
            return 900

    @staticmethod
    def _build_debug_release_file_path(sandbox_id: str) -> Path:
        configured_dir = os.environ.get("SWARMMIND_DEBUG_RELEASE_DIR", "").strip()
        release_dir = Path(configured_dir) if configured_dir else Path.cwd() / ".swarmmind-debug"
        release_dir.mkdir(parents=True, exist_ok=True)
        return release_dir / f"release-{sandbox_id}"

    async def _wait_for_debug_release(self, release_file: Path, timeout_seconds: int) -> None:
        loop = asyncio.get_running_loop()
        deadline = None if timeout_seconds == 0 else loop.time() + timeout_seconds

        while True:
            if release_file.exists():
                return
            if deadline is not None and loop.time() >= deadline:
                logger.warning(
                    "Timed out waiting to resume skill sandbox cleanup",
                    extra={
                        "release_file": str(release_file),
                        "timeout_seconds": timeout_seconds,
                    },
                )
                return
            await asyncio.sleep(1)

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

    def _resolve_script_spec(self, entry: SkillEntry, script_path: str) -> SkillScriptSpec | None:
        normalized_script = script_path.strip().lstrip("/")
        for script_spec in entry.metadata.script_specs:
            if script_spec.path.strip().lstrip("/") == normalized_script:
                return script_spec
        return None

    def _resolve_execution_policy(
        self,
        policy: SkillScriptExecutionPolicy,
        script_spec: SkillScriptSpec | None,
    ) -> tuple[SkillScriptExecutionPolicy, dict[str, object]]:
        if script_spec is None:
            return policy, {}

        applied_defaults: dict[str, object] = {}
        resolved_environment = dict(script_spec.environment)
        resolved_environment.update(policy.environment)
        resolved_script_args = [str(item) for item in policy.script_args]
        if not resolved_script_args and policy.script_input:
            resolved_script_args = self._script_input_to_args(policy.script_input, script_spec)
            applied_defaults["script_args"] = list(resolved_script_args)
            applied_defaults["script_input"] = dict(policy.script_input)
        resolved_artifact_paths = self._resolve_artifact_paths(policy, script_spec, resolved_script_args)
        if resolved_artifact_paths and not policy.artifact_paths and script_spec.artifacts:
            applied_defaults["artifact_paths"] = list(resolved_artifact_paths)

        return (
            policy.model_copy(
                update={
                    "environment": resolved_environment,
                    "artifact_paths": resolved_artifact_paths,
                    "script_args": resolved_script_args,
                }
            ),
            applied_defaults,
        )

    def _resolve_artifact_paths(
        self,
        policy: SkillScriptExecutionPolicy,
        script_spec: SkillScriptSpec | None,
        resolved_script_args: list[str],
    ) -> list[str]:
        if policy.artifact_paths:
            return [str(path) for path in policy.artifact_paths]
        if script_spec is None or not script_spec.artifacts:
            return []

        template_values = dict(policy.script_input)
        argument_names = list(script_spec.argument_names or self._infer_argument_names(script_spec))
        for index, argument_name in enumerate(argument_names):
            if not argument_name or argument_name in template_values or index >= len(resolved_script_args):
                continue
            template_values[argument_name] = resolved_script_args[index]

        return [
            self._expand_artifact_path_template(path, template_values)
            for path in script_spec.artifacts
        ]

    @staticmethod
    def _expand_artifact_path_template(path: str, template_values: dict[str, Any]) -> str:
        template = str(path)
        if not template_values:
            return template
        try:
            return template.format(**template_values)
        except (IndexError, KeyError, ValueError):
            return template

    def _script_input_to_args(self, script_input: dict[str, Any], script_spec: SkillScriptSpec) -> list[str]:
        argument_names = list(script_spec.argument_names or self._infer_argument_names(script_spec))
        if not argument_names:
            raise ValueError(
                f"Script spec for {script_spec.path} does not define argument_names or ordered args_schema properties for structured input"
            )
        missing = [name for name in argument_names if name not in script_input]
        if missing:
            raise ValueError(
                f"Missing required script_input keys for {script_spec.path}: {', '.join(missing)}"
            )
        return [self._stringify_script_input_value(script_input[name]) for name in argument_names]

    def _infer_argument_names(self, script_spec: SkillScriptSpec) -> list[str]:
        schema_properties = script_spec.args_schema.get("properties")
        if isinstance(schema_properties, dict) and schema_properties:
            return [str(name) for name in schema_properties.keys()]
        required = script_spec.args_schema.get("required")
        if isinstance(required, list):
            return [str(name) for name in required if str(name).strip()]
        return []

    def _stringify_script_input_value(self, value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return str(value)

    def _build_write_entries(self, entry: SkillEntry, sandbox_skill_root: str) -> list[WriteFileEntry]:
        return [
            WriteFileEntry(path=f"{sandbox_skill_root}/{relative_path}", data=content)
            for relative_path, content in collect_skill_files(entry.root_dir)
        ]

    def _build_command(
        self,
        runtime_requirements: SkillRuntimeRequirements,
        script_spec: SkillScriptSpec | None,
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

        command = self._build_script_invocation(script_spec, normalized_script, script_args)
        install_preambles = self._build_runtime_requirement_preambles(runtime_requirements)
        artifact_dir_preamble = self._build_artifact_dir_preamble(artifact_paths)
        preambles = [*install_preambles, *([artifact_dir_preamble] if artifact_dir_preamble else [])]
        if preambles:
            command = f"{' && '.join(preambles)} && {command}"
        if env_prefix:
            return f"{env_prefix}; {command}"
        return command

    def _build_runtime_requirement_preambles(
        self,
        runtime_requirements: SkillRuntimeRequirements,
    ) -> list[str]:
        preambles = [
            *[command.strip() for command in runtime_requirements.bootstrap_commands if command.strip()],
        ]
        system_preamble = self._build_system_dependency_preamble(runtime_requirements.system_packages)
        if system_preamble:
            preambles.append(system_preamble)
        python_preamble = self._build_python_dependency_preamble(runtime_requirements)
        if python_preamble:
            preambles.append(python_preamble)
        node_preamble = self._build_node_dependency_preamble(runtime_requirements)
        if node_preamble:
            preambles.append(node_preamble)
        return preambles

    def _build_python_dependency_preamble(self, runtime_requirements: SkillRuntimeRequirements) -> str:
        packages = [package.strip() for package in runtime_requirements.python_packages if package.strip()]
        if not packages:
            return ""
        index_url = self._resolve_python_package_index_url(runtime_requirements)
        quoted_packages = " ".join(shlex.quote(package) for package in packages)
        if index_url:
            return (
                "python3 -m pip install --disable-pip-version-check "
                f"-i {shlex.quote(index_url)} {quoted_packages}"
            )
        return f"python3 -m pip install --disable-pip-version-check {quoted_packages}"

    def _build_node_dependency_preamble(self, runtime_requirements: SkillRuntimeRequirements) -> str:
        packages = [package.strip() for package in runtime_requirements.node_packages if package.strip()]
        if not packages:
            return ""
        registry_url = self._resolve_node_registry_url(runtime_requirements)
        quoted_packages = " ".join(shlex.quote(package) for package in packages)
        registry_suffix = f" --registry={shlex.quote(registry_url)}" if registry_url else ""
        return f"npm install --no-save{registry_suffix} {quoted_packages}"

    def _build_system_dependency_preamble(self, system_packages: list[str]) -> str:
        packages = [package.strip() for package in system_packages if package.strip()]
        if not packages:
            return ""
        quoted_packages = " ".join(shlex.quote(package) for package in packages)
        return (
            "apt-get update && "
            f"DEBIAN_FRONTEND=noninteractive apt-get install -y {quoted_packages}"
        )

    def _resolve_python_package_index_url(self, runtime_requirements: SkillRuntimeRequirements) -> str:
        if runtime_requirements.python_index_url and runtime_requirements.python_index_url.strip():
            return runtime_requirements.python_index_url.strip()
        for env_name in ("SWARMMIND_SKILL_PIP_INDEX_URL", "PIP_INDEX_URL"):
            value = os.environ.get(env_name, "").strip()
            if value:
                return value
        return DEFAULT_SKILL_PIP_INDEX_URL

    def _resolve_node_registry_url(self, runtime_requirements: SkillRuntimeRequirements) -> str:
        if runtime_requirements.node_registry_url and runtime_requirements.node_registry_url.strip():
            return runtime_requirements.node_registry_url.strip()
        for env_name in ("SWARMMIND_SKILL_NPM_REGISTRY_URL", "NPM_CONFIG_REGISTRY"):
            value = os.environ.get(env_name, "").strip()
            if value:
                return value
        return DEFAULT_SKILL_NPM_REGISTRY_URL

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

    def _build_script_invocation(
        self,
        script_spec: SkillScriptSpec | None,
        normalized_script: str,
        script_args: list[str],
    ) -> str:
        quoted_script = shlex.quote(normalized_script)
        quoted_args = " ".join(shlex.quote(arg) for arg in script_args)
        arg_suffix = f" {quoted_args}" if quoted_args else ""
        runtime = (script_spec.runtime or "").strip().lower() if script_spec is not None and script_spec.runtime else ""
        if runtime in {"python", "py"}:
            return f"python3 {quoted_script}{arg_suffix}"
        if runtime in {"node", "javascript", "js", "typescript", "ts"}:
            return f"node {quoted_script}{arg_suffix}"
        if runtime in {"shell", "sh", "bash"}:
            return f"sh {quoted_script}{arg_suffix}"
        if runtime in {"executable", "binary"}:
            return f"./{quoted_script}{arg_suffix}"
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
            normalized_path = artifact_path.strip()
            if not normalized_path:
                continue
            encoding = "utf-8" if self._should_read_as_text(normalized_path) else None
            resolved_path = self._resolve_artifact_read_path(sandbox_skill_root, normalized_path)
            try:
                content = await self._sandbox_manager.read_file(
                    sandbox_id,
                    resolved_path,
                    encoding=encoding,
                )
            except Exception as exc:
                logger.warning(
                    "Failed to collect skill artifact from sandbox",
                    extra={
                        "sandbox_id": sandbox_id,
                        "artifact_path": normalized_path,
                        "resolved_artifact_path": resolved_path,
                        "encoding": encoding,
                        "error_type": type(exc).__name__,
                    },
                    exc_info=exc,
                )
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

    @staticmethod
    def _resolve_artifact_read_path(sandbox_skill_root: str, artifact_path: str) -> str:
        if Path(artifact_path).is_absolute():
            return artifact_path
        return f"{sandbox_skill_root}/{artifact_path.lstrip('/')}"

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