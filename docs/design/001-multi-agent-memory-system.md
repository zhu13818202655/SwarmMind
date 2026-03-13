# 多智能体记忆系统设计

> 面向客户需求的 SwarmMind 多智能体记忆方案。
>
> 目标：让 Planner、Coordinator、Coder、Tester、Reviewer 等多个 Agent 在长任务和跨会话场景中，既能共享必要上下文，又不会互相污染记忆；同时保留可追踪、可审计、可回放的完整执行记录。

---

## 1. 设计目标

1. 支持多层记忆：会话级、任务级、用户级、Agent 级、组织级知识。
2. 支持多智能体隔离：每个 Agent 有自己的工作记忆，同时可读取公共记忆池。
3. 支持自动记忆：无需每次显式调用，系统可以自动召回和自动沉淀。
4. 支持显式记忆工具：Agent 可主动 search/store/list/forget。
5. 支持可审计与可回放：所有记忆写入、更新、删除、召回都可追踪。
6. 支持后续扩展：先在本地和单机环境跑通，后续可平滑升级到分布式服务。

---

## 2. 借鉴的主流项目模式

### 2.1 OpenClaw + Mem0 插件

适合借鉴的点：

- **Auto-Recall**：在每轮推理前自动检索相关记忆并注入上下文。
- **Auto-Capture**：在任务结束或轮次结束后自动抽取新事实并写入记忆。
- **双层作用域**：同时支持 session memory 和 long-term memory。
- **Per-agent isolation**：通过 `agentId` 或派生命名空间隔离不同 Agent 的记忆。
- **显式工具**：`memory_search`、`memory_store`、`memory_list`、`memory_get`、`memory_forget`。

对 SwarmMind 的启发：

- 记忆系统不能只做“存储层”，还必须提供“自动注入”和“自动沉淀”能力。
- 记忆键不能只用 `user_id`，至少还要有 `task_id`、`session_id`、`agent_id`。
- 需要显式区分“短期记忆”和“长期记忆”，并允许合并检索结果。

### 2.2 Letta

适合借鉴的点：

- **Stateful Agent**：Agent 有稳定身份，不是一次性函数调用。
- **Memory Blocks**：把 persona、human profile、task context 分成结构化块。
- **Agent API**：外部系统通过标准 API 对 agent state 读写。

对 SwarmMind 的启发：

- 长期记忆不应只是向量片段，还应该有结构化档案，如用户偏好、团队规范、项目背景。
- 每个 Agent 需要一个“可解释的记忆面板”，而不仅是底层向量检索。

### 2.3 OpenHands

适合借鉴的点：

- **Conversation + Runtime State + Artifacts** 三者并存。
- 强调**回放能力**，不是只看最终结果。
- 执行过程和运行时状态与记忆是强关联的。

对 SwarmMind 的启发：

- Transcript 不能只是聊天记录，还要包括工具调用、沙箱输出、补丁、测试结果。
- 记忆层需要与任务轨迹、工件存储、可观测系统联动。

### 2.4 Mem0

适合借鉴的点：

- 专门做“Memory Layer”，强调低 token、高召回、跨会话个性化。
- 支持向量检索、分类、图谱增强、云端和自托管两种模式。

对 SwarmMind 的启发：

- 记忆要作为独立能力层，不要写死在某个 Agent 里。
- 存储模型需要同时支持结构化元数据和非结构化语义检索。

---

## 3. 推荐总体架构

```text
                         +----------------------+
                         |   API / CLI / Web    |
                         +----------+-----------+
                                    |
                                    v
                         +----------------------+
                         |   Task Orchestrator   |
                         +----------+-----------+
                                    |
                +-------------------+-------------------+
                |                                       |
                v                                       v
      +---------------------+                 +---------------------+
      |  Agent Runtime      |                 |   Memory Control    |
      |  AgentScope/MsgHub  |<--------------->|   Plane             |
      +----------+----------+                 +----------+----------+
                 |                                        |
                 |                                        |
      +----------+----------+                +------------+-------------+
      | Planner/Coder/...   |                | Retrieval / Capture /    |
      | explicit memory API |                | Consolidation / Policy   |
      +----------+----------+                +------------+-------------+
                 |                                        |
                 +-------------------+--------------------+
                                     |
                                     v
        +-------------+-------------------+-------------------+-------------+
        | Session KV  | Transcript Store  | Vector Store      | Metadata DB |
        | Redis       | JSONL / Object    | Qdrant / Chroma   | Postgres    |
        +-------------+-------------------+-------------------+-------------+
```

