"""Persist high-value execution traces as debug artifacts."""

from __future__ import annotations

import uuid

from swarmmind.models.artifact import Artifact, ArtifactType
from swarmmind.models.event import DomainEvent
from swarmmind.repositories import ArtifactRepository
from swarmmind.utils.audit import sanitize_audit_value


_AUDIT_ARTIFACT_TOPICS: dict[str, ArtifactType] = {
    "tool.started": ArtifactType.LOG,
    "tool.completed": ArtifactType.LOG,
    "tool.failed": ArtifactType.LOG,
    "llm.requested": ArtifactType.TRANSCRIPT,
    "llm.responded": ArtifactType.TRANSCRIPT,
    "llm.failed": ArtifactType.TRANSCRIPT,
}


class AuditArtifactRecorder:
    """Persist selected event payloads as file-backed artifacts."""

    def __init__(self, artifact_repository: ArtifactRepository):
        self._artifact_repository = artifact_repository

    async def handle_event(self, event: DomainEvent) -> None:
        artifact_type = _AUDIT_ARTIFACT_TOPICS.get(event.topic)
        if artifact_type is None or not event.run_id or not event.task_id:
            return

        artifact = Artifact(
            id=str(uuid.uuid4()),
            task_id=event.task_id,
            run_id=event.run_id,
            subtask_id=event.subtask_id,
            name=self._artifact_name(event),
            type=artifact_type,
            storage_ref=f"inline://runs/{event.run_id}/events/{event.event_id}/{event.topic}.json",
            metadata={
                "source": "audit_trace",
                "topic": event.topic,
                "event_id": event.event_id,
                "tenant_id": event.tenant_id,
                "session_id": event.session_id,
                "task_id": event.task_id,
                "run_id": event.run_id,
                "subtask_id": event.subtask_id,
                "sandbox_id": event.sandbox_id,
                "payload": sanitize_audit_value(event.payload),
            },
        )
        await self._artifact_repository.create(artifact)

    @staticmethod
    def _artifact_name(event: DomainEvent) -> str:
        topic_slug = event.topic.replace(".", "-")
        if event.subtask_id:
            return f"{topic_slug}-{event.subtask_id}-{event.event_id}.json"
        return f"{topic_slug}-{event.event_id}.json"