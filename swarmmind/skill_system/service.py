"""Formal service surface for querying and executing local skill packages."""

from __future__ import annotations

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

        await self._publish_event(
            "skill.script.started",
            execution_context,
            payload={
                "skill_name": entry.name,
                "script_path": script_path,
                "sandbox_profile": policy.sandbox_profile,
            },
        )

        try:
            result = await self._executor.execute(entry, script_path, policy)
        except Exception as exc:
            await self._publish_event(
                "skill.script.failed",
                execution_context,
                payload={
                    "skill_name": entry.name,
                    "script_path": script_path,
                    "error": str(exc),
                },
            )
            raise

        artifact_ids = await self._persist_artifacts(execution_context, result)
        topic = "skill.script.completed" if result.exit_code == 0 else "skill.script.failed"
        payload = {
            "skill_name": result.skill_name,
            "script_path": result.script_path,
            "sandbox_id": result.sandbox_id,
            "exit_code": result.exit_code,
            "artifact_ids": artifact_ids,
            "artifact_count": len(artifact_ids),
        }
        if result.exit_code != 0:
            payload["stderr"] = result.stderr
        await self._publish_event(topic, execution_context, payload=payload, sandbox_id=result.sandbox_id)
        return result

    async def _persist_artifacts(
        self,
        context: SkillExecutionContext,
        result: SkillScriptExecutionResult,
    ) -> list[str]:
        if self._artifact_repository is None or not context.run_id:
            return []

        artifact_ids: list[str] = []
        for artifact_path, content in result.artifacts.items():
            artifact = Artifact(
                id=str(uuid.uuid4()),
                task_id=context.task_id or "skill-script",
                run_id=context.run_id,
                subtask_id=context.subtask_id,
                name=f"{result.skill_name}:{artifact_path}",
                type=ArtifactType.FILE,
                storage_ref=f"skill://{result.skill_name}/{artifact_path}",
                content_type="text/plain",
                metadata={
                    "skill_name": result.skill_name,
                    "script_path": result.script_path,
                    "artifact_path": artifact_path,
                    "sandbox_id": result.sandbox_id,
                    "content": content,
                },
            )
            await self._artifact_repository.create(artifact)
            await self._publish_event(
                "artifact.created",
                context,
                payload={
                    "artifact_id": artifact.id,
                    "artifact_name": artifact.name,
                    "artifact_type": artifact.type.value,
                    "skill_name": result.skill_name,
                    "script_path": result.script_path,
                    "artifact_path": artifact_path,
                },
                sandbox_id=result.sandbox_id,
            )
            artifact_ids.append(artifact.id)
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