"""Tests for :class:`IntentParser` covering DESIGN-2 §13.3 scenarios."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from swarmmind.domains.fly_report.errors import FilterParseError
from swarmmind.domains.fly_report.intent import IntentParser
from swarmmind.domains.fly_report.schemas import DraftFilterSpec

# ---------------------------------------------------------------------------
# Canned LLM replies (one per scenario)
# ---------------------------------------------------------------------------

OVERALL_WEEKLY_JSON = json.dumps(
    {
        "period": {
            "kind": "weekly",
            "start": "2026-04-13T00:00:00+08:00",
            "end": "2026-04-19T23:59:59+08:00",
            "label": "2026年第16周",
        },
        "dimension": {
            "scope": "overall",
            "department_ids": [],
            "pilot_ids": [],
            "compare_with": [],
        },
        "indicators": ["flight"],
        "options": {
            "include_charts": True,
            "include_trend": True,
            "include_compare": False,
            "notes_section": False,
            "locale": "zh-CN",
            "output_format": "docx",
        },
        "missing": [],
        "conflicts": [],
    }
)

DEPT_MONTHLY_JSON = json.dumps(
    {
        "period": {
            "kind": "monthly",
            "start": "2026-03-01T00:00:00+08:00",
            "end": "2026-03-31T23:59:59+08:00",
            "label": "2026年3月",
        },
        "dimension": {
            "scope": "department",
            "department_ids": ["d-001"],
            "pilot_ids": [],
            "compare_with": [],
        },
        "indicators": ["flight", "algorithm"],
        "options": {
            "include_charts": True,
            "include_trend": True,
            "include_compare": False,
            "notes_section": False,
            "locale": "zh-CN",
            "output_format": "docx",
        },
        "missing": [],
        "conflicts": [],
    }
)

PILOT_WEEKLY_JSON = json.dumps(
    {
        "period": {
            "kind": "weekly",
            "start": "2026-04-06T00:00:00+08:00",
            "end": "2026-04-12T23:59:59+08:00",
            "label": "2026年第15周",
        },
        "dimension": {
            "scope": "pilot",
            "department_ids": [],
            "pilot_ids": ["P-001"],
            "compare_with": [],
        },
        "indicators": ["flight"],
        "options": {
            "include_charts": True,
            "include_trend": True,
            "include_compare": False,
            "notes_section": False,
            "locale": "zh-CN",
            "output_format": "docx",
        },
        "missing": [],
        "conflicts": [],
    }
)

DEPT_COMPARE_JSON = (
    "```json\n"
    + json.dumps(
        {
            "period": {
                "kind": "monthly",
                "start": "2026-04-01T00:00:00+08:00",
                "end": "2026-04-30T23:59:59+08:00",
                "label": "2026年4月",
            },
            "dimension": {
                "scope": "department",
                "department_ids": ["d-001", "d-002"],
                "pilot_ids": [],
                "compare_with": ["d-001", "d-002"],
            },
            "indicators": ["flight"],
            "options": {
                "include_charts": True,
                "include_trend": True,
                "include_compare": True,
                "notes_section": False,
                "locale": "zh-CN",
                "output_format": "pdf",
            },
            "missing": [],
            "conflicts": [],
        }
    )
    + "\n```"
)

CUSTOM_PERIOD_JSON = json.dumps(
    {
        "period": {
            "kind": "custom",
            "start": "2026-03-01T00:00:00+08:00",
            "end": "2026-03-15T23:59:59+08:00",
            "label": "2026-03-01 ~ 2026-03-15",
        },
        "dimension": {"scope": "overall"},
        "indicators": ["flight", "media_image"],
        "options": {"output_format": "markdown"},
        "missing": [],
        "conflicts": [],
    }
)

AMBIGUOUS_JSON = json.dumps(
    {
        "period": None,
        "dimension": {
            "scope": "department",
            "department_ids": [],
            "pilot_ids": [],
            "compare_with": [],
        },
        "indicators": ["flight"],
        "options": {},
        "missing": ["period", "dimension.department_ids"],
        "conflicts": [],
    }
)

FUTURE_CONFLICT_JSON = json.dumps(
    {
        "period": None,
        "dimension": {"scope": "overall"},
        "indicators": ["flight"],
        "options": {},
        "missing": ["period"],
        "conflicts": ["period.future_not_supported"],
    }
)


# ---------------------------------------------------------------------------
# Five core scenarios from DESIGN-2 §13.3
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_overall_weekly_report(stub_agent_factory) -> None:
    agent = stub_agent_factory(OVERALL_WEEKLY_JSON)
    parser = IntentParser(agent)

    draft = await parser.parse(
        "这周的飞行报告",
        now=datetime(2026, 4, 15, 9, 0, tzinfo=timezone.utc),
    )

    assert isinstance(draft, DraftFilterSpec)
    assert draft.period is not None and draft.period.kind == "weekly"
    assert draft.dimension.scope == "overall"
    assert draft.indicators == ["flight"]
    assert draft.options.output_format == "docx"
    assert draft.missing == [] and draft.conflicts == []
    # `now` is forwarded as ISO string in metadata.
    assert agent.calls[0].metadata["now"].startswith("2026-04-15")


@pytest.mark.asyncio
async def test_department_monthly_report(stub_agent_factory) -> None:
    agent = stub_agent_factory(DEPT_MONTHLY_JSON)
    parser = IntentParser(agent)

    draft = await parser.parse("农业局上个月的报告")

    assert draft.period is not None and draft.period.kind == "monthly"
    assert draft.dimension.scope == "department"
    assert draft.dimension.department_ids == ["d-001"]
    assert "algorithm" in draft.indicators


@pytest.mark.asyncio
async def test_pilot_personal_report(stub_agent_factory) -> None:
    agent = stub_agent_factory(PILOT_WEEKLY_JSON)
    parser = IntentParser(agent)

    draft = await parser.parse("飞手 P-001 上周飞行情况")

    assert draft.dimension.scope == "pilot"
    assert draft.dimension.pilot_ids == ["P-001"]
    assert draft.dimension.department_ids == []


@pytest.mark.asyncio
async def test_department_comparison_with_preference(stub_agent_factory) -> None:
    agent = stub_agent_factory(DEPT_COMPARE_JSON)
    parser = IntentParser(agent)
    preference = {"report_options_default": {"output_format": "pdf"}}

    draft = await parser.parse(
        "农业局 vs 自规局 本月飞行对比",
        preference=preference,
    )

    assert draft.dimension.compare_with == ["d-001", "d-002"]
    assert draft.dimension.department_ids == ["d-001", "d-002"]
    assert draft.options.include_compare is True
    assert draft.options.output_format == "pdf"
    # preference is propagated as metadata to the agent.
    assert agent.calls[0].metadata["preference"] == preference


@pytest.mark.asyncio
async def test_custom_period_markdown(stub_agent_factory) -> None:
    agent = stub_agent_factory(CUSTOM_PERIOD_JSON)
    parser = IntentParser(agent)

    draft = await parser.parse("3月1日到3月15日的报告，导出 markdown")

    assert draft.period is not None and draft.period.kind == "custom"
    assert draft.options.output_format == "markdown"
    assert "media_image" in draft.indicators


# ---------------------------------------------------------------------------
# Boundary scenarios
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ambiguous_input_does_not_raise(stub_agent_factory) -> None:
    """missing/conflicts是数据，不是异常 —— 由状态机决定是否走 clarifier。"""

    agent = stub_agent_factory(AMBIGUOUS_JSON)
    parser = IntentParser(agent)

    draft = await parser.parse("帮我看下最近那个部门的报告")

    assert draft.period is None
    assert "period" in draft.missing
    assert "dimension.department_ids" in draft.missing


@pytest.mark.asyncio
async def test_future_period_marked_as_conflict(stub_agent_factory) -> None:
    agent = stub_agent_factory(FUTURE_CONFLICT_JSON)
    parser = IntentParser(agent)

    draft = await parser.parse("下周的飞行报告")

    assert draft.period is None
    assert "period.future_not_supported" in draft.conflicts


# ---------------------------------------------------------------------------
# Failure modes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_non_json_reply_raises_filter_parse_error(stub_agent_factory) -> None:
    agent = stub_agent_factory("抱歉我不明白你想要什么")
    parser = IntentParser(agent)

    with pytest.raises(FilterParseError) as exc:
        await parser.parse("生成报告")

    assert "non-JSON" in exc.value.message or "JSON" in exc.value.message


@pytest.mark.asyncio
async def test_invalid_schema_raises_filter_parse_error(stub_agent_factory) -> None:
    bad = json.dumps({"period": {"kind": "yearly"}})  # invalid period kind
    agent = stub_agent_factory(bad)
    parser = IntentParser(agent)

    with pytest.raises(FilterParseError) as exc:
        await parser.parse("生成报告")

    assert "DraftFilterSpec" in exc.value.message
    assert "errors" in exc.value.details


@pytest.mark.asyncio
async def test_empty_user_text_rejected(stub_agent_factory) -> None:
    agent = stub_agent_factory()  # no replies expected
    parser = IntentParser(agent)

    with pytest.raises(FilterParseError):
        await parser.parse("   ")

    assert agent.calls == []
