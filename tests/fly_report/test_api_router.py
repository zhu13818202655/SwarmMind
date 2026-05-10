"""Smoke tests for the FlyReport HTTP router (DESIGN-2 §13 step 7)."""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from swarmmind.domains.fly_report.api import create_fly_report_router
from tests.fly_report.service_test_utils import build_fly_report_service


@pytest.fixture
def client(tmp_path) -> TestClient:
    """Build a minimal FastAPI app mounting only the FlyReport router.

    We do not exercise ``swarmmind.api.server.create_app`` here because that
    boots the whole SwarmMind container (tasks, runs, sandbox, ...). For a
    domain smoke test we only need the FlyReport endpoints, served against
    a fresh in-memory :class:`FlyReportService` (defaults to rule-based
    explicitly injected rule-based parser + fake dikong client).
    """

    app = FastAPI()
    app.include_router(
        create_fly_report_router(build_fly_report_service(output_root=tmp_path))
    )
    return TestClient(app)


# ---------------------------------------------------------------- templates


def test_list_templates_default_includes_all_formats(client: TestClient):
    resp = client.get("/v1/fly-reports/templates")
    assert resp.status_code == 200
    items = resp.json()
    formats = {item["output_format"] for item in items}
    assert formats == {"markdown", "pdf", "docx"}
    refs = {item["template_ref"] for item in items}
    assert "default" in refs
    assert "preset:default_zh" in refs


def test_list_templates_filtered_by_output_format(client: TestClient):
    resp = client.get(
        "/v1/fly-reports/templates", params={"output_format": "markdown"}
    )
    assert resp.status_code == 200
    items = resp.json()
    assert items, "should return at least the default template"
    assert all(item["output_format"] == "markdown" for item in items)


# ----------------------------------------------------------------- sessions


def test_full_session_lifecycle(client: TestClient):
    # 1. Start
    resp = client.post(
        "/v1/fly-reports/sessions",
        json={
            "tenant_id": "t-1",
            "user_id": "u-1",
            "initial_query": "总体周报",
        },
    )
    assert resp.status_code == 201, resp.text
    session_id = resp.json()["session_id"]

    # 2. Send message — pipeline re-runs end-to-end
    resp = client.post(
        f"/v1/fly-reports/sessions/{session_id}/messages",
        json={"user_id": "u-1", "text": "改成月报"},
    )
    assert resp.status_code == 200
    turn = resp.json()
    assert turn["role"] == "assistant"
    assert turn["payload"]["state"] == "previewing"
    stages = {s["stage"] for s in turn["payload"]["stages"]}
    assert {"parsing", "fetching", "analyzing", "previewing"} <= stages

    # 3. Confirm with explicit format + template
    resp = client.post(
        f"/v1/fly-reports/sessions/{session_id}/confirm",
        json={
            "user_id": "u-1",
            "output_format": "docx",
            "template_ref": "preset:gov_formal",
        },
    )
    assert resp.status_code == 200
    payload = resp.json()["payload"]
    assert payload["output_format"] == "docx"
    assert payload["template_ref"] == "markdown:preset:gov_formal"
    assert payload["artifact_path"]
    assert payload["download_url"].startswith(
        f"/v1/fly-reports/sessions/{session_id}/artifacts/"
    )

    # 4. Snapshot
    resp = client.get(
        f"/v1/fly-reports/sessions/{session_id}",
        params={"user_id": "u-1"},
    )
    assert resp.status_code == 200
    snap = resp.json()
    assert snap["session_id"] == session_id
    assert snap["turn_count"] >= 4  # initial query + reply + msg + reply + confirm

    # 5. Turns history reflects the conversation
    resp = client.get(
        f"/v1/fly-reports/sessions/{session_id}/turns",
        params={"user_id": "u-1"},
    )
    assert resp.status_code == 200
    turns = resp.json()
    roles = [t["role"] for t in turns]
    assert roles[0] == "user"
    assert "assistant" in roles


def test_confirm_defaults_template_ref_to_default(client: TestClient):
    resp = client.post(
        "/v1/fly-reports/sessions",
        json={
            "tenant_id": "t-1",
            "user_id": "u-1",
            "initial_query": "飞行周报",
        },
    )
    session_id = resp.json()["session_id"]

    resp = client.post(
        f"/v1/fly-reports/sessions/{session_id}/confirm",
        json={"user_id": "u-1", "output_format": "markdown"},
    )
    assert resp.status_code == 200
    assert resp.json()["payload"]["template_ref"] == "markdown:direct"


