# SwarmMind V2 基础设施抽象设计

> 这份文档回答一个很具体的问题：
>
> V2 既然明确选型 `PostgreSQL + Redis + Qdrant`，那还要不要做抽象？
>
> 结论是：**要抽象，但只抽象稳定的业务能力边界，不做过度供应商中立化。**

关联文档：

- `006-repository-storage-eventbus-system-design.md`
- `009-implementation-roadmap.md`
- `v2-002-implementation-scope.md`

---

## 1. 设计目标

V2 的基础设施抽象要同时满足四个目标：

1. 上层业务不直接依赖 `psycopg`、`redis-py`、`qdrant-client` 这类 SDK。
2. 默认主实现明确固定为 `PostgreSQL + Redis + Qdrant`，不引入“伪中立”架构。
3. 后续如果替换具体产品，只影响 adapter 层，而不是扩散到 API、gateway、orchestrator、query。
4. 抽象要贴近业务语义，而不是抽象成一个巨大而空泛的 `StorageProvider`。

一句话说：

**SwarmMind V2 抽象的是能力，不是品牌。**

---

## 2. 总体原则

### 2.1 抽象边界按能力拆分

推荐把基础设施抽象拆成四类边界：

1. `Repository`
   面向结构化主数据和聚合根。

2. `Cache / Lock / Event Stream`
   面向运行态缓存、锁和异步事件传播。

3. `Vector Retrieval / Long-Term Memory`
   面向语义检索和长期记忆。

4. `Object Storage`
   面向日志、报告、回放文件等大对象。

这些边界应该是彼此独立的，不应强行揉成一个统一存储接口。

### 2.2 默认实现先固定，再预留替换点

V2 的默认实现固定如下：

1. `PostgreSQL` 负责结构化元数据。
2. `Redis` 负责 cache、lock、stream。
3. `Qdrant` 负责向量检索。
4. `MinIO / S3` 负责大对象。

也就是说：

1. 业务层看到的是抽象。
2. 工程实现上先以这组默认基础设施为标准。
3. 替换能力是“保留的”，不是“当前优先级最高的”。

### 2.3 不做的抽象

V2 不建议做下面这些抽象：

1. `DatabaseProvider`
   过宽，最终会把事务、查询、索引、序列化都糊在一起。

2. `KeyValueStore`
   过于粗糙，无法表达 cache、lock、stream 的不同语义。

3. `UniversalVectorStore`
   如果接口直接暴露 collection、payload filter、hybrid search 等底层差异，上层很快会泄漏供应商细节。

4. `InfraManager`
   把 repository、cache、memory、event bus 全塞进去，会让依赖方向失控。

---

## 3. V2 推荐抽象层

### 3.1 Repository 层

这是 V2 最重要的一层抽象。

推荐继续保留并扩展当前这组协议：

1. `TaskRepository`
2. `SessionRepository`
3. `RunRepository`
4. `SubTaskRepository`
5. `ArtifactRepository`
6. `ReplayRepository`

后续如有需要，再补：

1. `IdentityRepository`
2. `PolicyRepository`
3. `QuotaRepository`

Repository 的规则是：

1. 只表达聚合级读写能力。
2. 返回领域对象或 DTO。
3. 不把 SQL、事务、连接池暴露到业务层。

默认实现映射：

1. `InMemory*Repository`
2. `Postgres*Repository`

也就是说，业务层依赖的是 `TaskRepository`，而不是 `PostgresTaskRepository`。

### 3.2 Cache 层

缓存建议单独抽象，不要混进 repository。

推荐接口：

1. `CacheStore`

建议职责：

1. `get(key)`
2. `set(key, value, ttl)`
3. `delete(key)`
4. `get_many(keys)`
5. `set_many(items, ttl)`

适用场景：

1. task/run 查询读缓存
2. 热点状态快照
3. 短期 admission / rate-limit 计数缓存

默认实现映射：

1. `InMemoryCacheStore`
2. `RedisCacheStore`

### 3.3 Lock 层

锁应该单独抽象，不应复用 `CacheStore`。

推荐接口：

1. `LockManager`

建议职责：

1. `acquire(key, ttl)`
2. `release(lock_token)`
3. `extend(lock_token, ttl)`

适用场景：

1. run 终态收敛竞争控制
2. subtask 消费幂等控制
3. replay / artifact 重复写入防抖

默认实现映射：

1. `InMemoryLockManager`
2. `RedisLockManager`

### 3.4 Event Bus / Stream 层

当前已经有 `EventBus` 协议，这是正确方向。

V2 建议区分两个层次：

1. `EventBus`
   面向进程内或轻量发布订阅。

2. `StreamBus` 或等价的 durable event stream
   面向 Redis Streams、Kafka 等可重放事件通道。

V2 第一阶段可以只保留：

1. `EventBus`

V2 第二阶段再引入：

1. `StreamBus`
2. `OutboxPublisher`

这样做的原因是：

1. 当前主目标是先打通执行闭环。
2. durable stream 和 outbox 会显著增加一致性复杂度。

### 3.5 Vector Retrieval / Long-Term Memory 层

向量检索不应该让业务层直接看到 Qdrant API。

推荐保留或升级当前抽象：

1. `LongTermMemoryBase`

更工程化一点，也可以拆成两层：

1. `EmbeddingProvider`
2. `VectorStore`

推荐职责：

`EmbeddingProvider`

