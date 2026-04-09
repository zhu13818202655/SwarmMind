"""Artifact collection helpers for sandbox executions."""

from __future__ import annotations

import uuid
from typing import Any

from swarmmind.models.artifact import Artifact, ArtifactType
from swarmmind.models.run import Run
from swarmmind.models.task import SubTask, Task
from swarmmind.sandbox.models import SandboxExecution, SandboxLease


class ArtifactCollector:
    """Transform sandbox execution results into artifact metadata."""

    def collect(
        self,
        task: Task,
        run: Run,
        subtask: SubTask,
        lease: SandboxLease,
        execution: SandboxExecution,
    ) -> list[Artifact]:
        """Return artifact metadata for a command execution."""
        artifacts: list[Artifact] = [
            self._create_artifact(
                task=task,
                run=run,
                subtask=subtask,
                name=f"{subtask.name}-execution-summary.json",
                artifact_type=ArtifactType.REPORT,
                storage_ref=f"inline://runs/{run.id}/subtasks/{subtask.id}/summary",
                metadata={
                    "source": "execution_summary",
                    "sandbox_id": lease.sandbox_id,
                    "lease_id": lease.lease_id,
                    "command": execution.command,
                    "exit_code": execution.exit_code,
                },
            )
        ]

        if execution.stdout:
            artifacts.append(
                self._create_artifact(
                    task=task,
                    run=run,
                    subtask=subtask,
                    name=f"{subtask.name}-stdout.log",
                    artifact_type=ArtifactType.LOG,
                    storage_ref=f"inline://runs/{run.id}/subtasks/{subtask.id}/stdout",
                    metadata={
                        "source": "stdout",
                        "sandbox_id": lease.sandbox_id,
                        "content_length": len(execution.stdout),
                        "content": execution.stdout,
                        "preview": execution.stdout[:1000],
                    },
                )
            )

        if execution.stderr:
            artifacts.append(
                self._create_artifact(
                    task=task,
                    run=run,
                    subtask=subtask,
                    name=f"{subtask.name}-stderr.log",
                    artifact_type=ArtifactType.LOG,
                    storage_ref=f"inline://runs/{run.id}/subtasks/{subtask.id}/stderr",
                    metadata={
                        "source": "stderr",
                        "sandbox_id": lease.sandbox_id,
                        "content_length": len(execution.stderr),
                        "content": execution.stderr,
                        "preview": execution.stderr[:1000],
                    },
                )
            )

        return artifacts

    @staticmethod
    def _create_artifact(
        *,
        task: Task,
        run: Run,
        subtask: SubTask,
        name: str,
        artifact_type: ArtifactType,
        storage_ref: str,
        metadata: dict[str, Any],
    ) -> Artifact:
        return Artifact(
            id=str(uuid.uuid4()),
            task_id=task.id,
            run_id=run.id,
            subtask_id=subtask.id,
            name=name,
            type=artifact_type,
            storage_ref=storage_ref,
            metadata=metadata,
        )