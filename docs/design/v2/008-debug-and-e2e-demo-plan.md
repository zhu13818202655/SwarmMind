# SwarmMind Debug 与端到端演示方案

> 目的：给本地手动演示和调试提供一套最小可复现操作路径。该文档不直接改动业务逻辑，只描述如何用现有 `.vscode/launch.json` 和脚本完成一次可观测的端到端运行。

---

## 1. 当前已有的 VS Code Debug 配置

当前仓库已经存在 [.vscode/launch.json](/home/admin2/proj/SwarmMind/.vscode/launch.json)，里面有 3 个可直接使用的入口：

1. `SwarmMind API`
   - 用 `uvicorn swarmmind.api.server:create_app --factory` 启动 API
   - 工作目录是 workspace root
   - 已设置 `PYTHONPATH=${workspaceFolder}`
2. `Submit Task Script`
   - 调试运行 `scripts/submit_task.py`
   - 默认目标地址是 `http://127.0.0.1:8000`
   - 会等待服务可用并轮询任务结果
3. `SwarmMind API + Submit Task`
   - compound 配置
   - 会同时启动 API 和提交脚本

这意味着：

1. 你不需要先自己手写 debug 配置
2. 现有 launch 配置已经足够做第一轮端到端演示

---

## 2. 我建议的 debug 观察点

如果你要自己操作，我建议断点优先打在这几个位置：

1. `swarmmind/gateway/gateway.py`
   - 看任务是如何变成 `Task`、`Run`、`ReplayRoot`
2. `swarmmind/orchestration/planner.py`
   - 看 planner 如何生成 subtasks，以及何时写入 `agent_profile_id`
3. `swarmmind/orchestration/coordinator.py`
   - 看 `AgentProfileStore` 如何解析最终 profile，并写入 `ExecutionProfile`
4. `swarmmind/orchestration/execution_runner.py`
   - 看 strategy 解析、selected tools、policy enforcement、handoff 事件
5. `swarmmind/orchestration/run_state_service.py`
   - 看 run/task 如何最终收敛到成功或失败

如果这次你重点想看新的 profile 和 handoff 主链，那么最值得下断点的是：

1. `Planner._build_subtasks_from_plan()`
2. `Coordinator.assign()`
3. `ExecutionRunner._execute_agent_backed_subtask()`
4. `ExecutionRunner._resolve_handoff_profile()`
5. `ExecutionRunner._publish_handoff_event()`

---

## 3. 我建议的第一轮端到端演示目标

我建议不要一开始就用复杂编码任务。

第一轮演示更适合验证这 4 件事：

1. 任务能否从 API 正常进入 orchestrator 主链
2. planner 是否会给 subtask 配出合理的 `agent_profile_id`
3. `agent_backed` strategy 是否能被正确选中和执行
4. handoff 事件是否按 policy 正常出现

所以演示目标建议分成两组。

### 场景 A：只看 `agent_backed` 基础路径

建议目标：

`整理一份版本发布说明`

建议参数：

- `preferred_strategy=agent_backed`
- 不传 handoff 请求

预期看到：

1. `prepare-implementation` 被解析为 `agent_backed`
2. `ExecutionProfile.agent_profile_id` 落到 `agent-backed-default` 或兼容 profile
3. subtask 正常完成
4. replay 中能看到 `strategy.started` / `strategy.completed`

### 场景 B：看受控 handoff 路径

建议目标：

`整理竞品调研摘要`

建议参数：

- `preferred_strategy=agent_backed`
- `agent_profile_id=delegating-coder` 或你自己准备的允许 handoff 的 profile
- `constraints.handoff_requests.prepare-implementation=researcher-default`

预期看到：

1. 进入 `agent_backed` strategy
2. runtime 检查 `HandoffPolicy`
3. 允许时发出：
   - `agent.handoff.started`
   - `agent.handoff.completed`
4. 不允许时发出：
   - `agent.handoff.denied`
   - `policy.denied`

---

## 4. 如果你自己操作，我建议的执行顺序

### Step 1：先只启动 API

用 launch 配置：

1. 运行 `SwarmMind API`

目的：

1. 单独确认服务能起来
2. 先把入口链路打通

### Step 2：单独运行提交脚本

用 launch 配置：

1. 运行 `Submit Task Script`

目的：

1. 把问题切成两段调试
2. 避免 compound 一上来同时停多个断点时不容易看清

### Step 3：确认基础链路后，再用 compound

用 launch 配置：

1. 运行 `SwarmMind API + Submit Task`

目的：

1. 复现“一键启动 + 提交任务”的操作体验
2. 验证完整链路是否稳定

---

## 5. 我建议你如何修改 launch 参数做 handoff 演示

当前 `Submit Task Script` 的 args 默认是：

1. `--base-url http://127.0.0.1:8000`
2. `--wait-for-service 20`
3. `--goal 写一个python版本贪吃蛇`
4. `--poll`

如果你要演示新的 profile / handoff 能力，我建议不要直接覆盖老配置，而是新增 1 到 2 个新的 debug configuration，例如：

1. `Submit Agent Backed Task`
2. `Submit Agent Backed Handoff Task`

我准备的改法思路是：

1. 保留现有 `Submit Task Script` 不动，避免影响你原有调试入口
2. 新增一个面向 `agent_backed` 的提交配置
3. 如果 `scripts/submit_task.py` 还不支持直接传 `agent_profile_id` 或复杂 `constraints`，则优先扩脚本参数，而不是在 launch.json 里塞过多魔法值

也就是说，我不建议先改 launch.json 去“硬凑”复杂 JSON；更稳的做法是：

1. 先确认提交脚本支持这些参数
2. 再给 launch.json 增加可读性好的专用 debug 入口

---

## 6. 我准备怎么做端到端演示

如果下一步由我来继续落地演示，我准备按下面顺序做：

1. 检查 `scripts/submit_task.py` 当前是否已支持：
   - `agent_profile_id`
   - `preferred_strategy=agent_backed`
   - 结构化 `constraints`
2. 如果脚本参数不够，就先补脚本能力
3. 再补 `.vscode/launch.json`：
   - 保留现有配置
   - 新增两个专用 debug 配置
4. 选择一个最短路径任务做演示
5. 明确需要观察的断点、事件和最终结果
6. 最后再跑一次真实任务，确认你可以本地重复操作

---

## 7. 我建议这次不要直接做的事

这次先不要一上来做下面这些事情：

1. 不要一边改 launch.json 一边改业务主链
2. 不要第一轮就演示“复杂编码 + verify + review + handoff”全部叠在一起
3. 不要先做多层 delegation tree 的真实演示

原因很简单：

1. 你现在先要验证的是新能力有没有真正接进主链
2. 不是一次性证明所有未来能力都已成熟

---

## 8. 当前结论

当前最适合你的下一步手动操作方式是：

1. 先直接使用已有 [.vscode/launch.json](/home/admin2/proj/SwarmMind/.vscode/launch.json) 里的 `SwarmMind API` 和 `Submit Task Script`
2. 先确认基础任务提交链路没问题
3. 然后再决定是否需要我补 `submit_task.py` 参数和新的 handoff 专用 debug 配置

如果你确认这份方案没问题，下一步我可以继续做两件事：

1. 检查并扩展 `scripts/submit_task.py`，让它能直接提交 `agent_profile_id` 和 `handoff_requests`
2. 基于这个脚本补一版更适合手动调试的 [.vscode/launch.json](/home/admin2/proj/SwarmMind/.vscode/launch.json)