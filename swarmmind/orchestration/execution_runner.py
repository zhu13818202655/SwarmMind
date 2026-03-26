"""Execution runner for assigned subtasks."""

from __future__ import annotations

import json
import shlex
import uuid
from typing import Any

from agentscope.message import Msg

from swarmmind.agents import AgentProfileStore
from swarmmind.agents.config import AgentConfig, AgentScopeConfig
from swarmmind.agents.factory import AgentFactory
from swarmmind.execution_strategies import CallbackStrategy, ExecutionStrategyRegistry, StrategyResult
from swarmmind.events import EventBus
from swarmmind.memory import LongTermMemoryBase
from swarmmind.models.artifact import Artifact, ArtifactType
from swarmmind.models.agent_profile import AgentProfile, HandoffContextMode
from swarmmind.models.capability import AgentRole
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
from swarmmind.prompt_template import load_prompt_template, render_prompt_template
from swarmmind.repositories import ArtifactRepository, RunRepository, SubTaskRepository, TaskRepository
from swarmmind.sandbox import CommandRequest, SandboxLeaseRequest, SandboxManager
from swarmmind.sandbox.artifact_collector import ArtifactCollector
from swarmmind.skill_system import SkillExecutionService
from swarmmind.tools import ToolRegistry
from swarmmind.tools.builtin import (
    SkillTool,
    browser_get,
    file_exists,
    list_files,
    read_file,
    search,
    write_file,
)


