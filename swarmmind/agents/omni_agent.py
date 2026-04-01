"""OmniAgent capability models and ReActAgent-based runtime."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, TypeAlias

from agentscope.agent import ReActAgent
from agentscope.formatter import FormatterBase
from agentscope.memory import LongTermMemoryBase, MemoryBase
from agentscope.message import Msg, ToolUseBlock
from agentscope.model import ChatModelBase
from agentscope.tool import Toolkit
from pydantic import BaseModel, ConfigDict, Field

from swarmmind.agents.agent_skill import build_agent_skill_catalog, build_agent_skill_details, resolve_agent_skill_entries
from swarmmind.models.agent_profile import AgentProfile, HandoffPolicy, SkillsMode
from swarmmind.models.capability import AgentRole, RuntimeKind, ToolExecutionContract, ToolGroup
from swarmmind.models.execution import ExecutionProfile

AgentEventPublisher: TypeAlias = Callable[[str, dict[str, object]], Awaitable[None]]


class PromptSpec(BaseModel):
    """Resolved prompt-facing capability surface for the agent."""

    system_prompt: str = ""
    output_schema_name: str | None = None
    skill_catalog: list[dict[str, str]] = Field(default_factory=list)
    skill_details: list[dict[str, object]] = Field(default_factory=list)


class ResolvedSkill(BaseModel):
    """Prompt and execution metadata for an equipped skill package."""

    name: str
    description: str
    body: str = ""
    source_type: str | None = None
    install_state: str | None = None
    script_paths: list[str] = Field(default_factory=list)
    reference_paths: list[str] = Field(default_factory=list)
    asset_paths: list[str] = Field(default_factory=list)


class RuntimePolicy(BaseModel):
    """Runtime defaults consumed by OmniAgent."""

    default_runtime: RuntimeKind = RuntimeKind.HOST_TOOLS
    allow_runtime_switch: bool = False
    sandbox_profile: str | None = None
    fallback_chain: list[RuntimeKind] = Field(default_factory=list)


class MemoryPolicy(BaseModel):
    """Minimal memory contract for the first OmniAgent version."""

    enable_working_memory: bool = True
    enable_artifact_memory: bool = True
    enable_long_term_memory: bool = False


class AuditPolicy(BaseModel):
    """Controls which native events OmniAgent emits."""

    emit_agent_events: bool = True
    emit_tool_events: bool = True
    emit_skill_events: bool = True
    emit_runtime_events: bool = True


class CapabilityBundle(BaseModel):
    """Resolved capability bundle consumed by OmniAgent."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    role: AgentRole
    prompt_spec: PromptSpec
    output_schema_name: str | None = None
    allowed_tool_groups: list[ToolGroup] = Field(default_factory=list)
    allowed_tool_names: list[str] = Field(default_factory=list)
    resolved_tool_functions: list[Any] = Field(default_factory=list)
    skill_mode: SkillsMode = SkillsMode.ALL
    resolved_skills: list[ResolvedSkill] = Field(default_factory=list)
    allowed_skill_scripts: list[str] = Field(default_factory=list)
    runtime_policy: RuntimePolicy = Field(default_factory=RuntimePolicy)
    memory_policy: MemoryPolicy = Field(default_factory=MemoryPolicy)
    handoff_policy: HandoffPolicy = Field(default_factory=HandoffPolicy)
    audit_policy: AuditPolicy = Field(default_factory=AuditPolicy)
    tool_contracts: dict[str, ToolExecutionContract] = Field(default_factory=dict)
    default_tool_runtime: dict[str, RuntimeKind] = Field(default_factory=dict)


