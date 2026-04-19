"""FlyReport observability helpers (DESIGN-3 §2.8).

Small, dependency-free metrics + event-bus glue used by
:class:`FlyReportService`. Kept intentionally minimal so tests can use an
in-memory bus without bringing up the full platform container.

- :class:`FlyReportMetrics` — per-stage counters + latency histogram
  (as a list of (stage, seconds) tuples; easy to aggregate in tests).
- :func:`make_event` — build a :class:`DomainEvent` for ``fly_report.*``
  topics with the standard context fields populated.

The event bus is duck-typed (``publish(event)``) so callers can pass any
:class:`swarmmind.events.bus.EventBus` implementation (including
``InMemoryEventBus``). If no bus is wired the service silently skips
publishes.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from threading import Lock
from typing import Any

from swarmmind.models.event import DomainEvent


# ---------------------------------------------------------------------------
# Event helper
# ---------------------------------------------------------------------------


FLY_REPORT_EVENT_TOPICS: tuple[str, ...] = (
    "fly_report.intent_parsed",
    "fly_report.clarify_needed",
    "fly_report.clarify_exhausted",
    "fly_report.authorize_denied",
    "fly_report.data_fetched",
    "fly_report.analyzed",
    "fly_report.previewed",
    "fly_report.generated",
    "fly_report.failed",
    "fly_report.followup_handled",
)


def make_event(
    topic: str,
    *,
    tenant_id: str,
    session_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> DomainEvent:
    """Build a standardised ``fly_report.*`` :class:`DomainEvent`."""
    return DomainEvent(
        event_id=str(uuid.uuid4()),
        topic=topic,
        tenant_id=tenant_id,
        session_id=session_id,
        payload=payload or {},
    )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@dataclass
class FlyReportMetrics:
    """Lightweight process-local metrics sink.

    Not a Prometheus client — we only track the things the tests care about
    and keep the shape simple so any future exporter can map over it.
    """

    stage_durations: list[tuple[str, float]] = field(default_factory=list)
    stage_counts: dict[str, int] = field(default_factory=dict)
    render_success: int = 0
    render_failure: int = 0
    clarify_rounds: list[int] = field(default_factory=list)
    _lock: Lock = field(default_factory=Lock, repr=False)

    def observe_stage(self, stage: str, seconds: float) -> None:
        with self._lock:
            self.stage_durations.append((stage, seconds))
            self.stage_counts[stage] = self.stage_counts.get(stage, 0) + 1

    def record_render(self, *, success: bool) -> None:
        with self._lock:
            if success:
                self.render_success += 1
            else:
                self.render_failure += 1

    def record_clarify_round(self, round_count: int) -> None:
        with self._lock:
            self.clarify_rounds.append(round_count)

    # ---- readers (test helpers) ----

    def durations_for(self, stage: str) -> list[float]:
        return [s for st, s in self.stage_durations if st == stage]

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "stage_counts": dict(self.stage_counts),
                "stage_durations": list(self.stage_durations),
                "render_success": self.render_success,
                "render_failure": self.render_failure,
                "clarify_rounds": list(self.clarify_rounds),
            }


__all__ = [
    "FLY_REPORT_EVENT_TOPICS",
    "FlyReportMetrics",
    "make_event",
]
