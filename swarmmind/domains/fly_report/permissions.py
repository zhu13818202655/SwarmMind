"""Permission gate for the FlyReport AUTHORIZING stage.

The default :class:`AllowAllPermissionGate` keeps backwards-compatible
behaviour. Real deployments inject a custom gate (e.g. one wired to the
identity / RBAC system) that can reject a request based on the session's
``tenant_id`` / ``user_id`` and the normalised filter being requested
(department / pilot / indicator scope).

Decisions are surfaced both:
- As ``record.state_history`` entries (visible in the snapshot).
- As rows in ``fly_report_audit`` (durable, see :mod:`.repository`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from swarmmind.domains.fly_report.schemas import NormalizedFilter


@dataclass(frozen=True)
class PermissionDecision:
    """Outcome of a permission evaluation."""

    allowed: bool
    reason: str = ""
    scope_required: str = ""
    audit: dict[str, Any] = field(default_factory=dict)


class PermissionGate(Protocol):
    """Pluggable AUTHORIZING-stage policy."""

    def evaluate(
        self,
        *,
        tenant_id: str,
        user_id: str,
        normalized_filter: NormalizedFilter,
    ) -> PermissionDecision: ...


class AllowAllPermissionGate:
    """Default gate: accepts every request (preserves old behaviour)."""

    def evaluate(
        self,
        *,
        tenant_id: str,
        user_id: str,
        normalized_filter: NormalizedFilter,
    ) -> PermissionDecision:
        return PermissionDecision(
            allowed=True,
            reason="allow-all",
            scope_required="",
            audit={
                "tenant_id": tenant_id,
                "user_id": user_id,
                "filter_hash": normalized_filter.hash,
            },
        )


class DenyAllPermissionGate:
    """Useful in tests / smoke checks."""

    def evaluate(
        self,
        *,
        tenant_id: str,
        user_id: str,
        normalized_filter: NormalizedFilter,
    ) -> PermissionDecision:
        return PermissionDecision(
            allowed=False,
            reason="deny-all",
            scope_required="fly_report.read",
            audit={
                "tenant_id": tenant_id,
                "user_id": user_id,
                "filter_hash": normalized_filter.hash,
            },
        )


__all__ = [
    "AllowAllPermissionGate",
    "DenyAllPermissionGate",
    "PermissionDecision",
    "PermissionGate",
]
