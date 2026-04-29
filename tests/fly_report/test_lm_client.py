from __future__ import annotations

import httpx
import pytest

from swarmmind.config.schema import ModelConfig
from swarmmind.domains.fly_report.lm import (
    LMChatRequest,
    LMMessage,
    LMOutputFormat,
    LMProviderError,
    LMRequestError,
    LMTimeoutError,
    OpenAICompatibleLMClient,
    parse_json_best_effort,
)


def _json_response(content: str, *, model: str = "test-model") -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "model": model,
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 5, "total_tokens": 8},
        },
    )


@pytest.mark.asyncio
async def test_chat_posts_system_and_user_prompts_and_returns_text() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("authorization")
        captured["payload"] = request.read()
        return _json_response("hello")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://lm.example/v1",
    ) as http_client:
        client = OpenAICompatibleLMClient(
            model_name="test-model",
            api_key="secret",
            base_url="https://lm.example/v1",
            http_client=http_client,
        )

        text = await client.chat(system_prompt="sys", user_prompt="user")

    assert text == "hello"
    assert captured["url"] == "https://lm.example/v1/chat/completions"
    assert captured["authorization"] == "Bearer secret"
    payload = httpx.Request("POST", "https://unused", content=captured["payload"]).read().decode()
    assert '"model":"test-model"' in payload
    assert '"role":"system"' in payload
    assert '"content":"sys"' in payload
    assert '"role":"user"' in payload
    assert '"content":"user"' in payload


@pytest.mark.asyncio
async def test_messages_take_priority_over_prompt_fields() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = request.read().decode()
        return _json_response("ok")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://lm.example/v1",
    ) as http_client:
        client = OpenAICompatibleLMClient(model_name="test-model", http_client=http_client)
        await client.chat(
            system_prompt="ignored",
            user_prompt="ignored",
            messages=[LMMessage(role="user", content="real message")],
        )

    assert "real message" in str(captured["payload"])
    assert "ignored" not in str(captured["payload"])


@pytest.mark.asyncio
async def test_chat_response_parses_json_output() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return _json_response('{"answer": 42}')

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://lm.example/v1",
    ) as http_client:
        client = OpenAICompatibleLMClient(model_name="test-model", http_client=http_client)
        response = await client.chat_response(
            LMChatRequest(user_prompt="return json", output_format=LMOutputFormat.JSON)
        )

    assert response.text == '{"answer": 42}'
    assert response.parsed == {"answer": 42}
    assert response.model_name == "test-model"
    assert response.usage == {"prompt_tokens": 3, "completion_tokens": 5, "total_tokens": 8}


@pytest.mark.asyncio
async def test_raw_output_keeps_provider_payload() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return _json_response("raw text")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://lm.example/v1",
    ) as http_client:
        client = OpenAICompatibleLMClient(model_name="test-model", http_client=http_client)
        response = await client.chat_response(
            LMChatRequest(user_prompt="return raw", output_format=LMOutputFormat.RAW)
        )

    assert response.text == "raw text"
    assert isinstance(response.raw, dict)


@pytest.mark.asyncio
async def test_empty_request_raises_request_error() -> None:
    client = OpenAICompatibleLMClient(model_name="test-model")

    with pytest.raises(LMRequestError):
        await client.chat()


@pytest.mark.asyncio
async def test_provider_http_error_is_wrapped() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="provider failed")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://lm.example/v1",
    ) as http_client:
        client = OpenAICompatibleLMClient(model_name="test-model", http_client=http_client)
        with pytest.raises(LMProviderError) as exc_info:
            await client.chat(user_prompt="hello")

    assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_timeout_is_wrapped() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://lm.example/v1",
    ) as http_client:
        client = OpenAICompatibleLMClient(model_name="test-model", http_client=http_client)
        with pytest.raises(LMTimeoutError):
            await client.chat(user_prompt="hello")


def test_parse_json_best_effort_handles_fenced_json() -> None:
    assert parse_json_best_effort('before ```json\n{"ok": true}\n``` after') == {"ok": True}


def test_parse_json_best_effort_handles_embedded_array() -> None:
    assert parse_json_best_effort("answer: [1, 2, 3]") == [1, 2, 3]


def test_client_can_be_created_from_existing_model_config() -> None:
    model_config = ModelConfig(
        name="qwen-test",
        api_key="secret",
        base_url="https://lm.example/v1",
        temperature=0.4,
        max_tokens=1234,
    )

    client = OpenAICompatibleLMClient.from_model_config(model_config, timeout_sec=12.0)

    assert client.model_name == "qwen-test"
    assert client.api_key == "secret"
    assert client.base_url == "https://lm.example/v1"
    assert client.temperature == 0.4
    assert client.max_tokens == 1234
    assert client.timeout_sec == 12.0