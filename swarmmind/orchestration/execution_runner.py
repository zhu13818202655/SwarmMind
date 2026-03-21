"""Execution runner for assigned subtasks."""

from __future__ import annotations

import json
import shlex
import uuid

from agentscope.message import Msg

from swarmmind.agents.config import AgentConfig, AgentScopeConfig
from swarmmind.agents.factory import AgentFactory
from swarmmind.events import EventBus
from swarmmind.models.event import DomainEvent
from swarmmind.models.task import TaskStatus
from swarmmind.orchestration.run_state_service import RunStateService
from swarmmind.repositories import ArtifactRepository, RunRepository, SubTaskRepository, TaskRepository
from swarmmind.sandbox import CommandRequest, SandboxLeaseRequest, SandboxManager
from swarmmind.sandbox.artifact_collector import ArtifactCollector
from swarmmind.prompt_template import load_prompt_template, render_prompt_template
from swarmmind.utils import utc_now


class ExecutionRunner:
    """Consume assigned subtasks and execute them inside sandboxes."""

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
        model_name: str = "gpt-4o",
        model_api_key: str | None = None,
        model_base_url: str | None = None,
        model_temperature: float = 0.2,
        model_max_tokens: int = 2048,
        system_prompt_template_name: str = "execution_system_v1.txt",
        user_prompt_template_name: str = "execution_subtask_markdown_v1.md",
        fallback_content_template_name: str = "execution_fallback_content_v1.md",
    ):
        self._task_repository = task_repository
        self._run_repository = run_repository
        self._subtask_repository = subtask_repository
        self._artifact_repository = artifact_repository
        self._event_bus = event_bus
        self._sandbox_manager = sandbox_manager
        self._artifact_collector = artifact_collector
        self._run_state_service = run_state_service
        self._model_name = model_name
        self._model_api_key = model_api_key
        self._model_base_url = model_base_url
        self._model_temperature = model_temperature
        self._model_max_tokens = model_max_tokens
        self._system_prompt_template_name = system_prompt_template_name
        self._user_prompt_template_name = user_prompt_template_name
        self._fallback_content_template_name = fallback_content_template_name

    async def handle_subtask_assigned(self, event: DomainEvent) -> None:
        """Execute an assigned subtask and persist its evidence."""
        if not event.subtask_id or not event.run_id or not event.task_id:
            return

        task = await self._task_repository.get(event.task_id)
        run = await self._run_repository.get(event.run_id)
        subtask = await self._subtask_repository.get(event.subtask_id)
        if task is None or run is None or subtask is None:
            return

        if subtask.status in {TaskStatus.RUNNING, TaskStatus.SUCCEEDED, TaskStatus.FAILED}:
            return

        lease = None
        try:
            subtask.status = TaskStatus.RUNNING
            subtask.metadata["started_at"] = utc_now().isoformat()
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
            await self._subtask_repository.save(subtask)

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

            execution = await self._sandbox_manager.execute(lease, command_request)
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
                await self._artifact_repository.create(artifact)
                await self._event_bus.publish(
                    DomainEvent(
                        event_id=str(uuid.uuid4()),
                        topic="artifact.created",
                        tenant_id=task.metadata.get("tenant_id", event.tenant_id),
                        session_id=run.session_id,
                        task_id=task.id,
                        run_id=run.id,
                        subtask_id=subtask.id,
                        sandbox_id=lease.sandbox_id,
                        payload={
                            "artifact_id": artifact.id,
                            "name": artifact.name,
                            "type": artifact.type,
                        },
                    )
                )

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
        except Exception as exc:
            subtask.fail(str(exc))
            await self._subtask_repository.save(subtask)
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
            if lease is not None:
                await self._sandbox_manager.release(lease.lease_id)

            await self._run_state_service.reconcile(run.id)

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
        return self._render_subtask_content_template(task, subtask)

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
                )
            )
            agent = agent_factory.create_main_agent(tools=[])
            prompt = self._compose_subtask_prompt(task, subtask)
            result = await agent(Msg(name="user", role="user", content=prompt))
            text = result.get_text_content()
            if text and text.strip():
                return text.strip()
            return json.dumps(result.to_dict(), ensure_ascii=False, indent=2)
        except Exception:
            return None

    def _compose_subtask_prompt(self, task, subtask) -> str:
        return render_prompt_template(
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

    def _render_subtask_content_template(self, task, subtask) -> str:
        criteria = "\\n".join(f"- {item}" for item in subtask.acceptance_criteria) or "- None"
        constraints = json.dumps(task.constraints, ensure_ascii=False, indent=2)
        return render_prompt_template(
            self._fallback_content_template_name,
            {
                "subtask_name": subtask.name,
                "subtask_description": subtask.description,
                "task_goal": task.goal,
                "acceptance_criteria_lines": criteria,
                "constraints_json_pretty": constraints,
            },
        )