核心原则：

- **控制面与数据面分离**：Memory Manager 负责策略与编排，底层存储分别处理不同类型的数据。
- **热数据和冷数据分离**：短期上下文放 Redis/内存，长期知识放向量库和关系库，完整轨迹放对象存储。
- **记忆写入异步化**：Agent 主流程不等待重型抽取和索引，先投递事件，再异步处理。

---

## 4. 必要组件清单

### 4.1 Runtime 侧组件

1. **WorkingMemory**
   每个 Agent 的工作记忆，保存最近 N 轮消息、工具结果、当前计划和局部草稿。

2. **SharedTaskMemory**
   当前任务的共享记忆池，保存已经确认的事实、接口约束、验收标准、公共结论。

3. **MemoryToolkit**
   暴露给 Agent 的记忆工具：
   - `memory_search`
   - `memory_store`
   - `memory_list`
   - `memory_get`
   - `memory_forget`
   - `memory_pin` 可选，用于强制保留高价值结论

4. **ContextAssembler**
   在推理前把 system prompt、任务上下文、共享记忆、Agent 私有记忆、外部检索结果组装为最终 prompt。

### 4.2 Memory Control Plane 组件

1. **MemoryManager**
   统一入口，负责读写路由、命名空间、策略校验、存储编排。

2. **MemoryExtractor**
   从 transcript 或 message batch 中抽取“值得记住”的事实、偏好、决策、失败经验。

3. **MemoryConsolidator**
   去重、合并、升级和失效处理。
   例子：
   - 新事实覆盖旧事实
   - 重复表述合并为一条 canonical memory
   - 临时信息在 TTL 到期后自动删除

4. **MemoryRetriever**
   混合检索模块，支持：
   - 精确过滤：按 `task_id`、`agent_id`、`scope`、`type`
   - 语义检索：embedding similarity
   - 时间衰减：近期记忆加权
   - 重排：按相关性和可信度排序

5. **MemoryPolicyEngine**
   控制哪些内容可以被存、谁能读、保留多久、是否需要脱敏。

6. **MemoryEventBus**
   负责把记忆写入、更新、删除、索引等操作做成事件流，便于异步处理与审计。

7. **MemoryIndexer**
   为长期记忆生成 embedding、写入向量库、维护分类标签和关系图。

### 4.3 Storage 侧组件

1. **Redis**
   用于 session memory、recent buffer、热点摘要、分布式锁。

2. **PostgreSQL**
   用于记忆元数据、命名空间、索引状态、审计记录、关系查询。

3. **Qdrant**
   用于长期语义记忆检索。MVP 也可以先用 Chroma，生产建议 Qdrant。

4. **MinIO / S3**
   用于 transcript、sandbox 日志、patch、测试报告、截图等大对象工件。

5. **可选 Graph Store**
   用于人物、项目、依赖关系和决策链条。MVP 可先不落地，二期再加。

---

## 5. 记忆分层设计

| 层级 | 作用域 | 典型内容 | 推荐存储 | 生命周期 |
|------|--------|----------|----------|----------|
| Working Memory | `session_id + agent_id` | 最近对话、当前 plan、最近工具结果 | 进程内存 / Redis | 分钟到小时 |
| Task Shared Memory | `task_id` | 公共事实、验收标准、关键决定 | Redis + Postgres | 任务期间 |
| Session Memory | `session_id` | 本轮任务临时上下文 | Redis + Vector Store | 小时到天 |
| Agent Long-Term Memory | `user_id + agent_id` | 某角色的经验、偏好、历史结论 | Postgres + Qdrant | 长期 |
| User Long-Term Memory | `user_id` | 用户偏好、团队约定、常见栈 | Postgres + Qdrant | 长期 |
| Org Knowledge | `tenant_id` | 项目规范、模板、最佳实践 | Docs/RAG + Vector Store | 长期 |
| Transcript / Audit | `task_id + run_id` | 全量执行轨迹和工件索引 | JSONL + Object Store | 长期归档 |

