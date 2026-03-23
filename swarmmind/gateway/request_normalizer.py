"""Request normalization logic for the gateway."""

from swarmmind.gateway.envelopes import TaskSubmitRequest
from swarmmind.models.task import TaskRequest


class RequestNormalizer:
    """Normalize external requests into internal task requests."""

    def normalize(self, request: TaskSubmitRequest) -> TaskRequest:
        """Convert the gateway request into a domain request."""
        return TaskRequest(
            goal=request.goal,
            constraints=request.constraints,
            priority=request.priority,
            profile=request.profile,
            preferred_strategy=request.preferred_strategy,
            metadata=request.metadata,
        )
