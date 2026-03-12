"""Transcript for logging complete execution traces."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from swarmmind.models.task import Task


class TranscriptEvent:
    """Transcript event."""

    def __init__(
        self,
        event_type: str,
        timestamp: datetime | None = None,
        data: dict[str, Any] | None = None,
    ):
        self.event_type = event_type
        self.timestamp = timestamp or datetime.utcnow()
        self.data = data or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
        }


class Transcript:
    """Transcript for task execution."""

    def __init__(self, task_id: str):
        self.task_id = task_id
        self.events: list[TranscriptEvent] = []
        self.started_at = datetime.utcnow()

    def add_event(self, event_type: str, data: dict[str, Any] | None = None) -> None:
        """Add an event to the transcript."""
        event = TranscriptEvent(event_type=event_type, data=data)
        self.events.append(event)

    def add_message(self, role: str, content: str) -> None:
        """Add a message event."""
        self.add_event("message", {"role": role, "content": content})

    def add_tool_call(self, tool_name: str, args: dict[str, Any], result: Any) -> None:
        """Add a tool call event."""
        self.add_event(
            "tool_call",
            {"tool": tool_name, "args": args, "result": str(result)[:500]},
        )

    def add_error(self, error: str) -> None:
        """Add an error event."""
        self.add_event("error", {"error": error})

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "started_at": self.started_at.isoformat(),
            "finished_at": datetime.utcnow().isoformat(),
            "events": [e.to_dict() for e in self.events],
        }

    async def save(self, path: str | Path) -> None:
        """Save transcript to file."""
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str | Path) -> "Transcript":
        """Load transcript from file."""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        transcript = cls(task_id=data["task_id"])
        transcript.events = [
            TranscriptEvent(
                event_type=e["event_type"],
                timestamp=datetime.fromisoformat(e["timestamp"]),
                data=e["data"],
            )
            for e in data["events"]
        ]
        return transcript
