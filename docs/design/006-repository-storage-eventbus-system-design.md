# Repository / Storage / Event Bus 架构设计

> 这份文档承接前面的 `003 Gateway`、`004 Identity`、`005 数据模型`，重点回答三个问题：
>
> 1. 这些核心对象应该怎么持久化。
> 2. 哪些数据应该进数据库，哪些应该进对象存储，哪些应该走向量库。
> 3. 平台里的异步事件流应该怎么设计，才能支撑多智能体执行、记忆沉淀、回放和审计。

---

## 1. 结论先说

SwarmMind 后续不应该把数据访问直接写在 Gateway、Orchestrator、Memory、Sandbox 这些业务模块里，而应该明确三层：

1. **Repository Layer**
   负责对象级读写抽象。

2. **Storage Layer**
   负责底层数据落点和多存储协同。

3. **Event Bus Layer**
   负责异步事件传播和跨模块解耦。

一句话说：

**Repository 负责“怎么读写对象”，Storage 负责“数据放哪里”，Event Bus 负责“状态怎么传播”。**

---

## 2. 为什么这一层必须独立设计

如果不单独设计，最常见的后果是：

1. Gateway 直接写数据库
2. Orchestrator 直接写 transcript 文件
3. Memory 直接写向量库和 JSON 文件
4. Sandbox 直接把日志塞进 task result

这样会导致：

- 数据写入路径混乱
- 无法替换底层存储
- 无法做统一审计
- 无法做事件驱动扩展
- 读模型和写模型纠缠在一起

所以推荐原则是：

- **业务模块只依赖 repository 接口**
- **底层存储通过 storage adapters 组合**
- **跨模块状态传播通过 event bus 完成**

---

## 3. 总体架构

```text
                +----------------------------------+
                | Gateway / Orchestrator / Memory  |
                | Sandbox / Runtime / Query APIs   |
                +----------------+-----------------+
                                 |
                                 v
                +----------------------------------+
                |         Repository Layer         |
                | TaskRepo / SessionRepo / RunRepo |
                | ArtifactRepo / ReplayRepo        |
                +----------------+-----------------+
                                 |
                +----------------+------------------+
                |                                   |
                v                                   v
      +------------------------+        +------------------------+
      |      Storage Layer     |        |     Event Bus Layer    |
      | Postgres / Redis / S3  |        | Queue / Stream / Topic |
      | Qdrant / Transcript    |        | task.* / run.* / ...   |
      +------------------------+        +------------------------+
```

核心思想：

- 业务模块只关心对象和事件。
- Repository 负责对象访问协议。
- Storage 负责具体技术选型。
- Event Bus 负责异步解耦。

---

## 4. Repository 层设计

### 4.1 Repository 的职责

Repository 不应该是“万能 DAO”，而应该围绕核心对象建模。

它的职责是：

- 提供对象级读写接口
- 屏蔽底层存储细节
- 保持业务对象的一致性边界
- 提供最小必要查询

Repository 不应该承载：

- 复杂业务流程
- 跨模块编排逻辑
- event bus 消费逻辑

### 4.2 推荐 Repository 清单

建议围绕 `005` 的核心对象，至少建立这些 repository：

1. `TenantRepository`
2. `UserRepository`
3. `SessionRepository`
4. `TaskRepository`
5. `RunRepository`
6. `ArtifactRepository`
7. `ReplayRepository`
8. `MemoryRepository`
9. `TranscriptRepository`

### 4.3 Repository 示例职责

#### TaskRepository

负责：

- 创建 task
- 更新 task 状态
- 绑定 `current_run_id`
- 查询 task 摘要

#### RunRepository

负责：

- 创建 run
- 更新 run phase/status
- 写入错误摘要和成本摘要
- 查询最新 run

#### ArtifactRepository

负责：

- 创建 artifact 元数据
- 按 `task_id / run_id / subtask_id` 查询 artifact
- 返回 storage_ref

#### ReplayRepository

负责：

- 创建 replay root
- 更新 replay 引用
- 查询某个 run 的 replay 入口

### 4.4 Repository 设计原则

建议遵守：

1. 一个 repository 对应一个核心聚合或聚合根。
2. repository 返回的是领域对象或 DTO，不是裸 SQL 结果。
3. repository 方法名尽量表达业务语义，而不是数据库动作。

