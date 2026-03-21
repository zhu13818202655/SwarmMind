---
type: todo
date: 2026-03-20
topic: event-bus
status: open
owner: copilot
---

# Event Bus / RedisBufferedEventBus TODO

> 这份文档用于承接 2026-03-20 代码审查期间识别出的事件总线后续工作项，重点覆盖平台 `EventBus` 边界澄清和 `RedisBufferedEventBus` 的演进路径。

---

## 1. 背景

当前代码已经明确区分了两类能力：

1. AgentScope `MsgHub`：用于局部多 Agent 对话广播。
2. SwarmMind `EventBus`：用于 task/run/subtask/sandbox 等领域事件传播。

当前 `RedisBufferedEventBus` 已经具备两类能力：

1. 当前进程内本地 subscriber 分发。
2. Redis Stream 持久写入和 Redis Pub/Sub 广播。

但它还不是完整的异步消费基础设施。当前缺失的核心能力包括：

1. consumer group。
2. ack / retry。
3. dead letter queue。
4. 消费者偏移与重放策略。
5. 生产级监控与错误分类。

---

## 2. TODO 列表

### 2.1 边界与术语

1. 明确文档和代码中的术语边界：把 AgentScope `MsgHub` 与平台 `EventBus` 的职责彻底分开，避免后续在 orchestrator 或 gateway 层误用对话广播语义。
2. 在架构文档中统一使用“领域事件”“会话广播”“本地分发”“异步消费”四组术语，避免在 review 和实现中混用 `message`、`event`、`broadcast`、`queue`。

### 2.2 事件模型

1. 为领域事件 envelope 增补 `producer`、`schema_version`、`correlation_id`、`causation_id` 字段设计。
2. 评估是否需要 `trace_id` / `span_id` 直接进入事件 envelope，还是只依赖日志与 tracing 层透传。
3. 统一 topic 命名规则，避免后续出现 `task.created`、`task_create`、`task.create` 并存。

### 2.3 同步与异步边界

1. 梳理当前哪些事件应继续走同步本地订阅，哪些事件应迁移到真正的异步 worker 消费。
2. 为 `task.created`、`task.planning.completed`、`subtask.assigned`、`run.updated` 定义期望的投递语义：同步、至少一次、可回放、是否需要幂等消费。
3. 明确 query projection、replay、memory capture、sandbox telemetry 哪些适合从 stream 异步消费。

### 2.4 测试与验证

1. 补事件总线的集成测试，至少覆盖 in-memory 与 Redis 两种实现的 publish / subscribe、stream 写入和 topic 分发行为。
2. 补 Redis 异常场景测试，包括连接失败、stream 写入失败、Pub/Sub 发布失败、本地 handler 抛错。
3. 为后续 consumer group 方案准备幂等消费和重试测试基线。

---

## 3. RedisBufferedEventBus 演进设计

### 3.1 当前定位

`RedisBufferedEventBus` 当前更准确的定位是：

**本地事件总线 + Redis 缓冲 / 外部观察出口。**

它解决的问题是：

1. 在不改变当前同步控制流的前提下，把事件写入 Redis。
2. 给未来的审计、进度流、回放、外部消费者预留统一出口。
3. 保持当前进程内 `subscribe()` 语义不变，减少第一阶段接入成本。

它暂时不解决的问题是：

1. 后台 worker 消费调度。
2. 至少一次投递保证。
3. 消费失败重试和死信。
4. 跨进程订阅处理的一致性。

### 3.2 目标架构

建议把后续目标拆成四层，而不是一步到位替换当前实现：

1. `EventBus` 接口层
   继续给 gateway、orchestrator、query、memory、sandbox 暴露统一 `publish/subscribe` 契约。
2. 本地分发层
   负责低延迟的进程内同步处理，适合状态推进等主链路动作。
3. Stream 持久层
   负责把标准化领域事件写入 Redis Stream，供外部消费者、审计和回放使用。
