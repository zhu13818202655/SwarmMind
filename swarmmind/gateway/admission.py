"""Admission control for incoming tasks."""

from swarmmind.gateway.envelopes import TaskSubmitRequest
from swarmmind.identity.models import IdentityContext


class AdmissionController:
    """Minimal admission checks for the first implementation round."""

    def validate(self, request: TaskSubmitRequest, identity: IdentityContext) -> None:
        """Validate that the request can be admitted."""
        if not request.goal.strip():
            raise ValueError("goal must not be empty")
        if not identity.tenant_id:
            raise ValueError("identity must include a tenant_id")
