from __future__ import annotations

import asyncio
import html
import logging
import shutil
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, AsyncIterator
from zoneinfo import ZoneInfo

from swarmmind.config.settings import get_settings
from swarmmind.domains.fly_report.analyzer import analyze
from swarmmind.domains.fly_report.composer import compose_report_context
from swarmmind.domains.fly_report.conflict_checker import (
    check_conflicts,
    merge_drafts,
)
from swarmmind.domains.fly_report.data_fetcher import DataFetcher
from swarmmind.domains.fly_report.errors import (
    FlyReportError,
    InvalidStateTransition,
    PermissionDenied,
    SessionNotFound,
)
from swarmmind.domains.fly_report.export import RendererRouter
from swarmmind.domains.fly_report.export.base import RenderedArtifact
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
    FlyReportInteraction,
    FlyReportMessage,
    FlyReportMessageType,
    InteractionPhase,
    NormalizedFilter,
    OutputFormat,
    RawDataset,
    SessionState,
)
from swarmmind.domains.fly_report.state_machine import (
    assert_transition,
    is_terminal,
)

logger = logging.getLogger(__name__)

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
REPORT_MARKDOWN_TITLE = "武义飞行服务平台飞行统计报告"

def _utcnow() -> datetime:
    return datetime.now(SHANGHAI_TZ)


def _empty_filter_spec() -> FilterSpec:
    return FilterSpec.model_construct(
        period=None,
        dept_names=[],
        missing=[],
        conflicts=[],
    )


@dataclass
class _SessionRecord:
    id: str
    tenant_id: str
    user_id: str
    state: SessionState = SessionState.PARSING
    filter_spec: FilterSpec = field(default_factory=_empty_filter_spec)
    raw: RawDataset | None = None
    analysis: AnalysisResult | None = None
    ctx: str | None = None
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


