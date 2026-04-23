"""FlyReport service — wires the real pipeline behind the conversational API.

End-to-end flow per ``send_message`` call (DESIGN-2 §3.1, §14.3):

    PARSING      → IntentParser (LLM or rule-based) → DraftFilterSpec
    AUTHORIZING  → permission gate (placeholder, see DESIGN-2 §14.4.1)
    FETCHING     → DataFetcher → RawDataset
    ANALYZING    → analyze() → AnalysisResult
    PREVIEWING   → SimpleComposer → ReportContext (cached on the session)

``confirm`` then drives PREVIEWING → RENDERING → ARCHIVED via
:class:`RendererRouter`, returning the on-disk artifact path in
``ChatTurn.payload``.

Dependencies are injected; defaults make the service usable out-of-the-box
even without dikong / LLM connectivity (uses ``RuleBasedIntentParser`` +
``FakeDikongClient``).
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from swarmmind.config.settings import get_settings
from swarmmind.domains.fly_report.analyzer import analyze
from swarmmind.domains.fly_report.composer import compose_report_context
from swarmmind.domains.fly_report.conflict_checker import (
    check_conflicts,
    merge_drafts,
)
from swarmmind.domains.fly_report.data_fetcher import DataFetcher
from swarmmind.domains.fly_report.dikong.fake import FakeDikongClient
from swarmmind.domains.fly_report.errors import (
    FlyReportError,
    InvalidStateTransition,
    PermissionDenied,
    SessionNotFound,
)
from swarmmind.domains.fly_report.export import RendererRouter
from swarmmind.domains.fly_report.intent.parser import IntentParser

from swarmmind.domains.fly_report.observability import (
    FlyReportMetrics,
    make_event,
)
from swarmmind.domains.fly_report.permissions import (
    AllowAllPermissionGate,
    PermissionGate,
)
from swarmmind.domains.fly_report.repository import (
    FlyReportRepository,
    InMemoryFlyReportRepository,
)
from swarmmind.domains.fly_report.schemas import (
    AnalysisResult,
    ChatTurn,
    FilterSpec,
    NormalizedFilter,
    OutputFormat,
    RawDataset,
    ReportContext,
    SessionState,
)
from swarmmind.domains.fly_report.state_machine import (
    assert_transition,
    is_terminal,
)


logger = logging.getLogger(__name__)

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


def _utcnow() -> datetime:
    return datetime.now(SHANGHAI_TZ)


# ---------------------------------------------------------------------------
# Session record (in-memory; PG persistence lands in DESIGN-2 §14.4.1)
# ---------------------------------------------------------------------------


@dataclass
class _SessionRecord:
    id: str
    tenant_id: str
    user_id: str
    state: SessionState = SessionState.PARSING
    filter_spec: FilterSpec = field(default_factory=FilterSpec)
    raw: RawDataset | None = None
    analysis: AnalysisResult | None = None
    ctx: ReportContext | None = None
    revision: int = 0
    turns: list[ChatTurn] = field(default_factory=list)
    state_history: list[tuple[str, str, str | None]] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)
    last_user_text: str | None = None
    title: str | None = None
    clarify_round: int = 0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class FlyReportService:
    """Conversational FlyReport orchestrator.

    Parameters
    ----------
    intent_parser:
        Anything with ``async parse(text) -> DraftFilterSpec``. Defaults to
        :class:`RuleBasedIntentParser` (no LLM required).
    data_fetcher:
        Pre-built :class:`DataFetcher`. Defaults to one wrapping
        :class:`FakeDikongClient` so the service runs offline.
    renderer_router:
        Optional override; defaults to :class:`RendererRouter`.
    output_root:
        Root directory where artifact files are written. Each session gets a
        subfolder ``<output_root>/<session_id>/<format>/``. Defaults to a
        process-local temp dir.
    """

    def __init__(
        self,
        *,
        intent_parser: IntentParser,
        data_fetcher: DataFetcher,
        renderer_router: RendererRouter | None = None,
        output_root: Path | str | None = None,
        repository: FlyReportRepository | None = None,
        permission_gate: PermissionGate | None = None,
        event_bus: Any | None = None,
        metrics: FlyReportMetrics | None = None,
        max_clarify_rounds: int = 3,
        render_timeout_seconds: float = 60.0,
        max_text_length: int = 4000,
    ) -> None:
        self._intent_parser = intent_parser
        self._data_fetcher = data_fetcher
        self._renderer_router: RendererRouter = (
            renderer_router or RendererRouter()
        )
        self._output_root: Path = Path(
            output_root
            or tempfile.mkdtemp(prefix="fly_report_artifacts_")
        )
        self._output_root.mkdir(parents=True, exist_ok=True)
        self._sessions: dict[str, _SessionRecord] = {}
        self._sessions_lock = asyncio.Lock()
        self._repo: FlyReportRepository = (
            repository or InMemoryFlyReportRepository()
        )
        self._permission_gate: PermissionGate = (
            permission_gate or AllowAllPermissionGate()
        )
        self._event_bus = event_bus
        self._metrics: FlyReportMetrics = metrics or FlyReportMetrics()
        self._max_clarify_rounds = max(1, int(max_clarify_rounds))
        self._render_timeout_seconds = float(render_timeout_seconds)
        self._max_text_length = int(max_text_length)

    # ------------------------------------------------------------------
    # Public accessors for observability / ops tooling
    # ------------------------------------------------------------------

    @property
    def metrics(self) -> FlyReportMetrics:
        return self._metrics

    @property
    def max_text_length(self) -> int:
        return self._max_text_length

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start_session(
        self,
        *,
        tenant_id: str,
        user_id: str,
        initial_query: str | None = None,
    ) -> str:
        async with self._sessions_lock:
            session_id = str(uuid.uuid4())
            record = _SessionRecord(
                id=session_id, tenant_id=tenant_id, user_id=user_id
            )
            self._sessions[session_id] = record
        await self._persist_session(record)
        if initial_query:
            await self.send_message(session_id, initial_query, user_id=user_id)
        return session_id

    # ------------------------------------------------------------------
    # send_message: drive PARSING → ... → PREVIEWING
    # ------------------------------------------------------------------

    async def send_message(
        self,
        session_id: str,
        text: str,
        *,
        user_id: str,
    ) -> ChatTurn:
        if not isinstance(text, str) or not text.strip():
            raise InvalidStateTransition("text must be a non-empty string")
        if len(text) > self._max_text_length:
            raise InvalidStateTransition(
                f"text length {len(text)} exceeds max {self._max_text_length}"
            )
        record = await self._load_session(session_id, user_id=user_id)
        if is_terminal(record.state):
            raise InvalidStateTransition(
                f"session {session_id} is terminal ({record.state.value})"
            )
        async with record.lock:
            return await self._drive_pipeline(record, text)

    async def _drive_pipeline(
        self, record: _SessionRecord, text: str
    ) -> ChatTurn:
        record.last_user_text = text
        record.title = record.title or text[:60]
        user_turn = ChatTurn(role="user", text=text)
        record.turns.append(user_turn)
        await self._persist_turn(record, user_turn)

        config = get_settings()

        stages: list[dict[str, Any]] = []

        try:
            # ----- PARSING -----
            """
            1. 如果是多轮的，包括之前模糊的，需要把多轮对话传进来
            """
            self._enter(record, SessionState.PARSING, "user_message")
            t0 = time.perf_counter()
            # 1. get 时间范围
            # 2. TODO get 部门列表
            dept_names = await self._data_fetcher.get_department_name_list_by_id_list(
                dept_id_list=config.fly_report.dikong.department_id_list
            )
            draft = await self._intent_parser.parse(
                text,
                now=_utcnow(),
                extra_metadata={"dept_names": dept_names},
            )

            self._metrics.observe_stage("parsing", time.perf_counter() - t0)
            # Merge follow-up clarifications with the previously-known filter.
            had_prior_spec = bool(
                record.filter_spec.period
                or record.filter_spec.indicators
                or record.filter_spec.dimension.scope != "overall"
            )
            if had_prior_spec:
                merged = merge_drafts(record.filter_spec, draft)
                record.filter_spec = merged
            else:
                record.filter_spec = FilterSpec(**draft.model_dump())
            stages.append(
                {
                    "stage": "parsing",
                    "period": (
                        f"{record.filter_spec.period.start}~{record.filter_spec.period.end}"
                        if record.filter_spec.period
                        else None
                    ),
                    "scope": record.filter_spec.dimension.scope,
                    "indicators": list(record.filter_spec.indicators),
                }
            )
            await self._emit(
                "fly_report.intent_parsed",
                record,
                {
                    "period": (
                        f"{record.filter_spec.period.start}~{record.filter_spec.period.end}"
                        if record.filter_spec.period
                        else None
                    ),
                    "indicators": list(record.filter_spec.indicators),
                    "scope": record.filter_spec.dimension.scope,
                },
            )

            # ----- CLARIFY check (DESIGN-2 §14.4.2) -----
            report = check_conflicts(record.filter_spec)
            if report.needs_clarification:
                record.clarify_round += 1
                self._metrics.record_clarify_round(record.clarify_round)
                exhausted = record.clarify_round >= self._max_clarify_rounds
                self._enter(record, SessionState.CLARIFYING, "needs_clarify")
                stages.append(
                    {
                        "stage": "clarifying",
                        "round": record.clarify_round,
                        "exhausted": exhausted,
                        "missing": list(report.missing),
                        "conflicts": list(report.conflicts),
                        "suggestions": list(report.suggestions),
                    }
                )
                await self._emit(
                    "fly_report.clarify_exhausted"
                    if exhausted
                    else "fly_report.clarify_needed",
                    record,
                    {
                        "round": record.clarify_round,
                        "missing": list(report.missing),
                        "conflicts": list(report.conflicts),
                    },
                )
                if exhausted:
                    clarifier_text = (
                        "已连续多轮仍无法确定报告范围，请参考以下示例重新提交：\n"
                        "- 「本周 部门 101 的飞行和算法报告」\n"
                        "- 「上周 全公司 飞行+媒体统计」\n"
                        "- 「本月 飞手 42 的媒体报告」"
                    )
                else:
                    clarifier_text = (
                        "为了生成报告还需要补充以下信息：\n"
                        + "\n".join(
                            f"- {s}"
                            for s in (report.suggestions or report.missing)
                        )
                    )
                clarifier = ChatTurn(
                    role="assistant",
                    text=clarifier_text,
                    payload={
                        "state": record.state.value,
                        "stages": stages,
                        "missing": list(report.missing),
                        "conflicts": list(report.conflicts),
                        "suggestions": list(report.suggestions),
                        "clarify_round": record.clarify_round,
                        "clarify_exhausted": exhausted,
                    },
                )
                record.turns.append(clarifier)
                record.updated_at = _utcnow()
                await self._persist_turn(record, clarifier)
                await self._persist_session(record)
                return clarifier
            # Cleared clarifications → reset round counter.
            record.clarify_round = 0

            # ----- AUTHORIZING (real permission gate, DESIGN-2 §14.4.1) -----
            # TODO 针对用户本身的权限进行过滤，针对用户请求的维度/部门进行过滤
            self._enter(record, SessionState.AUTHORIZING, "intent_parsed")
            t0 = time.perf_counter()
            normalized = NormalizedFilter.from_filter(record.filter_spec)
            decision = self._permission_gate.evaluate(
                tenant_id=record.tenant_id,
                user_id=record.user_id,
                normalized_filter=normalized,
            )
            self._metrics.observe_stage(
                "authorizing", time.perf_counter() - t0
            )
            await self._persist_audit(
                record,
                decision_value="allow" if decision.allowed else "deny",
                reason=decision.reason,
                scope_required=decision.scope_required,
                payload=decision.audit,
            )
            stages.append(
                {
                    "stage": "authorizing",
                    "decision": "allow" if decision.allowed else "deny",
                    "reason": decision.reason,
                    "scope_required": decision.scope_required,
                }
            )
            if not decision.allowed:
                await self._emit(
                    "fly_report.authorize_denied",
                    record,
                    {
                        "reason": decision.reason,
                        "scope_required": decision.scope_required,
                    },
                )
                raise PermissionDenied(
                    decision.reason or "permission denied",
                    details={
                        "scope_required": decision.scope_required,
                        "audit": decision.audit,
                    },
                )

            # ----- FETCHING -----
            self._enter(record, SessionState.FETCHING, "authorized")
            t0 = time.perf_counter()
            record.raw = await self._data_fetcher.fetch(normalized)
            self._metrics.observe_stage("fetching", time.perf_counter() - t0)
            stages.append(
                {
                    "stage": "fetching",
                    "current_keys": sorted(
                        k for k in record.raw.current if not k.startswith("__")
                    ),
                    "previous_keys": sorted(
                        k for k in record.raw.previous if not k.startswith("__")
                    ),
                }
            )
            await self._emit(
                "fly_report.data_fetched",
                record,
                {
                    "indicators": list(normalized.indicators),
                    "dept_scope": normalized.dimension.scope,
                },
            )

            # ----- ANALYZING -----
            self._enter(record, SessionState.ANALYZING, "data_fetched")
            t0 = time.perf_counter()
            record.analysis = analyze(record.raw, normalized)
            self._metrics.observe_stage("analyzing", time.perf_counter() - t0)
            stages.append(
                {
                    "stage": "analyzing",
                    "kpi_count": len(record.analysis.kpis),
                    "anomaly_count": len(record.analysis.anomalies),
                    "comparison_count": len(record.analysis.comparisons),
                }
            )
            await self._emit(
                "fly_report.analyzed",
                record,
                {
                    "kpi_count": len(record.analysis.kpis),
                    "anomaly_count": len(record.analysis.anomalies),
                    "comparison_count": len(record.analysis.comparisons),
                },
            )

            # ----- PREVIEWING -----
            self._enter(record, SessionState.PREVIEWING, "analyzed")
            t0 = time.perf_counter()
            record.revision += 1
            record.ctx = compose_report_context(
                session_id=record.id,
                analysis=record.analysis,
                filt=normalized,
                revision=record.revision,
            )
            self._metrics.observe_stage("previewing", time.perf_counter() - t0)
            stages.append(
                {
                    "stage": "previewing",
                    "revision": record.ctx.revision,
                    "sections": [
                        {"id": s.id, "title": s.title, "kpis": len(s.kpis)}
                        for s in record.ctx.sections
                    ],
                }
            )
            await self._emit(
                "fly_report.previewed",
                record,
                {
                    "revision": record.ctx.revision,
                    "section_count": len(record.ctx.sections),
                },
            )
        except FlyReportError as exc:
            logger.exception(
                "fly_report.pipeline_failed",
                extra={
                    "session_id": record.id,
                    "user_id": record.user_id,
                    "state": record.state.value,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "stage": "pipeline",
                },
            )
            self._enter(record, SessionState.FAILED, "pipeline_error")
            await self._emit("fly_report.failed", record, {"stage": "pipeline"})
            raise
        except Exception as exc:
            logger.exception(
                "fly_report.pipeline_unhandled_exception",
                extra={
                    "session_id": record.id,
                    "user_id": record.user_id,
                    "state": record.state.value,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "stage": "pipeline",
                },
            )
            self._enter(record, SessionState.FAILED, "pipeline_error")
            await self._emit("fly_report.failed", record, {"stage": "pipeline"})
            raise

        # Auto-render once parsing/fetching/analyzing is complete so the
        # API caller can get a final artifact in a single round-trip.
        self._enter(record, SessionState.RENDERING, "auto_render")
        output_format = normalized.options.output_format
        session_dir = self._output_root / record.id / output_format
        t0 = time.perf_counter()
        try:
            artifact = await asyncio.wait_for(
                asyncio.to_thread(
                    self._renderer_router.render,
                    record.ctx,
                    output_format=output_format,
                    output_dir=session_dir,
                    template_ref=None,
                ),
                timeout=self._render_timeout_seconds,
            )
        except (Exception, asyncio.TimeoutError) as exc:
            logger.exception(
                "fly_report.render_failed",
                extra={
                    "session_id": record.id,
                    "user_id": record.user_id,
                    "state": record.state.value,
                    "output_format": output_format,
                    "template_ref": None,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "stage": "rendering",
                },
            )
            self._metrics.record_render(success=False)
            self._metrics.observe_stage("rendering", time.perf_counter() - t0)
            self._enter(record, SessionState.FAILED, "render_error")
            await self._emit(
                "fly_report.failed",
                record,
                {"stage": "rendering"},
            )
            raise
        self._metrics.record_render(success=True)
        self._metrics.observe_stage("rendering", time.perf_counter() - t0)
        stages.append(
            {
                "stage": "rendering",
                "output_format": artifact.output_format,
                "template_ref": artifact.template_ref,
                "filename": Path(artifact.artifact_path).name,
            }
        )
        artifact_record = {
            "output_format": artifact.output_format,
            "template_ref": artifact.template_ref,
            "artifact_path": artifact.artifact_path,
            "chart_paths": list(artifact.chart_paths),
            "warnings": list(artifact.warnings),
            "created_at": _utcnow().isoformat(),
            "filename": Path(artifact.artifact_path).name,
            "download_url": (
                f"/v1/fly-reports/sessions/{record.id}"
                f"/artifacts/{Path(artifact.artifact_path).name}"
                f"?user_id={record.user_id}"
            ),
        }
        record.artifacts.append(artifact_record)
        self._enter(record, SessionState.ARCHIVED, "render_succeeded")
        await self._emit(
            "fly_report.generated",
            record,
            {
                "output_format": artifact.output_format,
                "template_ref": artifact.template_ref,
                "filename": Path(artifact.artifact_path).name,
            },
        )

        reply = ChatTurn(
            role="assistant",
            text=(
                f"报告已生成：{artifact.artifact_path} "
                f"(format={artifact.output_format}, template={artifact.template_ref})"
            ),
            payload={
                "state": record.state.value,
                "filter_hash": normalized.hash,
                "stages": stages,
                "preview_brief": record.ctx.brief(),
                **artifact_record,
            },
        )
        record.turns.append(reply)
        record.updated_at = _utcnow()
        await self._persist_artifact(record, artifact_record)
        await self._persist_turn(record, reply)
        await self._persist_session(record)
        return reply

    # ------------------------------------------------------------------
    # confirm: PREVIEWING → RENDERING → ARCHIVED
    # ------------------------------------------------------------------

    async def confirm(
        self,
        session_id: str,
        *,
        user_id: str,
        output_format: OutputFormat = "docx",
        template_ref: str | None = None,
    ) -> ChatTurn:
        record = await self._load_session(session_id, user_id=user_id)
        if is_terminal(record.state):
            raise InvalidStateTransition(
                f"session {session_id} is terminal ({record.state.value})"
            )
        async with record.lock:
            if record.ctx is None:
                if record.last_user_text is None:
                    raise InvalidStateTransition(
                        "no preview available; send a message first"
                    )
                # Re-run pipeline with the last user text (keeps revision sane).
                await self._drive_pipeline(record, record.last_user_text)

            assert record.ctx is not None  # for mypy / clarity

            self._enter(record, SessionState.RENDERING, "user_confirm")
            session_dir = self._output_root / record.id / output_format
            t0 = time.perf_counter()
            try:
                artifact = await asyncio.wait_for(
                    asyncio.to_thread(
                        self._renderer_router.render,
                        record.ctx,
                        output_format=output_format,
                        output_dir=session_dir,
                        template_ref=template_ref,
                    ),
                    timeout=self._render_timeout_seconds,
                )
            except (Exception, asyncio.TimeoutError) as exc:
                logger.exception(
                    "fly_report.render_failed",
                    extra={
                        "session_id": record.id,
                        "user_id": record.user_id,
                        "state": record.state.value,
                        "output_format": output_format,
                        "template_ref": template_ref,
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                        "stage": "rendering",
                    },
                )
                self._metrics.record_render(success=False)
                self._metrics.observe_stage(
                    "rendering", time.perf_counter() - t0
                )
                self._enter(record, SessionState.FAILED, "render_error")
                await self._emit(
                    "fly_report.failed",
                    record,
                    {"stage": "rendering"},
                )
                raise
            self._metrics.record_render(success=True)
            self._metrics.observe_stage("rendering", time.perf_counter() - t0)

            artifact_record = {
                "output_format": artifact.output_format,
                "template_ref": artifact.template_ref,
                "artifact_path": artifact.artifact_path,
                "chart_paths": list(artifact.chart_paths),
                "warnings": list(artifact.warnings),
                "created_at": _utcnow().isoformat(),
                "filename": Path(artifact.artifact_path).name,
                # Surface the download URL the API exposes (matches router).
                "download_url": (
                    f"/v1/fly-reports/sessions/{record.id}"
                    f"/artifacts/{Path(artifact.artifact_path).name}"
                    f"?user_id={record.user_id}"
                ),
            }
            record.artifacts.append(artifact_record)
            self._enter(record, SessionState.ARCHIVED, "render_succeeded")
            await self._emit(
                "fly_report.generated",
                record,
                {
                    "output_format": artifact.output_format,
                    "template_ref": artifact.template_ref,
                    "filename": Path(artifact.artifact_path).name,
                },
            )

            reply = ChatTurn(
                role="assistant",
                text=(
                    f"已生成 {artifact.output_format} 报告："
                    f"{artifact.artifact_path} (template={artifact.template_ref})"
                ),
                payload=artifact_record,
            )
            record.turns.append(reply)
            record.updated_at = _utcnow()
            await self._persist_artifact(record, artifact_record)
            await self._persist_turn(record, reply)
            await self._persist_session(record)
            return reply

    # ------------------------------------------------------------------
    # cancel
    # ------------------------------------------------------------------

    async def cancel(self, session_id: str, *, user_id: str) -> ChatTurn:
        record = await self._load_session(session_id, user_id=user_id)
        async with record.lock:
            self._enter(record, SessionState.CANCELLED, "user_cancel")
            reply = ChatTurn(role="system", text="session cancelled")
            record.turns.append(reply)
            record.updated_at = _utcnow()
            await self._persist_turn(record, reply)
            await self._persist_session(record)
            return reply

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    async def list_user_sessions(
        self,
        *,
        tenant_id: str,
        user_id: str,
        limit: int = 50,
        keyword: str | None = None,
        state_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return recent sessions for ``user_id``.

        Merges the durable view (``repo.list_sessions_for_user``) with the
        live in-memory cache so users see sessions that have not yet been
        persisted (e.g. when running with the in-memory repo).

        Optional ``keyword`` filters by substring match (case-insensitive)
        against ``title`` / ``last_user_text``. ``state_filter`` restricts
        results to a single :class:`SessionState` value (DESIGN-3 R3.1).
        """
        seen: dict[str, dict[str, Any]] = {}
        for r in self._sessions.values():
            if r.tenant_id == tenant_id and r.user_id == user_id:
                seen[r.id] = {
                    "session_id": r.id,
                    "state": r.state.value,
                    "title": r.title,
                    "last_user_text": r.last_user_text,
                    "revision": r.revision,
                    "created_at": r.created_at,
                    "updated_at": r.updated_at,
                }
        for row in await self._repo.list_sessions_for_user(
            tenant_id=tenant_id, user_id=user_id, limit=limit
        ):
            seen.setdefault(row["session_id"], row)
        rows = sorted(
            seen.values(),
            key=lambda x: str(x.get("updated_at") or ""),
            reverse=True,
        )
        if state_filter:
            rows = [r for r in rows if r.get("state") == state_filter]
        if keyword:
            needle = keyword.lower()
            rows = [
                r
                for r in rows
                if needle in (r.get("title") or "").lower()
                or needle in (r.get("last_user_text") or "").lower()
            ]
        return rows[:limit]

    async def get_session_snapshot(
        self, session_id: str, *, user_id: str
    ) -> dict[str, Any]:
        record = await self._load_session(session_id, user_id=user_id)
        return {
            "session_id": record.id,
            "state": record.state.value,
            "filter_spec": record.filter_spec.model_dump(mode="json"),
            "title": record.title,
            "last_user_text": record.last_user_text,
            "turn_count": len(record.turns),
            "revision": record.revision,
            "artifacts": list(record.artifacts),
            "state_history": list(record.state_history),
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }

    async def list_turns(
        self, session_id: str, *, user_id: str
    ) -> list[ChatTurn]:
        record = await self._load_session(session_id, user_id=user_id)
        return list(record.turns)

    # ------------------------------------------------------------------
    # Artifact access (used by the download endpoint)
    # ------------------------------------------------------------------

    async def get_artifact_path(
        self, session_id: str, filename: str, *, user_id: str
    ) -> Path:
        """Resolve ``filename`` to an on-disk path for a session.

        Constraints (defence in depth):
        - The session must exist for ``user_id``.
        - The filename must match one of the recorded artifacts (no traversal).
        - The resolved path must live under the session's output root.
        """
        record = await self._load_session(session_id, user_id=user_id)
        if "/" in filename or "\\" in filename or filename in {"", ".", ".."}:
            raise FileNotFoundError(filename)

        session_root = (self._output_root / record.id).resolve()
        for artifact in record.artifacts:
            if Path(artifact["artifact_path"]).name == filename:
                target = Path(artifact["artifact_path"]).resolve()
                try:
                    target.relative_to(session_root)
                except ValueError as exc:
                    raise FileNotFoundError(filename) from exc
                if not target.is_file():
                    raise FileNotFoundError(filename)
                return target
        raise FileNotFoundError(filename)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _emit(
        self,
        topic: str,
        record: _SessionRecord,
        payload: dict[str, Any] | None = None,
    ) -> None:
        if self._event_bus is None:
            return
        try:
            await self._event_bus.publish(
                make_event(
                    topic,
                    tenant_id=record.tenant_id,
                    session_id=record.id,
                    payload=payload or {},
                )
            )
        except Exception:  # pragma: no cover - events are best-effort
            logger.exception(
                "fly_report.event_emit_failed",
                extra={"topic": topic, "session_id": record.id},
            )

    def _enter(  # TODO 没有理解
        self,
        record: _SessionRecord,
        next_state: SessionState,
        reason: str | None,
    ) -> None:
        prev = record.state
        if prev == next_state:
            # Re-entering the same state (e.g. PREVIEWING during confirm
            # after a re-walk) is a no-op for the state machine.
            return
        assert_transition(prev, next_state)
        record.state = next_state
        record.state_history.append((prev.value, next_state.value, reason))
        record.updated_at = _utcnow()
        logger.debug(
            "fly_report.state_transition",
            extra={
                "session_id": record.id,
                "from": prev.value,
                "to": next_state.value,
                "reason": reason,
            },
        )

    def _require_session(
        self, session_id: str, *, user_id: str
    ) -> _SessionRecord:
        record = self._sessions.get(session_id)
        if record is None:
            raise SessionNotFound(f"session {session_id} not found")
        if record.user_id != user_id:
            raise SessionNotFound(f"session {session_id} not found")
        return record

    # ---- persistence helpers ----

    def _session_payload(self, record: _SessionRecord) -> dict[str, Any]:
        return {
            "id": record.id,
            "tenant_id": record.tenant_id,
            "user_id": record.user_id,
            "state": record.state.value,
            "title": record.title,
            "last_user_text": record.last_user_text,
            "revision": record.revision,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "filter_spec": record.filter_spec.model_dump(mode="json"),
            "state_history": list(record.state_history),
            "turn_count": len(record.turns),
            "artifacts": list(record.artifacts),
        }

    async def _persist_session(self, record: _SessionRecord) -> None:
        try:
            await self._repo.upsert_session(self._session_payload(record))
        except Exception:  # pragma: no cover - best-effort durability
            logger.exception(
                "fly_report.persist_session_failed",
                extra={"session_id": record.id},
            )

    async def _persist_turn(
        self, record: _SessionRecord, turn: ChatTurn
    ) -> None:
        try:
            await self._repo.append_turn(
                record.id,
                {
                    "role": turn.role,
                    "text": turn.text,
                    "payload": turn.payload,
                    "created_at": _utcnow(),
                },
            )
        except Exception:  # pragma: no cover
            logger.exception(
                "fly_report.persist_turn_failed",
                extra={"session_id": record.id},
            )

    async def _persist_artifact(
        self, record: _SessionRecord, artifact: dict[str, Any]
    ) -> None:
        try:
            await self._repo.append_artifact(
                record.id,
                {**artifact, "created_at": _utcnow()},
            )
        except Exception:  # pragma: no cover
            logger.exception(
                "fly_report.persist_artifact_failed",
                extra={"session_id": record.id},
            )

    async def _persist_audit(
        self,
        record: _SessionRecord,
        *,
        decision_value: str,
        reason: str,
        scope_required: str,
        payload: dict[str, Any],
    ) -> None:
        try:
            await self._repo.append_audit(
                record.id,
                {
                    "tenant_id": record.tenant_id,
                    "user_id": record.user_id,
                    "decision": decision_value,
                    "reason": reason,
                    "scope_required": scope_required,
                    "payload": payload,
                    "created_at": _utcnow(),
                },
            )
        except Exception:  # pragma: no cover
            logger.exception(
                "fly_report.persist_audit_failed",
                extra={"session_id": record.id},
            )

    async def list_audits(
        self, session_id: str, *, user_id: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        await self._load_session(session_id, user_id=user_id)
        return await self._repo.list_audits(session_id, limit=limit)

    async def render_preview_html(
        self, session_id: str, *, user_id: str
    ) -> str:
        """Render the current ``ReportContext`` as preview HTML.

        Raises :class:`InvalidStateTransition` when no preview is ready
        (e.g. session is still in PARSING / CLARIFYING).
        """
        from swarmmind.domains.fly_report.composer.preview_renderer import (
            render_preview_html,
        )

        record = await self._load_session(session_id, user_id=user_id)
        if record.ctx is None:
            raise InvalidStateTransition(
                "no preview available; send a message first"
            )
        return render_preview_html(record.ctx)

    # ------------------------------------------------------------------
    # Maintenance / cleanup
    # ------------------------------------------------------------------

    async def cleanup_old_sessions(
        self,
        *,
        max_age_days: int = 30,
        now: datetime | None = None,
    ) -> dict[str, int]:
        """Remove artifact files on disk older than ``max_age_days``.

        Best-effort. Returns ``{"removed_dirs": n, "scanned": n}``. The
        in-memory session cache is pruned for matching sessions; durable
        rows are left to the DB retention policy (no cascade delete
        here — DESIGN-3 R3.4 intentionally scopes disk-only cleanup).
        """
        cutoff = (now or _utcnow()) - timedelta(days=max_age_days)
        removed = 0
        scanned = 0
        if not self._output_root.exists():
            return {"removed_dirs": 0, "scanned": 0}
        for child in self._output_root.iterdir():
            if not child.is_dir():
                continue
            scanned += 1
            try:
                mtime = datetime.fromtimestamp(
                    child.stat().st_mtime, tz=SHANGHAI_TZ
                )
            except OSError:
                continue
            if mtime < cutoff:
                try:
                    shutil.rmtree(child, ignore_errors=True)
                    removed += 1
                except Exception:  # pragma: no cover - defensive
                    logger.exception(
                        "fly_report.cleanup_rmtree_failed",
                        extra={"path": str(child)},
                    )
                # Drop any matching session from the memory cache.
                self._sessions.pop(child.name, None)
        logger.info(
            "fly_report.cleanup_done",
            extra={
                "removed": removed,
                "scanned": scanned,
                "max_age_days": max_age_days,
            },
        )
        return {"removed_dirs": removed, "scanned": scanned}

    async def _load_session(
        self, session_id: str, *, user_id: str
    ) -> _SessionRecord:
        """Return the in-memory record, or rehydrate from the repo.

        Rehydration is best-effort: only enough fields are restored to
        recognise the session and serve metadata / downloads. Live state
        (raw / analysis / ctx) is *not* re-derived; callers that need it
        should ``send_message`` again.
        """
        existing = self._sessions.get(session_id)
        if existing is not None:
            if existing.user_id != user_id:
                raise SessionNotFound(f"session {session_id} not found")
            return existing
        payload = await self._repo.get_session(session_id)
        if payload is None:
            raise SessionNotFound(f"session {session_id} not found")
        if payload.get("user_id") != user_id:
            raise SessionNotFound(f"session {session_id} not found")
        record = _rehydrate(payload)
        self._sessions[session_id] = record
        return record


def _rehydrate(payload: dict[str, Any]) -> _SessionRecord:
    state_value = payload.get("state", SessionState.PARSING.value)
    try:
        state = SessionState(state_value)
    except ValueError:
        state = SessionState.PARSING
    filter_spec_raw = payload.get("filter_spec") or {}
    try:
        filter_spec = FilterSpec(**filter_spec_raw)
    except Exception:
        filter_spec = FilterSpec()
    return _SessionRecord(
        id=payload["id"],
        tenant_id=payload.get("tenant_id", ""),
        user_id=payload.get("user_id", ""),
        state=state,
        filter_spec=filter_spec,
        revision=int(payload.get("revision", 0)),
        artifacts=list(payload.get("artifacts") or []),
        state_history=[tuple(t) for t in payload.get("state_history") or []],
        last_user_text=payload.get("last_user_text"),
        title=payload.get("title"),
    )


__all__ = ["FlyReportService", "FlyReportError"]