class CapabilityResolver:
    """Resolve the first version of OmniAgent capability bundles."""

    @classmethod
    def resolve(
        cls,
        *,
        role: AgentRole,
        system_prompt: str,
        tool_functions: list[Any],
        skill_profiles: list[str] | None = None,
        agent_profile: AgentProfile | None = None,
        execution_profile: ExecutionProfile | None = None,
    ) -> CapabilityBundle:
        effective_skill_profiles = list(skill_profiles or [])
        tool_names = cls._tool_names(tool_functions)
        runtime_policy = cls._resolve_runtime_policy(
            agent_profile=agent_profile,
            execution_profile=execution_profile,
        )
        resolved_skill_entries = resolve_agent_skill_entries(
            effective_skill_profiles,
            set(tool_names),
        )
        resolved_skills = [
            ResolvedSkill(
                name=entry.name,
                description=entry.description,
                body=entry.body,
                source_type=entry.source_type.value,
                install_state=entry.install_state.value,
                script_paths=list(entry.resources.scripts),
                reference_paths=list(entry.resources.references),
                asset_paths=list(entry.resources.assets),
            )
            for entry in resolved_skill_entries
        ]
        allowed_tool_groups = list(
            execution_profile.allowed_tool_groups
            if execution_profile is not None and execution_profile.allowed_tool_groups
            else agent_profile.allowed_tool_groups
            if agent_profile is not None
            else []
        )
        explicit_tool_names = list(
            execution_profile.allowed_tool_names
            if execution_profile is not None and execution_profile.allowed_tool_names
            else agent_profile.allowed_tool_names
            if agent_profile is not None
            else []
        )
        allowed_tool_names = sorted(set(tool_names).union(explicit_tool_names))
        allowed_skill_scripts = list(
            execution_profile.allowed_skill_scripts
            if execution_profile is not None and execution_profile.allowed_skill_scripts
            else agent_profile.allowed_skill_scripts
            if agent_profile is not None
            else []
        )
        prompt_spec = PromptSpec(
            system_prompt=system_prompt,
            skill_catalog=build_agent_skill_catalog(
                effective_skill_profiles,
                set(tool_names),
            ),
            skill_details=build_agent_skill_details(
                effective_skill_profiles,
                set(tool_names),
            ),
        )
        tool_contracts = cls._resolve_tool_contracts(tool_functions, runtime_policy.default_runtime)
        return CapabilityBundle(
            role=execution_profile.role if execution_profile is not None else role,
            prompt_spec=prompt_spec,
            output_schema_name=prompt_spec.output_schema_name,
            allowed_tool_groups=allowed_tool_groups,
            allowed_tool_names=allowed_tool_names,
            resolved_tool_functions=list(tool_functions),
            skill_mode=(
                execution_profile.skill_mode
                if execution_profile is not None
                else agent_profile.skill_mode
                if agent_profile is not None
                else SkillsMode.ALL
            ),
            resolved_skills=resolved_skills,
            allowed_skill_scripts=allowed_skill_scripts,
            runtime_policy=runtime_policy,
            memory_policy=MemoryPolicy(enable_long_term_memory=False),
            handoff_policy=(
                execution_profile.handoff_policy
                if execution_profile is not None
                else agent_profile.handoff_policy
                if agent_profile is not None
                else HandoffPolicy()
            ),
            audit_policy=AuditPolicy(),
            tool_contracts=tool_contracts,
            default_tool_runtime={
                tool_name: contract.default_runtime
                for tool_name, contract in tool_contracts.items()
            },
        )

    @staticmethod
    def _tool_names(tool_functions: list[Any]) -> list[str]:
        names: list[str] = []
        seen: set[str] = set()
        for tool in tool_functions:
            name = getattr(tool, "__name__", repr(tool))
            if name in seen:
                continue
            names.append(name)
            seen.add(name)
        return names

    @staticmethod
    def _resolve_runtime_policy(
        *,
        agent_profile: AgentProfile | None,
        execution_profile: ExecutionProfile | None,
    ) -> RuntimePolicy:
        if execution_profile is not None and execution_profile.resolved_runtime_kind is not None:
            default_runtime = execution_profile.resolved_runtime_kind
            fallback_chain = list(execution_profile.runtime_fallback_chain) or [default_runtime]
            sandbox_profile = execution_profile.sandbox_profile
        elif agent_profile is not None and agent_profile.default_sandbox_profile:
            default_runtime = RuntimeKind.SANDBOX
            fallback_chain = [RuntimeKind.SANDBOX, RuntimeKind.HOST_TOOLS]
            sandbox_profile = agent_profile.default_sandbox_profile
        else:
            default_runtime = RuntimeKind.HOST_TOOLS
            fallback_chain = [RuntimeKind.HOST_TOOLS]
            sandbox_profile = None
        return RuntimePolicy(
            default_runtime=default_runtime,
            allow_runtime_switch=len(fallback_chain) > 1,
            sandbox_profile=sandbox_profile,
            fallback_chain=fallback_chain,
        )

    @staticmethod
    def _resolve_default_tool_runtime(
        tool_names: list[str],
        default_runtime: RuntimeKind,
    ) -> dict[str, RuntimeKind]:
        mapping: dict[str, RuntimeKind] = {}
        for tool_name in tool_names:
            if tool_name in {"run_skill_script", "sandbox_exec"}:
                mapping[tool_name] = RuntimeKind.SANDBOX
                continue
            if default_runtime == RuntimeKind.SANDBOX and (
                tool_name.endswith("_write")
                or tool_name.endswith("_exec")
                or tool_name.startswith("project_write")
            ):
                mapping[tool_name] = RuntimeKind.SANDBOX
                continue
            mapping[tool_name] = RuntimeKind.HOST_TOOLS
        return mapping

    @classmethod
    def _resolve_tool_contracts(
        cls,
        tool_functions: list[Any],
        default_runtime: RuntimeKind,
    ) -> dict[str, ToolExecutionContract]:
        contracts: dict[str, ToolExecutionContract] = {}
        for tool in tool_functions:
            tool_name = getattr(tool, "__name__", repr(tool))
            if tool_name in contracts:
                continue
            raw_contract = getattr(tool, "__swarmmind_tool_contract__", None)
            if isinstance(raw_contract, ToolExecutionContract):
                contract = raw_contract.model_copy(deep=True)
            elif isinstance(raw_contract, dict):
                contract = ToolExecutionContract(**raw_contract)
            else:
                contract = cls._fallback_tool_contract(tool_name, default_runtime)
            contracts[tool_name] = cls._normalize_tool_contract(contract)
        return contracts

    @staticmethod
    def _normalize_tool_contract(contract: ToolExecutionContract) -> ToolExecutionContract:
        allowed_runtimes = list(contract.allowed_runtimes)
        if contract.sandbox_only:
            contract = contract.model_copy(update={"default_runtime": RuntimeKind.SANDBOX})
            allowed_runtimes = [RuntimeKind.SANDBOX]
        elif not allowed_runtimes:
            allowed_runtimes = [contract.default_runtime]
        return contract.model_copy(update={"allowed_runtimes": allowed_runtimes})

    @classmethod
    def _fallback_tool_contract(
        cls,
        tool_name: str,
        default_runtime: RuntimeKind,
    ) -> ToolExecutionContract:
        resolved_runtime = cls._resolve_default_tool_runtime([tool_name], default_runtime)[tool_name]
        return ToolExecutionContract(
            default_runtime=resolved_runtime,
            allowed_runtimes=[resolved_runtime],
            read_only=not (
                tool_name.endswith("_write")
                or tool_name.endswith("_exec")
                or tool_name in {"sandbox_exec", "run_skill_script", "memory_write"}
            ),
            audit_required=tool_name in {"sandbox_exec", "run_skill_script", "project_write", "memory_write"},
            dangerous=tool_name in {"sandbox_exec", "run_skill_script"},
            sandbox_only=tool_name in {"sandbox_exec", "run_skill_script"},
        )


