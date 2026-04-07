from __future__ import annotations

import json
from pathlib import PurePosixPath
import re
import shlex
import uuid
from collections.abc import Mapping
from typing import Any

from swarmmind.agents import AgentProfileStore, OmniAgentRequest, OmniAgentRunner
from swarmmind.events import EventBus
from swarmmind.memory import LongTermMemoryBase
from swarmmind.models.artifact import Artifact, ArtifactType
from swarmmind.models.agent_profile import AgentProfile, HandoffContextMode
from swarmmind.models.capability import AgentRole, RuntimeKind, ToolExecutionContract, ToolGroup
from swarmmind.models.event import DomainEvent
from swarmmind.models.execution import (
    ExecutionProfile,
    ReviewDecision,
    ReviewDecisionType,
    VerificationCriterionResult,
    VerificationResult,
)
from swarmmind.models.task import SubTaskStatus
from swarmmind.orchestration.run_state_service import RunStateService
from swarmmind.prompt_template import (
    EXECUTION_FALLBACK_CONTENT_PROMPT,
    EXECUTION_SUBTASK_MARKDOWN_PROMPT,
    EXECUTION_SYSTEM_PROMPT,
    PromptTemplate,
    REVIEW_DECISION_PROMPT,
    VALIDATION_AGENT_SYSTEM_PROMPT,
    VERIFICATION_RESULT_PROMPT,
    render_prompt,
)
from swarmmind.repositories import ArtifactRepository, RunRepository, SubTaskRepository, TaskRepository
from swarmmind.sandbox import CommandRequest, SandboxLeaseRequest, SandboxManager
from swarmmind.sandbox.artifact_collector import ArtifactCollector
from swarmmind.skill_system import SkillExecutionService
from swarmmind.tools import ToolRegistry


