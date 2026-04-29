"""Async OpenAI-compatible LM chat client for FlyReport."""

from __future__ import annotations

from typing import Any

import httpx

from swarmmind.config.schema import ModelConfig
from swarmmind.domains.fly_report.lm.output import parse_lm_output
from swarmmind.domains.fly_report.lm.types import (
    LMChatRequest,
    LMChatResponse,
    LMConfigError,
    LMMessage,
    LMOutputFormat,
    LMProviderError,
    LMRequestError,
    LMTimeoutError,
)


class OpenAICompatibleLMClient:
    """Minimal async client for OpenAI-compatible chat completions."""

    def __init__(
        self,
        *,
        model_name: str,
        api_key: str | None = None,
        base_url: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 8192 * 8,
        timeout_sec: float = 30.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if not model_name or not model_name.strip():
            raise LMConfigError("model_name is required")

        self.model_name = model_name
        self.api_key = api_key
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout_sec = timeout_sec
        self._http_client = http_client

    @classmethod
    def from_model_config(
        cls,
        config: ModelConfig,
        *,
        timeout_sec: float = 30.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> "OpenAICompatibleLMClient":
        """Create a lightweight LM client from the existing model config."""

        return cls(
            model_name=config.name,
            api_key=config.api_key,
            base_url=config.base_url,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            timeout_sec=timeout_sec,
            http_client=http_client,
        )

    async def chat(
        self,
        *,
        system_prompt: str | None = None,
        user_prompt: str | None = None,
        messages: list[LMMessage] | None = None,
        output_format: LMOutputFormat = LMOutputFormat.TEXT,
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> str:
        """Run a chat completion and return only the model text."""

        response = await self.chat_response(
            LMChatRequest(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                messages=messages,
                output_format=output_format,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
            )
        )
        return response.text

    async def chat_response(self, request: LMChatRequest) -> LMChatResponse:
        """Run a chat completion and return text plus optional parsed/raw data."""

        payload = self._build_payload(request)
        raw = await self._post_chat_completions(payload)
        text = self._extract_text(raw)
        return LMChatResponse(
            text=text,
            output_format=request.output_format,
            parsed=parse_lm_output(text, request.output_format),
            raw=raw if request.output_format == LMOutputFormat.RAW else None,
            model_name=raw.get("model") if isinstance(raw.get("model"), str) else self.model_name,
            usage=raw.get("usage") if isinstance(raw.get("usage"), dict) else None,
        )

    def _build_payload(self, request: LMChatRequest) -> dict[str, Any]:
        messages = self._build_messages(request)
        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": [message.model_dump(mode="json") for message in messages],
            "temperature": self.temperature if request.temperature is None else request.temperature,
            "max_tokens": self.max_tokens if request.max_tokens is None else request.max_tokens,
        }
        if request.response_format is not None:
            payload["response_format"] = request.response_format
        return payload

    @staticmethod
    def _build_messages(request: LMChatRequest) -> list[LMMessage]:
        if request.messages is not None:
            messages = [message for message in request.messages if message.content.strip()]
            if not messages:
                raise LMRequestError("messages cannot be empty")
            return messages

        messages: list[LMMessage] = []
        if request.system_prompt and request.system_prompt.strip():
            messages.append(LMMessage(role="system", content=request.system_prompt))
        if request.user_prompt and request.user_prompt.strip():
            messages.append(LMMessage(role="user", content=request.user_prompt))
        if not messages:
            raise LMRequestError("user_prompt or messages is required")
        return messages

    async def _post_chat_completions(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            if self._http_client is not None:
                response = await self._http_client.post(
                    "/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=self.timeout_sec,
                )
            else:
                async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout_sec) as client:
                    response = await client.post(
                        "/chat/completions",
                        json=payload,
                        headers=headers,
                    )
        except httpx.TimeoutException as exc:
            raise LMTimeoutError("LM provider request timed out") from exc
        except httpx.HTTPError as exc:
            raise LMRequestError(f"LM provider request failed: {exc}") from exc

        if response.status_code >= 400:
            raise LMProviderError(
                f"LM provider returned HTTP {response.status_code}: {response.text[:500]}",
                status_code=response.status_code,
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise LMProviderError("LM provider returned non-JSON response") from exc
        if not isinstance(data, dict):
            raise LMProviderError("LM provider response must be a JSON object")
        return data

    @staticmethod
    def _extract_text(raw: dict[str, Any]) -> str:
        choices = raw.get("choices")
        if not isinstance(choices, list) or not choices:
            raise LMProviderError("LM provider response missing choices")

        first = choices[0]
        if not isinstance(first, dict):
            raise LMProviderError("LM provider choice must be an object")

        message = first.get("message")
        if not isinstance(message, dict):
            raise LMProviderError("LM provider choice missing message")

        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"])
            if parts:
                return "".join(parts)
        raise LMProviderError("LM provider message content must be text")