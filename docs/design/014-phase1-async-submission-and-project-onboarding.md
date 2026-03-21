# SwarmMind Phase 1 异步提交与项目快速入门指南

> 目的：
> 1) 说明本次“异步提交 + 进度流/回放（Phase 1）”已实现内容；
> 2) 帮助 Review 与二次开发快速上手；
> 3) 标注抽象层、实现层、LLM 与多 Agent 关键文件。

---

## 1. 本次已实现（Phase 1）

## 1.1 提交立即返回（Accepted-Immediate）

改动目标：避免 `POST /v1/tasks` 被编排执行链阻塞。

核心改动：

1. `task.created` 事件从同步派发改为后台派发：
   - 文件：`swarmmind/gateway/gateway.py`
   - `Gateway.submit_task()` 中：
     - `run.created` 仍同步发布
     - `task.created` 使用后台异步派发

2. 新增后台派发能力：
   - 文件：`swarmmind/gateway/dispatcher.py`
   - `GatewayDispatcher.dispatch_background(event)`
   - 通过 `asyncio.create_task(...)` 发出事件，并记录任务集合与异常日志

结果：

- 提交接口创建 `session/task/run/replay_root` 后即可返回
- 编排与执行继续在后台推进

---

## 1.2 进度回放接口（Replay API）

新增接口：

- `GET /v1/runs/{run_id}/events?cursor=0&limit=100`

文件：`swarmmind/api/server.py`

返回：

- `run_id`
- `next_cursor`
- `events[]`（包含 `cursor/event_type/timestamp/payload`）

说明：

- 游标为 replay entry 的顺序索引
- 可用于断线后增量补拉

---

## 1.3 实时进度流（SSE）

新增接口：

- `GET /v1/runs/{run_id}/stream?cursor=0&poll_interval=0.5`

文件：`swarmmind/api/server.py`

行为：

1. 轮询 replay root 增量事件并以 SSE 推送：`event: run.event`
2. 任务终态（`succeeded/failed/cancelled`）发送：`event: run.terminal`
3. 提供 keep-alive 注释帧，避免连接静默超时

适用场景：

- 前端实时进度
- CLI `curl` 流式观察

---

## 1.4 回归测试适配

由于提交改为“立即返回 + 后台执行”，原先同步断言需调整为“等待 run 终态”。

已改测试：

1. `tests/test_v2_execution_flow.py`
2. `tests/test_infra_live_integration.py`

改动点：

- 增加 `_wait_for_terminal_run(...)`
- 先等待 `RunStatus` 进入终态，再断言 artifact/replay/subtask 状态

---

## 2. 快速 Review 路径（建议 30~60 分钟）

按以下顺序读：

1. `swarmmind/gateway/gateway.py`
   - 任务提交、对象创建、事件发布入口
2. `swarmmind/gateway/dispatcher.py`
   - 同步派发与后台派发实现
3. `swarmmind/orchestration/task_orchestrator.py`
   - `task.created` 后的 planning/coordinating
4. `swarmmind/orchestration/execution_runner.py`
   - `subtask.assigned` 后执行、artifact、状态回写
5. `swarmmind/orchestration/run_state_service.py`
   - run/task 终态收敛
6. `swarmmind/api/server.py`
   - `/v1/tasks`、`/v1/runs/{run_id}/events`、`/stream`
7. `swarmmind/query/service.py`
   - run/task 聚合查询

---

## 3. 项目目录快速导览（开发视角）

## 3.1 顶层目录

1. `swarmmind/`
   - 主代码目录
2. `tests/`
   - 单测/集成测试
3. `docs/`
   - 设计、架构与实施文档
4. `configs/`
   - 默认配置与 profile 配置
5. `scripts/`
   - 提交/调试脚本
6. `.github/errors/`
   - 线上或开发问题记录与复盘

## 3.2 业务主链目录（最重要）

1. `swarmmind/api/`
   - HTTP 入口
2. `swarmmind/app/`
   - 容器装配（依赖注入）
3. `swarmmind/gateway/`
   - 提交入口、准入、归一化、事件发射
4. `swarmmind/orchestration/`
   - planner/coordinator/scheduler/execution runner
