"""F4: header builder."""

from __future__ import annotations

from swarmmind.domains.fly_report.dikong.auth import build_headers


def test_minimum_headers_have_accept() -> None:
    headers = build_headers(token=None)
    assert headers == {"Accept": "*/*"}


def test_token_uses_back_token_header() -> None:
    headers = build_headers(token="abc")
    # Dikong expects a custom ``back-token`` header, not Authorization.
    assert headers["back-token"] == "abc"
    assert "Authorization" not in headers


def test_extra_headers_override_built_ins() -> None:
    headers = build_headers(
        token="abc",
        extra={"back-token": "override", "X-Trace": "t"},
    )
    assert headers["back-token"] == "override"
    assert headers["X-Trace"] == "t"
