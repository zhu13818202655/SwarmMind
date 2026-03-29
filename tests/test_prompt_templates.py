from __future__ import annotations

import pytest
from jinja2 import UndefinedError

from swarmmind.prompt_template import (
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
            "profile": "py-basic",
            "preferred_strategy": "build_app",
            "agent_profiles_json": "[]",
        },
    )

    assert "目标：实现导出功能" in rendered
    assert "可用 Agent Profiles JSON：[]" in rendered


def test_render_prompt_fails_fast_when_variable_missing() -> None:
    with pytest.raises(UndefinedError):
        render_prompt(EXECUTION_FALLBACK_CONTENT_PROMPT, {"subtask_name": "demo"})