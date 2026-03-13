"""Authorization policy primitives."""

from swarmmind.identity.models import IdentityContext


class AuthorizationPolicy:
    """Very small authorization layer for the first implementation round."""

    def ensure_can_submit_task(self, identity: IdentityContext) -> None:
        """Validate submit-task capability."""
        if "tasks:submit" not in identity.scopes:
            raise PermissionError("identity is not allowed to submit tasks")

    def ensure_can_read_task(self, identity: IdentityContext) -> None:
        """Validate read-task capability."""
        if "tasks:read" not in identity.scopes:
            raise PermissionError("identity is not allowed to read tasks")

    def ensure_can_read_run(self, identity: IdentityContext) -> None:
        """Validate read-run capability."""
        if "runs:read" not in identity.scopes:
            raise PermissionError("identity is not allowed to read runs")