例如：

- `create_task(...)`
- `mark_run_succeeded(...)`
- `attach_artifact_to_run(...)`

比：

- `insert_task_row(...)`
- `update_run_table(...)`

更适合长期维护。

---

## 5. Storage 层设计

### 5.1 不同数据要分开存

SwarmMind 不适合把所有数据都塞进同一个数据库。

推荐分层如下：

1. **PostgreSQL**
   结构化主数据和元数据。

2. **Redis**
   热状态、session cache、分布式锁、短期队列。

3. **S3 / MinIO**
   transcript、日志、patch、测试报告、截图等大对象。

4. **Qdrant / Chroma**
   长期语义记忆和检索索引。

5. **可选 Search / Analytics Store**
   用于全文搜索、离线统计、BI 分析。

### 5.2 PostgreSQL 适合存什么

建议放：

- tenant / user / api keys
- session / task / run / artifact / replay 元数据
- policy / quota / model config
- audit 索引记录
- memory 元数据，不含大文本和 embedding 向量本体

### 5.3 Redis 适合存什么

建议放：

- session 活跃上下文缓存
- working memory cache
- admission 限流计数
- 分布式锁
- 短期任务状态缓存
- stream / queue 实现的临时事件流

### 5.4 S3 / MinIO 适合存什么

建议放：

- transcript JSON / JSONL
- sandbox stdout/stderr logs
- patch 文件
- 测试报告
- 报告、邮件、PPT 成品
- 截图与导出物

### 5.5 Qdrant / Chroma 适合存什么

建议放：

- memory embeddings
- long-term semantic recall data
- org knowledge chunks
- retrieval index

### 5.6 为什么不能只用 Postgres

只用 Postgres 会遇到这些问题：

- transcript 和日志会变得很重
- 大对象存储成本高且查询差
- embedding 和向量检索能力不够自然
- Redis 级别的热状态访问不够快

所以更合理的方案是：

- Postgres 管元数据
- Object Store 管大对象
- Redis 管热状态
- Vector Store 管语义检索

---

## 6. Event Bus 设计

### 6.1 为什么需要 Event Bus

因为这个平台里有大量跨模块异步动作：

- task 创建后要触发 orchestrator
- run 状态更新后要刷新 query model
- subtask 完成后要触发 verification
- task 完成后要触发 memory capture
- transcript 写入后要更新 replay

如果这些都做成同步直接调用，会导致：

- 耦合高
- 扩展困难
- 重试困难
- 失败传播不可控

所以 Event Bus 的作用是：

**把状态变化从直接调用，转成可订阅、可重试、可审计的事件流。**

### 6.2 推荐事件分类

建议按领域分 topic：

#### Gateway 事件

- `gateway.request.received`
- `gateway.request.rejected`
- `task.created`

#### Task / Run 事件

- `task.planning.started`
- `task.planning.completed`
- `run.created`
- `run.phase.changed`
- `run.succeeded`
- `run.failed`

#### Subtask 事件

- `subtask.ready`
- `subtask.assigned`
- `subtask.started`
- `subtask.completed`
- `subtask.failed`

#### Artifact / Replay 事件

- `artifact.created`
- `artifact.indexed`
- `replay.updated`

#### Memory 事件

- `memory.capture.requested`
- `memory.capture.completed`
- `memory.recall.logged`

#### Sandbox 事件

- `sandbox.created`
- `sandbox.command.executed`
- `sandbox.destroyed`

### 6.3 统一事件 envelope

推荐所有事件都遵守统一 envelope：

```json
{
  "event_id": "evt_001",
  "event_type": "task.created",
  "occurred_at": "2026-03-13T12:00:00Z",
  "tenant_id": "tenant_001",
  "task_id": "task_001",
  "run_id": null,
  "session_id": "sess_001",
  "producer": "gateway",
  "payload": {
    "goal": "实现一个导出 Excel 功能并补测试"
  }
}
```

统一 envelope 的好处：

- 审计一致
- tracing 一致
- consumer 实现简单

---

## 7. Event Bus 技术选型建议

### 7.1 MVP 建议

MVP 阶段建议用：

