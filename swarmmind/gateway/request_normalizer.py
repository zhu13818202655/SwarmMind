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
            agent_profile_id=request.agent_profile_id,
            metadata=request.metadata,
        )
