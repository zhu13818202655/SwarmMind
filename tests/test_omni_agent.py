from __future__ import annotations

from typing import Any

import pytest
from agentscope.agent import ReActAgent
from agentscope.message import Msg
from agentscope.message import TextBlock
from agentscope.model import ChatResponse, OpenAIChatModel

from swarmmind.agents import AgentConfig, AgentFactory, AgentScopeConfig, OmniAgent
from swarmmind.models.agent_profile import AgentProfile, SkillsMode
from swarmmind.models.capability import AgentRole, RuntimeKind, ToolExecutionContract, ToolGroup
from swarmmind.models.execution import ExecutionProfile


async def project_read(path: str) -> str:
    return path


async def project_write(path: str, content: str) -> str:
    return f"{path}:{len(content)}"


async def run_skill_script(skill_name: str, script_path: str) -> dict[str, str]:
    return {"skill_name": skill_name, "script_path": script_path}


setattr(
    project_read,
    "__swarmmind_tool_contract__",
    ToolExecutionContract(
        default_runtime=RuntimeKind.HOST_TOOLS,
        allowed_runtimes=[RuntimeKind.HOST_TOOLS],
        read_only=True,
    ),
)
setattr(project_read, "__swarmmind_tool_groups__", (ToolGroup.FILE_SYSTEM,))
setattr(
    project_write,
    "__swarmmind_tool_contract__",
    ToolExecutionContract(
        default_runtime=RuntimeKind.HOST_TOOLS,
        allowed_runtimes=[RuntimeKind.HOST_TOOLS, RuntimeKind.SANDBOX],
        audit_required=True,
    ),
)
setattr(project_write, "__swarmmind_tool_groups__", (ToolGroup.FILE_SYSTEM,))
setattr(
    run_skill_script,
    "__swarmmind_tool_contract__",
    ToolExecutionContract(
        default_runtime=RuntimeKind.SANDBOX,
        allowed_runtimes=[RuntimeKind.SANDBOX],
        audit_required=True,
        dangerous=True,
        sandbox_only=True,
    ),
)
setattr(run_skill_script, "__swarmmind_tool_groups__", (ToolGroup.CODE_EXEC,))


def _build_factory() -> AgentFactory:
    return AgentFactory(
        AgentConfig(
            name="omni-test",
            role=AgentRole.CODER,
            scope_config=AgentScopeConfig(
                model_name="gpt-4o",
                api_key="test-key",
                base_url="http://example.invalid/v1",
                temperature=0.1,
                max_tokens=512,
            ),
            max_steps=4,
            system_prompt="You are the coding agent.",
            skill_profiles=[],
            tool_groups=[ToolGroup.WORKSPACE, ToolGroup.FILE_SYSTEM, ToolGroup.CODE_EXEC],
        )
    )


def test_factory_creates_omni_agent_with_capability_bundle() -> None:
    factory = _build_factory()
    agent = factory.create_main_agent(tools=[project_read, project_write, run_skill_script])

    assert isinstance(agent, OmniAgent)
    assert agent.capability_bundle.role == AgentRole.CODER
    assert "project_read" in agent.capability_bundle.allowed_tool_names
    assert "project_write" in agent.capability_bundle.allowed_tool_names
    assert agent.capability_bundle.runtime_policy.default_runtime == RuntimeKind.HOST_TOOLS
    assert isinstance(agent.capability_bundle.resolved_skills, list)
    assert agent.capability_bundle.tool_contracts["project_read"].read_only is True
    assert agent.capability_bundle.default_tool_runtime["run_skill_script"] == RuntimeKind.SANDBOX


def test_factory_can_create_lightweight_agent_without_tools_or_skills() -> None:
    factory = _build_factory()

    agent = factory.create_main_agent(
        tools=[project_read, project_write, run_skill_script],
        allow_tools=False,
        allow_skills=False,
    )

    assert isinstance(agent, OmniAgent)
    assert agent.toolkit.get_json_schemas() == []
    assert agent.capability_bundle.allowed_tool_names == []
    assert agent.capability_bundle.resolved_tool_functions == []
    assert agent.capability_bundle.resolved_skills == []
    assert agent.sys_prompt == "You are the coding agent."


def test_factory_create_toolkit_activates_only_requested_groups() -> None:
    factory = _build_factory()

    toolkit = factory.create_toolkit(
        tools=[project_read, project_write, run_skill_script],
        tool_groups=[ToolGroup.FILE_SYSTEM],
    )

    exposed = {schema["function"]["name"] for schema in toolkit.get_json_schemas()}

    assert "project_read" in exposed
    assert "project_write" in exposed
    assert "run_skill_script" not in exposed


