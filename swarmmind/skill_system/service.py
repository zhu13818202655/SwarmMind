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
    SkillManifest,
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
        """Return a concise prompt summary for a selected skill.

        Returns the lightweight manifest format — name, description, and
        resource/script lists — instead of the full ``script_specs``.  The
        agent progressively loads details via ``read_skill_reference``.
        """
        manifest = self.build_skill_manifest(skill_name)
        return manifest.model_dump(mode="json")

    def build_skill_manifest(self, skill_name: str) -> SkillManifest:
        """Build a lightweight manifest for progressive discovery."""
        entry = self.get_skill_entry(skill_name)
        entrypoint_resources = self._collect_entrypoint_resources(entry)
        artifact_types = self._infer_artifact_types(entry)
        return SkillManifest(
            name=entry.name,
            description=entry.description,
            entrypoint_resources=entrypoint_resources,
            artifact_types=artifact_types,
        )

    def read_skill_reference(
        self,
        skill_name: str,
        reference_path: str | None = None,
        context: SkillExecutionContext | None = None,
    ) -> str:
        """Progressively read a resource from a skill package.

        - ``reference_path=None`` returns the SKILL.md body (methodology,
          design guides, script descriptions).
        - ``reference_path="editing.md"`` returns a specific reference doc.
        - ``reference_path="scripts/create_presentation.py"`` returns script
          source code so the agent can understand the interface.

        Reads on the host side — no sandbox creation required.
        """
        entry = self.get_skill_entry(skill_name)
        if reference_path is None:
            content = entry.body
        else:
            normalized = reference_path.strip().lstrip("/")
            target = (entry.root_dir / normalized).resolve()
            # Path traversal guard
            if entry.root_dir.resolve() not in target.parents and target != entry.root_dir.resolve():
                raise ValueError(f"Reference path escapes skill root: {reference_path}")
            if not target.is_file():
                raise FileNotFoundError(f"Reference not found: {reference_path}")
            content = target.read_text(encoding="utf-8")

        # Publish audit event (fire-and-forget style via sync wrapper)
        if self._event_bus is not None and context is not None:
            import asyncio

            async def _emit() -> None:
                await self._publish_event(
                    "skill.resource.loaded",
                    context,
                    payload={
                        "skill_name": skill_name,
                        "reference_path": reference_path or "SKILL.md (body)",
                        "content_length": len(content),
                    },
                )

            try:
                loop = asyncio.get_running_loop()
                loop.create_task(_emit())
            except RuntimeError:
                pass

        return content

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
    def _collect_entrypoint_resources(entry: SkillEntry) -> list[str]:
        """Collect top-level readable resources the agent can browse."""
        resources: list[str] = ["SKILL.md"]
        # Top-level .md files (editing.md, pptxgenjs.md, etc.)
        for child in sorted(entry.root_dir.iterdir()):
            if child.is_file() and child.suffix == ".md" and child.name != "SKILL.md":
                resources.append(child.name)
        # Files under references/
        resources.extend(entry.resources.references)
        return resources

    @staticmethod
    def _infer_artifact_types(entry: SkillEntry) -> list[str]:
        """Infer producible artifact types from description and scripts."""
        description_lower = entry.description.lower()
        types: list[str] = []
        extension_hints = {
            ".pptx": ["pptx", "presentation", "slide", "deck"],
            ".pdf": ["pdf"],
            ".docx": ["docx", "document", "word"],
            ".xlsx": ["xlsx", "spreadsheet", "excel"],
        }
        for ext, keywords in extension_hints.items():
            if any(kw in description_lower for kw in keywords):
                types.append(ext)
        return types

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