关键规则：

- Planner、Coordinator 可以读共享记忆，但不默认写用户长期记忆。
- Coder、Tester、Reviewer 可以写“任务经验”和“技术结论”，但需要策略过滤。
- 用户偏好、组织规范、项目约定要和任务临时信息严格分层。

---

## 6. 推荐文件格式

### 6.1 事件流格式：JSONL

用途：记录每一次记忆相关事件，便于审计、回放、离线分析。

文件名建议：

- `artifacts/transcripts/{task_id}/{run_id}.jsonl`
- `artifacts/memory-events/{date}/{task_id}.jsonl`

推荐原因：

- 追加写简单。
- 适合流式消费。
- 对日志平台和对象存储友好。

示例：

```json
{"ts":"2026-03-13T10:21:14Z","event":"memory.recall","task_id":"t_123","session_id":"s_1","agent_id":"coder","query":"pytest failure root cause","results":["m_9","m_12"]}
{"ts":"2026-03-13T10:21:18Z","event":"memory.store","task_id":"t_123","session_id":"s_1","agent_id":"tester","memory_id":"m_18","scope":"task","kind":"lesson"}
```

### 6.2 结构化记忆对象：JSON

用途：长期记忆主对象、API 读写、元数据持久化。

推荐 schema：

```json
{
  "id": "mem_01HXYZ",
  "tenant_id": "team_alpha",
  "user_id": "u_123",
  "agent_id": "coder",
  "task_id": "task_456",
  "session_id": "sess_789",
  "scope": "agent_long_term",
  "kind": "decision",
  "content": "User prefers pytest over unittest for Python projects.",
  "summary": "pytest preference",
  "tags": ["python", "testing", "preference"],
  "confidence": 0.92,
  "source": "agent_auto_capture",
  "source_event_id": "evt_123",
  "visibility": "shared",
  "ttl_sec": null,
  "created_at": "2026-03-13T10:21:18Z",
  "updated_at": "2026-03-13T10:21:18Z",
  "version": 3,
  "embedding_ref": "vec_qdrant:swarmmind:mem_01HXYZ"
}
```

### 6.3 Transcript 快照：JSON

用途：一次任务或一次运行的完整结构化记录，便于 UI 展示和回放。

文件名建议：

- `artifacts/runs/{task_id}/{run_id}/transcript.json`

适合保存：

- run metadata
- agent turn 列表
- tool 调用
- sandbox exec
- memory recall/store 记录
- 产物索引

### 6.4 人工可读摘要：Markdown

用途：给用户、运营、研发查看的记忆摘要，不作为主存储。

文件名建议：

- `artifacts/summaries/{task_id}/memory-summary.md`

适合保存：

- 本次任务沉淀了哪些关键记忆
- 哪些记忆被更新或失效
- 哪些经验被提升为长期知识

### 6.5 批量分析格式：Parquet，可选

用途：后续做离线评估、召回质量分析、命中率分析时使用。

结论：

- MVP 阶段以 `JSON + JSONL` 为主。
- 二期若要做数据分析和 BI，再增加 Parquet 导出。

---

## 7. 记忆传输方式

### 7.1 进程内传输

适用场景：AgentRuntime 调 MemoryManager。

方式：

- Python dataclass / Pydantic model
- 同步函数或异步方法调用

优点：

- 延迟低，MVP 最简单。

### 7.2 服务间同步传输

适用场景：API / Worker / Memory Service 分离部署。

建议：

- **HTTP + JSON** 作为默认控制接口
- 需要高性能再补 **gRPC + Protobuf**

建议接口：

- `POST /v1/memories/search`
- `POST /v1/memories/store`
- `POST /v1/memories/batch-store`
- `POST /v1/memories/forget`
- `GET /v1/memories/{memory_id}`
- `GET /v1/tasks/{task_id}/memory-summary`