@dataclass
class _InteractionRuntime:
    interaction_id: str
    session_id: str
    user_id: str
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    started_at: datetime | None = None


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class FlyReportService:
    """Conversational FlyReport orchestrator.

    Parameters
    ----------
    intent_parser:
        Anything with ``async parse(text) -> DraftFilterSpec``.
    data_fetcher:
        Pre-built :class:`DataFetcher`.
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
        self._interactions: dict[str, FlyReportInteraction] = {}
        self._interaction_tasks: dict[str, asyncio.Task] = {}
        self._interaction_runtimes: dict[str, _InteractionRuntime] = {}
        self._interaction_subscribers: dict[str, set[asyncio.Queue]] = {}
        self._messages_by_session: dict[str, list[FlyReportMessage]] = {}
        self._messages_by_id: dict[str, FlyReportMessage] = {}
        self._message_sequences: dict[str, int] = {}
        self._stream_lock = asyncio.Lock()

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
    # Streaming interactions
    # ------------------------------------------------------------------

    async def start_streaming_message(
        self,
        session_id: str,
        text: str,
        *,
        user_id: str,
        output_format: OutputFormat | None = None,
        template_ref: str | None = None,
        metadata: dict[str, Any] | None = None,
        start_background: bool = True,
    ) -> FlyReportInteraction:
        if not isinstance(text, str) or not text.strip():
            raise InvalidStateTransition("text must be a non-empty string")
        if len(text) > self._max_text_length:
            raise InvalidStateTransition(
                f"text length {len(text)} exceeds max {self._max_text_length}"
            )
        record = await self._load_session(session_id, user_id=user_id)
        async with self._stream_lock:
            interaction = FlyReportInteraction(
                id=f"it_{uuid.uuid4().hex}",
                session_id=record.id,
                tenant_id=record.tenant_id,
                user_id=record.user_id,
                status="pending",
                phase="intake",
                input_text=text,
                output_format=output_format,
                template_ref=template_ref,
                payload={"metadata": metadata or {}},
                created_at=_utcnow(),
                updated_at=_utcnow(),
            )
            self._interactions[interaction.id] = interaction
            self._interaction_runtimes[interaction.id] = _InteractionRuntime(
                interaction_id=interaction.id,
                session_id=record.id,
                user_id=record.user_id,
            )
            self._interaction_subscribers.setdefault(interaction.id, set())
            await self._persist_interaction(interaction)
            await self._record_interaction_message(
                interaction,
                role="user",
                message_type="plain_text",
                text=text,
                status="completed",
                payload={"data": {}, "actions": [], "meta": metadata or {}},
                publish=False,
            )
            if start_background:
                self._start_interaction_task(interaction.id)
        return interaction

    async def stream_interaction_events(
        self, interaction_id: str, *, start_background: bool = False
    ) -> AsyncIterator[dict[str, Any]]:
        interaction = await self.get_interaction(interaction_id)
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        self._interaction_subscribers.setdefault(interaction_id, set()).add(queue)
        if start_background:
            self._start_interaction_task(interaction_id)
        yield {
            "event": "interaction.started",
            "data": self._interaction_payload(interaction),
        }
        if interaction.status in {"completed", "failed", "cancelled"}:
            yield self._terminal_event(interaction)
            return
        try:
            while True:
                item = await queue.get()
                if item is None:
                    latest = await self.get_interaction(interaction_id)
                    yield self._terminal_event(latest)
                    return
                yield item
        finally:
            subscribers = self._interaction_subscribers.get(interaction_id)
            if subscribers is not None:
                subscribers.discard(queue)

    def _start_interaction_task(self, interaction_id: str) -> None:
        existing = self._interaction_tasks.get(interaction_id)
        if existing is not None and not existing.done():
            return
        self._interaction_tasks[interaction_id] = asyncio.create_task(
            self._run_streaming_interaction(interaction_id)
        )

    async def get_interaction(
        self, interaction_id: str, *, user_id: str | None = None
    ) -> FlyReportInteraction:
        interaction = self._interactions.get(interaction_id)
        if interaction is None:
            payload = await self._repo.get_interaction(interaction_id)
            if payload is None:
                raise SessionNotFound(f"interaction {interaction_id} not found")
            interaction = FlyReportInteraction.model_validate(payload)
            self._interactions[interaction_id] = interaction
        if user_id is not None and interaction.user_id != user_id:
            raise SessionNotFound(f"interaction {interaction_id} not found")
        return interaction

    async def cancel_interaction(
        self, interaction_id: str, *, user_id: str, reason: str | None = None
    ) -> FlyReportInteraction:
        interaction = await self.get_interaction(interaction_id, user_id=user_id)
        if interaction.status in {"completed", "failed", "cancelled"}:
            raise InvalidStateTransition(
                f"interaction {interaction_id} is terminal ({interaction.status})"
            )
        runtime = self._interaction_runtimes.get(interaction_id)
        if runtime is not None:
            runtime.cancel_event.set()
        await self._update_interaction(
            interaction,
            status="cancelled",
            phase=interaction.phase,
            error=reason or "user_requested",
            completed_at=_utcnow(),
        )
        await self._record_interaction_message(
            interaction,
            role="system",
            message_type="error",
            title="已取消",
            text="Interaction cancellation accepted",
            status="cancelled",
            payload={"data": {"reason": reason or "user_requested"}},
        )
        await self._finish_interaction_stream(interaction.id)
        return interaction

    async def list_messages(
        self,
        session_id: str,
        *,
        user_id: str,
        limit: int = 100,
        before_message_id: str | None = None,
    ) -> list[FlyReportMessage]:
        record = await self._load_session(session_id, user_id=user_id)
        rows = await self._repo.list_messages(
            record.id,
            user_id=user_id,
            limit=max(1, min(limit, 500)),
            before_message_id=before_message_id,
        )
        if rows:
            return [FlyReportMessage.model_validate(row) for row in rows]
        messages = list(self._messages_by_session.get(record.id, []))
        if before_message_id:
            before_index = next(
                (i for i, msg in enumerate(messages) if msg.id == before_message_id),
                len(messages),
            )
            messages = messages[:before_index]
        return messages[: max(1, min(limit, 500))]

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
            self._enter(record, SessionState.PARSING, "user_message")
            t0 = time.perf_counter()
            dept_names = await self._data_fetcher.get_department_name_list_by_id_list(
                dept_id_list=config.fly_report.dikong.department_id_list
            )
            parse_ctx = self._build_intent_parse_context(record, text, dept_names)
            draft = await self._intent_parser.parse(**parse_ctx)

            self._metrics.observe_stage("parsing", time.perf_counter() - t0)
            # Merge follow-up clarifications with the previously-known filter.
            had_prior_spec = bool(
                record.filter_spec.period
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
            normalized.dept_ids = [ int(_id) for name, _id in zip(dept_names, config.fly_report.dikong.department_id_list) if name in normalized.dept_names ]
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
                }
            )
            await self._emit(
                "fly_report.analyzed",
                record,
                {},
            )

            # ----- PREVIEWING -----
            self._enter(record, SessionState.PREVIEWING, "analyzed")
            t0 = time.perf_counter()
            record.revision += 1
            record.ctx = await compose_report_context(
                session_id=record.id,
                analysis=record.analysis,
                filt=normalized,
                revision=record.revision,
            )
            if not isinstance(record.ctx, str):
                raise TypeError("compose_report_context must return a Markdown string")
            preview_brief = _context_preview_brief(record.ctx, record, normalized)
            section_summaries = _context_section_summaries(record.ctx)
            self._metrics.observe_stage("previewing", time.perf_counter() - t0)
            stages.append(
                {
                    "stage": "previewing",
                    "revision": record.revision,
                    "sections": section_summaries,
                }
            )
            await self._emit(
                "fly_report.previewed",
                record,
                {
                    "revision": record.revision,
                    "section_count": len(section_summaries),
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

        reply = ChatTurn(
            role="assistant",
            text="已生成报告预览，请确认后导出。",
            payload={
                "state": record.state.value,
                "filter_hash": normalized.hash,
                "stages": stages,
                "preview_brief": preview_brief,
            },
        )
        record.turns.append(reply)
        record.updated_at = _utcnow()
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
                        self._render_context,
                        record,
                        output_format,
                        session_dir,
                        template_ref,
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

    async def list_artifacts(
        self,
        session_id: str,
        *,
        user_id: str,
        interaction_id: str | None = None,
    ) -> list[dict[str, Any]]:
        record = await self._load_session(session_id, user_id=user_id)
        artifacts = list(record.artifacts)
        if not artifacts:
            artifacts = await self._repo.list_artifacts(record.id)
        if interaction_id:
            artifacts = [
                artifact
                for artifact in artifacts
                if artifact.get("interaction_id") == interaction_id
            ]
        return artifacts

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

    @staticmethod
    def _build_intent_parse_context(
        record: _SessionRecord,
        text: str,
        dept_names: list[str],
    ) -> dict[str, Any]:
        """Collect structured context for :meth:`IntentParser.parse`.

        Mirrors ``Planner._compose_planning_prompt`` — service gathers the
        business context, parser renders it into the user prompt.
        """
        # Determine whether we already have a prior filter (multi-turn).
        has_prior = bool(
            record.filter_spec.period
            or record.filter_spec.dimension.scope != "overall"
        )
        return {
            "user_text": text,
            "now": _utcnow(),
            "dept_names": dept_names,
            "preference": None,
            "existing_filter": record.filter_spec if has_prior else None,
            "recent_turns": record.turns[-6:] if record.turns else None,
        }

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

    def _render_context(
        self,
        record: _SessionRecord,
        output_format: OutputFormat,
        output_dir: Path,
        template_ref: str | None,
    ) -> RenderedArtifact:
        if record.ctx is None:
            raise InvalidStateTransition("no report markdown available")

        markdown = record.ctx
        if output_format == "markdown":
            output_dir.mkdir(parents=True, exist_ok=True)
            path = output_dir / _artifact_filename(record, "md")
            path.write_text(markdown, encoding="utf-8")
            return RenderedArtifact(
                output_format="markdown",
                artifact_path=str(path),
                template_ref=template_ref or "markdown:direct",
            )

        if output_format == "docx":
            return self._renderer_router.render_markdown_to_docx(
                markdown,
                output_dir=output_dir,
                filename=_artifact_filename(record, "docx"),
                template_ref=template_ref,
                title=record.title or REPORT_MARKDOWN_TITLE,
            )

        raise ValueError(
            "FlyReport service now renders from Markdown only; "
            "supported formats are 'docx' and 'markdown'."
        )

    async def _run_streaming_interaction(self, interaction_id: str) -> None:
        interaction = await self.get_interaction(interaction_id)
        runtime = self._interaction_runtimes.get(interaction_id)
        started_at = _utcnow()
        if runtime is not None:
            runtime.started_at = started_at
        await self._update_interaction(
            interaction,
            status="streaming",
            phase="intake",
            started_at=started_at,
        )
        try:
            if self._is_report_request(interaction.input_text):
                await self._run_report_interaction(interaction)
            else:
                await self._run_plain_text_interaction(interaction)
        except asyncio.CancelledError:
            await self._update_interaction(
                interaction,
                status="cancelled",
                error="task_cancelled",
                completed_at=_utcnow(),
            )
            await self._finish_interaction_stream(interaction.id)
            raise
        except Exception as exc:
            logger.exception(
                "fly_report.streaming_interaction_failed",
                extra={
                    "interaction_id": interaction.id,
                    "session_id": interaction.session_id,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                },
            )
            await self._update_interaction(
                interaction,
                status="failed",
                error=str(exc),
                completed_at=_utcnow(),
            )
            await self._record_interaction_message(
                interaction,
                role="assistant",
                message_type="error",
                title="处理失败",
                text=str(exc) or "报告处理失败。",
                status="failed",
                payload={"data": {}, "actions": [], "meta": {"source": "fly_report"}},
            )
            await self._finish_interaction_stream(interaction.id)

    async def _run_plain_text_interaction(
        self, interaction: FlyReportInteraction
    ) -> None:
        await self._ensure_not_cancelled(interaction)
        message_id = f"msg_{uuid.uuid4().hex}"
        answer = self._plain_text_answer(interaction.input_text)
        midpoint = max(1, len(answer) // 2)
        for chunk in (answer[:midpoint], answer[midpoint:]):
            if not chunk:
                continue
            await self._publish_interaction_event(
                interaction.id,
                {
                    "event": "message.delta",
                    "data": {
                        "message_id": message_id,
                        "interaction_id": interaction.id,
                        "text": chunk,
                    },
                },
            )
        await self._record_interaction_message(
            interaction,
            message_id=message_id,
            role="assistant",
            message_type="plain_text",
            text=answer,
            status="completed",
            payload={"data": {}, "actions": [], "meta": {"source": "fly_report"}},
        )
        await self._update_interaction(
            interaction,
            status="completed",
            phase="done",
            completed_at=_utcnow(),
        )
        await self._finish_interaction_stream(interaction.id)

    async def _run_report_interaction(
        self, interaction: FlyReportInteraction
    ) -> None:
        record = await self._load_session(
            interaction.session_id, user_id=interaction.user_id
        )
        async with record.lock:
            await self._ensure_not_cancelled(interaction)
            await self._emit_phase(interaction, "parsing", "解析需求", "正在解析你的报告需求。")
            await self._record_interaction_message(
                interaction,
                role="assistant",
                message_type="todo",
                title="报告生成计划",
                text="已生成报告处理计划。",
                status="running",
                payload={
                    "data": {
                        "items": [
                            {"id": "step_1", "text": "解析报告时间和范围", "status": "running"},
                            {"id": "step_2", "text": "获取并分析业务数据", "status": "pending"},
                            {"id": "step_3", "text": "生成报告文件", "status": "pending"},
                        ]
                    },
                    "actions": [],
                    "meta": {"source": "fly_report", "phase": "parsing"},
                },
            )
            if is_terminal(record.state):
                record.state = SessionState.PARSING
            turn = await self._drive_pipeline(record, interaction.input_text)
            await self._ensure_not_cancelled(interaction)
            await self._emit_phase(interaction, "rendering", "生成文件", "正在生成报告文件。")
            assert record.ctx is not None
            output_format = interaction.output_format or _context_output_format(record)
            session_dir = self._output_root / record.id / output_format
            t0 = time.perf_counter()
            artifact = await asyncio.wait_for(
                asyncio.to_thread(
                    self._render_context,
                    record,
                    output_format,
                    session_dir,
                    interaction.template_ref,
                ),
                timeout=self._render_timeout_seconds,
            )
            self._metrics.record_render(success=True)
            self._metrics.observe_stage("rendering", time.perf_counter() - t0)
            await self._ensure_not_cancelled(interaction)
            filename = Path(artifact.artifact_path).name
            artifact_record = {
                "interaction_id": interaction.id,
                "output_format": artifact.output_format,
                "template_ref": artifact.template_ref,
                "content_type": _content_type_for_format(artifact.output_format, filename),
                "artifact_path": artifact.artifact_path,
                "chart_paths": list(artifact.chart_paths),
                "warnings": list(artifact.warnings),
                "created_at": _utcnow().isoformat(),
                "filename": filename,
                "download_url": (
                    f"/v1/fly-reports/sessions/{record.id}"
                    f"/artifacts/{filename}?user_id={record.user_id}"
                ),
            }
            record.artifacts.append(artifact_record)
            record.updated_at = _utcnow()
            await self._persist_artifact(record, artifact_record)
            await self._persist_session(record)
            await self._update_interaction(
                interaction,
                phase="delivering",
                artifact_count=interaction.artifact_count + 1,
            )
            await self._record_interaction_message(
                interaction,
                role="assistant",
                message_type="artifact",
                title="报告已生成",
                text="报告文件已生成。",
                status="completed",
                payload={
                    "data": {
                        "artifact_id": filename,
                        "artifact_name": filename,
                        "content_type": artifact_record["content_type"],
                        "download_url": artifact_record["download_url"],
                    },
                    "actions": [],
                    "meta": {"source": "fly_report", "phase": "delivering"},
                },
            )
            await self._record_interaction_message(
                interaction,
                role="assistant",
                message_type="summary",
                title="处理完成",
                text=turn.text,
                status="completed",
                payload={
                    "data": {"preview_brief": (turn.payload or {}).get("preview_brief")},
                    "actions": [],
                    "meta": {"source": "fly_report", "phase": "done"},
                },
            )
        await self._update_interaction(
            interaction,
            status="completed",
            phase="done",
            completed_at=_utcnow(),
        )
        await self._finish_interaction_stream(interaction.id)

    async def _emit_phase(
        self,
        interaction: FlyReportInteraction,
        phase: InteractionPhase,
        label: str,
        text: str,
    ) -> None:
        await self._update_interaction(interaction, phase=phase)
        await self._record_interaction_message(
            interaction,
            role="assistant",
            message_type="phase",
            title="阶段更新",
            text=text,
            status="running",
            payload={
                "data": {"phase": phase, "label": label},
                "actions": [],
                "meta": {"source": "fly_report", "phase": phase},
            },
        )

    async def _ensure_not_cancelled(
        self, interaction: FlyReportInteraction
    ) -> None:
        runtime = self._interaction_runtimes.get(interaction.id)
        if runtime is not None and runtime.cancel_event.is_set():
            raise asyncio.CancelledError()
        latest = await self.get_interaction(interaction.id)
        if latest.status == "cancelled":
            raise asyncio.CancelledError()

    async def _record_interaction_message(
        self,
        interaction: FlyReportInteraction,
        *,
        role: str,
        message_type: FlyReportMessageType,
        text: str,
        status: str = "completed",
        title: str | None = None,
        payload: dict[str, Any] | None = None,
        message_id: str | None = None,
        publish: bool = True,
    ) -> FlyReportMessage:
        sequence = self._message_sequences.get(interaction.id, 0) + 1
        self._message_sequences[interaction.id] = sequence
        now = _utcnow()
        message = FlyReportMessage(
            id=message_id or f"msg_{uuid.uuid4().hex}",
            session_id=interaction.session_id,
            interaction_id=interaction.id,
            tenant_id=interaction.tenant_id,
            user_id=interaction.user_id,
            role=role,  # type: ignore[arg-type]
            message_type=message_type,
            status=status,  # type: ignore[arg-type]
            title=title,
            text=text,
            sequence=sequence,
            payload=payload or {"data": {}, "actions": [], "meta": {}},
            created_at=now,
            updated_at=now,
        )
        self._messages_by_id[message.id] = message
        self._messages_by_session.setdefault(interaction.session_id, []).append(message)
        await self._repo.append_message(message.model_dump(mode="json"))
        await self._update_interaction(
            interaction,
            message_count=interaction.message_count + 1,
        )
        if publish:
            await self._publish_interaction_event(
                interaction.id,
                {"event": "message.item", "data": self._message_payload(message)},
            )
        return message

    async def _update_interaction(
        self,
        interaction: FlyReportInteraction,
        **changes: Any,
    ) -> FlyReportInteraction:
        for key, value in changes.items():
            if value is not None or key in {"error", "completed_at"}:
                setattr(interaction, key, value)
        interaction.updated_at = _utcnow()
        self._interactions[interaction.id] = interaction
        await self._persist_interaction(interaction)
        return interaction

    async def _persist_interaction(
        self, interaction: FlyReportInteraction
    ) -> None:
        try:
            await self._repo.upsert_interaction(interaction.model_dump(mode="json"))
        except Exception:  # pragma: no cover
            logger.exception(
                "fly_report.persist_interaction_failed",
                extra={"interaction_id": interaction.id},
            )

    async def _publish_interaction_event(
        self, interaction_id: str, event: dict[str, Any]
    ) -> None:
        for queue in list(self._interaction_subscribers.get(interaction_id, set())):
            await queue.put(event)

    async def _finish_interaction_stream(self, interaction_id: str) -> None:
        for queue in list(self._interaction_subscribers.get(interaction_id, set())):
            await queue.put(None)

    def _interaction_payload(self, interaction: FlyReportInteraction) -> dict[str, Any]:
        return {
            "interaction_id": interaction.id,
            "session_id": interaction.session_id,
            "status": interaction.status,
            "phase": interaction.phase,
            "message_count": interaction.message_count,
            "artifact_count": interaction.artifact_count,
            "created_at": interaction.created_at.isoformat(),
            "started_at": interaction.started_at.isoformat() if interaction.started_at else None,
            "completed_at": interaction.completed_at.isoformat() if interaction.completed_at else None,
            "error": interaction.error,
        }

    def _terminal_event(self, interaction: FlyReportInteraction) -> dict[str, Any]:
        event_name = {
            "completed": "interaction.completed",
            "failed": "interaction.failed",
            "cancelled": "interaction.cancelled",
        }.get(interaction.status, "interaction.completed")
        return {"event": event_name, "data": self._interaction_payload(interaction)}

    def _message_payload(self, message: FlyReportMessage) -> dict[str, Any]:
        payload = message.payload or {}
        return {
            "message_id": message.id,
            "interaction_id": message.interaction_id,
            "role": message.role,
            "type": message.message_type,
            "title": message.title,
            "text": message.text,
            "status": message.status,
            "created_at": message.created_at.isoformat(),
            "data": payload.get("data") or {},
            "actions": payload.get("actions") or [],
            "meta": payload.get("meta") or {},
        }

    @staticmethod
    def _is_report_request(text: str) -> bool:
        lowered = text.lower()
        keywords = ("报告", "周报", "月报", "导出", "docx", "pdf", "markdown", "生成")
        return any(keyword in lowered for keyword in keywords)

    @staticmethod
    def _plain_text_answer(text: str) -> str:
        return f"已收到你的问题：{text}。当前 FlyReport 会话可以继续生成报告或解释已有指标。"

    async def list_audits(
        self, session_id: str, *, user_id: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        await self._load_session(session_id, user_id=user_id)
        return await self._repo.list_audits(session_id, limit=limit)

    async def render_preview_html(
        self, session_id: str, *, user_id: str
    ) -> str:
        """Render the current Markdown report as preview HTML.

        Raises :class:`InvalidStateTransition` when no preview is ready
        (e.g. session is still in PARSING / CLARIFYING).
        """
        record = await self._load_session(session_id, user_id=user_id)
        if record.ctx is None:
            raise InvalidStateTransition(
                "no preview available; send a message first"
            )
        return _render_markdown_preview_html(record.ctx, record)

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


def _context_output_format(record: _SessionRecord) -> OutputFormat:
    return record.filter_spec.options.output_format


def _artifact_filename(record: _SessionRecord, suffix: str) -> str:
    return f"fly-report-r{record.revision}.{suffix}"


def _context_preview_brief(
    markdown: str,
    record: _SessionRecord,
    filt: NormalizedFilter,
) -> dict[str, Any]:
    preview_lines = [
        line.strip()
        for line in markdown.splitlines()
        if line.strip()
        and not line.lstrip().startswith("!")
        and not line.lstrip().startswith("|")
    ]
    excerpt = "\n".join(preview_lines[:8])
    return {
        "revision": record.revision,
        "period": filt.period.label if filt.period else None,
        "output_format": record.filter_spec.options.output_format,
        "section_count": len(_context_section_summaries(markdown)),
        "markdown_chars": len(markdown),
        "excerpt": excerpt,
    }


def _context_section_summaries(markdown: str) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped.startswith("#"):
            continue
        hashes, _, title = stripped.partition(" ")
        if not title or any(char != "#" for char in hashes):
            continue
        sections.append(
            {
                "id": f"section_{len(sections) + 1}",
                "title": title.strip(),
                "level": len(hashes),
            }
        )
    return sections


def _render_markdown_preview_html(markdown: str, record: _SessionRecord) -> str:
    title = html.escape(record.title or REPORT_MARKDOWN_TITLE)
    body = _markdown_to_preview_body(markdown)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;max-width:960px;margin:24px auto;padding:0 16px;color:#222;line-height:1.6;}}
h1{{font-size:24px;margin:0 0 16px;}}
h2{{font-size:19px;margin:24px 0 10px;border-bottom:1px solid #eee;padding-bottom:4px;}}
h3{{font-size:16px;margin:18px 0 8px;}}
p{{margin:8px 0;}}
table{{border-collapse:collapse;width:100%;margin:10px 0;}}
th,td{{border:1px solid #ddd;padding:5px 8px;font-size:13px;}}
th{{background:#f7f7f9;text-align:left;}}
img{{display:block;max-width:100%;margin:12px auto;}}
code{{background:#f7f7f9;padding:1px 4px;border-radius:3px;}}
</style>
</head>
<body>
{body}
</body>
</html>
"""


