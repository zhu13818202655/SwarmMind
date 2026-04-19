"""FlyReport session state machine helpers.

The state diagram is documented in ``docs/FlyReport/DESIGN-2.md`` §7.  This
module is intentionally pure: it only validates transitions and exposes the
allowed-edges map.  Persisting state history is the service's job.
"""

from __future__ import annotations

from swarmmind.domains.fly_report.errors import InvalidStateTransition
from swarmmind.domains.fly_report.schemas import SessionState

S = SessionState


# Allowed forward edges. ``FAILED`` is reachable from any non-terminal state
# and therefore wired up in code rather than enumerated here.
ALLOWED_TRANSITIONS: dict[SessionState, set[SessionState]] = {
    S.PARSING: {S.CLARIFYING, S.AUTHORIZING, S.CANCELLED, S.FAILED},
    S.CLARIFYING: {S.PARSING, S.AUTHORIZING, S.CANCELLED, S.FAILED},
    S.AUTHORIZING: {S.FETCHING, S.CANCELLED, S.FAILED},
    S.FETCHING: {S.ANALYZING, S.CANCELLED, S.FAILED},
    S.ANALYZING: {S.PREVIEWING, S.CANCELLED, S.FAILED},
    S.PREVIEWING: {S.PARSING, S.RENDERING, S.CANCELLED, S.FAILED},
    S.RENDERING: {S.ARCHIVED, S.CANCELLED, S.FAILED},
    S.ARCHIVED: set(),
    S.CANCELLED: set(),
    S.FAILED: set(),
}

TERMINAL_STATES: set[SessionState] = {S.ARCHIVED, S.CANCELLED, S.FAILED}


def can_transition(src: SessionState, dst: SessionState) -> bool:
    if dst is S.FAILED and src not in TERMINAL_STATES:
        return True
    return dst in ALLOWED_TRANSITIONS.get(src, set())


def assert_transition(src: SessionState, dst: SessionState) -> None:
    if not can_transition(src, dst):
        raise InvalidStateTransition(
            f"illegal transition {src.value} -> {dst.value}",
            details={"from": src.value, "to": dst.value},
        )


def is_terminal(state: SessionState) -> bool:
    return state in TERMINAL_STATES
