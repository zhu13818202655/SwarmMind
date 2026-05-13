"""Dikong response envelope & typed payload models.

Every dikong endpoint returns a uniform envelope::

    {
      "code": 0,
      "msg": "ok",
      "requestId": "...",
      "requestTime": "...",
      "data": { ... }   # or a list / scalar / null
    }

``code == 0`` (or ``200``) means success.  ``parse_envelope`` no longer
raises on non-success codes; callers can inspect
:pyattr:`DikongEnvelope.is_success` if they care.

Only the five core M1 endpoints get typed payload models in Step 2;
everything else round-trips as ``dict[str, Any]`` until a downstream caller
needs it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from swarmmind.domains.fly_report.errors import DikongApiError

T = TypeVar("T")


def _normalize_dikong_timestamp(value: Any) -> Any:
    """Convert epoch ms/sec timestamps to ``YYYY-MM-DD HH:MM:SS`` strings.

    Upstream dikong inconsistently returns either:
    - millisecond epoch ints (e.g. ``1776991320000``)
    - already formatted strings (e.g. ``"2026-01-13 11:37:00"``)

    Non-numeric / falsy values are passed through unchanged.
    """
    if value is None or value == "":
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped or not stripped.lstrip("-").isdigit():
            return value
        try:
            ts = int(stripped)
        except ValueError:
            return value
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        ts = int(value)
    else:
        return value

    # Heuristic: > 1e12 looks like ms; otherwise treat as seconds.
    seconds = ts / 1000 if abs(ts) >= 1_000_000_000_000 else ts
    try:
        return datetime.fromtimestamp(seconds).strftime("%Y-%m-%d %H:%M:%S")
    except (OverflowError, OSError, ValueError):
        return value


# ---------------------------------------------------------------------------
# Envelope
# ---------------------------------------------------------------------------


class DikongEnvelope(BaseModel, Generic[T]):
    """Generic ``{code, msg, data}`` wrapper used by every dikong endpoint."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    # Upstream is inconsistent: some endpoints return ``0`` (int), others
    # return ``200`` / ``"200"``.  Keep the raw value loose and normalise in
    # :pyattr:`is_success` so downstream code does not need to care.
    code: int | str = 0
    msg: str | None = None
    request_id: str | None = Field(default=None, alias="requestId")
    request_time: str | None = Field(default=None, alias="requestTime")
    data: T | None = None

    @property
    def is_success(self) -> bool:
        return int(self.code) in (0, 200)


def parse_envelope(
    payload: Any,
    *,
    endpoint: str,
    data_model: type[BaseModel] | None = None,
) -> DikongEnvelope[Any]:
    """Parse a raw upstream JSON body into a :class:`DikongEnvelope`.

    The success/failure decision is left to the caller (via
    :pyattr:`DikongEnvelope.is_success`); this function only handles
    deserialisation so that upstream variations in the ``code`` field do
    not cause well-formed responses to be rejected.
    """

    envelope_cls: type[DikongEnvelope[Any]]
    if data_model is None:
        envelope_cls = DikongEnvelope[Any]  # type: ignore[type-arg]
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


class FlyJobLogRow(BaseModel):
    """One row from ``GET /job/log/list`` -> ``data.records``."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: int | None = None
    name: str | None = None
    no: str | None = None
    type: str | int | None = None
    algorithm_type: str | int | None = Field(default=None, alias="algorithmType")
    auto_return: bool | None = Field(default=None, alias="autoReturn")
    params: dict[str, Any] = Field(default_factory=dict)
    del_flag: bool | None = Field(default=None, alias="delFlag")
    deptids_tag: str | None = Field(default=None, alias="deptidsTag")
    deptids_tag_name: str | None = Field(default=None, alias="deptidsTagName")
    device_sn: str | None = Field(default=None, alias="deviceSn")
    emergency_action: int | str | None = Field(default=None, alias="emergencyAction")
    is_collect: int | bool | None = Field(default=None, alias="isCollect")
    job_log_id: str | None = Field(default=None, alias="jobLogId")
    job_log_no: str | None = Field(default=None, alias="jobLogNo")
    job_id: int | str | None = Field(default=None, alias="jobId")
    job_name: str | None = Field(default=None, alias="jobName")
    job_group: str | None = Field(default=None, alias="jobGroup")
    invoke_target: str | None = Field(default=None, alias="invokeTarget")
    job_message: str | None = Field(default=None, alias="jobMessage")
    mission_id: int | str | None = Field(default=None, alias="missionId")
    operator_id: int | str | None = Field(default=None, alias="operatorId")
    operator_name: str | None = Field(default=None, alias="operatorName")
    region: int | str | None = None
    return_height: float | str | None = Field(default=None, alias="returnHeight")
    route_id: int | str | None = Field(default=None, alias="routeId")
    route_name: str | None = Field(default=None, alias="routeName")
    scene_tag: str | None = Field(default=None, alias="sceneTag")
    scene_tag_name: str | None = Field(default=None, alias="sceneTagName")
    status: str | int | None = None
    exception_info: str | None = Field(default=None, alias="exceptionInfo")
    start_time: str | None = Field(default=None, alias="startTime")
    stop_time: str | None = Field(default=None, alias="stopTime")
    create_time: str | None = Field(default=None, alias="createTime")
    total_length: float | int | str | None = Field(default=None, alias="totalLength")
    update_by: str | None = Field(default=None, alias="updateBy")
    data_status: int | None = Field(default=None, alias="dataStatus")


class FlyJobLogResp(BaseModel):
    """``GET /job/log/list`` -> ``data``."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    size: int | None = None
    current: int | None = None
    total: int | None = None
    pages: int | None = None
    records: list[FlyJobLogRow] = Field(default_factory=list)


