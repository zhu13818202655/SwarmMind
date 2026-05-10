# SwarmMind Task Board

## Done
- 任务主链路已打通：提交任务后可完成 `planning -> coordinating -> executing -> terminal`，并能自动分配/执行子任务（见 `tests/test_v2_execution_flow.py`）。
- Planner 已支持 `LLM 产出优先 + 规则兜底` 双路径；规则兜底可生成 `analyze/prepare/verify/review` 子任务链（见 `tests/test_planner_llm_fallback.py`）。
- Coordinator 已支持按角色与执行配置做运行时决策：`host_tools/sandbox/llm_only`、fallback chain、tool groups 与 skill profiles 合并（见 `tests/test_runtime_resolution.py`）。
- 执行器已具备子任务失败与复核回退链路：支持 review rework repair chain 与 failure repair chain（见 `tests/test_v2_execution_flow.py`）。
- Tool Registry 已实现工具分组、主组、runtime contract、schema 保真与严格白名单选择（见 `tests/test_tool_registry.py`）。
- Skill System 已形成闭环：技能解析/校验/注册、脚本执行、事件发布、产物落库、工具封装别名兼容（见 `tests/test_skill_system.py`, `tests/test_skill_execution_service.py`）。
- Sandbox 基础能力已可用：`local` 与 `opensandbox` provider 切换、OpenSandbox 重试与错误归因、二进制文件读取兼容（见 `tests/test_infra_selection.py`）。
- 可观测与持久化已具备：replay、audit trace、artifact 支持内存/文件后端并可跨重启恢复（见 `tests/test_replay_durability.py`）。
- API 已支持按 run/subtask 查询事件与产物，并支持二进制 artifact 下载（见 `tests/test_replay_durability.py`）。
- 浏览器与检索工具已覆盖核心行为：搜索结果解析、reader 失败回退、动态页面场景下 Playwright 工具路由（见 `tests/test_web_tools.py`, `tests/test_browser_runtime_tools.py`）。

## Doing
- 执行标签策略在重构中：`ExecutionRunner._resolve_execution_label` 仍保留“默认 build_app”兼容逻辑，代码注释提示后续要替换为更通用 agent 标识。
- 执行提示词上下文仍在收敛：`ExecutionRunner._compose_subtask_prompt` 标注了“组装了很多不必要元数据”，说明 prompt payload 正在瘦身阶段。
- 工具授权校验逻辑在验证期：`ExecutionRunner._ensure_tool_allowed` 旁有“确认逻辑正确吗”注释，策略虽已接入但还在确认边界。
- Planner 记忆上下文注入策略仍在迭代：`Planner._compose_planning_prompt` 对 memory 组织方式仍有待确定注释。
- 多租户/多任务隔离边界在持续完善：容器事件订阅处保留“怎么区分不同 task/用户”的待确认注释。

## Todo
- 明确并实现 run/task 事件读取边界与幂等约束：`TaskOrchestrator.handle_task_created` 仍有“task 和 run 区分”待完成项。
- 收敛执行标签与默认 agent 语义，去除历史兼容分支（`build_app` 默认标签）。
- 继续精简执行 prompt 上下文字段，减少无效元数据对模型决策的干扰，并补充回归测试。
- 将工具/技能白名单与运行时策略形成更严格的端到端策略测试矩阵（当前已有基础校验，但边界条件尚未全覆盖）。
- 补齐多租户并发场景下的隔离验证（事件、缓存、回放、artifact 命名空间）。
- 梳理并清理核心链路中的 TODO 注释，尤其是 orchestration 与 execution runner 中的策略类 TODO，沉淀为可执行 issue。
