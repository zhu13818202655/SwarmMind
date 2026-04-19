"""F4: header builder."""

from __future__ import annotations

from swarmmind.domains.fly_report.dikong.auth import build_headers


def test_minimum_headers_have_accept() -> None:
    headers = build_headers(token=None, tenant_id=None)
    assert headers == {"Accept": "*/*"}


def test_token_becomes_bearer() -> None:
    headers = build_headers(token="abc", tenant_id=None)
    assert headers["Authorization"] == "Bearer abc"


def test_tenant_uses_configured_header() -> None:
    headers = build_headers(token=None, tenant_id="t-1", tenant_header="X-Org")
    assert headers["X-Org"] == "t-1"
    assert "Authorization" not in headers


def test_extra_headers_override_built_ins() -> None:
    headers = build_headers(
        token="abc",
        tenant_id="t-1",
        extra={"Authorization": "Custom xyz", "X-Trace": "t"},
    )
    assert headers["Authorization"] == "Custom xyz"
    assert headers["X-Trace"] == "t"
    assert headers["X-Tenant-Id"] == "t-1"
