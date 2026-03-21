"""Replay recorder for run-scoped event timelines."""

from __future__ import annotations

from swarmmind.models.event import DomainEvent
from swarmmind.models.replay import ReplayEntry
from swarmmind.repositories import ReplayRepository


class ReplayRecorder:
    """Record selected domain events into replay timelines."""

    def __init__(self, replay_repository: ReplayRepository):
        self._replay_repository = replay_repository

    async def handle_event(self, event: DomainEvent) -> None:
        """Append an event to the replay timeline for its run."""
        if not event.run_id:
            return

        replay = await self._replay_repository.get_by_run(event.run_id)
        if replay is None:
            return

        payload = {
            **event.payload,
            "event_id": event.event_id,
            "tenant_id": event.tenant_id,
            "session_id": event.session_id,
            "task_id": event.task_id,
            "run_id": event.run_id,
            "subtask_id": event.subtask_id,
            "sandbox_id": event.sandbox_id,
        }

        replay.append(ReplayEntry(event_type=event.topic, payload=payload))

        artifact_id = event.payload.get("artifact_id")
        if isinstance(artifact_id, str) and artifact_id and artifact_id not in replay.artifact_ids:
            replay.artifact_ids.append(artifact_id)

        await self._replay_repository.save(replay)