"""Tests for M-D history / artifact / audit endpoints."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from swarmmind.domains.fly_report.api import create_fly_report_router
from swarmmind.domains.fly_report.service import FlyReportService
from tests.fly_report.service_test_utils import build_fly_report_service


@pytest.fixture
def client(tmp_path):
    svc = build_fly_report_service(output_root=tmp_path)
    app = FastAPI()
    app.include_router(create_fly_report_router(svc))
    app.state.svc = svc
    with TestClient(app) as c:
        yield c, svc


def _start_and_confirm(client: TestClient, svc: FlyReportService) -> str:
    r = client.post(
        "/v1/fly-reports/sessions",
        json={"tenant_id": "t1", "user_id": "u1", "initial_query": "飞行周报"},
    )
    assert r.status_code in (200, 201)
    sid = r.json()["session_id"]
    r2 = client.post(
        f"/v1/fly-reports/sessions/{sid}/confirm",
        json={"user_id": "u1", "output_format": "markdown"},
    )
    assert r2.status_code in (200, 201), r2.text
    return sid


def test_list_user_sessions_returns_in_memory(client) -> None:
    c, svc = client
    sid = _start_and_confirm(c, svc)
    r = c.get(
        "/v1/fly-reports/sessions",
        params={"tenant_id": "t1", "user_id": "u1"},
    )
    assert r.status_code == 200
    items = r.json()
    assert any(item["session_id"] == sid for item in items)
    me = next(item for item in items if item["session_id"] == sid)
    assert me["state"] == "archived"
    assert me["revision"] >= 1


def test_list_session_artifacts(client) -> None:
    c, svc = client
    sid = _start_and_confirm(c, svc)
    r = c.get(
        f"/v1/fly-reports/sessions/{sid}/artifacts",
        params={"user_id": "u1"},
    )
    assert r.status_code == 200
    arts = r.json()
    assert len(arts) == 1
    assert arts[0]["output_format"] == "markdown"
    assert arts[0]["filename"].endswith(".md")
    assert arts[0]["download_url"].startswith(
        f"/v1/fly-reports/sessions/{sid}/artifacts/"
    )


def test_list_session_audits(client) -> None:
    c, svc = client
    sid = _start_and_confirm(c, svc)
    r = c.get(
        f"/v1/fly-reports/sessions/{sid}/audits",
        params={"user_id": "u1"},
    )
    # In-memory repo returns [] for audits; that's still a 200.
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_cross_user_isolation(client) -> None:
    c, svc = client
    sid = _start_and_confirm(c, svc)
    r = c.get(
        f"/v1/fly-reports/sessions/{sid}/artifacts",
        params={"user_id": "other"},
    )
    assert r.status_code == 404