class ExecutionRunner:
    """Consume assigned subtasks and execute them via resolved runtimes and tools."""

    def __init__(
        self,
        task_repository: TaskRepository,
        run_repository: RunRepository,
        subtask_repository: SubTaskRepository,
        artifact_repository: ArtifactRepository,
        event_bus: EventBus,
        sandbox_manager: SandboxManager,
        artifact_collector: ArtifactCollector,
        run_state_service: RunStateService,
        tool_registry: ToolRegistry,
        agent_profile_store: AgentProfileStore,
        skill_execution_service: SkillExecutionService | None = None,
        model_name: str = "gpt-4o",
        model_api_key: str | None = None,
        model_base_url: str | None = None,
        model_temperature: float = 0.2,
        model_max_tokens: int = 2048,
        system_prompt_template: PromptTemplate = EXECUTION_SYSTEM_PROMPT,
        user_prompt_template: PromptTemplate = EXECUTION_SUBTASK_MARKDOWN_PROMPT,
        fallback_content_template: PromptTemplate = EXECUTION_FALLBACK_CONTENT_PROMPT,
        long_term_memory: LongTermMemoryBase | None = None,
    ):
        self._task_repository = task_repository
        self._run_repository = run_repository
        self._subtask_repository = subtask_repository
        self._artifact_repository = artifact_repository
        self._event_bus = event_bus
        self._sandbox_manager = sandbox_manager
        self._artifact_collector = artifact_collector
        self._run_state_service = run_state_service
        self._tool_registry = tool_registry
        self._agent_profile_store = agent_profile_store
        self._skill_execution_service = skill_execution_service
        self._model_name = model_name
        self._model_api_key = model_api_key
        self._model_base_url = model_base_url
        self._model_temperature = model_temperature
        self._model_max_tokens = model_max_tokens
        self._system_prompt_template = system_prompt_template
        self._user_prompt_template = user_prompt_template
        self._fallback_content_template = fallback_content_template
        self._long_term_memory = long_term_memory
        self._omni_agent = OmniAgentRunner(
            model_name=model_name,
            api_key=model_api_key,
            base_url=model_base_url,
            temperature=model_temperature,
            max_tokens=model_max_tokens,
        )
        self._register_runtime_tools()

    async def handle_subtask_assigned(self, event: DomainEvent) -> None:
        """Execute an assigned subtask and persist its evidence."""
        if not event.subtask_id or not event.run_id or not event.task_id:
            return

        task = await self._task_repository.get(event.task_id)
        run = await self._run_repository.get(event.run_id)
        subtask = await self._subtask_repository.get(event.subtask_id)
        if task is None or run is None or subtask is None:
            return

        if subtask.status in {
            SubTaskStatus.SUCCEEDED,
            SubTaskStatus.FAILED,
            SubTaskStatus.EXECUTING,
            SubTaskStatus.VERIFYING,
            SubTaskStatus.SANDBOX_CREATING,
        }:
            return
        if subtask.status != SubTaskStatus.ASSIGNED:
            return

        try:
            execution_profile = self._load_execution_profile(subtask)
            execution_label = self._resolve_execution_label(subtask)  # TODO 需要删除
            subtask.metadata["execution_label"] = execution_label
            if execution_profile.resolved_runtime_kind is not None:
                subtask.metadata["resolved_runtime_kind"] = execution_profile.resolved_runtime_kind.value
            if execution_profile.runtime_resolution_reason:
                subtask.metadata["runtime_resolution_reason"] = execution_profile.runtime_resolution_reason
            if execution_profile.runtime_fallback_chain:
                subtask.metadata["runtime_fallback_chain"] = [item.value for item in execution_profile.runtime_fallback_chain]
            subtask.metadata["selected_tools"] = self._select_tool_names(subtask)
            await self._subtask_repository.save(subtask)

            await self._publish_execution_event(
                topic="execution.started",
                task=task,
                run=run,
                subtask=subtask,
                payload={
                    "execution_label": execution_label,
                    "role": subtask.role,
                    "resolved_runtime_kind": subtask.metadata.get("resolved_runtime_kind"),
                    "runtime_resolution_reason": subtask.metadata.get("runtime_resolution_reason"),
                    "runtime_fallback_chain": subtask.metadata.get("runtime_fallback_chain", []),
                    "selected_tools": subtask.metadata["selected_tools"],
                },
            )

            await self._execute_subtask(task, run, subtask, event)

            await self._publish_execution_event(
                topic="execution.completed",
                task=task,
                run=run,
                subtask=subtask,
                payload={
                    "execution_label": execution_label,
                    "role": subtask.role,
                    "status": subtask.status,
                },
            )
        except Exception as exc:
            subtask.fail(str(exc))
            await self._subtask_repository.save(subtask)
            await self._publish_execution_event(
                topic="execution.failed",
                task=task,
                run=run,
                subtask=subtask,
                payload={"execution_label": self._resolve_execution_label(subtask), "error": str(exc)},
            )
            await self._event_bus.publish(
                DomainEvent(
                    event_id=str(uuid.uuid4()),
                    topic="subtask.failed",
                    tenant_id=task.metadata.get("tenant_id", event.tenant_id),
                    session_id=run.session_id,
                    task_id=task.id,
                    run_id=run.id,
                    subtask_id=subtask.id,
                    sandbox_id=subtask.metadata.get("sandbox_id"),
                    payload={"error": str(exc)},
                )
            )
            await self._publish_subtask_terminal_events(task, run, subtask, payload={"error": str(exc)})
        finally:
            await self._run_state_service.reconcile(run.id)

    async def _execute_subtask(self, task, run, subtask, event: DomainEvent) -> None:
        execution_profile = self._load_execution_profile(subtask)
        await self._validate_execution_policy(task, run, subtask, execution_profile)
        resolved_runtime_kind = execution_profile.resolved_runtime_kind or RuntimeKind.HOST_TOOLS

        if subtask.role in {AgentRole.VERIFIER, AgentRole.TESTER, AgentRole.REVIEWER}:
            await self._execute_validation_subtask(task, run, subtask, event)
        elif resolved_runtime_kind == RuntimeKind.SANDBOX and ToolGroup.CODE_EXEC in execution_profile.required_tool_groups:
            await self._execute_sandbox_subtask(task, run, subtask, event)
        else:
            await self._execute_inline_runtime_subtask(task, run, subtask, event, resolved_runtime_kind)

    async def _validate_execution_policy(self, task, run, subtask, execution_profile: ExecutionProfile) -> None:
        required_groups = set(execution_profile.required_tool_groups)
        allowed_groups = set(execution_profile.allowed_tool_groups)
        if allowed_groups and not required_groups.issubset(allowed_groups):
            missing_groups = sorted(group.value for group in required_groups.difference(allowed_groups))
            await self._publish_policy_denied(
                task=task,
                run=run,
                subtask=subtask,
                payload={
                    "reason": "required_tool_groups_not_allowed",
                    "required_tool_groups": sorted(group.value for group in required_groups),
                    "allowed_tool_groups": sorted(group.value for group in allowed_groups),
                    "missing_tool_groups": missing_groups,
                },
            )
            raise PermissionError(
                f"Execution profile for subtask {subtask.name} is missing required tool groups: {', '.join(missing_groups)}"
            )

    def _resolve_execution_label(self, subtask) -> str:
        execution_profile = self._load_execution_profile(subtask)
        if execution_profile.skill_profiles:
            return execution_profile.skill_profiles[0]
        if subtask.execution_configuration and subtask.execution_configuration.skill_profiles:
            return subtask.execution_configuration.skill_profiles[0]
        defaults = {
            AgentRole.VERIFIER: "verification",
            AgentRole.TESTER: "verification",
            AgentRole.REVIEWER: "review",
            AgentRole.WRITER: "write_report",
            AgentRole.RESEARCHER: "research",
            AgentRole.PLANNER: "task_planning",
        }
        return defaults.get(subtask.role, "build_app")  # TODO - 默认用一个通用的agent而不是build_app

    def _select_tool_names(self, subtask) -> list[str]:
        execution_profile = self._load_execution_profile(subtask)
        names: list[str] = []
        runtime_kind = execution_profile.resolved_runtime_kind
        required_groups = {group.value for group in execution_profile.required_tool_groups}
        allowed_groups = {group.value for group in execution_profile.allowed_tool_groups}
        explicit_allowed_names = set(execution_profile.allowed_tool_names)
        for metadata in self._tool_registry.get_tool_metadata():
            groups = set(metadata.get("groups", []))
            tool_name = str(metadata.get("name"))
            contract = metadata.get("contract") if isinstance(metadata.get("contract"), dict) else {}
            allowed_runtimes = {
                str(item)
                for item in contract.get("allowed_runtimes", [])
                if isinstance(item, str)
            }
            if runtime_kind is not None and allowed_runtimes and runtime_kind.value not in allowed_runtimes:
                continue
            if required_groups and not groups.intersection(required_groups) and tool_name not in explicit_allowed_names:
                continue
            if allowed_groups and not groups.intersection(allowed_groups) and tool_name not in explicit_allowed_names:
                continue
            names.append(tool_name)
        for tool_name in self._runtime_required_tool_names(subtask):
            if self._tool_allowed_by_execution_profile(tool_name, execution_profile):
                names.append(tool_name)
        if explicit_allowed_names:
            names.extend(name for name in explicit_allowed_names if name in self._tool_registry.get_tool_names())
        return sorted(set(names))

    def _runtime_required_tool_names(self, subtask) -> set[str]:
        execution_profile = self._load_execution_profile(subtask)
        role = subtask.role
        required: set[str] = set()
        if execution_profile.resolved_runtime_kind == RuntimeKind.SANDBOX and ToolGroup.CODE_EXEC in execution_profile.required_tool_groups:
            required.add("sandbox_exec")
        if role in {AgentRole.VERIFIER, AgentRole.TESTER, AgentRole.REVIEWER}:
            required.add("artifact_read")
        if self._long_term_memory is not None and role in {
            AgentRole.PLANNER,
            AgentRole.CODER,
            AgentRole.WRITER,
            AgentRole.RESEARCHER,
            AgentRole.REVIEWER,
        }:
            required.update({"memory_lookup", "memory_write"})
        return required

    def _tool_allowed_by_execution_profile(self, tool_name: str, execution_profile: ExecutionProfile) -> bool:
        if tool_name in execution_profile.allowed_tool_names:
            return True
        if not execution_profile.allowed_tool_groups:
            return True
        tool_groups = {
            group.value
            for group in self._tool_registry.get_tool_groups(tool_name)
        }
        allowed_groups = {group.value for group in execution_profile.allowed_tool_groups}
        return not allowed_groups or bool(tool_groups.intersection(allowed_groups))

    def _register_runtime_tools(self) -> None:
        existing = set(self._tool_registry.get_tool_names())
        if "sandbox_exec" not in existing:
            self._tool_registry.register(
                self._tool_sandbox_exec,
                name="sandbox_exec",
                description="Execute a command inside an acquired sandbox lease.",
                groups=["code_exec"],
                contract=ToolExecutionContract(
                    default_runtime=RuntimeKind.SANDBOX,
                    allowed_runtimes=[RuntimeKind.SANDBOX],
                    audit_required=True,
                    dangerous=True,
                    sandbox_only=True,
                ),
            )
        if "browser_playwright" not in existing:
            self._tool_registry.register(
                self._tool_browser_playwright,
                name="browser_playwright",
                description="Use Playwright inside a sandbox to inspect or screenshot a web page.",
                groups=["browser"],
                contract=ToolExecutionContract(
                    default_runtime=RuntimeKind.SANDBOX,
                    allowed_runtimes=[RuntimeKind.SANDBOX],
                    audit_required=True,
                    expensive=True,
                    sandbox_only=True,
                ),
            )
        if "artifact_read" not in existing:
            self._tool_registry.register(
                self._tool_artifact_read,
                name="artifact_read",
                description="Read artifacts associated with dependency subtasks.",
                groups=["artifact"],
                contract=ToolExecutionContract(
                    default_runtime=RuntimeKind.HOST_TOOLS,
                    allowed_runtimes=[RuntimeKind.HOST_TOOLS],
                    read_only=True,
                ),
            )
        if "memory_lookup" not in existing:
            self._tool_registry.register(
                self._tool_memory_lookup,
                name="memory_lookup",
                description="Retrieve related long-term memory items.",
                groups=["memory"],
                contract=ToolExecutionContract(
                    default_runtime=RuntimeKind.HOST_TOOLS,
                    allowed_runtimes=[RuntimeKind.HOST_TOOLS],
                    read_only=True,
                ),
            )
        if "memory_write" not in existing:
            self._tool_registry.register(
                self._tool_memory_write,
                name="memory_write",
                description="Store a concise long-term memory summary.",
                groups=["memory"],
                contract=ToolExecutionContract(
                    default_runtime=RuntimeKind.HOST_TOOLS,
                    allowed_runtimes=[RuntimeKind.HOST_TOOLS],
                    audit_required=True,
                ),
            )

    async def _execute_sandbox_subtask(self, task, run, subtask, event: DomainEvent) -> None:
        lease = None
        try:
            subtask.mark_sandbox_creating()
            await self._subtask_repository.save(subtask)

            lease = await self._sandbox_manager.acquire(
                SandboxLeaseRequest(
                    profile=self._resolve_sandbox_profile(task, subtask),
                    task_id=task.id,
                    run_id=run.id,
                    subtask_id=subtask.id,
                )
            )

            subtask.metadata["lease_id"] = lease.lease_id
            subtask.metadata["sandbox_id"] = lease.sandbox_id
            subtask.start_execution()
            await self._subtask_repository.save(subtask)

            await self._event_bus.publish(
                DomainEvent(
                    event_id=str(uuid.uuid4()),
                    topic="subtask.started",
                    tenant_id=task.metadata.get("tenant_id", event.tenant_id),
                    session_id=run.session_id,
                    task_id=task.id,
                    run_id=run.id,
                    subtask_id=subtask.id,
                    payload={"name": subtask.name, "role": subtask.role},
                )
            )

            await self._event_bus.publish(
                DomainEvent(
                    event_id=str(uuid.uuid4()),
                    topic="sandbox.created",
                    tenant_id=task.metadata.get("tenant_id", event.tenant_id),
                    session_id=run.session_id,
                    task_id=task.id,
                    run_id=run.id,
                    subtask_id=subtask.id,
                    sandbox_id=lease.sandbox_id,
                    payload={"lease_id": lease.lease_id, "profile": lease.profile},
                )
            )

            command_request = await self._build_command_request(task, subtask)
            await self._event_bus.publish(
                DomainEvent(
                    event_id=str(uuid.uuid4()),
                    topic="sandbox.command_started",
                    tenant_id=task.metadata.get("tenant_id", event.tenant_id),
                    session_id=run.session_id,
                    task_id=task.id,
                    run_id=run.id,
                    subtask_id=subtask.id,
                    sandbox_id=lease.sandbox_id,
                    payload={"command": command_request.command, "cwd": command_request.cwd},
                )
            )

            execution = await self._run_tool(
                "sandbox_exec",
                task=task,
                run=run,
                subtask=subtask,
                sandbox_id=lease.sandbox_id,
                lease=lease,
                command_request=command_request,
                command=command_request.command,
                cwd=command_request.cwd,
            )
            subtask.metadata["last_execution"] = {
                "command": execution.command,
                "exit_code": execution.exit_code,
                "executed_at": execution.executed_at.isoformat(),
            }

            await self._event_bus.publish(
                DomainEvent(
                    event_id=str(uuid.uuid4()),
                    topic="sandbox.command_completed",
                    tenant_id=task.metadata.get("tenant_id", event.tenant_id),
                    session_id=run.session_id,
                    task_id=task.id,
                    run_id=run.id,
                    subtask_id=subtask.id,
                    sandbox_id=lease.sandbox_id,
                    payload={
                        "command": execution.command,
                        "exit_code": execution.exit_code,
                        "stdout_length": len(execution.stdout),
                        "stderr_length": len(execution.stderr),
                    },
                )
            )

            artifacts = self._artifact_collector.collect(task, run, subtask, lease, execution)
            for artifact in artifacts:
                await self._store_artifact(task, run, subtask, artifact, lease.sandbox_id)

            if execution.exit_code == 0:
                subtask.complete(
                    {
                        "exit_code": execution.exit_code,
                        "artifact_count": len(artifacts),
                        "stdout_preview": execution.stdout[:300],
                    }
                )
                completion_topic = "subtask.completed"
                completion_payload = {
                    "exit_code": execution.exit_code,
                    "artifact_count": len(artifacts),
                }
            else:
                error = execution.stderr or execution.stdout or f"Command failed with exit code {execution.exit_code}"
                subtask.fail(error)
                completion_topic = "subtask.failed"
                completion_payload = {
                    "exit_code": execution.exit_code,
                    "error": error[:1000],
                }

            await self._subtask_repository.save(subtask)
            await self._store_memory_for_subtask(task, run, subtask)
            await self._event_bus.publish(
                DomainEvent(
                    event_id=str(uuid.uuid4()),
                    topic=completion_topic,
                    tenant_id=task.metadata.get("tenant_id", event.tenant_id),
                    session_id=run.session_id,
                    task_id=task.id,
                    run_id=run.id,
                    subtask_id=subtask.id,
                    sandbox_id=lease.sandbox_id,
                    payload=completion_payload,
                )
            )
            await self._publish_subtask_terminal_events(task, run, subtask, lease.sandbox_id, completion_payload)
        finally:
            if lease is not None:
                await self._sandbox_manager.release(lease.lease_id)

    async def _execute_validation_subtask(self, task, run, subtask, event: DomainEvent) -> None:
        subtask.start_verification()
        await self._subtask_repository.save(subtask)
        await self._event_bus.publish(
            DomainEvent(
                event_id=str(uuid.uuid4()),
                topic="subtask.started",
                tenant_id=task.metadata.get("tenant_id", event.tenant_id),
                session_id=run.session_id,
                task_id=task.id,
                run_id=run.id,
                subtask_id=subtask.id,
                payload={"name": subtask.name, "role": subtask.role},
            )
        )

        if task.constraints.get("force_fail_subtask") == subtask.name:
            raise RuntimeError(f"forced failure for {subtask.name}")

        dependencies = await self._load_dependency_subtasks(run.id, subtask)
        dependency_artifacts = await self._run_tool(
            "artifact_read",
            task=task,
            run=run,
            subtask=subtask,
            run_id=run.id,
            dependency_ids=[dep.id for dep in dependencies],
        )

        structured_result = await self._render_validation_result_with_model(
            task=task,
            run=run,
            subtask=subtask,
            dependencies=dependencies,
            dependency_artifacts=dependency_artifacts,
        )

        if self._is_verification_role(subtask.role):
            verification = structured_result if isinstance(structured_result, VerificationResult) else self._build_verification_result(subtask, dependencies, dependency_artifacts)
            backend = "agent" if isinstance(structured_result, VerificationResult) else "rules_fallback"
            subtask.complete(
                {
                    **verification.model_dump(mode="json"),
                    "verification_passed": verification.passed,
                    "validation_backend": backend,
                }
            )
            artifact = self._create_inline_artifact(
                task=task,
                run=run,
                subtask=subtask,
                name=f"{subtask.name}-verification.json",
                artifact_type=ArtifactType.TEST_RESULT,
                metadata={
                    **verification.model_dump(mode="json"),
                    "validation_backend": backend,
                    "dependency_summary": self._summarize_dependency_subtasks(dependencies),
                    "artifact_summary": self._summarize_artifacts(dependency_artifacts),
                },
            )
        else:
            decision = structured_result if isinstance(structured_result, ReviewDecision) else self._build_review_decision(task, subtask, dependencies)
            backend = "agent" if isinstance(structured_result, ReviewDecision) else "rules_fallback"
            subtask.complete(
                {
                    **decision.model_dump(mode="json"),
                    "verification_passed": all(
                        bool(dep.result and dep.result.get("passed"))
                        for dep in dependencies
                        if self._is_verification_role(dep.role)
                    ),
                    "validation_backend": backend,
                }
            )
            artifact = self._create_inline_artifact(
                task=task,
                run=run,
                subtask=subtask,
                name=f"{subtask.name}-review.json",
                artifact_type=ArtifactType.REPORT,
                metadata={
                    **decision.model_dump(mode="json"),
                    "validation_backend": backend,
                    "dependency_summary": self._summarize_dependency_subtasks(dependencies),
                    "artifact_summary": self._summarize_artifacts(dependency_artifacts),
                },
            )

        await self._subtask_repository.save(subtask)
        await self._store_artifact(task, run, subtask, artifact)
        await self._store_memory_for_subtask(task, run, subtask)
        await self._event_bus.publish(
            DomainEvent(
                event_id=str(uuid.uuid4()),
                topic="subtask.completed",
                tenant_id=task.metadata.get("tenant_id", event.tenant_id),
                session_id=run.session_id,
                task_id=task.id,
                run_id=run.id,
                subtask_id=subtask.id,
                payload=subtask.result or {},
            )
        )
        await self._publish_subtask_terminal_events(task, run, subtask, payload=subtask.result or {})

    async def _execute_inline_runtime_subtask(self, task, run, subtask, event: DomainEvent, runtime_kind: RuntimeKind) -> None:
        await self._execute_omni_agent_subtask(
            task=task,
            run=run,
            subtask=subtask,
            event=event,
            runtime_kind=runtime_kind,
        )

    async def _execute_omni_agent_subtask(
        self,
        *,
        task,
        run,
        subtask,
        event: DomainEvent,
        runtime_kind: RuntimeKind,
    ) -> None:
        subtask.start_execution()
        await self._subtask_repository.save(subtask)
        start_payload = {
            "name": subtask.name,
            "role": subtask.role,
            "runtime_kind": runtime_kind.value,
        }
        await self._event_bus.publish(
            DomainEvent(
                event_id=str(uuid.uuid4()),
                topic="subtask.started",
                tenant_id=task.metadata.get("tenant_id", event.tenant_id),
                session_id=run.session_id,
                task_id=task.id,
                run_id=run.id,
                subtask_id=subtask.id,
                payload=start_payload,
            )
        )

        content = await self._render_subtask_content(task, subtask, run=run)
        artifact_name = f"{subtask.name}-{runtime_kind.value}.md"

        execution_profile = self._load_execution_profile(subtask)
        skill_profiles = self._effective_skill_profiles(execution_profile, subtask)
        artifact = self._create_inline_artifact(
            task=task,
            run=run,
            subtask=subtask,
            name=artifact_name,
            artifact_type=ArtifactType.REPORT,
            metadata={
                "content": content,
                "runtime_kind": runtime_kind.value,
                "execution_label": self._resolve_execution_label(subtask),
                "skill_profiles": skill_profiles,
                "execution_backend": "omni_agent",
                "omni_agent": {
                    "tool_names": [getattr(tool, "__name__", repr(tool)) for tool in self._build_agent_tool_functions(task, run, subtask)],
                    "skill_profiles": skill_profiles,
                },
                **({"agent_profile_id": subtask.agent_profile_id, "handoff": subtask.metadata.get("handoff")} if subtask.agent_profile_id else {}),
            },
        )
        result_payload = {
            "content_preview": content[:300],
            "runtime_kind": runtime_kind.value,
            "artifact_count": 1,
            "execution_backend": "omni_agent",
        }
        if subtask.agent_profile_id:
            result_payload.update({"agent_profile_id": subtask.agent_profile_id, "handoff": subtask.metadata.get("handoff")})
        subtask.complete(result_payload)

        await self._subtask_repository.save(subtask)
        await self._store_artifact(task, run, subtask, artifact)
        await self._store_memory_for_subtask(task, run, subtask)
        await self._event_bus.publish(
            DomainEvent(
                event_id=str(uuid.uuid4()),
                topic="subtask.completed",
                tenant_id=task.metadata.get("tenant_id", event.tenant_id),
                session_id=run.session_id,
                task_id=task.id,
                run_id=run.id,
                subtask_id=subtask.id,
                payload=subtask.result or {},
            )
        )
        await self._publish_subtask_terminal_events(task, run, subtask, payload=subtask.result or {})

    async def _publish_subtask_terminal_events(
        self,
        task,
        run,
        subtask,
        sandbox_id: str | None = None,
        payload: Mapping[str, object] | None = None,
    ) -> None:
        summary_payload = {
            "name": subtask.name,
            "status": subtask.status,
            "role": subtask.role,
            "error": subtask.error,
            **(payload or {}),
        }
        await self._event_bus.publish(
            DomainEvent(
                event_id=str(uuid.uuid4()),
                topic="subtask.terminal",
                tenant_id=task.metadata.get("tenant_id", "local"),
                session_id=run.session_id,
                task_id=task.id,
                run_id=run.id,
                subtask_id=subtask.id,
                sandbox_id=sandbox_id,
                payload=summary_payload,
            )
        )
        await self._event_bus.publish(
            DomainEvent(
                event_id=str(uuid.uuid4()),
                topic="subtask.summary",
                tenant_id=task.metadata.get("tenant_id", "local"),
                session_id=run.session_id,
                task_id=task.id,
                run_id=run.id,
                subtask_id=subtask.id,
                sandbox_id=sandbox_id,
                payload={
                    **summary_payload,
                    "result": self._summarize_tool_payload(subtask.result),
                },
            )
        )

    async def _publish_handoff_event(self, topic: str, task, run, subtask, payload: dict[str, object]) -> None:
        await self._event_bus.publish(
            DomainEvent(
                event_id=str(uuid.uuid4()),
                topic=topic,
                tenant_id=task.metadata.get("tenant_id", "local"),
                session_id=run.session_id,
                task_id=task.id,
                run_id=run.id,
                subtask_id=subtask.id,
                payload=payload,
            )
        )

    async def _load_dependency_subtasks(self, run_id: str, subtask) -> list:
        run_subtasks = await self._subtask_repository.list_for_run(run_id)
        subtask_map = {item.id: item for item in run_subtasks}
        return [subtask_map[dependency] for dependency in subtask.dependencies if dependency in subtask_map]

    async def _render_validation_result_with_model(self, task, run, subtask, dependencies, dependency_artifacts) -> VerificationResult | ReviewDecision | None:
        prompt = self._compose_validation_prompt(task, subtask, dependencies, dependency_artifacts)
        if not prompt:
            return None

        await self._publish_execution_event(
            topic="validation.agent.started",
            task=task,
            run=run,
            subtask=subtask,
            payload={
                "role": subtask.role,
                "dependency_ids": [dependency.id for dependency in dependencies],
                "artifact_ids": [artifact.id for artifact in dependency_artifacts],
            },
        )

        text = await self._render_structured_prompt_with_model(
            task=task,
            subtask=subtask,
            prompt=prompt,
            system_prompt=render_prompt(VALIDATION_AGENT_SYSTEM_PROMPT),
            run=run,
        )
        if not text:
            await self._publish_execution_event(
                topic="validation.agent.fallback",
                task=task,
                run=run,
                subtask=subtask,
                payload={"reason": "model_unavailable_or_empty"},
            )
            return None

        payload = self._extract_json_payload(text)
        if payload is None:
            await self._publish_execution_event(
                topic="validation.agent.fallback",
                task=task,
                run=run,
                subtask=subtask,
                payload={"reason": "invalid_json", "response_preview": text[:500]},
            )
            return None

        try:
            if self._is_verification_role(subtask.role):
                result = VerificationResult.model_validate(payload)
            else:
                result = ReviewDecision.model_validate(payload)
        except Exception as exc:
            await self._publish_execution_event(
                topic="validation.agent.fallback",
                task=task,
                run=run,
                subtask=subtask,
                payload={"reason": "schema_validation_failed", "error": str(exc), "response_preview": text[:500]},
            )
            return None

        await self._publish_execution_event(
            topic="validation.agent.completed",
            task=task,
            run=run,
            subtask=subtask,
            payload={
                "role": subtask.role,
                "result": self._summarize_tool_payload(result.model_dump(mode="json")),
            },
        )
        return result

    def _compose_validation_prompt(self, task, subtask, dependencies, dependency_artifacts) -> str:
        template = VERIFICATION_RESULT_PROMPT if self._is_verification_role(subtask.role) else REVIEW_DECISION_PROMPT
        return render_prompt(
            template,
            {
                "task_goal": task.goal,
                "subtask_name": subtask.name,
                "subtask_description": subtask.description,
                "acceptance_criteria_json": json.dumps(subtask.acceptance_criteria, ensure_ascii=False),
                "dependency_summary_json": json.dumps(
                    self._summarize_dependency_subtasks(dependencies),
                    ensure_ascii=False,
                ),
                "artifact_summary_json": json.dumps(
                    self._summarize_artifacts(dependency_artifacts),
                    ensure_ascii=False,
                ),
            },
        )

    async def _render_structured_prompt_with_model(
        self,
        *,
        task,
        subtask,
        prompt: str,
        system_prompt: str,
        run=None,
        agent_profile_override: AgentProfile | None = None,
    ) -> str | None:
        result = await self._run_omni_agent_prompt(
            task=task,
            subtask=subtask,
            prompt=prompt,
            system_prompt=system_prompt,
            run=run,
            step_kind="validation.structured",
            agent_profile_override=agent_profile_override,
        )
        return result.content

    @staticmethod
    def _extract_json_payload(raw_text: str) -> dict[str, object] | None:
        fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw_text, flags=re.DOTALL | re.IGNORECASE)
        candidate = fenced.group(1) if fenced else raw_text
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start == -1 or end == -1 or end < start:
            return None
        snippet = candidate[start : end + 1]
        try:
            value = json.loads(snippet)
        except json.JSONDecodeError:
            return None
        if isinstance(value, dict):
            return value
        return None

    @staticmethod
    def _summarize_dependency_subtasks(dependencies) -> list[dict[str, object]]:
        summaries: list[dict[str, object]] = []
        for dependency in dependencies:
            summaries.append(
                {
                    "id": dependency.id,
                    "name": dependency.name,
                    "role": str(dependency.role),
                    "status": str(dependency.status),
                    "result": ExecutionRunner._summarize_tool_payload(dependency.result or {}),
                    "error": dependency.error,
                }
            )
        return summaries

    @staticmethod
    def _summarize_artifacts(artifacts: list[Artifact]) -> list[dict[str, object]]:
        return [
            {
                "id": artifact.id,
                "name": artifact.name,
                "type": artifact.type,
                "subtask_id": artifact.subtask_id,
                "storage_ref": artifact.storage_ref,
                "metadata": ExecutionRunner._summarize_tool_payload(artifact.metadata),
            }
            for artifact in artifacts
        ]

    @staticmethod
    def _is_verification_role(role: AgentRole) -> bool:
        return role in {AgentRole.VERIFIER, AgentRole.TESTER}

    def _build_verification_result(self, subtask, dependencies, artifacts) -> VerificationResult:
        dependency_failures = [dependency for dependency in dependencies if dependency.status == SubTaskStatus.FAILED]
        artifact_ids = [artifact.id for artifact in artifacts]
        criteria_results: list[VerificationCriterionResult] = []
        for criterion in subtask.acceptance_criteria or ["Verification evidence exists."]:
            passed = not dependency_failures and bool(artifacts) and all(
                dependency.status == SubTaskStatus.SUCCEEDED for dependency in dependencies
            )
            evidence = f"dependencies={len(dependencies)}, artifacts={len(artifacts)}, failed_dependencies={len(dependency_failures)}"
            criteria_results.append(
                VerificationCriterionResult(
                    criterion=criterion,
                    passed=passed,
                    evidence=evidence,
                )
            )

        passed = bool(criteria_results) and all(item.passed for item in criteria_results)
        summary = "Verification passed." if passed else "Verification failed and reviewer should decide whether to rework."
        return VerificationResult(
            passed=passed,
            summary=summary,
            criteria_results=criteria_results,
            evidence_subtask_ids=[dependency.id for dependency in dependencies],
            artifact_ids=artifact_ids,
        )

    def _build_review_decision(self, task, subtask, dependencies) -> ReviewDecision:
        forced_decisions = task.constraints.get("force_review_decisions") or {}
        forced_value = forced_decisions.get(subtask.name) or task.constraints.get("force_review_decision")
        if forced_value:
            decision_type = ReviewDecisionType(str(forced_value).lower())
        else:
            tester_results = [dependency for dependency in dependencies if self._is_verification_role(dependency.role)]
            passed = all(bool(item.result and item.result.get("passed")) for item in tester_results) and bool(tester_results)
            decision_type = ReviewDecisionType.ACCEPT if passed else ReviewDecisionType.REWORK

        if decision_type == ReviewDecisionType.ACCEPT:
            summary = "Review accepted the result."
            actions = []
        elif decision_type == ReviewDecisionType.REWORK:
            summary = "Review requests a targeted rework loop."
            actions = ["Generate repair subtask", "Re-run verification", "Run review again"]
        else:
            summary = "Review escalated the result for manual intervention."
            actions = ["Escalate to coordinator"]


        return ReviewDecision(
            decision=decision_type,
            summary=summary,
            rationale=f"Decision derived from {len(dependencies)} dependency subtasks.",
            follow_up_actions=actions,
        )

    async def _publish_execution_event(self, topic: str, task, run, subtask, payload: dict[str, object]) -> None:
        await self._event_bus.publish(
            DomainEvent(
                event_id=str(uuid.uuid4()),
                topic=topic,
                tenant_id=task.metadata.get("tenant_id", "local"),
                session_id=run.session_id,
                task_id=task.id,
                run_id=run.id,
                subtask_id=subtask.id,
                payload=payload,
            )
        )

    async def _publish_tool_event(
        self,
        topic: str,
        tool_name: str,
        task,
        run,
        subtask,
        payload: dict[str, object],
        sandbox_id: str | None = None,
    ) -> None:
        await self._event_bus.publish(
            DomainEvent(
                event_id=str(uuid.uuid4()),
                topic=topic,
                tenant_id=task.metadata.get("tenant_id", "local"),
                session_id=run.session_id,
                task_id=task.id,
                run_id=run.id,
                subtask_id=subtask.id,
                sandbox_id=sandbox_id,
                payload={"tool_name": tool_name, **payload},
            )
        )

    async def _run_tool(
        self,
        tool_name: str,
        *,
        task,
        run,
        subtask,
        sandbox_id: str | None = None,
        **kwargs: Any,
    ) -> Any:
        await self._ensure_tool_allowed(tool_name, task=task, run=run, subtask=subtask, sandbox_id=sandbox_id, kwargs=kwargs)
        payload = {
            key: self._summarize_tool_payload(value)
            for key, value in kwargs.items()
            if key not in {"lease", "command_request"}
        }
        await self._publish_tool_event(
            topic="tool.started",
            tool_name=tool_name,
            task=task,
            run=run,
            subtask=subtask,
            sandbox_id=sandbox_id,
            payload=payload,
        )
        try:
            result = await self._tool_registry.execute(tool_name, **kwargs)
        except Exception as exc:
            await self._publish_tool_event(
                topic="tool.failed",
                tool_name=tool_name,
                task=task,
                run=run,
                subtask=subtask,
                sandbox_id=sandbox_id,
                payload={**payload, "error": str(exc)},
            )
            raise
        await self._publish_tool_event(
            topic="tool.completed",
            tool_name=tool_name,
            task=task,
            run=run,
            subtask=subtask,
            sandbox_id=sandbox_id,
            payload={**payload, "result": self._summarize_tool_payload(result)},
        )
        return result

    async def _ensure_tool_allowed(
        self,
        tool_name: str,
        *,
        task,
        run,
        subtask,
        sandbox_id: str | None,
        kwargs: dict[str, Any],
    ) -> None:
        selected_tools = set(subtask.metadata.get("selected_tools") or [])
        if selected_tools and tool_name not in selected_tools:
            await self._publish_policy_denied(
                task=task,
                run=run,
                subtask=subtask,
                sandbox_id=sandbox_id,
                payload={
                    "tool_name": tool_name,
                    "reason": "tool_not_allowlisted",
                    "selected_tools": sorted(selected_tools),
                },
            )
            raise PermissionError(f"Tool not allowed for subtask {subtask.name}: {tool_name}")

        if tool_name == "run_skill_script":
            try:
                self._ensure_skill_script_allowed(subtask, kwargs)
            except PermissionError as exc:
                await self._publish_policy_denied(
                    task=task,
                    run=run,
                    subtask=subtask,
                    sandbox_id=sandbox_id,
                    payload={
                        "tool_name": tool_name,
                        "reason": "skill_script_not_allowlisted",
                        "skill_name": str(kwargs.get("skill_name") or ""),
                        "script_path": str(kwargs.get("script_path") or ""),
                    },
                )
                raise exc

    def _ensure_skill_script_allowed(self, subtask, kwargs: dict[str, Any]) -> None:
        execution_profile = self._load_execution_profile(subtask)
        allowlist = execution_profile.allowed_skill_scripts
        if not allowlist:
            return

        skill_name = str(kwargs.get("skill_name") or "").strip()
        script_path = str(kwargs.get("script_path") or "").strip().lstrip("/")
        candidates = {f"{skill_name}:{script_path}", script_path}
        if skill_name:
            candidates.add(f"{skill_name}:*")
        if not any(candidate in allowlist for candidate in candidates):
            raise PermissionError(
                f"Skill script not allowed for subtask {subtask.name}: {skill_name}:{script_path}"
            )

    async def _publish_policy_denied(self, task, run, subtask, payload: dict[str, object], sandbox_id: str | None = None) -> None:
        await self._event_bus.publish(
            DomainEvent(
                event_id=str(uuid.uuid4()),
                topic="policy.denied",
                tenant_id=task.metadata.get("tenant_id", "local"),
                session_id=run.session_id,
                task_id=task.id,
                run_id=run.id,
                subtask_id=subtask.id,
                sandbox_id=sandbox_id,
                payload=payload,
            )
        )

    @staticmethod
    def _load_execution_profile(subtask) -> ExecutionProfile:
        raw_profile = subtask.metadata.get("execution_profile") or {}
        if isinstance(raw_profile, ExecutionProfile):
            return raw_profile
        if isinstance(raw_profile, dict):
            return ExecutionProfile.model_validate(raw_profile)
        return ExecutionProfile(role=subtask.role)

    @staticmethod
    def _effective_skill_profiles(execution_profile: ExecutionProfile, subtask) -> list[str]:
        if execution_profile.skill_profiles:
            return list(execution_profile.skill_profiles)
        if subtask.execution_configuration and subtask.execution_configuration.skill_profiles:
            return list(subtask.execution_configuration.skill_profiles)
        return []

    @staticmethod
    def _summarize_tool_payload(value: Any) -> Any:
        if value is None or isinstance(value, (int, float, bool)):
            return value
        if isinstance(value, str):
            return value[:300]
        if isinstance(value, list):
            return [ExecutionRunner._summarize_tool_payload(item) for item in value[:5]]
        if isinstance(value, dict):
            return {key: ExecutionRunner._summarize_tool_payload(item) for key, item in list(value.items())[:8]}
        if hasattr(value, "model_dump"):
            return ExecutionRunner._summarize_tool_payload(value.model_dump(mode="json"))
        return str(value)

    async def _store_artifact(self, task, run, subtask, artifact: Artifact, sandbox_id: str | None = None) -> None:
        await self._artifact_repository.create(artifact)
        await self._event_bus.publish(
            DomainEvent(
                event_id=str(uuid.uuid4()),
                topic="artifact.created",
                tenant_id=task.metadata.get("tenant_id", "local"),
                session_id=run.session_id,
                task_id=task.id,
                run_id=run.id,
                subtask_id=subtask.id,
                sandbox_id=sandbox_id,
                payload={
                    "artifact_id": artifact.id,
                    "name": artifact.name,
                    "type": artifact.type,
                },
            )
        )

    def _create_inline_artifact(
        self,
        *,
        task,
        run,
        subtask,
        name: str,
        artifact_type: ArtifactType,
        metadata: dict[str, object],
    ) -> Artifact:
        return Artifact(
            id=str(uuid.uuid4()),
            task_id=task.id,
            run_id=run.id,
            subtask_id=subtask.id,
            name=name,
            type=artifact_type,
            storage_ref=f"inline://runs/{run.id}/subtasks/{subtask.id}/{name}",
            metadata=metadata,
        )

    async def _lookup_memory_context(self, task, subtask) -> str:
        if self._long_term_memory is None:
            return ""
        run = await self._run_repository.get(subtask.metadata.get("run_id") or "")
        if run is None:
            return ""
        query = " ".join([task.goal, subtask.name, subtask.description])
        try:
            items = await self._run_tool(
                "memory_lookup",
                task=task,
                run=run,
                subtask=subtask,
                query=query,
                top_k=3,
            )
        except Exception:
            return ""
        if not items:
            return ""
        return "\n".join(f"- {str(item.get('content', ''))[:280]}" for item in items)

    async def _store_memory_for_subtask(self, task, run, subtask) -> None:
        if self._long_term_memory is None or subtask.status != SubTaskStatus.SUCCEEDED:
            return
        summary = self._summarize_subtask_memory(task, subtask)
        if not summary:
            return
        try:
            await self._run_tool(
                "memory_write",
                task=task,
                run=run,
                subtask=subtask,
                content=summary,
                metadata={
                    "task_id": task.id,
                    "run_id": run.id,
                    "subtask_id": subtask.id,
                    "role": str(subtask.role),
                },
            )
        except Exception:
            return

    @staticmethod
    def _summarize_subtask_memory(task, subtask) -> str:
        result = subtask.result or {}
        if subtask.role == AgentRole.REVIEWER:
            decision = result.get("decision")
            summary = result.get("summary")
            if not decision or not summary:
                return ""
            return f"Task goal: {task.goal}\nReview decision: {decision}\nSummary: {summary}"
        if subtask.role in {AgentRole.VERIFIER, AgentRole.TESTER}:
            passed = result.get("passed")
            summary = result.get("summary")
            if passed is None or not summary:
                return ""
            return f"Task goal: {task.goal}\nVerification passed: {passed}\nSummary: {summary}"
        if subtask.role in {
            AgentRole.CODER,
            AgentRole.WRITER,
            AgentRole.RESEARCHER,
            AgentRole.PLANNER,
        }:
            preview = result.get("stdout_preview") or subtask.description
            return f"Task goal: {task.goal}\nSubtask: {subtask.name}\nOutcome: {preview}"
        return ""

    @staticmethod
    def _resolve_sandbox_profile(task, subtask) -> str:
        execution_profile = subtask.metadata.get("execution_profile", {})
        if isinstance(execution_profile, dict):
            sandbox_profile = execution_profile.get("sandbox_profile")
            if isinstance(sandbox_profile, str) and sandbox_profile:
                return sandbox_profile
        if subtask.execution_configuration and subtask.execution_configuration.sandbox_profile:
            return subtask.execution_configuration.sandbox_profile
        return task.metadata.get("profile", "py-basic")

    async def _build_command_request(self, task, subtask) -> CommandRequest:
        should_fail = task.constraints.get("force_fail_subtask") == subtask.name
        content = await self._render_subtask_content(task, subtask)
        payload = {
            "task_id": task.id,
            "run_id": subtask.metadata.get("run_id"),
            "goal": task.goal,
            "subtask": subtask.name,
            "description": subtask.description,
            "acceptance_criteria": subtask.acceptance_criteria,
            "tool_groups": [group.value for group in self._load_execution_profile(subtask).required_tool_groups],
            "content": content,
        }
        payload_json = json.dumps(payload, ensure_ascii=False)
        python_code = [
            "import json, sys",
            "from pathlib import Path",
            f"payload = json.loads({payload_json!r})",
            "output_dir = Path('outputs')",
            "output_dir.mkdir(parents=True, exist_ok=True)",
            "filename = payload['subtask'].replace('/', '_') + '.md'",
            "output_path = output_dir / filename",
            "output_path.write_text(payload['content'], encoding='utf-8')",
            "print(payload['content'])",
            "print(f'WROTE_ARTIFACT_FILE={output_path}')",
            "print(json.dumps({'subtask': payload['subtask'], 'artifact_file': str(output_path)}, ensure_ascii=False))",
        ]
        if should_fail:
            python_code.extend(
                [
                    f"sys.stderr.write('forced failure for {subtask.name}\\n')",
                    "raise SystemExit(1)",
                ]
            )
        command = f"python3 -c {shlex.quote('; '.join(python_code))}"
        return CommandRequest(command=command, cwd=".")

    async def _render_subtask_content(self, task, subtask, run=None) -> str:
        content = await self._render_subtask_content_with_model(task, subtask, run=run)
        if content:
            return content
        return await self._render_subtask_content_template(task, subtask)  # TODO - remove 不能依赖模板，没有就retry，我们需要加入错误信息提示，方便后续优化

    async def _render_subtask_content_with_model(
        self,
        task,
        subtask,
        run=None,
        agent_profile_override: AgentProfile | None = None,
    ) -> str | None:
        prompt = await self._compose_subtask_prompt(task, subtask)
        result = await self._run_omni_agent_prompt(
            task=task,
            subtask=subtask,
            prompt=prompt,
            system_prompt=render_prompt(self._system_prompt_template),
            run=run,
            step_kind="content.render",
            agent_profile_override=agent_profile_override,
        )
        if result.content:
            current_profile = agent_profile_override or self._resolve_agent_profile_for_omni_agent(subtask)
            if current_profile is not None and run is not None:
                await self._complete_handoff_if_needed(task, run, subtask, current_profile)
        return result.content

    def _resolve_agent_profile_for_omni_agent(self, subtask) -> AgentProfile | None:
        execution_profile = self._load_execution_profile(subtask)
        if not execution_profile.agent_profile_id:
            return None
        return self._agent_profile_store.get(execution_profile.agent_profile_id)

    async def _run_omni_agent_prompt(
        self,
        *,
        task,
        subtask,
        prompt: str,
        system_prompt: str,
        step_kind: str,
        run=None,
        agent_profile_override: AgentProfile | None = None,
    ):
        current_run = run or await self._run_repository.get(subtask.metadata.get("run_id") or "")
        execution_profile = self._load_execution_profile(subtask)
        active_profile = agent_profile_override or self._agent_profile_store.get(execution_profile.agent_profile_id)
        tool_functions = self._build_agent_tool_functions(task, current_run, subtask) if current_run is not None else []
        skill_profiles = self._effective_skill_profiles(execution_profile, subtask)
        return await self._omni_agent.run(
            OmniAgentRequest(
                agent_name=f"subtask-{subtask.name}-{step_kind}",
                prompt=prompt,
                system_prompt=system_prompt,
                step_kind=step_kind,
                tool_functions=tool_functions,
                skill_profiles=skill_profiles,
                agent_profile=active_profile,
                execution_profile=execution_profile,
            ),
            publisher=(
                None
                if current_run is None
                else lambda topic, payload: self._publish_agent_step_event(
                    topic=topic,
                    task=task,
                    run=current_run,
                    subtask=subtask,
                    payload=payload,
                )
            ),
        )

    async def _publish_agent_step_event(self, topic: str, task, run, subtask, payload: dict[str, object]) -> None:
        await self._event_bus.publish(
            DomainEvent(
                event_id=str(uuid.uuid4()),
                topic=topic,
                tenant_id=task.metadata.get("tenant_id", "local"),
                session_id=run.session_id,
                task_id=task.id,
                run_id=run.id,
                subtask_id=subtask.id,
                payload=payload,
            )
        )

    async def _complete_handoff_if_needed(self, task, run, subtask, active_profile: AgentProfile) -> None:
        handoff = subtask.metadata.get("handoff") if isinstance(subtask.metadata.get("handoff"), dict) else None
        if not handoff or handoff.get("status") != "started" or not subtask.agent_profile_id:
            return
        handoff["status"] = "completed"
        await self._subtask_repository.save(subtask)
        await self._publish_handoff_event(
            topic="agent.handoff.completed",
            task=task,
            run=run,
            subtask=subtask,
            payload={
                "from_agent_profile_id": handoff.get("from_agent_profile_id", subtask.agent_profile_id),
                "to_agent_profile_id": active_profile.id,
                "depth": handoff.get("depth", 1),
                "context_mode": handoff.get("context_mode", HandoffContextMode.SUMMARY.value),
            },
        )

    def _build_agent_tool_functions(self, task, run, subtask) -> list[Any]:
        selected_tools = set(subtask.metadata.get("selected_tools") or [])
        tools: list[Any] = []

        def register(name: str, description: str, func: Any) -> None:
            func.__name__ = name
            func.__doc__ = description
            contract = self._tool_registry.get_tool_contract(name)
            if contract is not None:
                setattr(func, "__swarmmind_tool_contract__", contract.model_copy(deep=True))
            groups = self._tool_registry.get_tool_groups(name)
            if groups:
                setattr(func, "__swarmmind_tool_groups__", tuple(groups))
            tools.append(func)

        if "read_file" in selected_tools:
            async def read_file(path: str, encoding: str = "utf-8") -> str:
                return await self._run_tool("read_file", task=task, run=run, subtask=subtask, path=path, encoding=encoding)
            register("read_file", "Read a workspace file.", read_file)

        if "write_file" in selected_tools:
            async def write_file(path: str, content: str, encoding: str = "utf-8") -> str:
                return await self._run_tool(
                    "write_file",
                    task=task,
                    run=run,
                    subtask=subtask,
                    path=path,
                    content=content,
                    encoding=encoding,
                )
            register("write_file", "Write a workspace file.", write_file)

        if "list_files" in selected_tools:
            async def list_files(path: str = ".") -> str:
                return await self._run_tool("list_files", task=task, run=run, subtask=subtask, path=path)
            register("list_files", "List workspace files.", list_files)

        if "file_exists" in selected_tools:
            async def file_exists(path: str) -> str:
                return await self._run_tool("file_exists", task=task, run=run, subtask=subtask, path=path)
            register("file_exists", "Check whether a workspace path exists.", file_exists)

        if "delete_file" in selected_tools:
            async def delete_file(path: str) -> str:
                return await self._run_tool("delete_file", task=task, run=run, subtask=subtask, path=path)
            register("delete_file", "Delete a workspace file or directory.", delete_file)

        if "rename_file" in selected_tools:
            async def rename_file(source_path: str, destination_path: str) -> str:
                return await self._run_tool(
                    "rename_file",
                    task=task,
                    run=run,
                    subtask=subtask,
                    source_path=source_path,
                    destination_path=destination_path,
                )
            register("rename_file", "Rename or move a workspace file or directory.", rename_file)

        if "make_directory" in selected_tools:
            async def make_directory(path: str) -> str:
                return await self._run_tool("make_directory", task=task, run=run, subtask=subtask, path=path)
            register("make_directory", "Create a workspace directory recursively.", make_directory)

        if "glob_search" in selected_tools:
            async def glob_search(pattern: str, base_path: str = ".", max_results: int = 200) -> list[str]:
                return await self._run_tool(
                    "glob_search",
                    task=task,
                    run=run,
                    subtask=subtask,
                    pattern=pattern,
                    base_path=base_path,
                    max_results=max_results,
                )
            register("glob_search", "Find workspace files by glob pattern.", glob_search)

        if "grep_search" in selected_tools:
            async def grep_search(
                query: str,
                base_path: str = ".",
                include_pattern: str = "**/*",
                is_regex: bool = False,
                max_results: int = 50,
            ) -> list[dict[str, object]]:
                return await self._run_tool(
                    "grep_search",
                    task=task,
                    run=run,
                    subtask=subtask,
                    query=query,
                    base_path=base_path,
                    include_pattern=include_pattern,
                    is_regex=is_regex,
                    max_results=max_results,
                )
            register("grep_search", "Search text content inside workspace files.", grep_search)

        if "web_search" in selected_tools:
            async def web_search(query: str, max_results: int = 5, provider: str | None = None) -> str:
                return await self._run_tool(
                    "web_search",
                    task=task,
                    run=run,
                    subtask=subtask,
                    query=query,
                    max_results=max_results,
                    provider=provider,
                )
            register(
                "web_search",
                "Search public web result pages. Use this to find candidate URLs and snippets, not to read full page details.",
                web_search,
            )

        if "browser_get" in selected_tools:
            async def browser_get(url: str, detail_provider: str | None = None) -> str:
                return await self._run_tool(
                    "browser_get",
                    task=task,
                    run=run,
                    subtask=subtask,
                    url=url,
                    detail_provider=detail_provider,
                )
            register(
                "browser_get",
                "Fetch one known page URL and extract detail content. Use this after search when you already know which page to inspect.",
                browser_get,
            )

        if "browser_screenshot" in selected_tools:
            async def browser_screenshot(url: str) -> str:
                return await self._run_tool("browser_screenshot", task=task, run=run, subtask=subtask, url=url)
            register("browser_screenshot", "Capture a webpage screenshot placeholder.", browser_screenshot)

        if "browser_playwright" in selected_tools:
            async def browser_playwright(
                url: str,
                action: str = "inspect",
                wait_until: str = "networkidle",
                timeout_seconds: int = 30000,
                selector: str | None = None,
                full_page: bool = True,
                sandbox_profile: str | None = None,
            ) -> dict[str, Any]:
                return await self._run_tool(
                    "browser_playwright",
                    task=task,
                    run=run,
                    subtask=subtask,
                    url=url,
                    action=action,
                    wait_until=wait_until,
                    timeout_seconds=timeout_seconds,
                    selector=selector,
                    full_page=full_page,
                    sandbox_profile=sandbox_profile,
                )
            register(
                "browser_playwright",
                "Use Playwright inside a sandbox for dynamic browser inspection or screenshots. This tool is sandbox-only.",
                browser_playwright,
            )

        if "send_mail" in selected_tools:
            async def send_mail(
                to: str,
                subject: str,
                body: str,
                from_addr: str | None = None,
                smtp_host: str = "smtp.gmail.com",
                smtp_port: int = 587,
                username: str | None = None,
                password: str | None = None,
            ) -> str:
                return await self._run_tool(
                    "send_mail",
                    task=task,
                    run=run,
                    subtask=subtask,
                    to=to,
                    subject=subject,
                    body=body,
                    from_addr=from_addr,
                    smtp_host=smtp_host,
                    smtp_port=smtp_port,
                    username=username,
                    password=password,
                )
            register("send_mail", "Send an email through configured SMTP.", send_mail)

        if "memory_lookup" in selected_tools:
            async def memory_lookup(query: str, top_k: int = 3) -> list[dict[str, Any]]:
                return await self._run_tool("memory_lookup", task=task, run=run, subtask=subtask, query=query, top_k=top_k)
            register("memory_lookup", "Retrieve related long-term memory items.", memory_lookup)

        if "memory_write" in selected_tools:
            async def memory_write(content: str, metadata: dict[str, Any] | None = None) -> str | None:
                return await self._run_tool(
                    "memory_write",
                    task=task,
                    run=run,
                    subtask=subtask,
                    content=content,
                    metadata=metadata,
                )
            register("memory_write", "Store a concise long-term memory summary.", memory_write)

        if "artifact_read" in selected_tools:
            dependency_ids = list(subtask.dependencies)

            async def artifact_read() -> list[dict[str, object]]:
                artifacts = await self._run_tool(
                    "artifact_read",
                    task=task,
                    run=run,
                    subtask=subtask,
                    run_id=run.id,
                    dependency_ids=dependency_ids,
                )
                return self._summarize_artifacts(artifacts)
            register("artifact_read", "Read artifacts associated with dependency subtasks.", artifact_read)

        if "list_skill_scripts" in selected_tools:
            async def list_skill_scripts(skill_name: str) -> list[str]:
                return await self._run_tool("list_skill_scripts", task=task, run=run, subtask=subtask, skill_name=skill_name)
            register("list_skill_scripts", "List declared scripts for a skill package.", list_skill_scripts)

        if "get_skill_details" in selected_tools:
            async def get_skill_details(skill_name: str) -> dict[str, object]:
                return await self._run_tool("get_skill_details", task=task, run=run, subtask=subtask, skill_name=skill_name)
            register("get_skill_details", "Inspect expanded metadata and resources for a skill package.", get_skill_details)

        if "run_skill_script" in selected_tools:
            async def run_skill_script(
                skill_name: str,
                script_path: str,
                sandbox_profile: str = "py-basic",
                sandbox_root: str = "/workspace/skill",
                allow_sandbox_exec: bool = False,
                environment: dict[str, str] | None = None,
                artifact_paths: list[str] | None = None,
            ) -> dict[str, object]:
                return await self._run_tool(
                    "run_skill_script",
                    task=task,
                    run=run,
                    subtask=subtask,
                    skill_name=skill_name,
                    script_path=script_path,
                    sandbox_profile=sandbox_profile,
                    sandbox_root=sandbox_root,
                    allow_sandbox_exec=allow_sandbox_exec,
                    environment=environment,
                    artifact_paths=artifact_paths,
                    tenant_id=task.metadata.get("tenant_id", "local"),
                    session_id=run.session_id,
                    task_id=task.id,
                    run_id=run.id,
                    subtask_id=subtask.id,
                )
            register("run_skill_script", "Execute a declared skill script inside a sandbox with audit context.", run_skill_script)

        return tools

    async def _compose_subtask_prompt(self, task, subtask) -> str:
        prompt = render_prompt(
            self._user_prompt_template,
            {
                "task_goal": task.goal,
                "subtask_name": subtask.name,
                "subtask_description": subtask.description,
                "acceptance_criteria_json": json.dumps(subtask.acceptance_criteria, ensure_ascii=False),
                "constraints_json": json.dumps(task.constraints, ensure_ascii=False),
                "tool_groups_json": json.dumps(
                    [group.value for group in self._load_execution_profile(subtask).required_tool_groups],
                    ensure_ascii=False,
                ),
            },
        )
        memory_context = await self._lookup_memory_context(task, subtask)
        if not memory_context:
            return prompt
        return f"{prompt}\n\nRelevant long-term memory:\n{memory_context}"

    async def _render_subtask_content_template(self, task, subtask) -> str:
        criteria = "\\n".join(f"- {item}" for item in subtask.acceptance_criteria) or "- None"
        constraints = json.dumps(task.constraints, ensure_ascii=False, indent=2)
        prompt = render_prompt(
            self._fallback_content_template,
            {
                "subtask_name": subtask.name,
                "subtask_description": subtask.description,
                "task_goal": task.goal,
                "acceptance_criteria_lines": criteria,
                "constraints_json_pretty": constraints,
            },
        )
        memory_context = await self._lookup_memory_context(task, subtask)
        if not memory_context:
            return prompt
        return f"{prompt}\n\nRelevant long-term memory:\n{memory_context}"

    async def _tool_sandbox_exec(self, lease, command_request, **_: Any):
        return await self._sandbox_manager.execute(lease, command_request)

    async def _tool_browser_playwright(
        self,
        url: str,
        action: str = "inspect",
        wait_until: str = "networkidle",
        timeout_seconds: int = 30000,
        selector: str | None = None,
        full_page: bool = True,
        sandbox_profile: str | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        profile = sandbox_profile or "browser-playwright"
        lease = await self._sandbox_manager.acquire(
            SandboxLeaseRequest(
                profile=profile,
                task_id="browser-playwright",
                run_id="browser-playwright",
                subtask_id="browser-playwright",
            )
        )
        script_payload = json.dumps(
            {
                "url": url,
                "action": action,
                "wait_until": wait_until,
                "timeout_ms": timeout_seconds,
                "selector": selector,
                "full_page": full_page,
            },
            ensure_ascii=False,
        )
        command = "\n".join(
            [
                "python - <<'PY'",
                "import asyncio, json",
                "from pathlib import Path",
                "from playwright.async_api import async_playwright",
                f"payload = json.loads({script_payload!r})",
                "async def main():",
                "    async with async_playwright() as playwright:",
                "        browser = await playwright.chromium.launch(headless=True)",
                "        page = await browser.new_page()",
                "        await page.goto(payload['url'], wait_until=payload['wait_until'], timeout=payload['timeout_ms'])",
                "        selector = payload.get('selector')",
                "        if selector:",
                "            await page.locator(selector).first.wait_for(state='visible', timeout=payload['timeout_ms'])",
                "        title = await page.title()",
                "        body_text = await page.locator('body').inner_text()",
                "        screenshot_path = None",
                "        if payload['action'] == 'screenshot':",
                "            artifact_dir = Path('/tmp/browser-playwright')",
                "            artifact_dir.mkdir(parents=True, exist_ok=True)",
                "            screenshot_path = artifact_dir / 'screenshot.png'",
                "            await page.screenshot(path=str(screenshot_path), full_page=bool(payload.get('full_page', True)))",
                "        await browser.close()",
                "        print(json.dumps({",
                "            'url': payload['url'],",
                "            'action': payload['action'],",
                "            'title': title,",
                "            'text_preview': body_text[:4000],",
                "            'screenshot_path': str(screenshot_path) if screenshot_path else None,",
                "        }, ensure_ascii=False))",
                "asyncio.run(main())",
                "PY",
            ]
        )
        try:
            execution = await self._sandbox_manager.execute(lease, CommandRequest(command=command, cwd="/tmp"))
            if execution.exit_code != 0:
                raise RuntimeError(execution.stderr or execution.stdout or f"Playwright command failed with exit code {execution.exit_code}")
            stdout = execution.stdout.strip()
            result = json.loads(stdout.splitlines()[-1]) if stdout else {}
            if not isinstance(result, dict):
                return {"stdout": stdout}
            screenshot_path = result.get("screenshot_path")
            if isinstance(screenshot_path, str) and screenshot_path:
                result["screenshot_name"] = PurePosixPath(screenshot_path).name
            return result
        finally:
            await self._sandbox_manager.release(lease.lease_id)

    async def _tool_artifact_read(self, run_id: str, dependency_ids: list[str], **_: Any) -> list[Artifact]:
        artifacts = await self._artifact_repository.list_for_run(run_id)
        dependency_set = set(dependency_ids)
        return [artifact for artifact in artifacts if artifact.subtask_id in dependency_set]

    async def _tool_memory_lookup(self, query: str, top_k: int = 3, **_: Any) -> list[dict[str, Any]]:
        if self._long_term_memory is None:
            return []
        items = await self._long_term_memory.retrieve(query, top_k=top_k)
        return [
            {
                "id": item.id,
                "content": item.content,
                "score": item.score,
                "metadata": item.metadata,
            }
            for item in items
        ]

    async def _tool_memory_write(self, content: str, metadata: dict[str, Any] | None = None, **_: Any) -> str | None:
        if self._long_term_memory is None:
            return None
        return await self._long_term_memory.store(content, metadata=metadata)
