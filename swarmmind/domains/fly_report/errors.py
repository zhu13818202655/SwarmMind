"""FlyReport domain exceptions.

All error classes inherit from :class:`FlyReportError` so the API layer can
translate them into stable HTTP responses without leaking internals.
"""

from __future__ import annotations

from typing import Any


class FlyReportError(Exception):
    """Base error for the FlyReport domain."""

    code: str = "fly_report.error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class FilterParseError(FlyReportError):
    code = "fly_report.filter_parse_error"


class ClarifyNeeded(FlyReportError):
    """Raised when the parser detects missing/conflicting fields."""

    code = "fly_report.clarify_needed"

    def __init__(
        self,
        message: str = "clarification required",
        *,
        missing: list[str] | None = None,
        conflicts: list[str] | None = None,
        questions: list[str] | None = None,
    ) -> None:
        super().__init__(
            message,
            details={
                "missing": missing or [],
                "conflicts": conflicts or [],
                "questions": questions or [],
            },
        )


class PermissionDenied(FlyReportError):
    code = "fly_report.permission_denied"


class DikongApiError(FlyReportError):
    code = "fly_report.dikong_api_error"


class DikongAuthError(DikongApiError):
    """Login / token-refresh failure against dikong."""

    code = "fly_report.dikong_auth_error"


class DikongPgSqlError(FlyReportError):
    """PostgreSQL query failure when running the SQL data fetcher."""

    code = "fly_report.dikong_pg_sql_error"


class DikongPgSqlTimeoutError(DikongPgSqlError):
    """A PostgreSQL statement hit ``statement_timeout``."""

    code = "fly_report.dikong_pg_sql_timeout"


class DikongTdError(FlyReportError):
    """TDengine REST API returned a non-zero ``code`` or transport failure."""

    code = "fly_report.dikong_td_error"

    def __init__(
        self,
        message: str,
        *,
        td_code: int | None = None,
        desc: str | None = None,
        sql: str | None = None,
    ) -> None:
        details: dict[str, Any] = {}
        if td_code is not None:
            details["td_code"] = td_code
        if desc is not None:
            details["desc"] = desc
        if sql is not None:
            # Avoid leaking the full statement in logs; trim to a short preview.
            details["sql_preview"] = sql.strip()[:512]
        super().__init__(message, details=details)


class DikongTdTimeoutError(DikongTdError):
    """TDengine REST request timed out."""

    code = "fly_report.dikong_td_timeout"


class RenderError(FlyReportError):
    code = "fly_report.render_error"


class ExportError(FlyReportError):
    code = "fly_report.export_error"


class SessionNotFound(FlyReportError):
    code = "fly_report.session_not_found"


class InvalidStateTransition(FlyReportError):
    code = "fly_report.invalid_state_transition"