class ExecutionRunner:
    """Consume assigned subtasks and execute them via runtime strategies and tools."""

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
        execution_strategy_registry: ExecutionStrategyRegistry,
        tool_registry: ToolRegistry,
        agent_profile_store: AgentProfileStore,
        skill_execution_service: SkillExecutionService | None = None,
        model_name: str = "gpt-4o",
        model_api_key: str | None = None,
        model_base_url: str | None = None,
        model_temperature: float = 0.2,
        model_max_tokens: int = 2048,
        system_prompt_template_name: str = "execution_system_v1.txt",
        user_prompt_template_name: str = "execution_subtask_markdown_v1.md",
        fallback_content_template_name: str = "execution_fallback_content_v1.md",
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
        self._execution_strategy_registry = execution_strategy_registry
        self._tool_registry = tool_registry
        self._agent_profile_store = agent_profile_store
        self._skill_execution_service = skill_execution_service
        self._model_name = model_name
        self._model_api_key = model_api_key
        self._model_base_url = model_base_url
        self._model_temperature = model_temperature
        self._model_max_tokens = model_max_tokens
        self._system_prompt_template_name = system_prompt_template_name
        self._user_prompt_template_name = user_prompt_template_name
        self._fallback_content_template_name = fallback_content_template_name
        self._long_term_memory = long_term_memory
        self._register_default_tools()
        self._register_default_strategies()

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
            resolved_strategy_name = self._resolve_strategy_name(subtask)
            subtask.metadata["resolved_strategy_name"] = resolved_strategy_name
            subtask.metadata["selected_tools"] = self._select_tool_names(subtask)
            await self._subtask_repository.save(subtask)

            await self._publish_strategy_event(
                topic="strategy.started",
                task=task,
                run=run,
                subtask=subtask,
                payload={
                    "strategy_name": resolved_strategy_name,
                    "role": subtask.role,
                    "selected_tools": subtask.metadata["selected_tools"],
                },
            )

            await self._execute_subtask_via_strategy(task, run, subtask, event)

            await self._publish_strategy_event(
                topic="strategy.completed",
                task=task,
                run=run,
                subtask=subtask,
                payload={
                    "strategy_name": resolved_strategy_name,
                    "role": subtask.role,
                    "status": subtask.status,
                },
            )
        except Exception as exc:
            subtask.fail(str(exc))
            await self._subtask_repository.save(subtask)
            await self._publish_strategy_event(
                topic="strategy.failed",
                task=task,
                run=run,
                subtask=subtask,
                payload={"strategy_name": self._resolve_strategy_name(subtask), "error": str(exc)},
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
        finally:
            await self._run_state_service.reconcile(run.id)

    async def _execute_subtask_via_strategy(self, task, run, subtask, event: DomainEvent) -> StrategyResult:
        strategy_name = self._resolve_strategy_name(subtask)
        result = await self._execution_strategy_registry.execute(
            strategy_name,
            task=task,
            run=run,
            subtask=subtask,
            event=event,
        )
        if not result.success and subtask.status not in {SubTaskStatus.SUCCEEDED, SubTaskStatus.FAILED}:
            raise RuntimeError(result.error or f"Strategy execution failed: {strategy_name}")
        return result

    def _resolve_strategy_name(self, subtask) -> str:
        if subtask.preferred_strategy and self._execution_strategy_registry.get(subtask.preferred_strategy):
            return subtask.preferred_strategy
        defaults = {
            AgentRole.TESTER: "verification",
            AgentRole.REVIEWER: "review",
            AgentRole.WRITER: "write_report",
            AgentRole.RESEARCHER: "research",
            AgentRole.PLANNER: "task_planning",
        }
        return defaults.get(subtask.role, "build_app")

    def _select_tool_names(self, subtask) -> list[str]:
        execution_profile = self._load_execution_profile(subtask)
        names: list[str] = []
        required_groups = {group.value for group in subtask.required_tool_groups}
        allowed_groups = {group.value for group in execution_profile.allowed_tool_groups}
        explicit_allowed_names = set(execution_profile.allowed_tool_names)
        for metadata in self._tool_registry.get_tool_metadata():
            groups = set(metadata.get("groups", []))
            tool_name = str(metadata.get("name"))
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
        strategy_name = self._resolve_strategy_name(subtask)
        required: set[str] = set()
        if strategy_name in {"build_app", "research", "write_report", "task_planning"}:
            required.add("sandbox_exec")
        if strategy_name in {"verification", "review"}:
            required.add("artifact_read")
        if self._long_term_memory is not None and subtask.role in {
            AgentRole.PLANNER,
            AgentRole.CODER,
            AgentRole.EXECUTOR,
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

    def _register_default_tools(self) -> None:
        existing = set(self._tool_registry.get_tool_names())
        if "sandbox_exec" not in existing:
            self._tool_registry.register(
                self._tool_sandbox_exec,
                name="sandbox_exec",
                description="Execute a command inside an acquired sandbox lease.",
                groups=["sandbox_exec"],
            )
        if "artifact_read" not in existing:
            self._tool_registry.register(
                self._tool_artifact_read,
                name="artifact_read",
                description="Read artifacts associated with dependency subtasks.",
                groups=["artifact_read"],
            )
        if "memory_lookup" not in existing:
            self._tool_registry.register(
                self._tool_memory_lookup,
                name="memory_lookup",
                description="Retrieve related long-term memory items.",
                groups=["memory_lookup"],
            )
        if "memory_write" not in existing:
            self._tool_registry.register(
                self._tool_memory_write,
                name="memory_write",
                description="Store a concise long-term memory summary.",
                groups=["memory_lookup"],
            )
        if "project_read" not in existing:
            self._tool_registry.register(read_file, name="project_read", description="Read a project file.", groups=["project_read"])
        if "project_write" not in existing:
            self._tool_registry.register(write_file, name="project_write", description="Write a project file.", groups=["project_write"])
        if "project_list" not in existing:
            self._tool_registry.register(list_files, name="project_list", description="List project files.", groups=["project_read"])
        if "project_exists" not in existing:
            self._tool_registry.register(file_exists, name="project_exists", description="Check whether a project file exists.", groups=["project_read"])
        if "web_search" not in existing:
            self._tool_registry.register(search, name="web_search", description="Search the web.", groups=["web_search"])
        if "browser_read" not in existing:
            self._tool_registry.register(browser_get, name="browser_read", description="Fetch and summarize a webpage.", groups=["browser_read"])
        if self._skill_execution_service is not None:
            skill_tool = SkillTool(self._skill_execution_service)
            if "list_skill_scripts" not in existing:
                self._tool_registry.register(
                    skill_tool.list_skill_scripts,
                    name="list_skill_scripts",
                    description="List declared scripts for a skill package.",
                    groups=["project_read"],
                )
            if "get_skill_details" not in existing:
                self._tool_registry.register(
                    skill_tool.get_skill_details,
                    name="get_skill_details",
                    description="Inspect expanded metadata and resources for a skill package.",
                    groups=["project_read"],
                )
            if "run_skill_script" not in existing:
                self._tool_registry.register(
                    skill_tool.run_skill_script,
                    name="run_skill_script",
                    description="Execute a declared skill script inside a sandbox with audit context.",
                    groups=["sandbox_exec"],
                )

    def _register_default_strategies(self) -> None:
        defaults = {
            "build_app": ("Build application artifacts inside a sandbox.", self._strategy_execute_sandbox),
            "research": ("Research or summarize work inside a sandbox.", self._strategy_execute_sandbox),
            "write_report": ("Write a structured report artifact.", self._strategy_execute_sandbox),
            "task_planning": ("Analyze and summarize requirements as a task artifact.", self._strategy_execute_sandbox),
            "verification": ("Verify dependency outputs against acceptance criteria.", self._strategy_execute_verification),
            "review": ("Review verification evidence and decide accept/rework/escalate.", self._strategy_execute_review),
            "agent_backed": ("Run a controlled agent runtime backend with AgentProfile constraints.", self._strategy_execute_agent_backed),
        }
        for name, (description, handler) in defaults.items():
            if self._execution_strategy_registry.get(name) is None:
                self._execution_strategy_registry.register(CallbackStrategy(name=name, description=description, handler=handler))

    async def _strategy_execute_sandbox(self, **kwargs: Any) -> StrategyResult:
        await self._execute_sandbox_subtask(kwargs["task"], kwargs["run"], kwargs["subtask"], kwargs["event"])
        return StrategyResult(success=True, output=kwargs["subtask"].result, metadata={"runtime": "sandbox"})

    async def _strategy_execute_verification(self, **kwargs: Any) -> StrategyResult:
        await self._execute_validation_subtask(kwargs["task"], kwargs["run"], kwargs["subtask"], kwargs["event"])
        return StrategyResult(success=True, output=kwargs["subtask"].result, metadata={"runtime": "verification"})

    async def _strategy_execute_review(self, **kwargs: Any) -> StrategyResult:
        await self._execute_validation_subtask(kwargs["task"], kwargs["run"], kwargs["subtask"], kwargs["event"])
        return StrategyResult(success=True, output=kwargs["subtask"].result, metadata={"runtime": "review"})

    async def _strategy_execute_agent_backed(self, **kwargs: Any) -> StrategyResult:
        await self._execute_agent_backed_subtask(kwargs["task"], kwargs["run"], kwargs["subtask"], kwargs["event"])
        return StrategyResult(success=True, output=kwargs["subtask"].result, metadata={"runtime": "agent_backed"})

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

        if subtask.role == AgentRole.TESTER:
            verification = self._build_verification_result(subtask, dependencies, dependency_artifacts)
            subtask.complete(
                {
                    **verification.model_dump(mode="json"),
                    "verification_passed": verification.passed,
                }
            )
            artifact = self._create_inline_artifact(
                task=task,
                run=run,
                subtask=subtask,
                name=f"{subtask.name}-verification.json",
                artifact_type=ArtifactType.TEST_RESULT,
                metadata=verification.model_dump(mode="json"),
            )
        else:
            decision = self._build_review_decision(task, subtask, dependencies)
            subtask.complete(
                {
                    **decision.model_dump(mode="json"),
                    "verification_passed": all(
                        bool(dep.result and dep.result.get("passed"))
                        for dep in dependencies
                        if dep.role == AgentRole.TESTER
                    ),
                }
            )
            artifact = self._create_inline_artifact(
                task=task,
                run=run,
                subtask=subtask,
                name=f"{subtask.name}-review.json",
                artifact_type=ArtifactType.REPORT,
                metadata=decision.model_dump(mode="json"),
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

    async def _execute_agent_backed_subtask(self, task, run, subtask, event: DomainEvent) -> None:
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
                payload={
                    "name": subtask.name,
                    "role": subtask.role,
                    "agent_profile_id": subtask.agent_profile_id,
                },
            )
        )

        content = await self._render_agent_backed_content(task, run, subtask)
        artifact = self._create_inline_artifact(
            task=task,
            run=run,
            subtask=subtask,
            name=f"{subtask.name}-agent-backed.md",
            artifact_type=ArtifactType.REPORT,
            metadata={
                "agent_profile_id": subtask.agent_profile_id,
                "content": content,
                "strategy": "agent_backed",
                "handoff": subtask.metadata.get("handoff"),
            },
        )
        subtask.complete(
            {
                "agent_profile_id": subtask.agent_profile_id,
                "content_preview": content[:300],
                "strategy_backend": "agent_backed",
                "handoff": subtask.metadata.get("handoff"),
            }
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

    async def _render_agent_backed_content(self, task, run, subtask) -> str:
        execution_profile = self._load_execution_profile(subtask)
        source_profile = self._resolve_agent_profile_for_execution(execution_profile, subtask)
        target_profile = await self._resolve_handoff_profile(task, run, subtask, source_profile, execution_profile)
        active_profile = target_profile or source_profile

        content = await self._render_subtask_content_with_model(
            task,
            subtask,
            run=run,
            agent_profile_override=active_profile,
        )
        if content:
            return content
        return await self._render_agent_backed_fallback_content(task, run, subtask, source_profile, active_profile)

    def _resolve_agent_profile_for_execution(self, execution_profile: ExecutionProfile, subtask) -> AgentProfile:
        profile = self._agent_profile_store.get(execution_profile.agent_profile_id)
        if profile is not None:
            return profile
        return self._agent_profile_store.resolve_for_subtask(
            profile_id=subtask.agent_profile_id,
            role=subtask.role,
            preferred_strategy=self._resolve_strategy_name(subtask),
        )

    async def _resolve_handoff_profile(self, task, run, subtask, source_profile: AgentProfile, execution_profile: ExecutionProfile) -> AgentProfile | None:
        requested_target_id = self._resolve_handoff_target_profile_id(task, subtask)
        if not requested_target_id:
            return None

        handoff_policy = execution_profile.handoff_policy
        depth = int(subtask.metadata.get("handoff_depth") or 0)
        deny_reason: str | None = None
        if not handoff_policy.allow_handoff:
            deny_reason = "handoff_disabled"
        elif handoff_policy.allowed_targets and requested_target_id not in handoff_policy.allowed_targets:
            deny_reason = "handoff_target_not_allowed"
        elif depth >= handoff_policy.max_depth:
            deny_reason = "handoff_depth_exceeded"

        target_profile = self._agent_profile_store.get(requested_target_id)
        if target_profile is None:
            deny_reason = deny_reason or "handoff_target_not_found"

        if deny_reason is not None:
            await self._publish_handoff_denied(
                task=task,
                run=run,
                subtask=subtask,
                source_profile=source_profile,
                target_profile_id=requested_target_id,
                reason=deny_reason,
            )
            return None

        await self._publish_handoff_event(
            topic="agent.handoff.started",
            task=task,
            run=run,
            subtask=subtask,
            payload={
                "from_agent_profile_id": source_profile.id,
                "to_agent_profile_id": target_profile.id,
                "depth": depth + 1,
                "context_mode": handoff_policy.context_mode.value,
            },
        )
        subtask.metadata["handoff"] = {
            "from_agent_profile_id": source_profile.id,
            "to_agent_profile_id": target_profile.id,
            "depth": depth + 1,
            "context_mode": handoff_policy.context_mode.value,
            "status": "started",
        }
        subtask.metadata["handoff_depth"] = depth + 1
        await self._subtask_repository.save(subtask)
        return target_profile

    def _resolve_handoff_target_profile_id(self, task, subtask) -> str | None:
        handoff_requests = task.constraints.get("handoff_requests") or {}
        if isinstance(handoff_requests, dict):
            target = handoff_requests.get(subtask.name) or handoff_requests.get(subtask.id) or handoff_requests.get("*")
            if isinstance(target, str) and target.strip():
                return target.strip()
        direct_target = task.constraints.get("handoff_target_profile_id")
        if isinstance(direct_target, str) and direct_target.strip():
            return direct_target.strip()
        return None

    async def _publish_handoff_denied(self, task, run, subtask, source_profile: AgentProfile, target_profile_id: str, reason: str) -> None:
        payload = {
            "from_agent_profile_id": source_profile.id,
            "to_agent_profile_id": target_profile_id,
            "reason": reason,
        }
        await self._publish_handoff_event(
            topic="agent.handoff.denied",
            task=task,
            run=run,
            subtask=subtask,
            payload=payload,
        )
        await self._publish_policy_denied(task=task, run=run, subtask=subtask, payload={"reason": reason, **payload})

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

    async def _render_agent_backed_fallback_content(self, task, run, subtask, source_profile: AgentProfile, active_profile: AgentProfile) -> str:
        handoff = subtask.metadata.get("handoff") if isinstance(subtask.metadata.get("handoff"), dict) else None
        if handoff and handoff.get("status") == "started":
            handoff["status"] = "completed"
            await self._subtask_repository.save(subtask)
            await self._publish_handoff_event(
                topic="agent.handoff.completed",
                task=task,
                run=run,
                subtask=subtask,
                payload={
                    "from_agent_profile_id": source_profile.id,
                    "to_agent_profile_id": active_profile.id,
                    "depth": handoff.get("depth", 1),
                    "context_mode": handoff.get("context_mode", HandoffContextMode.SUMMARY.value),
                },
            )
        handoff_lines: list[str] = []
        if handoff:
            handoff_lines = [
                "Delegation:",
                f"- Source Profile: {source_profile.id}",
                f"- Active Profile: {active_profile.id}",
                f"- Handoff Depth: {handoff.get('depth', 0)}",
                f"- Context Mode: {handoff.get('context_mode', HandoffContextMode.SUMMARY.value)}",
            ]
        return "\n".join(
            [
                f"# Agent-Backed Execution: {subtask.name}",
                f"Task Goal: {task.goal}",
                f"Subtask Description: {subtask.description}",
                f"Source Agent Profile: {source_profile.id}",
                f"Active Agent Profile: {active_profile.id}",
                *(handoff_lines or []),
                "Acceptance Criteria:",
                *[f"- {criterion}" for criterion in subtask.acceptance_criteria],
            ]
        )

    async def _load_dependency_subtasks(self, run_id: str, subtask) -> list:
        run_subtasks = await self._subtask_repository.list_for_run(run_id)
        subtask_map = {item.id: item for item in run_subtasks}
        return [subtask_map[dependency] for dependency in subtask.dependencies if dependency in subtask_map]

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
            tester_results = [dependency for dependency in dependencies if dependency.role == AgentRole.TESTER]
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

    async def _publish_strategy_event(self, topic: str, task, run, subtask, payload: dict[str, object]) -> None:
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
        if subtask.role in {AgentRole.CODER, AgentRole.EXECUTOR, AgentRole.WRITER, AgentRole.RESEARCHER, AgentRole.PLANNER}:
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
        return subtask.sandbox_profile or task.metadata.get("profile", "py-basic")

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
            "tool_groups": [str(group) for group in subtask.required_tool_groups],
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

    async def _render_subtask_content(self, task, subtask) -> str:
        generated = await self._render_subtask_content_with_model(task, subtask)
        if generated:
            return generated
        return await self._render_subtask_content_template(task, subtask)

    async def _render_subtask_content_with_model(
        self,
        task,
        subtask,
        run=None,
        agent_profile_override: AgentProfile | None = None,
    ) -> str | None:
        if not self._model_name:
            return None
        if not self._model_api_key and not self._model_base_url:
            return None

        try:
            execution_profile = self._load_execution_profile(subtask)
            agent_profile = agent_profile_override or self._agent_profile_store.get(execution_profile.agent_profile_id)
            agent_factory = AgentFactory(
                AgentConfig(
                    name=f"subtask-{subtask.name}",
                    scope_config=AgentScopeConfig(
                        model_name=agent_profile.preferred_model if agent_profile and agent_profile.preferred_model else self._model_name,
                        api_key=self._model_api_key,
                        base_url=agent_profile.preferred_endpoint if agent_profile and agent_profile.preferred_endpoint else self._model_base_url,
                        temperature=self._model_temperature,
                        max_tokens=self._model_max_tokens,
                    ),
                    max_steps=6,
                    system_prompt=load_prompt_template(self._system_prompt_template_name),
                    skill_profiles=execution_profile.skill_profiles or [self._resolve_strategy_name(subtask)],
                )
            )
            if agent_profile is not None:
                agent = agent_factory.create_profile_agent(
                    agent_profile,
                    tools=[],
                    system_prompt=load_prompt_template(self._system_prompt_template_name),
                )
            else:
                agent = agent_factory.create_main_agent(tools=[])
            prompt = await self._compose_subtask_prompt(task, subtask)
            result = await agent(Msg(name="user", role="user", content=prompt))
            text = result.get_text_content()
            if text and text.strip():
                handoff = subtask.metadata.get("handoff") if isinstance(subtask.metadata.get("handoff"), dict) else None
                if handoff and handoff.get("status") == "started" and agent_profile is not None and subtask.agent_profile_id:
                    handoff["status"] = "completed"
                    await self._subtask_repository.save(subtask)
                    current_run = run or await self._run_repository.get(subtask.metadata.get("run_id") or "")
                    if current_run is not None:
                        await self._publish_handoff_event(
                            topic="agent.handoff.completed",
                            task=task,
                            run=current_run,
                            subtask=subtask,
                            payload={
                                "from_agent_profile_id": handoff.get("from_agent_profile_id", subtask.agent_profile_id),
                                "to_agent_profile_id": agent_profile.id,
                                "depth": handoff.get("depth", 1),
                                "context_mode": handoff.get("context_mode", HandoffContextMode.SUMMARY.value),
                            },
                        )
                return text.strip()
            return json.dumps(result.to_dict(), ensure_ascii=False, indent=2)
        except Exception:
            return None

    async def _compose_subtask_prompt(self, task, subtask) -> str:
        prompt = render_prompt_template(
            self._user_prompt_template_name,
            {
                "task_goal": task.goal,
                "subtask_name": subtask.name,
                "subtask_description": subtask.description,
                "acceptance_criteria_json": json.dumps(subtask.acceptance_criteria, ensure_ascii=False),
                "constraints_json": json.dumps(task.constraints, ensure_ascii=False),
                "tool_groups_json": json.dumps(
                    [str(group) for group in subtask.required_tool_groups],
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
        prompt = render_prompt_template(
            self._fallback_content_template_name,
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
