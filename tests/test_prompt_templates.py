from __future__ import annotations

import pytest
from jinja2 import UndefinedError

from swarmmind.agents.agent_skill import list_installed_skill_profile_names
from swarmmind.prompt_template import (
    EXECUTION_SUBTASK_MARKDOWN_PROMPT,
    EXECUTION_SYSTEM_PROMPT,
    PLANNER_EXECUTION_CONFIGURATION_PROMPT,
    PLANNER_EXECUTION_CONFIGURATION_SYSTEM_PROMPT,
    PLANNER_SYSTEM_PROMPT,
    PLANNER_TASK_DECOMPOSITION_SYSTEM_PROMPT,
    EXECUTION_FALLBACK_CONTENT_PROMPT,
    PLANNER_TASK_DECOMPOSITION_PROMPT,
    render_prompt,
)


def test_render_prompt_renders_jinja_template() -> None:
    rendered = render_prompt(
        PLANNER_TASK_DECOMPOSITION_PROMPT,
        {
            "task_goal": "实现导出功能",
            "constraints_json": "{}",
            "agent_profiles_json": "[]",
            "role_definitions": "coder: implement code",
        },
    )

    assert "目标：实现导出功能" in rendered
    assert "输出 Schema" in rendered
    assert "角色定义" in rendered


def test_render_prompt_fails_fast_when_variable_missing() -> None:
    with pytest.raises(UndefinedError):
        render_prompt(EXECUTION_FALLBACK_CONTENT_PROMPT, {"subtask_name": "demo"})


def test_planner_prompts_include_aio_only_sandbox_policy() -> None:
    installed_skill_names = "|".join(list_installed_skill_profile_names())
    assert "当前阶段只负责任务拆解" in PLANNER_TASK_DECOMPOSITION_SYSTEM_PROMPT.template
    assert "不负责 execution candidate 选择" in PLANNER_TASK_DECOMPOSITION_SYSTEM_PROMPT.template
    assert PLANNER_SYSTEM_PROMPT is PLANNER_TASK_DECOMPOSITION_SYSTEM_PROMPT
    assert "只负责补全 `tool_groups`、`runtime_kinds`、`skill_profiles`" in PLANNER_EXECUTION_CONFIGURATION_SYSTEM_PROMPT.template
    assert "只通过 `runtime_kinds` 是否包含 `sandbox` 表达" in PLANNER_EXECUTION_CONFIGURATION_SYSTEM_PROMPT.template
    assert "只能根据当前输入中提供的候选 `tool_groups`、`runtime_kinds`、`skill_profiles` 做选择" in PLANNER_EXECUTION_CONFIGURATION_SYSTEM_PROMPT.template
    assert '"tool_groups": ["file_system|workspace|web_search|browser|code_exec|memory|artifact|communication"]' in PLANNER_EXECUTION_CONFIGURATION_PROMPT.template
    assert '"runtime_kinds": ["llm_only|host_tools|sandbox"]' in PLANNER_EXECUTION_CONFIGURATION_PROMPT.template
    assert f'"skill_profiles": ["{installed_skill_names}"]' in PLANNER_EXECUTION_CONFIGURATION_PROMPT.template
    assert "如果输入中的 `available_skill_profiles` 为空，必须输出 `[]`" in PLANNER_EXECUTION_CONFIGURATION_PROMPT.template
    assert "`llm_only`：只依赖模型推理，不调用外部工具。" in PLANNER_EXECUTION_CONFIGURATION_PROMPT.template
    assert "只有在需要读取依赖产物、附件或已有输出时才包含 `artifact`" in PLANNER_EXECUTION_CONFIGURATION_PROMPT.template
    assert "`file_system` 用于基础文件读写、重命名和建目录" in PLANNER_EXECUTION_CONFIGURATION_PROMPT.template


def test_execution_prompts_include_capability_boundaries() -> None:
    assert "你不需要选择、输出或请求 sandbox profile 名称" in EXECUTION_SYSTEM_PROMPT.template
    assert "工具组能力边界：" in EXECUTION_SUBTASK_MARKDOWN_PROMPT.template
    assert "workspace：仅用于检查和修改仓库或工作区文件。" in EXECUTION_SUBTASK_MARKDOWN_PROMPT.template
    assert "系统会自动绑定 `aio`" in EXECUTION_SUBTASK_MARKDOWN_PROMPT.template
    assert "Markdown 只是一份摘要，不能替代文件本身" in EXECUTION_SUBTASK_MARKDOWN_PROMPT.template
    assert "依赖子任务摘要：{{ dependency_summary_json }}" in EXECUTION_SUBTASK_MARKDOWN_PROMPT.template


def test_planner_execution_configuration_prompt_requires_code_exec_for_real_files() -> None:
    assert "真实文件产物" in PLANNER_EXECUTION_CONFIGURATION_PROMPT.template
    assert "必须包含 `code_exec`" in PLANNER_EXECUTION_CONFIGURATION_PROMPT.template
    assert "优先把 `sandbox` 放在 `runtime_kinds` 的第一位" in PLANNER_EXECUTION_CONFIGURATION_PROMPT.template