5. `swarmmind/sandbox/`
   - sandbox provider、manager、artifact/replay 辅助
6. `swarmmind/query/`
   - 聚合读模型

## 3.3 基础设施抽象目录

1. `swarmmind/repositories/`
   - repository 协议与 in-memory/postgres 实现
2. `swarmmind/events/`
   - event bus 协议与实现（in-memory/redis buffered）
3. `swarmmind/cache/`
   - cache 抽象与实现（in-memory/redis）
4. `swarmmind/locks/`
   - lock 抽象与实现（in-memory/redis）
5. `swarmmind/memory/`
   - 长短期记忆抽象与实现
6. `swarmmind/config/`
   - 统一配置模型与加载

---

## 4. 抽象层 vs 具体实现（怎么改最安全）

## 4.1 抽象层（优先依赖）

1. repository 协议：`TaskRepository/RunRepository/...`
2. 事件协议：`EventBus`
3. sandbox 协议：`SandboxProvider`
4. memory 抽象：`LongTermMemoryBase`
5. cache/lock 抽象：`CacheStore/LockManager`

原则：

- 上层服务（gateway/orchestration/query）尽量只依赖抽象，不直接依赖具体驱动。

## 4.2 具体实现（按环境切换）

1. 内存实现：`repositories/in_memory`、`InMemoryEventBus`、`LocalSandboxAdapter`
2. 持久化实现：`repositories/postgres.py`、`RedisBufferedEventBus`
3. 外部执行：`OpenSandboxAdapter`

切换入口：

- `swarmmind/app/container.py`
- `_build_*` 系列函数决定装配哪套实现

---

## 5. 大模型利用（LLM）怎么做的

## 5.1 Planner 的 LLM 路径

文件：`swarmmind/orchestration/planner.py`

流程：

1. 拼装 planning prompt（模板来自 `swarmmind/prompt_template/`）
2. 调用 AgentScope/OpenAI 模型
3. 解析 JSON 结构化 subtasks
4. 失败时回退规则计划

关键点：

- LLM-first + rules-fallback
- `metadata.plan_source` 标记来源（`llm` / `rules`）

## 5.2 Execution 的 LLM 路径

文件：`swarmmind/orchestration/execution_runner.py`

流程：

1. 尝试模型生成 subtask markdown 内容
2. 失败回退模板内容
3. 将内容写入 sandbox 输出并产出 artifact

提示词模板目录：

- `swarmmind/prompt_template/`

---

## 6. 多 Agent / 推理执行链重点文件

当前是“多角色编排骨架 + 局部 LLM 执行”，重点看：

1. `swarmmind/agents/factory.py`
   - AgentScope 模型与 agent 构造
2. `swarmmind/orchestration/planner.py`
   - 任务拆解（LLM + fallback）
3. `swarmmind/orchestration/task_orchestrator.py`
   - DAG 推进与事件发射
4. `swarmmind/orchestration/execution_runner.py`
   - 子任务执行与证据回流
5. `swarmmind/orchestration/run_state_service.py`
   - 状态聚合终态

如果你要改“推理链”，通常从 `planner.py` 和 `execution_runner.py` 入手；
如果你要改“编排策略”，从 `task_orchestrator.py`、`scheduler.py`、`coordinator.py` 入手。

---

## 7. 二次开发建议（你接下来改代码时）

1. 先改抽象接口，再改容器装配，再改具体实现
2. 每次改动都至少跑：
   - `tests/test_v2_execution_flow.py`
   - `tests/test_planner_llm_fallback.py`
3. 涉及事件语义改动时，同时检查：
   - `/v1/runs/{run_id}/events`
   - `/v1/runs/{run_id}/stream`
4. 新问题统一记录到 `.github/errors/`

---

## 8. 本文档对应的 Phase 1 结论

本次已完成：

1. 提交立即返回
2. 后台推进执行
3. 回放事件分页查询
4. SSE 实时流
5. 测试适配异步终态等待

下一阶段（可选）建议：

1. 引入真正队列 worker（Redis Streams 消费者）
2. `POST /v1/tasks` 语义升级为 `202 Accepted`
3. 增加 `cursor` 持久化与客户端断线恢复示例
