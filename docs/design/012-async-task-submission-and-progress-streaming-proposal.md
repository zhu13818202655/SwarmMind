# SwarmMind 异步任务提交与实时进度回放方案（讨论稿）

> 目标：支持长耗时任务时“快速返回 task_id/run_id”，并让前端可实时查看进度、断线回溯、最终回放。
>
> 文档性质：评审草案，优先给出“是否有必要改、改到什么程度、先改哪些”。

---

## 1. 现状结论（基于当前代码）

当前系统虽然大量使用 `async/await`，但 **不是独立后台任务模型**：

1. `POST /v1/tasks` 内部调用 `gateway.submit_task()`。
2. `submit_task()` 发布 `task.created` 后，`EventBus.publish()` 直接 `await` 订阅 handler。
3. `task.created -> orchestrator.handle_task_created -> subtask.assigned -> execution_runner.handle_subtask_assigned` 在同一进程链路内推进。

这会导致：

1. 请求返回时间容易被执行链路拖长。
2. 长任务时，前端体验不稳定（容易超时、重试语义不清晰）。
3. 很难天然支持“断线后从游标继续回放进度”。

---

## 2. 是否有必要改

## 2.1 结论

**有必要改，且建议分阶段改。**

原因：

1. 长任务是核心场景，接口必须“快速确认提交成功”。
2. 前端需要实时进度和回放，单纯轮询无法覆盖重连和事件丢失场景。
3. 当前链路将“控制面提交”和“执行面推进”耦合在一次 HTTP 请求里，扩展性与稳定性受限。

## 2.2 不改的代价

如果维持现状，随着任务时长和并发提升，典型问题会放大：

1. 提交接口偶发超时，用户误判“任务没创建”。
2. 前端重复提交导致幂等风险。
3. 难以构建规范的审计与回放时间线。

---

## 3. 目标能力（按优先级）

P0（必须）：

1. `POST /v1/tasks` 在短时间内返回 `task_id/run_id`（建议 HTTP 202）。
2. 后台继续推进任务，不依赖本次请求生命周期。
3. 前端可查询统一进度视图（run/task/subtask）。

P1（强烈建议）：

1. 提供实时事件流（SSE 优先，WebSocket 可后续）。
2. 提供按游标回放事件（断线重连后补齐）。

P2（增强）：

1. 任务取消/重试具备真实执行语义（不仅改状态）。
2. SLA 指标（排队时长、执行时长、失败分类）可观测。

---

## 4. 两种改造路径对比

## 路径 A：最小改造（单进程后台任务）

思路：

1. `POST /v1/tasks` 完成落库后，使用 `asyncio.create_task(...)` 触发编排入口。
2. API 立即返回 `task_id/run_id`。
3. 增加事件查询接口与 SSE。

优点：

1. 改动小，落地快。
2. 可立即改善“提交超时”体验。

缺点：

1. 进程重启会丢在途任务。
2. 多实例部署时任务调度一致性差。

适用：

1. 本地验证、MVP 过渡阶段。

## 路径 B：标准改造（队列 + Worker）

思路：

1. API 仅写入任务并投递队列消息。
2. 独立 Worker 消费 `task.created`，推进 orchestrator/execution。
3. Event log 存储用于 SSE 和回放。

优点：

1. 架构清晰，天然适配长任务与多实例。
2. 更容易做重试、限流、死信、幂等。

缺点：

1. 初期工程量高于路径 A。

适用：

1. 计划进入稳定运行和并发增长阶段。

---

## 5. 推荐方案（分阶段）

建议采用：**A 先落地、B 作为下一阶段演进**。

## Phase 1（1~3 天，可快速验证）

目标：提交立即返回 + 可实时观察。

改动建议：

1. `gateway.submit_task()` 仅负责创建 `session/task/run/replay_root` 与初始事件写入。
2. 新增 `task_executor.submit(run_id, task_id, ...)`，由 `asyncio.create_task` 后台执行。
3. `POST /v1/tasks` 返回 `202 accepted`（或保持 `200` 但语义为 accepted）。
4. 新增 `GET /v1/runs/{run_id}/events?cursor=&limit=`。
5. 新增 `GET /v1/runs/{run_id}/stream`（SSE，按 event_id 连续推送）。

验收标准：

1. 提交接口在目标时间内返回（例如 < 1s，排除数据库慢查询）。
2. 前端断线重连后可从 `cursor` 补齐事件，不丢进度。

## Phase 2（1~2 周，进入可生产化）

目标：独立 Worker 与可恢复执行。

改动建议：

1. 引入队列（优先 Redis Stream，和现有 Redis 方向一致）。
2. Worker 进程消费任务事件并推进状态机。
3. 增加幂等键（`task_id/run_id/event_id`）与重复消费保护。
4. 增加重试与死信策略。

验收标准：

1. API 实例重启不影响在途任务最终执行。
2. Worker 重启可从队列恢复。

---

## 6. API 变更草案

## 6.1 提交任务

`POST /v1/tasks`

响应建议：

```json
{
  "task_id": "...",
  "run_id": "...",
  "session_id": "...",
  "status": "accepted",
  "accepted_at": "..."
}
```

## 6.2 事件查询（回放）

`GET /v1/runs/{run_id}/events?cursor=<event_id>&limit=100`

响应建议：

```json
{
  "run_id": "...",
  "next_cursor": "evt_...",
  "events": [
    {
      "event_id": "evt_1",
      "topic": "subtask.started",
      "occurred_at": "...",
      "payload": {}
    }
  ]
}
```

## 6.3 实时推送（SSE）

`GET /v1/runs/{run_id}/stream`

事件格式建议：

```text
event: run.event
id: evt_123
data: {"topic":"subtask.completed","subtask_id":"..."}
```

---

## 7. 进度模型建议（前端友好）

建议新增统一 Progress DTO（run 级别）：

1. `total_subtasks`
2. `completed_subtasks`
3. `failed_subtasks`
4. `running_subtasks`
5. `percent`（整数 0~100）
6. `current_phase`
7. `updated_at`

说明：

1. `percent` 不需要精确预测耗时，先用“完成子任务占比”。
2. 复杂任务后续可引入 weighted progress。

---

## 8. 数据与存储建议

1. 保留现有 `ReplayRecorder`，但补一个可索引查询的事件存储接口（至少支持 run_id + event_id 顺序查询）。
2. 事件需要稳定排序字段：`sequence` 或单调递增 `event_id`。
3. SSE 与回放都基于同一事件源，避免双写不一致。

---

## 9. 风险与规避

1. 风险：Phase 1 使用 `asyncio.create_task` 在服务重启时丢任务。
   - 规避：明确标注为过渡方案；同时推进 Phase 2。
2. 风险：SSE 连接过多导致 API 压力。
   - 规避：限制连接数、心跳包、超时断开、按租户限流。
3. 风险：事件重复推送。
   - 规避：客户端按 `event_id` 去重，服务端保证幂等。

---

## 10. 建议的讨论决策点

请先确认以下四个问题：

1. 是否接受“先 A 后 B”路线（先体验、后架构完备）？
2. 提交接口是否改为 `202 accepted`（语义更清晰）？
3. 实时通道是否先选 SSE（实现快）？
4. 事件源是否以 Replay 体系为唯一事实来源？

---

## 11. 一句话总结

对于长任务场景，**必须把“提交确认”与“执行推进”解耦**。推荐先做最小异步化 + 事件流回放，快速提升前端体验，再演进到队列 Worker 形态保证可恢复与可扩展。
