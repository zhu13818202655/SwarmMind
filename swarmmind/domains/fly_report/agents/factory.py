"""Builders for FlyReport's domain-private LLM agents.

Each agent is a thin :class:`agentscope.agent.ReActAgent`:

- ``response_format`` is locked to JSON so callers can ``model_validate_json``;
- ``Toolkit()`` is empty by design — these agents must not gain side-effects;
- ``max_iters=1`` so we never enter a tool-use loop.

The LLM client is :class:`AuditedOpenAIChatModel` so every call is captured by
the standard SwarmMind audit/event pipeline.
"""

from __future__ import annotations

from typing import Any

from agentscope.agent import ReActAgent
from agentscope.formatter import OpenAIChatFormatter
from agentscope.memory import InMemoryMemory
from agentscope.tool import Toolkit

from swarmmind.agents.audited_model import AuditedOpenAIChatModel
from swarmmind.config.schema import ModelConfig
from swarmmind.prompt_template.fly_report import (
    CLARIFY_SYSTEM_PROMPT,
    FOLLOWUP_PATCH_SYSTEM_PROMPT,
    INTENT_PARSE_SYSTEM_PROMPT,
)


def _build_model(
    model_config: ModelConfig,
    *,
    event_publisher: Any = None,
) -> AuditedOpenAIChatModel:
    """Build a JSON-only audited chat model from a ``ModelConfig``."""

    return AuditedOpenAIChatModel(
        model_name=model_config.name,
        api_key=model_config.api_key,
        event_publisher=event_publisher,
        generate_kwargs={
            "temperature": model_config.temperature,
            "max_tokens": model_config.max_tokens,
            "response_format": {"type": "json_object"},
        },
        client_kwargs={"base_url": model_config.base_url},
    )


def _build_agent(
    *,
    name: str,
    sys_prompt: str,
    model_config: ModelConfig,
    event_publisher: Any = None,
) -> ReActAgent:
    return ReActAgent(
        name=name,
        sys_prompt=sys_prompt,
        model=_build_model(model_config, event_publisher=event_publisher),
        formatter=OpenAIChatFormatter(),
        memory=InMemoryMemory(),
        toolkit=Toolkit(),  # intentionally empty - JSON-only LLM node
        max_iters=1,
    )


def build_intent_agent(
    model_config: ModelConfig,
    *,
    event_publisher: Any = None,
) -> ReActAgent:
    return _build_agent(
        name="fly_report.intent_parser",
        sys_prompt=INTENT_PARSE_SYSTEM_PROMPT.template,
        model_config=model_config,
        event_publisher=event_publisher,
    )


def build_clarifier_agent(
    model_config: ModelConfig,
    *,
    event_publisher: Any = None,
) -> ReActAgent:
    return _build_agent(
        name="fly_report.clarifier",
        sys_prompt=CLARIFY_SYSTEM_PROMPT.template,
        model_config=model_config,
        event_publisher=event_publisher,
    )


def build_followup_router_agent(
    model_config: ModelConfig,
    *,
    event_publisher: Any = None,
) -> ReActAgent:
    return _build_agent(
        name="fly_report.followup_router",
        sys_prompt=FOLLOWUP_PATCH_SYSTEM_PROMPT.template,
        model_config=model_config,
        event_publisher=event_publisher,
    )


__all__ = [
    "build_intent_agent",
    "build_clarifier_agent",
    "build_followup_router_agent",
]
