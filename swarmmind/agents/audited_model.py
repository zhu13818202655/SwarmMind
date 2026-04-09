"""Audited chat model wrappers used by SwarmMind agents."""

from __future__ import annotations

import inspect
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Any

from pydantic import BaseModel

from agentscope.model import OpenAIChatModel

from swarmmind.utils.audit import extract_text_preview, sanitize_audit_value


AuditEventPublisher = Callable[[str, dict[str, object]], Awaitable[None]]


class AuditedOpenAIChatModel(OpenAIChatModel):
    """OpenAI chat model that emits per-call audit events."""

    def __init__(self, *args: Any, event_publisher: AuditEventPublisher | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._event_publisher = event_publisher

    async def __call__(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
        structured_model: type[BaseModel] | None = None,
        **kwargs: Any,
    ):
        request_payload = {
            "event_source": "audited_model",
            "model_name": self.model_name,
            "stream": self.stream,
            "messages": sanitize_audit_value(messages),
            "tools": sanitize_audit_value(tools or []),
            "tool_choice": sanitize_audit_value(tool_choice),
            "structured_model": structured_model.__name__ if structured_model is not None else None,
            "call_kwargs": sanitize_audit_value(kwargs),
        }
        await self._emit("llm.requested", request_payload)
        try:
            response = await super().__call__(
                messages,
                tools=tools,
                tool_choice=tool_choice,
                structured_model=structured_model,
                **kwargs,
            )
        except Exception as exc:
            await self._emit("llm.failed", {**request_payload, "error": str(exc)})
            raise

        if inspect.isasyncgen(response):
            return self._wrap_stream(response, request_payload)

        await self._emit_response(request_payload, response)
        return response

    async def _wrap_stream(
        self,
        response_stream: AsyncGenerator[Any, None],
        request_payload: dict[str, object],
    ) -> AsyncGenerator[Any, None]:
        last_chunk: Any = None
        try:
            async for chunk in response_stream:
                last_chunk = chunk
                yield chunk
        except Exception as exc:
            await self._emit("llm.failed", {**request_payload, "error": str(exc)})
            raise

        await self._emit_response(request_payload, last_chunk)

    async def _emit_response(self, request_payload: dict[str, object], response: Any) -> None:
        response_payload = sanitize_audit_value(response)
        await self._emit(
            "llm.responded",
            {
                **request_payload,
                "response": response_payload,
                "response_preview": extract_text_preview(response_payload),
            },
        )

    async def _emit(self, topic: str, payload: dict[str, object]) -> None:
        if self._event_publisher is None:
            return
        await self._event_publisher(topic, payload)