理由：

- 现有 SwarmMind 已经有 API 层，HTTP 最易接入。
- JSON 对调试和日志最友好。

### 7.3 异步事件传输

适用场景：自动沉淀、embedding 索引、异步合并、审计流。

MVP 建议：

- **Redis Streams**

生产建议：

- **NATS JetStream** 或 **Kafka**

推荐事件主题：

- `memory.capture.requested`
- `memory.capture.completed`
- `memory.index.requested`
- `memory.index.completed`
- `memory.consolidation.requested`
- `memory.recall.logged`
- `memory.forget.requested`

事件 envelope：

```json
{
  "event_id": "evt_001",
  "event_type": "memory.capture.requested",
  "occurred_at": "2026-03-13T10:21:18Z",
  "tenant_id": "team_alpha",
  "task_id": "task_456",
  "run_id": "run_001",
  "session_id": "sess_789",
  "agent_id": "reviewer",
  "payload": {
    "message_refs": ["msg_10", "msg_11"],
    "scope": "task",
    "source": "agent_end"
  }
}
```

### 7.4 向量和大对象传输

原则：

- embedding 不走聊天主链路。
- transcript、日志、测试报告不放进 memory 主表，改为对象存储，记忆对象中只保存引用。

示例：

- `artifact_ref = s3://swarmmind-artifacts/runs/task_456/run_001/test-report.json`
- `embedding_ref = qdrant://swarmmind/mem_01HXYZ`

---

## 8. 推荐的数据模型

### 8.1 MemoryRecord

建议字段：

- `id`
- `tenant_id`
- `user_id`
- `agent_id`
- `task_id`
- `session_id`
- `run_id`
- `scope`
- `kind`
- `content`
- `summary`
- `tags`
- `confidence`
- `visibility`
- `status`：`active` / `superseded` / `expired` / `deleted`
- `ttl_sec`
- `source`
- `source_event_id`
- `artifact_refs`
- `embedding_ref`
- `version`
- `created_at`
- `updated_at`

### 8.2 Scope 枚举

推荐：

- `working`
- `task_shared`
- `session`
- `agent_long_term`
- `user_long_term`
- `org_knowledge`

### 8.3 Kind 枚举

推荐：

- `fact`
- `preference`
- `constraint`
- `decision`
- `lesson`
- `plan`
- `profile`
- `artifact_index`

---

## 9. 读写流程设计

### 9.1 Recall 流程

1. Agent 接收到新任务或新消息。
2. ContextAssembler 生成检索 query。
3. MemoryRetriever 先按命名空间过滤：
   - 当前 `task_id`
   - 当前 `session_id`
   - 当前 `agent_id`
   - 当前 `user_id`
4. 对长期记忆做向量检索。
5. 对近期 session/task 记忆做关键词或 metadata 检索。
6. 混合排序并截断为 top-k。
7. 注入 prompt，格式化成 `<relevant_memories>` 或结构化 blocks。
8. 把 recall 结果写入 `memory.recall.logged` 事件。

### 9.2 Capture 流程

1. Agent 完成一个 turn 或子任务。
2. Transcript 记录消息、工具和结果。
3. MemoryExtractor 从增量事件中抽取候选记忆。
4. PolicyEngine 过滤敏感、临时、低价值内容。
5. Consolidator 做去重和升级。
6. 写入 Postgres 元数据。
7. 异步生成 embedding 并写入 Qdrant。
8. 记录 `memory.store` 和 `memory.index.completed` 事件。

### 9.3 Forget / Expire 流程

1. 显式调用 `memory_forget`，或命中 TTL 规则。
2. 将记录状态改为 `deleted` 或 `expired`。
3. 异步删除向量库条目。
4. 追加审计事件，保留操作人和原因。

---

## 10. 多智能体隔离策略

推荐命名空间主键：

```text
tenant_id / user_id / session_id / task_id / agent_id / scope
```

建议隔离规则：

1. **Working memory 强隔离**
   只有当前 Agent 可读写。