class FlyJobLogDetailResp(BaseModel):
    """``GET /job/log/{jobLogId}`` -> ``data``."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    no: str | None = None
    name: str | None = None
    mission_id: int | str | None = Field(default=None, alias="missionId")
    algorithm_type_name: str | None = Field(default=None, alias="algorithmTypeName")
    device_type_name: str | None = Field(default=None, alias="deviceTypeName")
    type: int | str | None = None
    job_log_no: str | None = Field(default=None, alias="jobLogNo")
    plan_start_time: str | None = Field(default=None, alias="planStartTime")
    total_length: str | float | None = Field(default=None, alias="totalLength")
    route_id: int | str | None = Field(default=None, alias="routeId")
    route_planning_name: str | None = Field(default=None, alias="routePlanningName")
    operator_name: str | None = Field(default=None, alias="operatorName")
    device_mn: str | None = Field(default=None, alias="deviceMn")
    device_sn: str | None = Field(default=None, alias="deviceSn")
    device_name: str | None = Field(default=None, alias="deviceName")
    plan_exec_time: str | None = Field(default=None, alias="planExecTime")
    plan_end_time: str | None = Field(default=None, alias="planEndTime")
    job_time: str | None = Field(default=None, alias="jobTime")
    max_speed: str | float | None = Field(default=None, alias="maxSpeed")
    ave_speed: str | float | None = Field(default=None, alias="aveSpeed")
    real_total_length: str | float | None = Field(default=None, alias="realTotallength")


class WarnStaticRow(BaseModel):
    """One row from ``GET /missions/getWarnStatic`` -> ``data.records``."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: int | str | None = None
    object_key: str | None = Field(default=None, alias="objectKey")
    file_url: str | None = Field(default=None, alias="fileUrl")
    file_type: str | None = Field(default=None, alias="fileType")
    algorithm_id: int | str | None = Field(default=None, alias="algorithmId")
    algorithm_name: str | None = Field(default=None, alias="algorithmName")
    algorithm_result: str | None = Field(default=None, alias="algorithmResult")
    extra_result: str | None = Field(default=None, alias="extraResult")
    joblog_id: str | None = Field(default=None, alias="joblogId")
    mission_id: int | str | None = Field(default=None, alias="missionId")
    mission_no: str | None = Field(default=None, alias="missionNo")
    mission_name: str | None = Field(default=None, alias="missionName")
    device_sn: str | None = Field(default=None, alias="deviceSn")
    status: int | str | None = None
    create_time: str | int | None = Field(default=None, alias="createTime")
    approval_time: str | int | None = Field(default=None, alias="approvalTime")
    dispose_time: str | int | None = Field(default=None, alias="disposeTime")
    approvaler: int | str | None = None
    disposer: int | str | None = None
    approvaler_name: str | None = Field(default=None, alias="approvalerName")
    disposer_name: str | None = Field(default=None, alias="disposerName")
    work_order_no: str | None = Field(default=None, alias="workOrderNo")
    work_order_name: str | None = Field(default=None, alias="workOrderName")
    level: int | str | None = None
    longitude: str | float | None = None
    latitude: str | float | None = None
    work_order_remark: str | None = Field(default=None, alias="workOrderRemark")
    address: str | None = None
    push_result: str | None = Field(default=None, alias="pushResult")
    push_status: int | str | None = Field(default=None, alias="pushStatus")

    @field_validator("create_time", "approval_time", "dispose_time", mode="before")
    @classmethod
    def _normalize_timestamps(cls, value: Any) -> Any:
        return _normalize_dikong_timestamp(value)


class WarnStaticResp(BaseModel):
    """``GET /missions/getWarnStatic`` -> ``data``."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    size: int | None = None
    current: int | None = None
    total: int | None = None
    pages: int | None = None
    records: list[WarnStaticRow] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _wrap_unknown(cls, value: Any) -> Any:
        if isinstance(value, dict) and not {
            "raw",
            "records",
            "size",
            "current",
            "total",
            "pages",
        } & set(value):
            return {"raw": value}
        return value

    @model_validator(mode="after")
    def _derive_raw_summary(self) -> "WarnStaticResp":
        if self.raw or not self.records:
            return self

        summary: dict[str, Any] = {"total": len(self.records)}
        for record in self.records:
            key = record.algorithm_name or (
                f"algorithm_{record.algorithm_id}"
                if record.algorithm_id is not None
                else "unknown"
            )
            summary[key] = int(summary.get(key, 0)) + 1

        self.raw = summary
        return self


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
    "FlyJobLogDetailResp",
    "FlyJobLogResp",
    "FlyJobLogRow",
    "FlyStatisResp",
    "HmsStatsResp",
    "MediaStaticResp",
    "MissionPageRow",
    "MissionQueryByPageResp",
    "WarnStaticRow",
    "WarnStaticResp",
    "parse_envelope",
]