def test_factory_uses_execution_profile_overrides_in_capability_bundle() -> None:
    factory = _build_factory()
    profile = AgentProfile(
        id="coder-sandbox",
        name="Coder Sandbox",
        role=AgentRole.CODER,
        skill_mode=SkillsMode.INCLUSIVE,
        skill_profiles=["pptx"],
        allowed_tool_groups=[ToolGroup.WORKSPACE, ToolGroup.FILE_SYSTEM, ToolGroup.CODE_EXEC],
        allowed_tool_names=["project_read", "project_write", "run_skill_script"],
        allowed_skill_scripts=["pptx:scripts/render.py"],
        default_sandbox_profile="aio",
    )
    execution_profile = ExecutionProfile(
        role=AgentRole.WRITER,
        resolved_runtime_kind=RuntimeKind.HOST_TOOLS,
        runtime_fallback_chain=[RuntimeKind.SANDBOX],
        runtime_resolution_reason="Test override",
        allowed_tool_names=["project_read", "run_skill_script"],
        skill_profiles=["pptx"],
        allowed_skill_scripts=["pptx:scripts/render.py"],
    )

    agent = factory.create_profile_agent(
        profile,
        tools=[project_read, project_write, run_skill_script],
        execution_profile=execution_profile,
    )

    assert agent.capability_bundle.role == AgentRole.WRITER
    assert agent.capability_bundle.runtime_policy.default_runtime == RuntimeKind.HOST_TOOLS
    assert agent.capability_bundle.allowed_skill_scripts == ["pptx:scripts/render.py"]
    assert "project_write" not in agent.capability_bundle.allowed_tool_names
    assert any(skill.name == "pptx" for skill in agent.capability_bundle.resolved_skills)


@pytest.mark.asyncio
async def test_omni_agent_emits_preflight_events(monkeypatch: pytest.MonkeyPatch) -> None:
    factory = _build_factory()
    events: list[tuple[str, dict[str, object]]] = []
    agent = factory.create_main_agent(
        tools=[project_read, project_write, run_skill_script],
        event_publisher=lambda topic, payload: _capture(events, topic, payload),
    )

    async def fake_reply(self: ReActAgent, msg: Msg | list[Msg] | None = None, structured_model: Any | None = None) -> Msg:
        return Msg(name="assistant", role="assistant", content="ok")

    monkeypatch.setattr(ReActAgent, "reply", fake_reply)

    response = await agent.reply(Msg(name="user", role="user", content="build it"))

    assert response.get_text_content() == "ok"
    event_types = [topic for topic, _ in events]
    assert "agent.started" in event_types
    assert "runtime.selected" in event_types
    assert "tool.selected" in event_types
    assert "agent.completed" in event_types


@pytest.mark.asyncio
async def test_omni_agent_acting_emits_tool_and_skill_events(monkeypatch: pytest.MonkeyPatch) -> None:
    factory = _build_factory()
    events: list[tuple[str, dict[str, object]]] = []
    profile = AgentProfile(
        id="coder-sandbox",
        name="Coder Sandbox",
        role=AgentRole.CODER,
        skill_mode=SkillsMode.INCLUSIVE,
        skill_profiles=["pptx"],
        allowed_tool_groups=[ToolGroup.WORKSPACE, ToolGroup.FILE_SYSTEM, ToolGroup.CODE_EXEC],
        default_sandbox_profile="aio",
    )
    agent = factory.create_profile_agent(
        profile,
        tools=[project_read, project_write, run_skill_script],
        event_publisher=lambda topic, payload: _capture(events, topic, payload),
    )

    async def fake_acting(self: ReActAgent, tool_call: dict[str, object]) -> dict[str, str] | None:
        return {"ok": "1"}

    monkeypatch.setattr(ReActAgent, "_acting", fake_acting)

    await agent._acting(
        {
            "id": "call-1",
            "name": "run_skill_script",
            "arguments": {"skill_name": "pptx", "script_path": "scripts/render.py"},
        }
    )

    event_types = [topic for topic, _ in events]
    assert "tool.started" in event_types
    assert "tool.completed" in event_types
    assert "skill.executed" in event_types
    tool_started = next(payload for topic, payload in events if topic == "tool.started")
    assert tool_started["tool_runtime"] == RuntimeKind.SANDBOX.value
    assert tool_started["tool_audit_required"] is True
    assert tool_started["tool_sandbox_only"] is True


@pytest.mark.asyncio
async def test_factory_model_client_emits_llm_audit_events(monkeypatch: pytest.MonkeyPatch) -> None:
    factory = _build_factory()
    events: list[tuple[str, dict[str, object]]] = []
    model = factory.create_model_client(event_publisher=lambda topic, payload: _capture(events, topic, payload))

    async def fake_call(
        self: OpenAIChatModel,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]] | None = None,
        tool_choice: str | None = None,
        structured_model: Any | None = None,
        **kwargs: Any,
    ) -> ChatResponse:
        del self, tools, tool_choice, structured_model, kwargs
        assert messages[0]["content"] == "inspect llm call"
        return ChatResponse(content=[TextBlock(type="text", text="ok")])

    monkeypatch.setattr(OpenAIChatModel, "__call__", fake_call)

    response = await model(messages=[{"role": "user", "content": "inspect llm call"}])

    assert response.content[0]["text"] == "ok"
    assert [topic for topic, _ in events] == ["llm.requested", "llm.responded"]
    assert events[0][1]["messages"][0]["content"] == "inspect llm call"
    assert events[1][1]["response"]["content"][0]["text"] == "ok"


def test_factory_sanitizes_profile_agent_name() -> None:
    factory = _build_factory()
    profile = AgentProfile(
        id="writer-default",
        name="Writer Default",
        role=AgentRole.WRITER,
    )

    agent = factory.create_profile_agent(profile, tools=[])

    assert agent.name == "Writer_Default"


async def _capture(
    events: list[tuple[str, dict[str, object]]],
    topic: str,
    payload: dict[str, object],
) -> None:
    events.append((topic, payload))