1. `embed_text(text)`
2. `embed_texts(texts)`

`VectorStore`

1. `upsert(id, vector, payload)`
2. `query(vector, top_k, filters)`
3. `delete(id)`
4. `clear(namespace)`

`LongTermMemory`

1. `store(content, metadata)`
2. `retrieve(query, top_k)`
3. `delete(memory_id)`

依赖关系建议是：

```text
LongTermMemory
  -> EmbeddingProvider
  -> VectorStore
```

默认实现映射：

1. `InMemoryLongTermMemory`
2. `QdrantVectorStore`
3. `QdrantLongTermMemory`

如果未来替换成 Milvus、Weaviate、pgvector，本质上只替换 `VectorStore` 实现。

### 3.6 Object Storage 层

虽然这轮重点不在对象存储，但 V2 已经需要为 artifact/replay 预留边界。

推荐接口：

1. `ObjectStore`

建议职责：

1. `put(key, bytes, content_type)`
2. `get(key)`
3. `delete(key)`
4. `signed_url(key)`

默认实现映射：

1. `LocalObjectStore`
2. `MinioObjectStore`
3. `S3ObjectStore`

---

## 4. 推荐依赖方向

V2 推荐的依赖方向如下：

```text
API / Gateway / Orchestration / Query
  -> Repository / Cache / Lock / EventBus / LongTermMemory / ObjectStore
  -> Concrete Adapters
  -> PostgreSQL / Redis / Qdrant / MinIO
```

必须避免的方向：

1. API 直接持有 Redis client。
2. Orchestrator 直接写 SQL。
3. Query service 直接拼接缓存 key 并依赖具体 Redis 命令。
4. Memory service 直接依赖 Qdrant collection 管理 API。

换句话说，业务服务只能依赖抽象，基础设施 client 只能出现在 adapter 层。

---

## 5. V2 应该新增的接口清单

建议按优先级拆成两批。

### 5.1 V2 第一阶段必须有

这一批直接服务于执行闭环。

1. `TaskRepository`
2. `SessionRepository`
3. `RunRepository`
4. `SubTaskRepository`
5. `ArtifactRepository`
6. `ReplayRepository`
7. `EventBus`
8. `LongTermMemoryBase`

说明：

1. 前 7 个当前基本已有。
2. `LongTermMemoryBase` 当前已有雏形，但还需要和 embedding / vector store 边界继续整理。

### 5.2 V2 第二阶段建议新增

这一批服务于基础设施替换和系统稳定性。

1. `CacheStore`
2. `LockManager`
3. `ObjectStore`
4. `EmbeddingProvider`
5. `VectorStore`
6. `StreamBus`
7. `OutboxPublisher`

这些接口不一定要在第一阶段全部落代码，但文档和目录结构应为它们预留位置。

---

## 6. 推荐目录结构

V2 可以按下面的方式组织抽象与实现：

```text
swarmmind/
  repositories/
    task_repository.py
    run_repository.py
    ...
    in_memory/
    postgres/

  cache/
    base.py
    in_memory.py
    redis.py

  locks/
    base.py
    in_memory.py
    redis.py

  events/
    bus.py
    in_memory_bus.py
    redis_stream_bus.py
    outbox.py

  memory/
    long_term.py
    embeddings.py
    vector_store.py
    qdrant_store.py

  storage/
    object_store.py
    local.py
    minio.py
```

这个结构的重点不是“目录好看”，而是让抽象和实现天然分层。

---

## 7. V2 具体落地建议

### 7.1 第一阶段

目标：先打通执行闭环。

建议做法：

1. 保持现有 `InMemory*Repository`。
2. 保持现有 `EventBus` + `InMemoryEventBus`。
3. 继续用 `InMemoryLongTermMemory` 或简单版 `QdrantLongTermMemory`。
4. 先不要引入 Redis cache、lock、stream 的真实实现。

判断标准：

1. 业务闭环是否稳定。
2. 接口是否已经稳定。
3. 状态推进和证据链是否可测试。

### 7.2 第二阶段

目标：替换到底层真实基础设施。

建议顺序：

1. 先补 `Postgres*Repository`
2. 再补 `RedisCacheStore` 和 `RedisLockManager`
3. 再补 `Qdrant VectorStore`
4. 最后引入 `Redis StreamBus` 和 `OutboxPublisher`

这个顺序的原因是：

1. repository 替换对业务价值最大。
2. cache / lock 次之。
3. event stream 的一致性设计最复杂，应该放后。

---

## 8. 反模式

V2 实施时建议明确避免下面这些反模式：

1. 为了“以后可能换数据库”，把 repository 全部降级成通用 CRUD 接口。
2. 为了“兼容所有缓存”，把锁、缓存、stream 全塞进一个 Redis wrapper。
3. 为了“向量库可替换”，把底层向量过滤、namespace、payload 能力硬编码进业务层。
4. 在业务类里直接 import 三方 client，然后靠约定说“以后再抽象”。

这些做法短期看起来快，后面会让替换成本更高。

---

## 9. 最终建议

如果把 V2 的基础设施策略压缩成一句工程判断，就是：

**默认实现明确固定为 PostgreSQL、Redis、Qdrant；业务边界抽象为 repository、cache、lock、event bus、vector retrieval；替换发生在 adapter 层，而不是传播到业务层。**

这能同时满足三件事：

1. 当前能高效落地。
2. 后续能替换实现。
3. 不会因为过度抽象把系统做空。