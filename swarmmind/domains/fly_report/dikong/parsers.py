"""Dikong response envelope & typed payload models.

Every dikong endpoint returns a uniform envelope::

    {
      "code": 0,
      "msg": "ok",
      "requestId": "...",
      "requestTime": "...",
      "data": { ... }   # or a list / scalar / null
    }

``code == 0`` means success.  Anything else is mapped to
:class:`DikongApiError` by the client.

Only the five core M1 endpoints get typed payload models in Step 2;
everything else round-trips as ``dict[str, Any]`` until a downstream caller
needs it.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from swarmmind.domains.fly_report.errors import DikongApiError

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Envelope
# ---------------------------------------------------------------------------


class DikongEnvelope(BaseModel, Generic[T]):
    """Generic ``{code, msg, data}`` wrapper used by every dikong endpoint."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    code: int = 0
    msg: str | None = None
    request_id: str | None = Field(default=None, alias="requestId")
    request_time: str | None = Field(default=None, alias="requestTime")
    data: T | None = None

    @property
    def is_success(self) -> bool:
        return self.code == 0


def parse_envelope(
    payload: Any,
    *,
    endpoint: str,
    data_model: type[BaseModel] | None = None,
) -> DikongEnvelope[Any]:
    """Parse a raw upstream JSON body into a :class:`DikongEnvelope`.

    Raises :class:`DikongApiError` when the envelope has a non-zero ``code``.
    The exception's ``details`` carries ``endpoint``, ``code``, ``msg`` and
    the raw payload for debugging.
    """

    envelope_cls: type[DikongEnvelope[Any]]
    if data_model is None:
        envelope_cls = DikongEnvelope[dict]  # type: ignore[type-arg]
    else:
        envelope_cls = DikongEnvelope[data_model]  # type: ignore[valid-type]

    envelope = envelope_cls.model_validate(payload)
    if not envelope.is_success:
        raise DikongApiError(
            f"dikong returned non-success code {envelope.code} for {endpoint}: {envelope.msg}",
            details={
                "endpoint": endpoint,
                "code": envelope.code,
                "msg": envelope.msg,
                "request_id": envelope.request_id,
            },
        )
    return envelope


# ---------------------------------------------------------------------------
# Typed payload models for the 5 core M1 endpoints
# ---------------------------------------------------------------------------


class FlyStatisResp(BaseModel):
    """``GET /missions/getFlyStatis`` -> ``data``."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    drone_count: int | None = Field(default=None, alias="droneCount")
    hangar_count: int | None = Field(default=None, alias="hangarCount")
    route_plan_count: int | None = Field(default=None, alias="routePlanCount")
    fly_mileage_total: float | None = Field(default=None, alias="flyMileageTotal")
    fly_time_total: float | None = Field(default=None, alias="flyTimeTotal")
    num_total: int | None = Field(default=None, alias="numTotal")
    drone_job_count: int | None = Field(default=None, alias="droneJobCount")
    hangar_job_count: int | None = Field(default=None, alias="hangarJobCount")
    algorithm_count: int | None = Field(default=None, alias="algorithmCount")


class WarnStaticResp(BaseModel):
    """``GET /missions/getWarnStatic`` -> ``data`` (loose-typed map)."""

    model_config = ConfigDict(extra="allow")

    raw: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _wrap_unknown(cls, value: Any) -> Any:
        if isinstance(value, dict) and "raw" not in value:
            return {"raw": value}
        return value


class MediaStaticResp(BaseModel):
    """``GET /missions/getMediaStatic`` -> ``data`` (loose-typed map)."""

    model_config = ConfigDict(extra="allow")

    raw: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _wrap_unknown(cls, value: Any) -> Any:
        if isinstance(value, dict) and "raw" not in value:
            return {"raw": value}
        return value


class HmsStatsResp(BaseModel):
    """``GET /devices/hms/stats`` -> ``data``."""

    model_config = ConfigDict(extra="allow")

    raw: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _wrap_unknown(cls, value: Any) -> Any:
        if isinstance(value, dict) and "raw" not in value:
            return {"raw": value}
        return value


class MissionPageRow(BaseModel):
    """One row from ``/missions/queryByPage``.  Schema is loose on purpose."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: int | str | None = None
    no: str | None = None
    status: str | int | None = None
    dept_id: int | str | None = Field(default=None, alias="deptId")


class MissionQueryByPageResp(BaseModel):
    """``GET /missions/queryByPage`` -> ``data``."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    total: int | None = None
    page: int | None = Field(default=None, alias="pageNum")
    page_size: int | None = Field(default=None, alias="pageSize")
    rows: list[MissionPageRow] = Field(default_factory=list, alias="list")


__all__ = [
    "DikongEnvelope",
    "FlyStatisResp",
    "HmsStatsResp",
    "MediaStaticResp",
    "MissionPageRow",
    "MissionQueryByPageResp",
    "WarnStaticResp",
    "parse_envelope",
]