def test_artifact_download_after_confirm(client: TestClient):
    resp = client.post(
        "/v1/fly-reports/sessions",
        json={
            "tenant_id": "t-1",
            "user_id": "u-1",
            "initial_query": "飞行周报",
        },
    )
    session_id = resp.json()["session_id"]

    resp = client.post(
        f"/v1/fly-reports/sessions/{session_id}/confirm",
        json={"user_id": "u-1", "output_format": "markdown"},
    )
    filename = resp.json()["payload"]["filename"]

    resp = client.get(
        f"/v1/fly-reports/sessions/{session_id}/artifacts/{filename}",
        params={"user_id": "u-1"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/markdown")
    assert resp.content  # non-empty file body

    # Cross-user blocked
    resp = client.get(
        f"/v1/fly-reports/sessions/{session_id}/artifacts/{filename}",
        params={"user_id": "u-other"},
    )
    assert resp.status_code == 404


def test_unknown_session_returns_404(client: TestClient):
    resp = client.get(
        "/v1/fly-reports/sessions/does-not-exist",
        params={"user_id": "u-1"},
    )
    assert resp.status_code == 404


def test_cross_user_access_returns_404(client: TestClient):
    resp = client.post(
        "/v1/fly-reports/sessions",
        json={"tenant_id": "t-1", "user_id": "u-1"},
    )
    session_id = resp.json()["session_id"]

    resp = client.get(
        f"/v1/fly-reports/sessions/{session_id}",
        params={"user_id": "u-2"},
    )
    assert resp.status_code == 404


def test_cancel_then_send_returns_409(client: TestClient):
    resp = client.post(
        "/v1/fly-reports/sessions",
        json={"tenant_id": "t-1", "user_id": "u-1"},
    )
    session_id = resp.json()["session_id"]

    resp = client.post(
        f"/v1/fly-reports/sessions/{session_id}/cancel",
        json={"user_id": "u-1"},
    )
    assert resp.status_code == 200

    resp = client.post(
        f"/v1/fly-reports/sessions/{session_id}/messages",
        json={"user_id": "u-1", "text": "still there?"},
    )
    assert resp.status_code == 409


def test_streaming_message_persists_history_and_interaction(client: TestClient):
    resp = client.post(
        "/v1/fly-reports/sessions",
        json={"tenant_id": "t-1", "user_id": "u-1"},
    )
    assert resp.status_code == 201, resp.text
    session_id = resp.json()["session_id"]

    with client.stream(
        "POST",
        f"/v1/fly-reports/sessions/{session_id}/messages/stream",
        json={"user_id": "u-1", "text": "这个指标是什么意思？"},
    ) as stream_resp:
        assert stream_resp.status_code == 200, stream_resp.text
        body = stream_resp.read().decode("utf-8")

    events = _parse_sse(body)
    names = [event for event, _ in events]
    assert names[0] == "interaction.started"
    assert "message.delta" in names
    assert "message.item" in names
    assert names[-1] == "interaction.completed"
    interaction_id = events[0][1]["interaction_id"]

    resp = client.get(
        f"/v1/fly-reports/interactions/{interaction_id}",
        params={"user_id": "u-1"},
    )
    assert resp.status_code == 200, resp.text
    interaction = resp.json()
    assert interaction["status"] == "completed"
    assert interaction["message_count"] >= 2

    resp = client.get(
        f"/v1/fly-reports/sessions/{session_id}/messages",
        params={"user_id": "u-1"},
    )
    assert resp.status_code == 200, resp.text
    messages = resp.json()["messages"]
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[-1]["type"] == "plain_text"


def test_streaming_report_generates_artifact_card(client: TestClient):
    resp = client.post(
        "/v1/fly-reports/sessions",
        json={"tenant_id": "t-1", "user_id": "u-1"},
    )
    assert resp.status_code == 201, resp.text
    session_id = resp.json()["session_id"]

    with client.stream(
        "POST",
        f"/v1/fly-reports/sessions/{session_id}/messages/stream",
        json={
            "user_id": "u-1",
            "text": "生成飞行周报，导出 markdown",
        },
    ) as stream_resp:
        assert stream_resp.status_code == 200, stream_resp.text
        body = stream_resp.read().decode("utf-8")

    events = _parse_sse(body)
    interaction_id = events[0][1]["interaction_id"]
    item_payloads = [data for event, data in events if event == "message.item"]
    item_types = [payload["type"] for payload in item_payloads]
    assert "phase" in item_types
    assert "todo" in item_types
    assert "artifact" in item_types
    assert events[-1][0] == "interaction.completed"

    resp = client.get(
        f"/v1/fly-reports/sessions/{session_id}/artifacts",
        params={"user_id": "u-1", "interaction_id": interaction_id},
    )
    assert resp.status_code == 200, resp.text
    artifacts = resp.json()
    assert len(artifacts) == 1
    assert artifacts[0]["interaction_id"] == interaction_id
    assert artifacts[0]["filename"].endswith(".md")


def _parse_sse(body: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    for block in body.strip().split("\n\n"):
        event_name = ""
        data = "{}"
        for line in block.splitlines():
            if line.startswith("event: "):
                event_name = line.removeprefix("event: ")
            elif line.startswith("data: "):
                data = line.removeprefix("data: ")
        if event_name:
            events.append((event_name, json.loads(data)))
    return events
