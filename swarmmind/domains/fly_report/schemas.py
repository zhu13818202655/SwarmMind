"""Pydantic schemas for the FlyReport domain.

Mirrors ``docs/FlyReport/DESIGN-2.md`` §5.  These models are the canonical
contract between the LLM agents (``DraftFilterSpec``), the orchestrator
(``NormalizedFilter``), the analyzer (``RawDataset`` / ``AnalysisResult``)
and the renderers (``ReportContext``).
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Basic enums / aliases
# ---------------------------------------------------------------------------

PeriodKind = Literal["weekly", "monthly", "custom"]
ScopeKind = Literal["overall", "department", "pilot"]
OutputFormat = Literal["docx", "pdf", "markdown"]
ChatRole = Literal["user", "assistant", "system"]
InteractionStatus = Literal[
    "pending", "streaming", "completed", "failed", "cancelled"
]
InteractionPhase = Literal[
    "intake",
    "parsing",
    "clarifying",
    "authorizing",
    "fetching",
    "analyzing",
    "previewing",
    "rendering",
    "delivering",
    "done",
]
FlyReportMessageStatus = Literal[
    "pending", "running", "completed", "failed", "cancelled"
]
FlyReportMessageType = Literal[
    "plain_text", "todo", "phase", "artifact", "error", "summary"
]


class SessionState(str, Enum):
    """Lifecycle of a FlyReport conversation (see DESIGN-2 §7)."""

    PARSING = "parsing"
    CLARIFYING = "clarifying"
    AUTHORIZING = "authorizing"
    FETCHING = "fetching"
    ANALYZING = "analyzing"
    PREVIEWING = "previewing"
    RENDERING = "rendering"
    ARCHIVED = "archived"
    CANCELLED = "cancelled"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Filter spec & friends
# ---------------------------------------------------------------------------


class Period(BaseModel):
    kind: PeriodKind
    start: datetime
    end: datetime
    label: str | None = None


class Dimension(BaseModel):
    scope: ScopeKind = "overall"
    department_ids: list[str] = Field(default_factory=list)
    pilot_ids: list[str] = Field(default_factory=list)
    compare_with: list[str] = Field(default_factory=list)


class ReportOptions(BaseModel):
    include_charts: bool = True
    include_trend: bool = True
    include_compare: bool = True
    notes_section: bool = False
    locale: str = "zh-CN"
    output_format: OutputFormat = "docx"


class FilterSpec(BaseModel):
    """User-visible filter (may still contain ambiguity)."""

    period: Period | None = None
    dept_names: list[str] = Field(default_factory=list)
    dept_ids: list[int] = Field(default_factory=list)
    indicators: list[str] = Field(default_factory=list)
    dimension: Dimension = Field(default_factory=Dimension)
    options: ReportOptions = Field(default_factory=ReportOptions)
    missing: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)


class DraftFilterSpec(FilterSpec):
    """Output of :class:`IntentParserAgent` before normalization."""


class NormalizedFilter(FilterSpec):
    """Resolved, hashable filter that downstream caches key off of."""

    hash: str

    @classmethod
    def from_filter(cls, spec: FilterSpec) -> "NormalizedFilter":
        if spec.period is None:
            raise ValueError("NormalizedFilter requires a non-null period")

        payload = spec.model_dump(mode="json", exclude={"missing", "conflicts"})
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        return cls(**payload, hash=digest)


class FilterPatch(BaseModel):
    """Incremental update emitted by :class:`FollowupRouterAgent`."""

    period: Period | None = None
    dimension: Dimension | None = None
    options: ReportOptions | None = None
    notes: str | None = None


# ---------------------------------------------------------------------------
# Datasets / analysis
# ---------------------------------------------------------------------------


class RawDataset(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    current: dict[str, Any] = Field(default_factory=dict)
    previous: dict[str, Any] = Field(default_factory=dict)


class AnalysisResult(BaseModel):
    flight_stat_overall: dict[str, Any] = Field(default_factory=dict)
    flight_stat_day_trend: dict[str, Any] = Field(default_factory=dict)
    flight_stat_department_share: dict[str, Any] = Field(default_factory=dict)
    media_collection_summary: dict[str, Any] = Field(default_factory=dict)
    algorithm_recognition_overall: dict[str, Any] = Field(default_factory=dict)
    algorithm_recognition_distribution: dict[str, Any] = Field(default_factory=dict)
    algorithm_disposal_summary: dict[str, Any] = Field(default_factory=dict)
    algorithm_high_frequency_locations: dict[str, Any] = Field(default_factory=dict)
    algorithm_high_frequency_time_slots: dict[str, Any] = Field(default_factory=dict)
    algorithm_push_events: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Composer / renderer artifacts
# ---------------------------------------------------------------------------


ChartType = Literal["line", "bar", "pie", "stacked_bar", "heatmap"]


class ChartSpec(BaseModel):
    id: str
    title: str
    chart_type: ChartType
    echarts_option: dict[str, Any] = Field(default_factory=dict)
    series: list[dict[str, Any]] = Field(default_factory=list)
    data_ref: str | None = None


class ReportSection(BaseModel):
    id: str
    title: str
    summary_md: str = ""
    kpis: list[dict[str, Any]] = Field(default_factory=list)
    tables: list[dict[str, Any]] = Field(default_factory=list)
    charts: list[ChartSpec] = Field(default_factory=list)


class ReportContext(BaseModel):
    session_id: str
    filter: NormalizedFilter
    sections: list[ReportSection] = Field(default_factory=list)
    revision: int = 1
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    preview_html_path: str | None = None
    artifact_path: str | None = None
    artifact_format: OutputFormat | None = None

    def brief(self) -> dict[str, Any]:
        """Compact summary for chat replies / data overview."""

        return {
            "session_id": self.session_id,
            "filter_hash": self.filter.hash,
            "period": (
                f"{self.filter.period.start.isoformat()}"
                f"~{self.filter.period.end.isoformat()}"
            ),
            "section_count": len(self.sections),
            "revision": self.revision,
        }


# ---------------------------------------------------------------------------
# Chat / API payloads
# ---------------------------------------------------------------------------


class ChatTurn(BaseModel):
    role: ChatRole
    text: str
    payload: dict[str, Any] | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class FlyReportInteraction(BaseModel):
    id: str
    session_id: str
    tenant_id: str
    user_id: str
    status: InteractionStatus = "pending"
    phase: InteractionPhase = "intake"
    input_text: str
    output_format: OutputFormat | None = None
    template_ref: str | None = None
    error: str | None = None
    message_count: int = 0
    artifact_count: int = 0
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class FlyReportMessage(BaseModel):
    id: str
    session_id: str
    interaction_id: str
    tenant_id: str
    user_id: str
    role: ChatRole
    message_type: FlyReportMessageType
    status: FlyReportMessageStatus = "completed"
    title: str | None = None
    text: str = ""
    sequence: int
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PreviewPayload(BaseModel):
    preview_path: str
    data_brief: dict[str, Any]
    revision: int


class ConfirmPayload(BaseModel):
    output_format: OutputFormat = "docx"
    template_ref: str | None = None  # "default" / "preset:<name>"


class ArtifactRef(BaseModel):
    report_id: str
    output_format: OutputFormat
    download_url: str
    expires_at: datetime | None = None
