"""Formal service surface for querying and executing local skill packages."""

from __future__ import annotations

import re
import mimetypes
import uuid
from pathlib import Path

from swarmmind.events import EventBus
from swarmmind.models.artifact import Artifact, ArtifactType
from swarmmind.models.event import DomainEvent
from swarmmind.repositories import ArtifactRepository
from swarmmind.skill_system.catalog import build_expanded_catalog_payload
from swarmmind.skill_system.executor import SkillScriptExecutor
from swarmmind.skill_system.loader import get_skill_package_root, load_skill_registry
from swarmmind.skill_system.models import (
    SkillEntry,
    SkillExecutionContext,
    SkillScriptExecutionPolicy,
    SkillScriptExecutionResult,
    SkillScriptSpec,
)


class SkillExecutionService:
    """High-level operations for skill discovery and script execution."""

    def __init__(
        self,
        executor: SkillScriptExecutor,
        event_bus: EventBus | None = None,
        artifact_repository: ArtifactRepository | None = None,
        skill_root: Path | None = None,
    ) -> None:
        self._executor = executor
        self._event_bus = event_bus
        self._artifact_repository = artifact_repository
        self._skill_root = skill_root

    def list_skill_scripts(self, skill_name: str) -> list[str]:
        """List declared scripts for a valid, enabled skill."""
        entry = self.get_skill_entry(skill_name)
        return list(entry.resources.scripts)

    def get_skill_details(self, skill_name: str) -> dict[str, object]:
        """Return the expanded skill payload for a valid, enabled skill."""
        entry = self.get_skill_entry(skill_name)
        return build_expanded_catalog_payload([entry])[0]

    def get_skill_prompt_context(self, skill_name: str) -> dict[str, object]:
        """Return a concise prompt summary for a selected skill."""
        entry = self.get_skill_entry(skill_name)
        return {
            "name": entry.name,
            "description": entry.description,
            "runtime_requirements": entry.metadata.runtime_requirements.model_dump(mode="json"),
            "script_specs": [
                {
                    "path": spec.path,
                    "runtime": spec.runtime,
                    "description": spec.description,
                    "args_schema": spec.args_schema,
                    "argument_names": list(spec.argument_names),
                    "artifacts": list(spec.artifacts),
                    "examples": list(spec.examples),
                }
                for spec in entry.metadata.script_specs[:8]
            ],
            "body_excerpt": self._extract_body_excerpt(entry.body),
        }

    def get_skill_entry(self, skill_name: str) -> SkillEntry:
        """Load a valid, enabled skill entry by name."""
        registry = load_skill_registry(self._skill_root or get_skill_package_root(), [skill_name])
        entry = registry.get_by_name(skill_name)
        if entry is None:
            raise ValueError(f"Skill not found: {skill_name}")
        if not entry.valid:
            raise ValueError(f"Skill is invalid: {skill_name}")
        if entry.metadata.disabled:
            raise ValueError(f"Skill is disabled: {skill_name}")
        return entry

    async def run_skill_script(
        self,
        skill_name: str,
        script_path: str,
        policy: SkillScriptExecutionPolicy,
        context: SkillExecutionContext | None = None,
    ) -> SkillScriptExecutionResult:
        """Execute a declared skill script and emit audit events."""
        execution_context = context or SkillExecutionContext()
        entry = self.get_skill_entry(skill_name)
        resolved_script_path = self._resolve_declared_script_path(entry, script_path)

        await self._publish_event(
            "skill.script.started",
            execution_context,
            payload={
                "skill_name": entry.name,
                "script_path": resolved_script_path,
                "sandbox_profile": policy.sandbox_profile,
            },
        )

        try:
            result = await self._executor.execute(entry, resolved_script_path, policy)
        except Exception as exc:
            failure_category, retry_suggestions = self._classify_failure(
                entry,
                resolved_script_path,
                policy,
                error=exc,
            )
            error_message = self._format_failure_message(str(exc), failure_category, retry_suggestions)
            await self._publish_event(
                "skill.script.failed",
                execution_context,
                payload={
                    "skill_name": entry.name,
                    "script_path": resolved_script_path,
                    "error": error_message,
                    "failure_category": failure_category,
                    "retry_suggestions": retry_suggestions,
                },
            )
            raise ValueError(error_message) from exc

        result = self._attach_retry_guidance(entry, policy, result)

        artifact_ids = await self._persist_artifacts(execution_context, result)
        topic = "skill.script.completed" if result.exit_code == 0 else "skill.script.failed"
        payload = {
            "skill_name": result.skill_name,
            "script_path": result.script_path,
            "sandbox_id": result.sandbox_id,
            "exit_code": result.exit_code,
            "artifact_ids": artifact_ids,
            "artifact_count": len(artifact_ids),
            "failure_category": result.failure_category,
            "retry_suggestions": list(result.retry_suggestions),
        }
        if result.exit_code != 0:
            payload["stderr"] = result.stderr
        await self._publish_event(topic, execution_context, payload=payload, sandbox_id=result.sandbox_id)
        return result

    def _resolve_declared_script_path(self, entry: SkillEntry, script_path: str) -> str:
        normalized_script = script_path.strip().lstrip("/")
        if normalized_script in entry.resources.scripts:
            return normalized_script
        matches = [
            candidate
            for candidate in entry.resources.scripts
            if Path(candidate).name == normalized_script or Path(candidate).stem == normalized_script
        ]
        if len(matches) == 1:
            return matches[0]
        return normalized_script

    def _find_script_spec(self, entry: SkillEntry, script_path: str) -> SkillScriptSpec | None:
        normalized_script = script_path.strip().lstrip("/")
        for script_spec in entry.metadata.script_specs:
            if script_spec.path.strip().lstrip("/") == normalized_script:
                return script_spec
        return None

    def _attach_retry_guidance(
        self,
        entry: SkillEntry,
        policy: SkillScriptExecutionPolicy,
        result: SkillScriptExecutionResult,
    ) -> SkillScriptExecutionResult:
        failure_category, retry_suggestions = self._classify_failure(
            entry,
            result.script_path,
            policy,
            result=result,
        )
        if failure_category is None and not retry_suggestions:
            return result
        return result.model_copy(
            update={
                "failure_category": failure_category,
                "retry_suggestions": retry_suggestions,
            }
        )

    def _classify_failure(
        self,
        entry: SkillEntry,
        script_path: str,
        policy: SkillScriptExecutionPolicy,
        *,
        error: Exception | None = None,
        result: SkillScriptExecutionResult | None = None,
    ) -> tuple[str | None, list[str]]:
        del policy
        script_spec = self._find_script_spec(entry, script_path)
        if error is not None:
            message = str(error)
            if "Script is not declared under scripts/" in message:
                return (
                    "script_not_found",
                    [
                        "Call list_skill_scripts(skill_name) to inspect declared scripts before retrying.",
                        f"Declared scripts: {', '.join(entry.resources.scripts[:8])}",
                    ],
                )
            if "Missing required script_input keys" in message or "does not define argument_names" in message:
                return (
                    "input_mismatch",
                    self._build_input_retry_suggestions(script_path, script_spec),
                )
            if (
                "Missing required environment variable" in message
                or "Required binary is not available" in message
            ):
                return (
                    "environment_missing",
                    [
                        "Review required_env/required_bins and runtime_requirements before retrying.",
                        "If bootstrap is needed, add it under runtime_requirements.bootstrap_commands or package fields.",
                    ],
                )

        if result is None:
            return None, []

        missing_artifacts = [
            artifact_path
            for artifact_path in result.resolved_artifact_paths
            if artifact_path not in result.artifacts
        ]
        if missing_artifacts:
            return (
                "missing_artifacts",
                [
                    f"Expected artifacts were not collected: {', '.join(missing_artifacts)}.",
                    "Review script_specs artifacts or pass artifact_paths explicitly before retrying.",
                ],
            )

        combined_output = f"{result.stderr}\n{result.stdout}".lower()
        if result.exit_code != 0:
            if "connection timed out while downloading" in combined_output or "incomplete-download" in combined_output:
                return (
                    "bootstrap_failed",
                    [
                        "Dependency bootstrap failed while downloading packages.",
                        "Check runtime_requirements mirror settings or override SWARMMIND_SKILL_PIP_INDEX_URL / SWARMMIND_SKILL_NPM_REGISTRY_URL.",
                    ],
                )
            if script_spec is not None and ("usage:" in combined_output or re.search(r"\berror\b", combined_output)):
                return (
                    "input_mismatch",
                    self._build_input_retry_suggestions(script_path, script_spec),
                )
            return (
                "script_failed",
                [
                    "Inspect stderr/stdout from the previous attempt before retrying.",
                    "If arguments look wrong, call get_skill_details(skill_name) and review script_specs/examples.",
                ],
            )

        return None, []

    def _build_input_retry_suggestions(
        self,
        script_path: str,
        script_spec: SkillScriptSpec | None,
    ) -> list[str]:
        suggestions = [
            "Call get_skill_details(skill_name) and review the script_specs section before retrying.",
        ]
        if script_spec is not None:
            if script_spec.argument_names:
                suggestions.append(
                    f"Prefer script_input with keys in this order: {', '.join(script_spec.argument_names)}."
                )
            if script_spec.examples:
                suggestions.append(f"Use the examples declared for {script_path} as the retry template.")
        return suggestions

    def _format_failure_message(
        self,
        message: str,
        failure_category: str | None,
        retry_suggestions: list[str],
    ) -> str:
        if not failure_category and not retry_suggestions:
            return message
        guidance = " | ".join(retry_suggestions)
        if failure_category:
            return f"[{failure_category}] {message}" + (f" Retry guidance: {guidance}" if guidance else "")
        return f"{message} Retry guidance: {guidance}"

    @staticmethod
    def _extract_body_excerpt(body: str, max_lines: int = 10) -> str:
        lines = [line.strip() for line in body.splitlines() if line.strip()]
        return "\n".join(lines[:max_lines])

    async def _persist_artifacts(
        self,
        context: SkillExecutionContext,
        result: SkillScriptExecutionResult,
    ) -> list[str]:
        if self._artifact_repository is None or not context.run_id:
            return []

        artifact_ids: list[str] = []
        for artifact_path, content in result.artifacts.items():
            artifact_id = str(uuid.uuid4())
            payload = result.artifact_payloads.get(artifact_path, content.encode("utf-8"))
            content_type = mimetypes.guess_type(artifact_path)[0] or "application/octet-stream"
            artifact = Artifact(
                id=artifact_id,
                task_id=context.task_id or "skill-script",
                run_id=context.run_id,
                subtask_id=context.subtask_id,
                name=f"{result.skill_name}:{artifact_path}",
                type=ArtifactType.FILE,
                storage_ref=f"/v1/runs/{context.run_id}/artifacts/{artifact_id}/content",
                content_type=content_type,
                metadata={
                    "skill_name": result.skill_name,
                    "script_path": result.script_path,
                    "artifact_path": artifact_path,
                    "file_name": Path(artifact_path).name,
                    "sandbox_id": result.sandbox_id,
                    "content": content,
                },
            )
            stored_artifact = await self._artifact_repository.create(artifact, payload=payload)
            await self._publish_event(
                "artifact.created",
                context,
                payload={
                    "artifact_id": stored_artifact.id,
                    "artifact_name": stored_artifact.name,
                    "artifact_type": stored_artifact.type.value,
                    "skill_name": result.skill_name,
                    "script_path": result.script_path,
                    "artifact_path": artifact_path,
                    "download_url": stored_artifact.storage_ref,
                },
                sandbox_id=result.sandbox_id,
            )
            artifact_ids.append(stored_artifact.id)
        return artifact_ids

    async def _publish_event(
        self,
        topic: str,
        context: SkillExecutionContext,
        payload: dict[str, object],
        sandbox_id: str | None = None,
    ) -> None:
        if self._event_bus is None:
            return

        await self._event_bus.publish(
            DomainEvent(
                event_id=str(uuid.uuid4()),
                topic=topic,
                tenant_id=context.tenant_id,
                session_id=context.session_id,
                task_id=context.task_id,
                run_id=context.run_id,
                subtask_id=context.subtask_id,
                sandbox_id=sandbox_id,
                payload=payload,
            )
        )