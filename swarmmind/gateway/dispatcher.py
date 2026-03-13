"""Gateway dispatch helpers."""

from swarmmind.events.bus import EventBus
from swarmmind.models.event import DomainEvent


class GatewayDispatcher:
    """Dispatch gateway events onto the event bus."""

    def __init__(self, event_bus: EventBus):
        self._event_bus = event_bus

    async def dispatch(self, event: DomainEvent) -> None:
        """Publish an event to the bus."""
        await self._event_bus.publish(event)