def _markdown_to_preview_body(markdown: str) -> str:
    lines = markdown.splitlines()
    parts: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if not line:
            index += 1
            continue
        if line.startswith("#"):
            hashes, _, text = line.partition(" ")
            level = min(max(len(hashes), 1), 6)
            if text and all(char == "#" for char in hashes):
                parts.append(f"<h{level}>{html.escape(text.strip())}</h{level}>")
                index += 1
                continue
        if line.startswith("!["):
            _, _, rest = line.partition("](")
            src, _, _ = rest.partition(")")
            parts.append(f"<img src='{html.escape(src, quote=True)}' alt=''>")
            index += 1
            continue
        if line.startswith("|"):
            table_lines: list[str] = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                table_lines.append(lines[index].strip())
                index += 1
            parts.append(_render_markdown_table(table_lines))
            continue
        parts.append(f"<p>{html.escape(line)}</p>")
        index += 1
    return "\n".join(parts) or "<p><em>暂无预览内容</em></p>"


def _render_markdown_table(lines: list[str]) -> str:
    rows = [
        [cell.strip() for cell in line.strip("|").split("|")]
        for line in lines
        if line.strip("|").strip()
    ]
    rows = [
        row for row in rows if not all(set(cell) <= {"-", ":", " "} for cell in row)
    ]
    if not rows:
        return ""
    header = "".join(f"<th>{html.escape(cell)}</th>" for cell in rows[0])
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(cell)}</td>" for cell in row) + "</tr>"
        for row in rows[1:]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


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
        filter_spec = _empty_filter_spec()
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


def _content_type_for_format(output_format: str, filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if output_format == "docx" or suffix == ".docx":
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if output_format == "pdf" or suffix == ".pdf":
        return "application/pdf"
    if output_format == "markdown" or suffix in {".md", ".markdown"}:
        return "text/markdown; charset=utf-8"
    if suffix == ".html":
        return "text/html; charset=utf-8"
    return "application/octet-stream"


__all__ = ["FlyReportService", "FlyReportError"]
