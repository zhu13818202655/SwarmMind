"""Execution runner for assigned subtasks."""

from __future__ import annotations

import json
import shlex
import uuid
from typing import Any

from agentscope.message import Msg

from swarmmind.agents.config import AgentConfig, AgentScopeConfig
from swarmmind.agents.factory import AgentFactory
from swarmmind.execution_strategies import CallbackStrategy, ExecutionStrategyRegistry, StrategyResult
from swarmmind.events import EventBus
from swarmmind.memory import LongTermMemoryBase
from swarmmind.models.artifact import Artifact, ArtifactType
from swarmmind.models.capability import AgentRole
from swarmmind.models.event import DomainEvent
from swarmmind.models.execution import (
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
        names: list[str] = []
        required_groups = {group.value for group in subtask.required_tool_groups}
        for metadata in self._tool_registry.get_tool_metadata():
            groups = set(metadata.get("groups", []))
            if not required_groups or groups.intersection(required_groups):
                names.append(str(metadata.get("name")))
        if subtask.role in {AgentRole.CODER, AgentRole.EXECUTOR, AgentRole.WRITER, AgentRole.RESEARCHER, AgentRole.PLANNER}:
            names.append("sandbox_exec")
        if subtask.role in {AgentRole.TESTER, AgentRole.REVIEWER}:
            names.append("artifact_read")
        return sorted(set(names))

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

    async def _render_subtask_content_with_model(self, task, subtask) -> str | None:
        if not self._model_name:
            return None
        if not self._model_api_key and not self._model_base_url:
            return None

        try:
            agent_factory = AgentFactory(
                AgentConfig(
                    name=f"subtask-{subtask.name}",
                    scope_config=AgentScopeConfig(
                        model_name=self._model_name,
                        api_key=self._model_api_key,
                        base_url=self._model_base_url,
                        temperature=self._model_temperature,
                        max_tokens=self._model_max_tokens,
                    ),
                    max_steps=6,
                    system_prompt=load_prompt_template(self._system_prompt_template_name),
                    skill_profiles=[self._resolve_strategy_name(subtask)],
                )
            )
            agent = agent_factory.create_main_agent(tools=[])
            prompt = await self._compose_subtask_prompt(task, subtask)
            result = await agent(Msg(name="user", role="user", content=prompt))
            text = result.get_text_content()
            if text and text.strip():
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
