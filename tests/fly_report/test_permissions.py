"""Tests for the AUTHORIZING-stage permission gate."""

from __future__ import annotations

import pytest

from swarmmind.domains.fly_report.errors import PermissionDenied
from swarmmind.domains.fly_report.permissions import (
    AllowAllPermissionGate,
    DenyAllPermissionGate,
    PermissionDecision,
)
from swarmmind.domains.fly_report.schemas import NormalizedFilter
from tests.fly_report.service_test_utils import build_fly_report_service


@pytest.mark.asyncio
async def test_allow_all_gate_lets_pipeline_finish(tmp_path) -> None:
    svc = build_fly_report_service(
        output_root=tmp_path,
        permission_gate=AllowAllPermissionGate(),
    )
    sid = await svc.start_session(
        tenant_id="t1", user_id="u1", initial_query="飞行周报"
    )
    snap = await svc.get_session_snapshot(sid, user_id="u1")
    assert snap["state"] == "previewing"


@pytest.mark.asyncio
async def test_deny_gate_marks_session_failed(tmp_path) -> None:
    svc = build_fly_report_service(
        output_root=tmp_path,
        permission_gate=DenyAllPermissionGate(),
    )
    sid = await svc.start_session(tenant_id="t1", user_id="u1")
    with pytest.raises(PermissionDenied):
        await svc.send_message(sid, "飞行周报", user_id="u1")
    snap = await svc.get_session_snapshot(sid, user_id="u1")
    assert snap["state"] == "failed"


class _ScopedGate:
    """Approves only when the user has the required scope."""

    def __init__(self, allowed_users: set[str]) -> None:
        self._allowed = allowed_users

    def evaluate(
        self, *, tenant_id: str, user_id: str, normalized_filter: NormalizedFilter
    ) -> PermissionDecision:
        if user_id in self._allowed:
            return PermissionDecision(
                allowed=True,
                reason="scope-matched",
                scope_required="fly_report.read",
                audit={"user_id": user_id},
            )
        return PermissionDecision(
            allowed=False,
            reason="missing-scope",
            scope_required="fly_report.read",
            audit={"user_id": user_id},
        )


@pytest.mark.asyncio
async def test_scoped_gate_separates_users(tmp_path) -> None:
    svc = build_fly_report_service(
        output_root=tmp_path,
        permission_gate=_ScopedGate({"alice"}),
    )
    sid_ok = await svc.start_session(
        tenant_id="t1", user_id="alice", initial_query="飞行周报"
    )
    snap_ok = await svc.get_session_snapshot(sid_ok, user_id="alice")
    assert snap_ok["state"] == "previewing"

    sid_bad = await svc.start_session(tenant_id="t1", user_id="bob")
    with pytest.raises(PermissionDenied):
        await svc.send_message(sid_bad, "飞行周报", user_id="bob")