class AgentEventEmitter:
    """Small async publisher used by OmniAgent native events."""

    def __init__(self, publisher: AgentEventPublisher | None = None) -> None:
        self._publisher = publisher

    async def emit(self, topic: str, payload: dict[str, object]) -> None:
        if self._publisher is None:
            return
        await self._publisher(topic, payload)


class OmniAgent(ReActAgent):
    """ReActAgent subclass that consumes a capability bundle."""

    def __init__(
        self,
        *,
        capability_bundle: CapabilityBundle,
        event_publisher: AgentEventPublisher | None = None,
        name: str,
        sys_prompt: str,
        model: ChatModelBase,
        formatter: FormatterBase,
        toolkit: Toolkit | None = None,
        memory: MemoryBase | None = None,
        long_term_memory: LongTermMemoryBase | None = None,
        long_term_memory_mode: str = "both",
        enable_meta_tool: bool = False,
        parallel_tool_calls: bool = False,
        knowledge: Any = None,
        enable_rewrite_query: bool = True,
        plan_notebook: Any = None,
        print_hint_msg: bool = False,
        max_iters: int = 10,
        tts_model: Any = None,
        compression_config: Any = None,
    ) -> None:
        super().__init__(
            name=name,
            sys_prompt=sys_prompt,
            model=model,
            formatter=formatter,
            toolkit=toolkit,
            memory=memory,
            long_term_memory=long_term_memory,
            long_term_memory_mode=long_term_memory_mode,
            enable_meta_tool=enable_meta_tool,
            parallel_tool_calls=parallel_tool_calls,
            knowledge=knowledge,
            enable_rewrite_query=enable_rewrite_query,
            plan_notebook=plan_notebook,
            print_hint_msg=print_hint_msg,
            max_iters=max_iters,
            tts_model=tts_model,
            compression_config=compression_config,
        )
        self.capability_bundle = capability_bundle
        self._event_emitter = AgentEventEmitter(event_publisher)

    async def reply(
        self,
        msg: Msg | list[Msg] | None = None,
        structured_model: type[BaseModel] | None = None,
    ) -> Msg:
        await self._emit_reply_started(structured_model)
        try:
            reply_msg = await super().reply(msg=msg, structured_model=structured_model)
        except Exception as exc:
            if self.capability_bundle.audit_policy.emit_agent_events:
                await self._event_emitter.emit(
                    "agent.failed",
                    {
                        **self._base_payload(),
                        "event_source": "omni_agent",
                        "error": str(exc),
                    },
                )
            raise

        if self.capability_bundle.audit_policy.emit_agent_events:
            await self._event_emitter.emit(
                "agent.completed",
                {
                    **self._base_payload(),
                    "event_source": "omni_agent",
                    "content_preview": (reply_msg.get_text_content() or "")[:500],
                },
            )
        return reply_msg

    async def _acting(self, tool_call: ToolUseBlock) -> dict | None:
        tool_name = str(tool_call["name"])
        tool_args = self._extract_tool_arguments(tool_call)
        tool_runtime = self.capability_bundle.default_tool_runtime.get(
            tool_name,
            self.capability_bundle.runtime_policy.default_runtime,
        )
        tool_contract = self.capability_bundle.tool_contracts.get(tool_name)
        if self.capability_bundle.audit_policy.emit_tool_events:
            await self._event_emitter.emit(
                "tool.started",
                {
                    **self._base_payload(),
                    "event_source": "omni_agent",
                    "tool_name": tool_name,
                    "tool_runtime": tool_runtime.value,
                    "tool_call_id": str(tool_call.get("id", "")),
                    **self._tool_contract_payload(tool_contract),
                },
            )
        try:
            result = await super()._acting(tool_call)
        except Exception as exc:
            if self.capability_bundle.audit_policy.emit_tool_events:
                await self._event_emitter.emit(
                    "tool.failed",
                    {
                        **self._base_payload(),
                        "event_source": "omni_agent",
                        "tool_name": tool_name,
                        "tool_runtime": tool_runtime.value,
                        "tool_call_id": str(tool_call.get("id", "")),
                        **self._tool_contract_payload(tool_contract),
                        "error": str(exc),
                    },
                )
            raise

        if self.capability_bundle.audit_policy.emit_tool_events:
            await self._event_emitter.emit(
                "tool.completed",
                {
                    **self._base_payload(),
                    "event_source": "omni_agent",
                    "tool_name": tool_name,
                    "tool_runtime": tool_runtime.value,
                    "tool_call_id": str(tool_call.get("id", "")),
                    **self._tool_contract_payload(tool_contract),
                },
            )
        if tool_name == "run_skill_script" and self.capability_bundle.audit_policy.emit_skill_events:
            await self._event_emitter.emit(
                "skill.executed",
                {
                    **self._base_payload(),
                    "event_source": "omni_agent",
                    "skill_name": str(tool_args.get("skill_name", "")),
                    "script_path": str(tool_args.get("script_path", "")),
                    "tool_runtime": tool_runtime.value,
                },
            )
        return result

    async def _emit_reply_started(
        self,
        structured_model: type[BaseModel] | None,
    ) -> None:
        if self.capability_bundle.audit_policy.emit_agent_events:
            await self._event_emitter.emit(
                "agent.started",
                {
                    **self._base_payload(),
                    "event_source": "omni_agent",
                    "structured_output": structured_model.__name__ if structured_model is not None else None,
                },
            )
        if self.capability_bundle.audit_policy.emit_runtime_events:
            await self._event_emitter.emit(
                "runtime.selected",
                {
                    **self._base_payload(),
                    "event_source": "omni_agent",
                    "runtime": self.capability_bundle.runtime_policy.default_runtime.value,
                    "sandbox_profile": self.capability_bundle.runtime_policy.sandbox_profile,
                    "fallback_chain": [item.value for item in self.capability_bundle.runtime_policy.fallback_chain],
                    "allow_runtime_switch": self.capability_bundle.runtime_policy.allow_runtime_switch,
                },
            )
        if self.capability_bundle.audit_policy.emit_skill_events:
            for skill in self.capability_bundle.resolved_skills:
                await self._event_emitter.emit(
                    "skill.resolved",
                    {
                        **self._base_payload(),
                        "event_source": "omni_agent",
                        "skill_name": skill.name,
                        "script_paths": list(skill.script_paths),
                    },
                )
        if self.capability_bundle.audit_policy.emit_tool_events:
            for tool_name in self.capability_bundle.allowed_tool_names:
                runtime = self.capability_bundle.default_tool_runtime.get(
                    tool_name,
                    self.capability_bundle.runtime_policy.default_runtime,
                )
                tool_contract = self.capability_bundle.tool_contracts.get(tool_name)
                await self._event_emitter.emit(
                    "tool.selected",
                    {
                        **self._base_payload(),
                        "event_source": "omni_agent",
                        "tool_name": tool_name,
                        "tool_runtime": runtime.value,
                        **self._tool_contract_payload(tool_contract),
                    },
                )

    def _base_payload(self) -> dict[str, object]:
        return {
            "agent_name": self.name,
            "role": self.capability_bundle.role.value,
            "allowed_tool_names": list(self.capability_bundle.allowed_tool_names),
            "allowed_skill_scripts": list(self.capability_bundle.allowed_skill_scripts),
        }

    @staticmethod
    def _extract_tool_arguments(tool_call: ToolUseBlock) -> dict[str, Any]:
        arguments = tool_call.get("arguments", {})
        if isinstance(arguments, dict):
            return dict(arguments)
        return {}

    @staticmethod
    def _tool_contract_payload(
        contract: ToolExecutionContract | None,
    ) -> dict[str, object]:
        if contract is None:
            return {}
        return {
            "tool_read_only": contract.read_only,
            "tool_audit_required": contract.audit_required,
            "tool_dangerous": contract.dangerous,
            "tool_sandbox_only": contract.sandbox_only,
        }
