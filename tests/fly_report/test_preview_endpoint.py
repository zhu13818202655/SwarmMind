"""Tests for the M-F /preview HTML endpoint."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from swarmmind.domains.fly_report.api import create_fly_report_router
from tests.fly_report.service_test_utils import build_fly_report_service


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "swarmmind.domains.fly_report.composer.preview_renderer.render_preview_html",
        lambda ctx: "<!doctype html><title>FlyReport 预览</title>",
    )
    svc = build_fly_report_service(output_root=tmp_path)
    app = FastAPI()
    app.include_router(create_fly_report_router(svc))
    with TestClient(app) as c:
        yield c, svc


def test_preview_html_returns_after_send_message(client) -> None:
    c, _ = client
    r = c.post(
        "/v1/fly-reports/sessions",
        json={"tenant_id": "t1", "user_id": "u1", "initial_query": "飞行周报"},
    )
    sid = r.json()["session_id"]

    pr = c.get(
        f"/v1/fly-reports/sessions/{sid}/preview", params={"user_id": "u1"}
    )
    assert pr.status_code == 200
    assert pr.headers["content-type"].startswith("text/html")
    body = pr.text
    assert "<!doctype html>" in body
    assert "FlyReport 预览" in body


def test_preview_html_409_when_no_preview_yet(client) -> None:
    c, _ = client
    r = c.post(
        "/v1/fly-reports/sessions",
        json={"tenant_id": "t1", "user_id": "u1"},
    )
    sid = r.json()["session_id"]
    pr = c.get(
        f"/v1/fly-reports/sessions/{sid}/preview", params={"user_id": "u1"}
    )
    assert pr.status_code == 409


def test_preview_html_404_for_other_user(client) -> None:
    c, _ = client
    r = c.post(
        "/v1/fly-reports/sessions",
        json={"tenant_id": "t1", "user_id": "u1", "initial_query": "飞行周报"},
    )
    sid = r.json()["session_id"]
    pr = c.get(
        f"/v1/fly-reports/sessions/{sid}/preview",
        params={"user_id": "intruder"},
    )
    assert pr.status_code == 404