- **Redis Streams** 或简单队列

原因：

- 成本低
- 好部署
- 对 Python 友好
- 足够支撑初期异步任务和状态传播

### 7.2 生产建议

生产阶段可考虑：

- **NATS JetStream**
- **Kafka**

如何选：

- 更强调轻量和服务间解耦，可优先 NATS JetStream
- 更强调高吞吐、长期事件积压和分析链路，可优先 Kafka

### 7.3 选型原则

不要过早把 Event Bus 做重。

MVP 先满足：

- 可靠投递
- 可重试
- 消费可观测
- 支撑状态推进

就够了。

---

## 8. 写模型与读模型分离

这一层设计里，建议尽早考虑 CQRS 思路，但不必过度工程化。

### 8.1 写模型

写模型关注：

- task/session/run/artifact/replay 的一致性更新
- 状态变更
- 事件发布

### 8.2 读模型

读模型关注：

- API 查询速度
- UI 面板展示
- 当前 phase / 当前 subtask / 最新 error
- artifact 列表和 replay 概览

这意味着：

- Repository 更偏写模型
- Query service 可以单独维护读模型视图

MVP 可以先不彻底拆开，但设计上要留这个口子。

---

## 9. Repository 与 Event Bus 的关系

推荐原则：

1. 先写 repository
2. 再发 domain event

也就是：

```text
Update Aggregate -> Persist State -> Publish Event
```

原因：

- 先保证状态落地
- 再传播状态变化

如果后续需要更强一致性，可以再演进到 outbox pattern。

### 9.1 后续建议：Outbox Pattern

生产阶段建议考虑：

- repository 写主表
- 同事务写 outbox 表
- 后台 worker 把 outbox 推送到 event bus

这样可以降低“数据库成功但事件没发出”这类问题。

---

## 10. 推荐的 Repository / Storage 映射表

| 对象 | Repository | 主存储 | 辅助存储 |
|------|------------|--------|----------|
| Tenant | `TenantRepository` | Postgres | Redis cache |
| User | `UserRepository` | Postgres | Redis cache |
| Session | `SessionRepository` | Postgres | Redis |
| Task | `TaskRepository` | Postgres | Redis read cache |
| Run | `RunRepository` | Postgres | Redis read cache |
| Artifact | `ArtifactRepository` | Postgres metadata | S3 / MinIO body |
| Replay | `ReplayRepository` | Postgres metadata | S3 / MinIO refs |
| Transcript | `TranscriptRepository` | S3 / MinIO | Postgres index |
| Memory | `MemoryRepository` | Postgres metadata | Qdrant / Redis |

---

## 11. 推荐最小落地方案

如果现在还处于设计阶段，MVP 建议先定义下面这些抽象，而不是急着定具体 ORM 或 SDK：

### Repository MVP

1. `TaskRepository`
2. `SessionRepository`
3. `RunRepository`
4. `ArtifactRepository`
5. `ReplayRepository`

### Storage MVP

1. Postgres 负责元数据
2. MinIO / 本地对象目录负责大对象
3. Redis 负责 cache 和 stream

### Event Bus MVP

1. 统一事件 envelope
2. `task.created`
3. `run.created`
4. `subtask.completed`
5. `memory.capture.requested`
6. `artifact.created`

这套最小闭环就足够支撑后续代码设计。

---

## 12. 与前面文档的关系

### 对 `003 Gateway`

- Gateway 通过 repository 写 task/session/run
- Gateway 通过 event bus 发布 `task.created`

### 对 `004 Identity`

- repository 中所有关键对象必须带 `tenant_id`
- event envelope 必须带 identity 相关字段

### 对 `005 对象模型`

- repository 直接围绕 `Task / Session / Run / Artifact / Replay` 建模
- storage 按对象特征选择落点

---

## 13. 最终建议

SwarmMind 后续代码设计时，建议把下面三条作为硬约束：

1. 业务模块不直接依赖底层数据库和对象存储。
2. 核心状态变化通过事件传播，而不是同步直连到处调用。
3. 所有持久化对象都围绕统一的数据模型和身份上下文展开。

一句话总结：

**Repository 让对象访问可控，Storage 让数据落点合理，Event Bus 让系统异步解耦。**