2. **Task shared memory 弱隔离**
   同一任务的 Agent 都可读，但仅 Coordinator、Reviewer、指定角色可做升级写入。

3. **Agent long-term memory 半隔离**
   某角色可优先读取自己的长期经验，其他角色默认只读公共摘要。

4. **User long-term memory 全局可读但受策略控制**
   例如用户语言偏好、代码风格偏好可以被多个 Agent 共享。

这一点要明确借鉴 OpenClaw 的 `agentId` 隔离做法，但在 SwarmMind 中进一步扩展为 `task + agent + user` 三维命名空间。

---

## 11. 与当前 SwarmMind 代码的映射建议

当前已有：

- `swarmmind/memory/manager.py`
- `swarmmind/memory/long_term.py`
- `swarmmind/memory/transcript.py`

建议扩展为：

```text
swarmmind/memory/
  __init__.py
  manager.py              # 总入口，统一读写
  working.py              # Agent 工作记忆
  shared.py               # 任务共享记忆
  long_term.py            # 向量记忆与长期存储适配
  transcript.py           # 轨迹记录与回放
  extractor.py            # 候选记忆抽取
  retriever.py            # 混合检索
  consolidator.py         # 去重/合并/升级
  policy.py               # 脱敏、TTL、权限策略
  schemas.py              # Pydantic models
  events.py               # 记忆事件定义
  bus.py                  # Redis Streams / NATS 封装
  storage.py              # Postgres/Qdrant/MinIO 适配
```

对应职责：

- `manager.py` 不再只包一层 `InMemoryMemory`，而是作为门面。
- `long_term.py` 不能继续用随机向量占位，必须接真实 embedding provider。
- `transcript.py` 继续保留，但建议增加 JSONL append 模式和 artifact refs。

---

## 12. MVP 推荐选型

### 12.1 MVP 组件

- Agent Runtime: AgentScope
- Short-term memory: `InMemoryMemory + Redis`
- Long-term metadata: PostgreSQL
- Long-term vector store: Qdrant
- Transcript store: JSONL + MinIO 本地兼容目录
- Async pipeline: Redis Streams
- Embedding provider: OpenAI `text-embedding-3-small` 或兼容模型

### 12.2 MVP 文件格式

- 结构化对象：JSON
- 流式轨迹：JSONL
- 人类可读摘要：Markdown

### 12.3 MVP 传输方式

- 进程内：Python model
- 服务间：HTTP + JSON
- 异步：Redis Streams

这是当前项目成本最低、实现路径最短、后续升级阻力最小的组合。

---

## 13. 二期升级方向

1. 把 `MemoryExtractor` 升级为双通路：
   - 规则抽取
   - LLM 抽取

2. 增加图谱记忆：
   - 用户
   - 项目
   - 技术栈
   - 决策关系

3. 增加记忆质量评估：
   - recall 命中率
   - 误召回率
   - 重复率
   - stale memory 比例

4. 增加“记忆审计 UI”：
   - 看见每条记忆从哪来
   - 谁写入的
   - 什么时候被更新或失效

---

## 14. 给客户的结论

如果客户要的是“可落地的多智能体记忆系统”，建议不要只做一个 `LongTermMemory` 类，而是建设下面这套组合：

- **Agent 工作记忆**：支撑单个 Agent 当前推理。
- **任务共享记忆**：支撑多个 Agent 协作。
- **长期语义记忆**：支撑跨任务、跨会话召回。
- **轨迹与审计系统**：支撑回放、监管、调试。
- **异步记忆管道**：支撑自动沉淀、索引和合并。

具体选型建议：

- 组件：AgentScope + Redis + PostgreSQL + Qdrant + MinIO
- 文件格式：JSON、JSONL、Markdown
- 传输方式：HTTP/JSON + Redis Streams
- 参考模式：OpenClaw 的 auto-recall/auto-capture 和 per-agent isolation，Letta 的 stateful memory blocks，OpenHands 的 transcript/artifact/replay，Mem0 的独立 memory layer

这套方案既适合当前 SwarmMind 的单机 MVP，也适合后续升级成多 Worker、多租户、可观测的生产系统。
