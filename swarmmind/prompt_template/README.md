# SwarmMind Prompt Templates

统一存放所有提示词模板的 Python 模块定义，按类型拆分，运行时通过 Jinja2 渲染。

## 规则

1. 所有模板定义都位于 `swarmmind/prompt_template/*.py`，并按职责拆分。
2. 调用方直接 import `PromptTemplate` 常量，不再通过文件名字符串加载。
3. 使用 Jinja2 语法渲染模板，并通过 `StrictUndefined` 对缺失变量 fail fast。

## 模块划分

- `base.py`: `PromptTemplate`
- `planner.py`: planner 相关模板
- `task_decomposer.py`: task decomposer 相关模板
- `execution.py`: execution runner 相关模板
- `review.py`: review 相关模板
- `registry.py`: 模板注册表
