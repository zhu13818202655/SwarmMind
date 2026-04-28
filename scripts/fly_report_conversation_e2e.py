#!/usr/bin/env python3
"""Validate FlyReport conversation APIs against a running SwarmMind server.

Start the API first, for example with the VS Code task "Run SwarmMind API",
then run:

    python scripts/fly_report_conversation_e2e.py

Edit the CONFIG block below to change server URL, user, messages, or timeouts.

The script exercises the client-facing conversation flow:

1. Create a session.
2. Send a single-turn plain streaming message.
3. Read message history and interaction detail.
4. Send a report-generation streaming message and validate artifact output.
5. Send a follow-up streaming message in the same session.
6. Read message history again and validate multi-turn ordering/counts.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from dataclasses import dataclass
from typing import Any

import httpx

CONFIG: dict[str, Any] = {
    "base_url": "http://127.0.0.1:8000",
    "tenant_id": "e2e-tenant",
    "user_id": "e2e-user",
    "plain_text": "这个报告系统能做什么？",
    "report_text": "生成上周飞行报告",
    "followup_text": "解释一下刚才的飞行总次数",
    "wait_for_service_seconds": 150.0,
    "request_timeout_seconds": 300.0,
    "verbose": True,
}


class ScenarioError(AssertionError):
    """Raised when the API responds but the conversation contract is broken."""


@dataclass(frozen=True)
class StreamResult:
    interaction_id: str
    events: list[tuple[str, dict[str, Any]]]
    messages: list[dict[str, Any]]


class FlyReportConversationE2E:
    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        tenant_id: str,
        user_id: str,
        verbose: bool = False,
    ) -> None:
        self._client = client
        self._tenant_id = tenant_id
        self._user_id = user_id
        self._verbose = verbose
        self.session_id: str | None = None

    async def run(
        self,
        *,
        plain_text: str,
        report_text: str,
        followup_text: str,
    ) -> None:
        await self._create_session()

        report = await self._stream_message(report_text)
        self._assert_event_order(report.events, must_include={"message.item"})
        self._assert_message_types(report.messages, expected_any={"todo", "phase", "artifact", "summary"})
        await self._assert_interaction_completed(report.interaction_id)
        await self._assert_artifact(
            report.interaction_id,
            expected_format=_expected_output_format_from_query(report_text),
        )

        followup = await self._stream_message(followup_text)
        self._assert_event_order(followup.events, must_include={"message.delta", "message.item"})
        self._assert_message_types(followup.messages, expected_any={"plain_text"})
        await self._assert_interaction_completed(followup.interaction_id)

        final_history = await self._list_messages()
        self._assert_history_contains_roles(final_history, min_user=3, min_assistant=3)
        self._assert_history_interactions(
            final_history,
            expected_interaction_ids={
                plain.interaction_id,
                report.interaction_id,
                followup.interaction_id,
            },
        )

    async def _create_session(self) -> None:
        payload = {"tenant_id": self._tenant_id, "user_id": self._user_id}
        response = await self._request("POST", "/v1/fly-reports/sessions", json=payload)
        self._expect_status(response, 201, "create session")
        body = response.json()
        session_id = body.get("session_id")
        if not isinstance(session_id, str) or not session_id:
            raise ScenarioError(f"create session response missing session_id: {body!r}")
        self.session_id = session_id
        self._log(f"session_id={session_id}")

    async def _stream_message(self, text: str) -> StreamResult:
        session_id = self._require_session()
        payload: dict[str, Any] = {"user_id": self._user_id, "text": text}

        path = f"/v1/fly-reports/sessions/{session_id}/messages/stream"
        self._log(f"stream -> {text}")
        async with self._client.stream("POST", path, json=payload) as response:
            self._expect_status(response, 200, f"stream message {text!r}")
            raw = ""
            async for chunk in response.aiter_text():
                raw += chunk

        events = _parse_sse(raw)
        if not events:
            raise ScenarioError("stream returned no SSE events")
        first_event, first_payload = events[0]
        if first_event != "interaction.started":
            raise ScenarioError(f"first event should be interaction.started, got {first_event!r}")
        interaction_id = first_payload.get("interaction_id")
        if not isinstance(interaction_id, str) or not interaction_id:
            raise ScenarioError(f"interaction.started missing interaction_id: {first_payload!r}")

        messages = [payload for event, payload in events if event == "message.item"]
        self._log(
            f"interaction={interaction_id} events={len(events)} message_items={len(messages)}"
        )
        return StreamResult(interaction_id=interaction_id, events=events, messages=messages)

    async def _list_messages(self) -> list[dict[str, Any]]:
        session_id = self._require_session()
        response = await self._request(
            "GET",
            f"/v1/fly-reports/sessions/{session_id}/messages",
            params={"user_id": self._user_id, "limit": 100},
        )
        self._expect_status(response, 200, "list messages")
        body = response.json()
        messages = body.get("messages")
        if not isinstance(messages, list):
            raise ScenarioError(f"message history response missing messages list: {body!r}")
        self._log(f"history messages={len(messages)}")
        return messages

    async def _assert_interaction_completed(self, interaction_id: str) -> None:
        response = await self._request(
            "GET",
            f"/v1/fly-reports/interactions/{interaction_id}",
            params={"user_id": self._user_id},
        )
        self._expect_status(response, 200, f"get interaction {interaction_id}")
        body = response.json()
        if body.get("status") != "completed":
            raise ScenarioError(f"interaction {interaction_id} not completed: {body!r}")
        if int(body.get("message_count") or 0) < 2:
            raise ScenarioError(f"interaction {interaction_id} recorded too few messages: {body!r}")

    async def _assert_artifact(self, interaction_id: str, *, expected_format: str) -> None:
        session_id = self._require_session()
        response = await self._request(
            "GET",
            f"/v1/fly-reports/sessions/{session_id}/artifacts",
            params={"user_id": self._user_id, "interaction_id": interaction_id},
        )
        self._expect_status(response, 200, f"list artifacts for {interaction_id}")
        artifacts = response.json()
        if not isinstance(artifacts, list) or not artifacts:
            raise ScenarioError(f"expected at least one artifact for {interaction_id}, got {artifacts!r}")
        matching = [artifact for artifact in artifacts if artifact.get("interaction_id") == interaction_id]
        if not matching:
            raise ScenarioError(f"artifact list missing interaction_id {interaction_id}: {artifacts!r}")
        if not any(artifact.get("output_format") == expected_format for artifact in matching):
            raise ScenarioError(f"artifact list missing output_format={expected_format}: {matching!r}")

    def _assert_event_order(
        self,
        events: list[tuple[str, dict[str, Any]]],
        *,
        must_include: set[str],
    ) -> None:
        names = [event for event, _ in events]
        if names[0] != "interaction.started":
            raise ScenarioError(f"first stream event should be interaction.started, got {names[0]!r}")
        if names[-1] != "interaction.completed":
            raise ScenarioError(f"last stream event should be interaction.completed, got {names[-1]!r}")
        missing = must_include - set(names)
        if missing:
            raise ScenarioError(f"stream missing expected events {sorted(missing)}; got {names}")

    def _assert_message_types(
        self,
        messages: list[dict[str, Any]],
        *,
        expected_any: set[str],
    ) -> None:
        types = {str(message.get("type")) for message in messages}
        missing = expected_any - types
        if missing:
            raise ScenarioError(f"message.item types missing {sorted(missing)}; got {sorted(types)}")

    def _assert_history_contains_roles(
        self,
        messages: list[dict[str, Any]],
        *,
        min_user: int,
        min_assistant: int,
    ) -> None:
        user_count = sum(1 for message in messages if message.get("role") == "user")
        assistant_count = sum(1 for message in messages if message.get("role") == "assistant")
        if user_count < min_user or assistant_count < min_assistant:
            raise ScenarioError(
                "history role counts are too low: "
                f"user={user_count}, assistant={assistant_count}, messages={messages!r}"
            )

    def _assert_history_interactions(
        self,
        messages: list[dict[str, Any]],
        *,
        expected_interaction_ids: set[str],
    ) -> None:
        actual = {
            str(message.get("interaction_id"))
            for message in messages
            if message.get("interaction_id")
        }
        missing = expected_interaction_ids - actual
        if missing:
            raise ScenarioError(
                f"history missing interaction ids {sorted(missing)}; got {sorted(actual)}"
            )

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        response = await self._client.request(method, path, **kwargs)
        self._log(f"{method} {path} -> {response.status_code}")
        return response

    def _expect_status(self, response: httpx.Response, expected: int, label: str) -> None:
        if response.status_code != expected:
            raise ScenarioError(
                f"{label} expected HTTP {expected}, got {response.status_code}: {response.text}"
            )

    def _require_session(self) -> str:
        if not self.session_id:
            raise ScenarioError("session_id is not initialized")
        return self.session_id

    def _log(self, message: str) -> None:
        if self._verbose:
            print(f"[fly-report-e2e] {message}")


def _parse_sse(body: str) -> list[tuple[str, dict[str, Any]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    for block in body.strip().split("\n\n"):
        if not block.strip():
            continue
        event_name = ""
        data_lines: list[str] = []
        for line in block.splitlines():
            if line.startswith("event: "):
                event_name = line.removeprefix("event: ")
            elif line.startswith("data: "):
                data_lines.append(line.removeprefix("data: "))
        if not event_name:
            continue
        raw_data = "\n".join(data_lines) or "{}"
        try:
            payload = json.loads(raw_data)
        except json.JSONDecodeError as exc:
            raise ScenarioError(f"invalid SSE JSON for {event_name}: {raw_data!r}") from exc
        if not isinstance(payload, dict):
            raise ScenarioError(f"SSE payload for {event_name} should be an object: {payload!r}")
        events.append((event_name, payload))
    return events


async def _wait_for_service(client: httpx.AsyncClient, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() <= deadline:
        try:
            response = await client.get("/health")
            if response.status_code == 200:
                return
            last_error = ScenarioError(f"/health returned {response.status_code}")
        except httpx.HTTPError as exc:
            last_error = exc
        await asyncio.sleep(0.5)
    if last_error is None:
        raise ScenarioError("service did not become ready")
    raise ScenarioError(f"service did not become ready: {last_error}")


async def async_main() -> int:
    _validate_config(CONFIG)
    async with httpx.AsyncClient(
        base_url=str(CONFIG["base_url"]),
        timeout=float(CONFIG["request_timeout_seconds"]),
    ) as client:
        await _wait_for_service(client, float(CONFIG["wait_for_service_seconds"]))
        scenario = FlyReportConversationE2E(
            client,
            tenant_id=str(CONFIG["tenant_id"]),
            user_id=str(CONFIG["user_id"]),
            verbose=bool(CONFIG["verbose"]),
        )
        await scenario.run(
            plain_text=str(CONFIG["plain_text"]),
            report_text=str(CONFIG["report_text"]),
            followup_text=str(CONFIG["followup_text"]),
        )
    print("PASS fly_report conversation e2e")
    return 0


def _validate_config(config: dict[str, Any]) -> None:
    required = {
        "base_url",
        "tenant_id",
        "user_id",
        "plain_text",
        "report_text",
        "followup_text",
        "wait_for_service_seconds",
        "request_timeout_seconds",
        "verbose",
    }
    missing = sorted(required - set(config))
    if missing:
        raise ScenarioError(f"CONFIG is missing keys: {missing}")


def _expected_output_format_from_query(text: str) -> str:
    lowered = text.lower()
    if "markdown" in lowered or "md" in lowered:
        return "markdown"
    if "pdf" in lowered:
        return "pdf"
    return "docx"


def main() -> int:
    try:
        if len(sys.argv) > 1:
            raise ScenarioError("this script is configured by editing CONFIG; CLI args are not supported")
        return asyncio.run(async_main())
    except (httpx.HTTPError, ScenarioError) as exc:
        print(f"FAIL fly_report conversation e2e: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
