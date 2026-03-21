# SwarmMind Prompt Templates

统一存放所有提示词模板（平铺结构，不按功能再建子目录）。

## 规则

1. 所有模板文件都放在 `swarmmind/prompt_template/` 根目录。
2. 代码中不得内联业务 prompt，统一通过模板加载。
3. 使用 `{{placeholder}}` 作为变量占位符。

## 当前模板

- `planner_system_v1.txt`
- `planner_task_decomposition_v1.md`
- `execution_system_v1.txt`
- `execution_subtask_markdown_v1.md`
- `execution_fallback_content_v1.md`
- `task_decomposer_llm_v1.md`
- `review_subtask_verification_v1.md`
