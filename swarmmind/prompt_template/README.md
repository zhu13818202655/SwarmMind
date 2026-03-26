# SwarmMind Prompt Templates

统一存放所有提示词模板的 Python 模块定义，运行时通过 Jinja2 渲染。

## 规则

1. 所有模板定义都位于 `swarmmind/prompt_template/*.py`。
2. 调用方直接 import `PromptTemplate` 常量，不再通过文件名字符串加载。
3. 使用 Jinja2 语法渲染模板，并通过 `StrictUndefined` 对缺失变量 fail fast。

## 当前模板

- `PLANNER_SYSTEM_PROMPT`
- `PLANNER_TASK_DECOMPOSITION_PROMPT`
- `TASK_DECOMPOSER_LLM_PROMPT`
- `EXECUTION_SYSTEM_PROMPT`
- `EXECUTION_SUBTASK_MARKDOWN_PROMPT`
- `EXECUTION_FALLBACK_CONTENT_PROMPT`
- `REVIEW_SUBTASK_VERIFICATION_PROMPT`
