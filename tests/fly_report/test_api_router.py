"""Smoke tests for the FlyReport HTTP router (DESIGN-2 §13 step 7)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from swarmmind.domains.fly_report.api import create_fly_report_router
from swarmmind.domains.fly_report.service import FlyReportService


@pytest.fixture
def client(tmp_path) -> TestClient:
    """Build a minimal FastAPI app mounting only the FlyReport router.

    We do not exercise ``swarmmind.api.server.create_app`` here because that
    boots the whole SwarmMind container (tasks, runs, sandbox, ...). For a
    domain smoke test we only need the FlyReport endpoints, served against
    a fresh in-memory :class:`FlyReportService` (defaults to rule-based
    intent parser + fake dikong client).
    """

    app = FastAPI()
    app.include_router(
        create_fly_report_router(FlyReportService(output_root=tmp_path))
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
    assert payload["template_ref"] == "preset:gov_formal"
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
    assert resp.json()["payload"]["template_ref"] == "default"


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
