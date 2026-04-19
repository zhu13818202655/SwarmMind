"""Shared fixtures for FlyReport dikong client tests."""

from __future__ import annotations

import pytest

from swarmmind.config.schema import FlyReportDikongConfig


@pytest.fixture
def dikong_config() -> FlyReportDikongConfig:
    """A predictable config that points at a fake host with low timeouts."""

    return FlyReportDikongConfig(
        base_url="http://dikong.test",
        token="test-token",
        tenant_header="X-Tenant-Id",
        request_timeout_seconds=2.0,
        max_retries=2,
        retry_backoff_seconds=0.0,  # zero backoff keeps tests fast
        max_concurrency=4,
        rate_limit_per_second=100.0,
    )


@pytest.fixture
def envelope_ok() -> dict:
    return {
        "code": 0,
        "msg": "ok",
        "requestId": "req-1",
        "requestTime": "2026-04-01T00:00:00Z",
        "data": {},
    }
