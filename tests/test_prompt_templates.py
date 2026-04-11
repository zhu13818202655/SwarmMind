from __future__ import annotations

import pytest
from jinja2 import UndefinedError

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
    assert "当前阶段只负责任务拆解" in PLANNER_TASK_DECOMPOSITION_SYSTEM_PROMPT.template
    assert "不负责 execution candidate 选择" in PLANNER_TASK_DECOMPOSITION_SYSTEM_PROMPT.template
    assert PLANNER_SYSTEM_PROMPT is PLANNER_TASK_DECOMPOSITION_SYSTEM_PROMPT
    assert "sandbox 能力统一由 `aio` 提供" in PLANNER_EXECUTION_CONFIGURATION_SYSTEM_PROMPT.template
    assert "系统会自动绑定 `aio`" in PLANNER_EXECUTION_CONFIGURATION_PROMPT.template
    assert '"sandbox_profile"' not in PLANNER_EXECUTION_CONFIGURATION_PROMPT.template


def test_execution_prompts_include_capability_boundaries() -> None:
    assert "你不需要选择、输出或请求 sandbox profile 名称" in EXECUTION_SYSTEM_PROMPT.template
    assert "工具组能力边界：" in EXECUTION_SUBTASK_MARKDOWN_PROMPT.template
    assert "workspace：仅用于检查和修改仓库或工作区文件。" in EXECUTION_SUBTASK_MARKDOWN_PROMPT.template
    assert "系统会自动绑定 `aio`" in EXECUTION_SUBTASK_MARKDOWN_PROMPT.template