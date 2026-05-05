"""HTTP API router for the FlyReport domain (DESIGN-2 §13 step 7).

Mounts the M1 / M1.5 endpoints under ``/v1/fly-reports``:

- ``GET    /v1/fly-reports/templates``                 — list built-in templates
- ``POST   /v1/fly-reports/sessions``                  — start session
- ``POST   /v1/fly-reports/sessions/{id}/messages``    — send chat message
- ``POST   /v1/fly-reports/sessions/{id}/confirm``     — confirm + pick format/template
- ``POST   /v1/fly-reports/sessions/{id}/cancel``      — cancel session
- ``GET    /v1/fly-reports/sessions/{id}``             — session snapshot
- ``GET    /v1/fly-reports/sessions/{id}/turns``       — chat history

User-uploaded templates (``user:<id>``), the skin mode and the renderer-
exposing download endpoints are deferred to M2+ per §4.1.6.1.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field

from swarmmind.domains.fly_report.errors import (
    InvalidStateTransition,
    SessionNotFound,
)
from swarmmind.domains.fly_report.export import TemplateLoader
from swarmmind.domains.fly_report.schemas import OutputFormat
from swarmmind.domains.fly_report.service import FlyReportService

# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class TemplateRefView(BaseModel):
    """Public view of a single built-in template."""

    template_ref: str
    name: str
    source: str  # "default" | "preset"
    output_format: OutputFormat


class StartSessionRequest(BaseModel):
    tenant_id: str = Field(..., description="租户 ID")
    user_id: str = Field(..., description="发起会话的用户 ID")
    initial_query: str | None = None


class StartSessionResponse(BaseModel):
    session_id: str
    status: str = "created"
    links: dict[str, str] = Field(default_factory=dict)


class SendMessageRequest(BaseModel):
    user_id: str
    text: str


class StreamMessageRequest(BaseModel):
    user_id: str
    text: str
    output_format: OutputFormat | None = None
    template_ref: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CancelInteractionRequest(BaseModel):
    user_id: str
    reason: str | None = "user_requested"


class ConfirmRequest(BaseModel):
    user_id: str
    output_format: OutputFormat = "docx"
    template_ref: str | None = None


class CancelRequest(BaseModel):
    user_id: str


class TurnView(BaseModel):
    role: str
    text: str
    payload: dict[str, Any] | None = None
    created_at: str


class SessionSnapshot(BaseModel):
    session_id: str
    state: str
    title: str | None
    last_user_text: str | None
    turn_count: int
    filter_spec: dict[str, Any]
    created_at: str
    updated_at: str


class SessionListItem(BaseModel):
    session_id: str
    state: str
    title: str | None
    last_user_text: str | None
    revision: int
    created_at: str
    updated_at: str


class ArtifactView(BaseModel):
    artifact_id: str | None = None
    interaction_id: str | None = None
    filename: str
    output_format: str
    template_ref: str | None = None
    content_type: str | None = None
    artifact_path: str
    download_url: str | None = None
    created_at: str | None = None


class MessageView(BaseModel):
    message_id: str
    interaction_id: str
    role: str
    type: str
    text: str
    status: str
    created_at: str
    title: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    actions: list[dict[str, Any]] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


class MessageListResponse(BaseModel):
    session_id: str
    messages: list[MessageView]
    next_before_message_id: str | None = None


class InteractionView(BaseModel):
    interaction_id: str
    session_id: str
    status: str
    phase: str
    message_count: int
    artifact_count: int
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None


class CancelInteractionResponse(BaseModel):
    interaction_id: str
    session_id: str
    status: str
    message: str


class AuditView(BaseModel):
    decision: str
    reason: str | None = None
    scope_required: str | None = None
    payload: dict[str, Any] | None = None
    created_at: str | None = None


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------


def create_fly_report_router(
    service: FlyReportService,
    *,
    template_loader: TemplateLoader | None = None,
) -> APIRouter:
    """Build a FastAPI router bound to a single :class:`FlyReportService`."""

    loader = template_loader or TemplateLoader()
    router = APIRouter(prefix="/v1/fly-reports", tags=["fly-reports"])

    # --------------------------------------------------------------- templates
    @router.get("/templates", response_model=list[TemplateRefView])
    async def list_templates(
        output_format: OutputFormat | None = None,
    ) -> list[TemplateRefView]:
        formats: list[OutputFormat] = (
            [output_format] if output_format else ["markdown", "pdf", "docx"]
        )
        items: list[TemplateRefView] = []
        for fmt in formats:
            for loaded in loader.list_templates(fmt):
                items.append(
                    TemplateRefView(
                        template_ref=loaded.template_ref,
                        name=loaded.name,
                        source=loaded.source,
                        output_format=loaded.output_format,
                    )
                )
        return items

    # ---------------------------------------------------------------- sessions
    @router.post(
        "/sessions",
        response_model=StartSessionResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def start_session(req: StartSessionRequest) -> StartSessionResponse:
        session_id = await service.start_session(
            tenant_id=req.tenant_id,
            user_id=req.user_id,
            initial_query=req.initial_query,
        )
        return StartSessionResponse(
            session_id=session_id,
            links={
                "session": f"/v1/fly-reports/sessions/{session_id}",
                "messages": f"/v1/fly-reports/sessions/{session_id}/messages",
                "stream": f"/v1/fly-reports/sessions/{session_id}/messages/stream",
            },
        )

    @router.post(
        "/sessions/{session_id}/messages", response_model=TurnView
    )
    async def send_message(
        session_id: str, req: SendMessageRequest
    ) -> TurnView:
        try:
            turn = await service.send_message(
                session_id, req.text, user_id=req.user_id
            )
        except SessionNotFound as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc
        except InvalidStateTransition as exc:
            detail = str(exc)
            # Input-validation errors surface as 400; true state conflicts as 409.
            if (
                detail.startswith("text must be")
                or "exceeds max" in detail
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=detail
                ) from exc
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=detail
            ) from exc
        return _turn_view(turn)

    @router.post("/sessions/{session_id}/messages/stream")
    async def stream_message(
        session_id: str, req: StreamMessageRequest
    ) -> StreamingResponse:
        try:
            interaction = await service.start_streaming_message(
                session_id,
                req.text,
                user_id=req.user_id,
                output_format=req.output_format,
                template_ref=req.template_ref,
                metadata=req.metadata,
                start_background=False,
            )
        except SessionNotFound as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc
        except InvalidStateTransition as exc:
            detail = str(exc)
            if detail.startswith("text must be") or "exceeds max" in detail:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=detail
                ) from exc
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=detail
            ) from exc

        async def event_iter():
            async for item in service.stream_interaction_events(
                interaction.id, start_background=True
            ):
                yield _sse(item["event"], item.get("data") or {})

        return StreamingResponse(
            event_iter(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @router.get(
        "/sessions/{session_id}/messages",
        response_model=MessageListResponse,
    )
    async def list_messages(
        session_id: str,
        user_id: str,
        limit: int = 100,
        before_message_id: str | None = None,
    ) -> MessageListResponse:
        try:
            messages = await service.list_messages(
                session_id,
                user_id=user_id,
                limit=max(1, min(limit, 500)),
                before_message_id=before_message_id,
            )
        except SessionNotFound as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc
        views = [_message_view(message) for message in messages]
        return MessageListResponse(
            session_id=session_id,
            messages=views,
            next_before_message_id=views[0].message_id if len(views) == limit else None,
        )

    @router.get(
        "/interactions/{interaction_id}",
        response_model=InteractionView,
    )
    async def get_interaction(
        interaction_id: str, user_id: str
    ) -> InteractionView:
        try:
            interaction = await service.get_interaction(
                interaction_id, user_id=user_id
            )
        except SessionNotFound as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc
        return _interaction_view(interaction)

    @router.post(
        "/interactions/{interaction_id}/cancel",
        response_model=CancelInteractionResponse,
    )
    async def cancel_interaction(
        interaction_id: str, req: CancelInteractionRequest
    ) -> CancelInteractionResponse:
        try:
            interaction = await service.cancel_interaction(
                interaction_id,
                user_id=req.user_id,
                reason=req.reason,
            )
        except SessionNotFound as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc
        except InvalidStateTransition as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(exc)
            ) from exc
        return CancelInteractionResponse(
            interaction_id=interaction.id,
            session_id=interaction.session_id,
            status=interaction.status,
            message="Interaction cancellation accepted",
        )

    @router.post(
        "/sessions/{session_id}/confirm", response_model=TurnView
    )
    async def confirm(session_id: str, req: ConfirmRequest) -> TurnView:
        # Validate template_ref shape early so the API returns a clean 400
        # instead of silently falling back to "default" inside the loader.
        if req.template_ref and req.template_ref != "default":
            try:
                loader.load(
                    output_format=req.output_format,
                    template_ref=req.template_ref,
                )
            except FileNotFoundError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(exc),
                ) from exc

        try:
            turn = await service.confirm(
                session_id,
                user_id=req.user_id,
                output_format=req.output_format,
                template_ref=req.template_ref,
            )
        except SessionNotFound as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc
        except InvalidStateTransition as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(exc)
            ) from exc
        return _turn_view(turn)

    @router.post("/sessions/{session_id}/cancel", response_model=TurnView)
    async def cancel(session_id: str, req: CancelRequest) -> TurnView:
        try:
            turn = await service.cancel(session_id, user_id=req.user_id)
        except SessionNotFound as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc
        except InvalidStateTransition as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(exc)
            ) from exc
        return _turn_view(turn)

    @router.get("/sessions/{session_id}", response_model=SessionSnapshot)
    async def get_session(session_id: str, user_id: str) -> SessionSnapshot:
        try:
            snap = await service.get_session_snapshot(
                session_id, user_id=user_id
            )
        except SessionNotFound as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc
        return SessionSnapshot(
            session_id=snap["session_id"],
            state=snap["state"],
            title=snap.get("title"),
            last_user_text=snap.get("last_user_text"),
            turn_count=snap["turn_count"],
            filter_spec=snap["filter_spec"],
            created_at=snap["created_at"].isoformat(),
            updated_at=snap["updated_at"].isoformat(),
        )

    @router.get(
        "/sessions/{session_id}/turns", response_model=list[TurnView]
    )
    async def list_turns(session_id: str, user_id: str) -> list[TurnView]:
        try:
            turns = await service.list_turns(session_id, user_id=user_id)
        except SessionNotFound as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc
        return [_turn_view(t) for t in turns]

    @router.get("/sessions/{session_id}/artifacts/{filename}")
    async def download_artifact(
        session_id: str, filename: str, user_id: str
    ) -> FileResponse:
        """Download a generated report artifact by filename.

        The service validates that ``filename`` matches a recorded artifact
        for ``(session_id, user_id)`` and is contained under the session's
        output directory (no path traversal).
        """
        try:
            path = await service.get_artifact_path(
                session_id, filename, user_id=user_id
            )
        except SessionNotFound as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"artifact not found: {filename}",
            ) from exc
        media_type = _MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")
        return FileResponse(
            path=str(path), media_type=media_type, filename=filename
        )

    # ---------------------------------------------------- history / search

    @router.get("/sessions", response_model=list[SessionListItem])
    async def list_user_sessions(
        tenant_id: str,
        user_id: str,
        limit: int = 50,
        keyword: str | None = None,
        state: str | None = None,
    ) -> list[SessionListItem]:
        """List recent sessions for ``(tenant_id, user_id)``
        """
        rows = await service.list_user_sessions(
            tenant_id=tenant_id,
            user_id=user_id,
            limit=max(1, min(limit, 200)),
            keyword=keyword,
            state_filter=state,
        )
        return [_session_list_item(r) for r in rows]

    @router.get("/metrics")
    async def metrics_snapshot() -> dict[str, Any]:
        """Return a JSON snapshot of the FlyReport metrics sink.

        This is **not** a Prometheus exporter — it is intended for smoke
        tests and operator inspection during M-pending phases
        (DESIGN-3 §2.8 R8.2).
        """
        return service.metrics.snapshot()

    @router.get(
        "/sessions/{session_id}/artifacts",
        response_model=list[ArtifactView],
    )
    async def list_session_artifacts(
        session_id: str, user_id: str, interaction_id: str | None = None
    ) -> list[ArtifactView]:
        try:
            artifacts = await service.list_artifacts(
                session_id, user_id=user_id, interaction_id=interaction_id
            )
        except SessionNotFound as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc
        return [_artifact_view(a) for a in artifacts]

    @router.get(
        "/sessions/{session_id}/audits",
        response_model=list[AuditView],
    )
    async def list_session_audits(
        session_id: str, user_id: str, limit: int = 100
    ) -> list[AuditView]:
        try:
            audits = await service.list_audits(
                session_id, user_id=user_id, limit=max(1, min(limit, 500))
            )
        except SessionNotFound as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc
        return [_audit_view(a) for a in audits]

    @router.get(
        "/sessions/{session_id}/preview",
        response_class=HTMLResponse,
    )
    async def preview_html(session_id: str, user_id: str) -> HTMLResponse:
        """Render the current draft as a self-contained HTML preview."""
        try:
            html_doc = await service.render_preview_html(
                session_id, user_id=user_id
            )
        except SessionNotFound as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc
        except InvalidStateTransition as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(exc)
            ) from exc
        return HTMLResponse(content=html_doc, status_code=200)

    return router


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _turn_view(turn) -> TurnView:
    return TurnView(
        role=turn.role,
        text=turn.text,
        payload=turn.payload,
        created_at=turn.created_at.isoformat(),
    )


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _session_list_item(row: dict[str, Any]) -> SessionListItem:
    return SessionListItem(
        session_id=row["session_id"],
        state=row.get("state", ""),
        title=row.get("title"),
        last_user_text=row.get("last_user_text"),
        revision=int(row.get("revision") or 0),
        created_at=_iso(row.get("created_at")) or "",
        updated_at=_iso(row.get("updated_at")) or "",
    )


def _artifact_view(row: dict[str, Any]) -> ArtifactView:
    return ArtifactView(
        artifact_id=str(row.get("id") or row.get("artifact_id") or row.get("filename") or ""),
        interaction_id=row.get("interaction_id"),
        filename=row.get("filename", ""),
        output_format=row.get("output_format", ""),
        template_ref=row.get("template_ref"),
        content_type=row.get("content_type"),
        artifact_path=row.get("artifact_path", ""),
        download_url=row.get("download_url"),
        created_at=_iso(row.get("created_at")),
    )


def _message_view(message) -> MessageView:
    payload = message.payload or {}
    return MessageView(
        message_id=message.id,
        interaction_id=message.interaction_id,
        role=message.role,
        type=message.message_type,
        title=message.title,
        text=message.text,
        status=message.status,
        created_at=message.created_at.isoformat(),
        data=payload.get("data") or {},
        actions=payload.get("actions") or [],
        meta=payload.get("meta") or {},
    )


def _interaction_view(interaction) -> InteractionView:
    return InteractionView(
        interaction_id=interaction.id,
        session_id=interaction.session_id,
        status=interaction.status,
        phase=interaction.phase,
        message_count=interaction.message_count,
        artifact_count=interaction.artifact_count,
        created_at=interaction.created_at.isoformat(),
        started_at=interaction.started_at.isoformat() if interaction.started_at else None,
        completed_at=interaction.completed_at.isoformat() if interaction.completed_at else None,
        error=interaction.error,
    )


def _sse(event: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {payload}\n\n"


def _audit_view(row: dict[str, Any]) -> AuditView:
    return AuditView(
        decision=row.get("decision", ""),
        reason=row.get("reason"),
        scope_required=row.get("scope_required"),
        payload=row.get("payload"),
        created_at=_iso(row.get("created_at")),
    )


_MEDIA_TYPES: dict[str, str] = {
    ".docx": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ),
    ".pdf": "application/pdf",
    ".md": "text/markdown; charset=utf-8",
    ".png": "image/png",
}


__all__ = ["create_fly_report_router"]
