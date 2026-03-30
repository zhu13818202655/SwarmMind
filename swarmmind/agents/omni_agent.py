"""Unified SwarmMind agent wrapper built on top of AgentScope."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from agentscope.message import Msg

from swarmmind.agents.config import AgentConfig, AgentScopeConfig
from swarmmind.agents.factory import AgentFactory
from swarmmind.models.agent_profile import AgentProfile


AgentStepPublisher = Callable[[str, dict[str, object]], Awaitable[None]]


@dataclass(slots=True)
class OmniAgentRequest:
    """Resolved request for a single unified agent step."""

    agent_name: str
    prompt: str
    system_prompt: str
    step_kind: str
    tool_functions: list[Any] = field(default_factory=list)
    skill_profiles: list[str] = field(default_factory=list)
    agent_profile: AgentProfile | None = None


@dataclass(slots=True)
class OmniAgentResult:
    """Outcome of a unified agent step."""

    status: str
    content: str | None = None
    reason: str | None = None
    error: str | None = None
    tool_names: list[str] = field(default_factory=list)
    skill_profiles: list[str] = field(default_factory=list)
    agent_name: str | None = None
    agent_profile_id: str | None = None
    model_name: str | None = None


class OmniAgent:
    """Execute SwarmMind agent steps through a single wrapper."""

    def __init__(
        self,
        *,
        model_name: str,
        api_key: str | None,
        base_url: str | None,
        temperature: float,
        max_tokens: int,
        max_steps: int = 6,
    ) -> None:
        self._model_name = model_name
        self._api_key = api_key
        self._base_url = base_url
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._max_steps = max_steps

    async def run(
        self,
        request: OmniAgentRequest,
        *,
        publisher: AgentStepPublisher | None = None,
    ) -> OmniAgentResult:
        """Run a single prompt through the unified agent wrapper."""
        tool_names = [getattr(tool, "__name__", repr(tool)) for tool in request.tool_functions]
        common_payload = {
            "step_kind": request.step_kind,
            "agent_name": request.agent_profile.name if request.agent_profile is not None else request.agent_name,
            "agent_profile_id": request.agent_profile.id if request.agent_profile is not None else None,
            "tool_names": tool_names,
            "skill_profiles": list(request.skill_profiles),
        }

        if not self._model_name or (not self._api_key and not self._base_url):
            result = OmniAgentResult(
                status="fallback",
                reason="model_unavailable",
                tool_names=tool_names,
                skill_profiles=list(request.skill_profiles),
                agent_name=common_payload["agent_name"],
                agent_profile_id=common_payload["agent_profile_id"],
                model_name=self._model_name,
            )
            await self._publish(publisher, "agent.step.fallback", {**common_payload, "reason": result.reason})
            return result

        await self._publish(publisher, "agent.step.started", common_payload)

        try:
            agent_profile = request.agent_profile
            agent_factory = AgentFactory(
                AgentConfig(
                    name=request.agent_name,
                    scope_config=AgentScopeConfig(
                        model_name=agent_profile.preferred_model if agent_profile and agent_profile.preferred_model else self._model_name,
                        api_key=self._api_key,
                        base_url=agent_profile.preferred_endpoint if agent_profile and agent_profile.preferred_endpoint else self._base_url,
                        temperature=self._temperature,
                        max_tokens=self._max_tokens,
                    ),
                    max_steps=self._max_steps,
                    system_prompt=request.system_prompt,
                    skill_profiles=list(request.skill_profiles),
                )
            )
            if agent_profile is not None:
                agent = agent_factory.create_profile_agent(
                    agent_profile,
                    tools=request.tool_functions,
                    system_prompt=request.system_prompt,
                )
            else:
                agent = agent_factory.create_main_agent(tools=request.tool_functions)

            response = await agent(Msg(name="user", role="user", content=request.prompt))
            content = response.get_text_content()
            if content and content.strip():
                normalized = content.strip()
            else:
                normalized = json.dumps(response.to_dict(), ensure_ascii=False, indent=2)

            result = OmniAgentResult(
                status="completed",
                content=normalized,
                tool_names=tool_names,
                skill_profiles=list(request.skill_profiles),
                agent_name=common_payload["agent_name"],
                agent_profile_id=common_payload["agent_profile_id"],
                model_name=agent_profile.preferred_model if agent_profile and agent_profile.preferred_model else self._model_name,
            )
            await self._publish(
                publisher,
                "agent.step.completed",
                {
                    **common_payload,
                    "response_preview": normalized[:500],
                    "model_name": result.model_name,
                },
            )
            return result
        except Exception as exc:
            result = OmniAgentResult(
                status="failed",
                reason="execution_failed",
                error=str(exc),
                tool_names=tool_names,
                skill_profiles=list(request.skill_profiles),
                agent_name=common_payload["agent_name"],
                agent_profile_id=common_payload["agent_profile_id"],
                model_name=self._model_name,
            )
            await self._publish(
                publisher,
                "agent.step.failed",
                {**common_payload, "reason": result.reason, "error": result.error or ""},
            )
            return result

    @staticmethod
    async def _publish(
        publisher: AgentStepPublisher | None,
        topic: str,
        payload: dict[str, object],
    ) -> None:
        if publisher is None:
            return
        await publisher(topic, payload)