4. Worker 消费层
   基于 consumer group 承担 projection、memory capture、artifact indexing、notification 等异步任务。

### 3.3 分阶段演进

#### Phase A: 补强当前 buffered 模式

目标：保持现有 API 不变，先把当前实现补到可观测、可诊断。

建议事项：

1. 为 publish 链路增加结构化日志，记录 `event_id`、`topic`、`task_id`、`run_id`、`subtask_id`。
2. 明确 stream 写入失败和 local dispatch 失败的异常策略，避免 silent failure。
3. 为 stream name、channel prefix、payload schema 写清契约。
4. 增加关闭连接和资源释放能力，避免长期运行下 Redis client 悬挂。

验收标准：

1. 本地分发与 Redis 写入失败都能被明确观测。
2. 事件格式可通过集成测试稳定校验。

#### Phase B: 引入独立 stream consumer

目标：把部分非关键路径消费从同步 handler 中剥离出去。

建议事项：

1. 建立单独 worker，从 Redis Stream 读取事件。
2. 第一批迁移的消费者优先选择 query projection、artifact indexing、memory capture。
3. 保持 orchestrator 主推进链仍在本地分发层，避免一次性打断主流程。

验收标准：

1. 至少一个非关键 consumer 从 Redis Stream 独立消费成功。
2. API 提交链路不再依赖该 consumer 的执行时长。

#### Phase C: 引入 consumer group + ack / retry

目标：把 stream 从“可读日志”升级成“可靠异步通道”。

建议事项：

1. 为每类 worker 建立独立 consumer group。
2. 设计消息 ack 时机，避免先 ack 后处理失败。
3. 为重复投递定义幂等策略，至少按 `event_id` 去重。
4. 加入重试计数和回退策略，避免 poison message 无限重放。

验收标准：

1. worker 重启后可以继续消费未 ack 消息。
2. 消费异常可触发有限重试且不会无界阻塞。

#### Phase D: 加入 dead letter 与回放能力

目标：让事件流真正支持生产排障与补偿。

建议事项：

1. 为重试超限消息建立 dead letter stream。
2. 提供按 `task_id` / `run_id` / `event_id` 的事件回放工具。
3. 为 schema version 引入兼容策略，避免事件模型演进时破坏旧消费者。

验收标准：

1. 失败消息可被追踪、隔离和人工重放。
2. 回放不会污染线上主链路状态。

### 3.4 事件分类建议

为了控制复杂度，建议把事件按消费语义分层：

1. 主链路同步事件
   例如 `task.created`、`task.planning.completed`、`subtask.assigned`。
2. 辅助异步事件
   例如 `artifact.created`、`replay.updated`、`memory.capture.requested`。
3. 遥测 / 观测事件
   例如 sandbox command execution telemetry、progress streaming、审计事件。

原则是：

1. 主链路状态推进优先低延迟和确定性。
2. 辅助链路优先异步解耦和可回放。
3. 遥测链路优先可观测和可聚合。

### 3.5 设计约束

后续演进时建议坚持下面几条硬约束：

1. 不让业务模块直接操作 Redis Stream 细节，仍然通过 `EventBus` 或独立 consumer adapter 间接访问。
2. 不把 Agent 对话消息混进领域事件总线。
3. 不把所有事件都强行异步化，主链路推进需要保留清晰边界。
4. 任何至少一次投递设计都必须配套幂等消费。

---

## 4. 建议执行顺序

1. 先补 `RedisBufferedEventBus` 当前实现的文档契约、日志和测试。
2. 再挑一个低风险 consumer 做 Redis Stream 独立消费试点。
3. 稳定后再引入 consumer group、ack/retry、dead letter。

一句话总结：

**`RedisBufferedEventBus` 不该被直接视为最终态消息系统，而应作为 SwarmMind 从“同步本地事件总线”平滑演进到“可回放、可重试、可观测异步事件基础设施”的过渡层。**