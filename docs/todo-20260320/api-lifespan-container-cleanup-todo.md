---
type: todo
date: 2026-03-20
topic: api-lifespan-cleanup
status: open
owner: copilot
---

# API Lifespan / AppContainer Cleanup TODO

> 这份文档用于承接 2026-03-20 代码审查期间识别出的 API 生命周期资源释放问题，重点覆盖 FastAPI `lifespan`、`AppContainer` 以及底层 Redis / 外部连接类组件的 shutdown 设计。

---

## 1. 背景

当前 FastAPI 应用在启动时会通过 `lifespan` 初始化容器：

1. `swarmmind/api/server.py` 在 `lifespan()` 中调用 `get_container(app.state.settings)`。
2. `swarmmind/app/bootstrap.py` 使用模块级 `_container` 缓存容器实例。
3. `swarmmind/app/container.py` 负责组装 `AppContainer` 及各类基础设施组件。

但当前实现存在一个明确缺口：

1. `lifespan` 在 `yield` 之后没有执行任何 cleanup。
2. `AppContainer` 没有统一的 `close()` / `shutdown()` 协议。
3. `reset_container()` 仅仅清空全局引用，不会关闭已创建的连接和资源。

这意味着应用虽然具备初始化路径，但没有完整的退出路径。

---

## 2. 当前问题

### 2.1 代码层面缺失

当前已确认的缺口包括：

1. FastAPI `lifespan` 没有 `try/finally` 结构来保证退出时执行清理。
2. `AppContainer` 没有统一收口底层资源释放的方法。
3. Redis 相关实现已经创建 client，但没有提供显式关闭入口。
4. 一旦未来引入更多外部资源，例如 HTTP client、DB pool、后台任务、consumer worker，也没有现成的统一清理机制可复用。

### 2.2 受影响的资源类型

目前最值得关注的是以下组件：

1. `RedisBufferedEventBus`
2. `RedisCacheStore`
3. `RedisLockManager`
4. 未来可能引入的 `PostgresStore` 长连接或连接池
5. 未来可能引入的后台 polling task、stream consumer、telemetry worker

### 2.3 可能风险

在开发环境中，这个问题可能暂时不明显；但在以下场景中会逐步放大：

1. Uvicorn reload 多次重启后连接没有按预期回收。
2. 测试反复启动应用时，资源状态不可控，导致 flaky tests。
3. 生产环境平滑退出时，无法明确保证连接关闭、后台任务取消、缓存状态回收。
4. 后续架构扩展时，生命周期管理会继续散落在各模块，增加维护成本。

---

## 3. 设计目标

本次 cleanup 设计应满足以下目标：

1. 让应用生命周期具备对称性：`startup -> running -> shutdown`。
2. 让容器成为资源生命周期的统一入口和统一出口。
3. 让每个持有外部资源的组件都能显式声明是否需要释放。
4. 保持对当前 MVP 代码的改动尽量小，不打乱现有对象组装方式。
5. 为未来新增 Redis consumer、HTTP client、连接池、后台任务预留扩展位。

---

## 4. 设计原则

### 4.1 单一收口

所有应用级资源释放逻辑统一收敛到 `AppContainer.shutdown()`，而不是散落在 `server.py`、`bootstrap.py` 或各调用方。

### 4.2 最小侵入

优先在现有容器对象上补生命周期方法，不引入复杂 DI 框架或新的容器层级。

### 4.3 显式协议

凡是持有连接、线程、后台任务、socket、文件句柄、client session 的对象，都应该实现显式关闭方法，例如：

1. `async close()`
2. `async shutdown()`

应用层不依赖对象析构或 GC 触发释放。

### 4.4 幂等释放

cleanup 过程应支持重复调用而不报错，避免：

1. FastAPI shutdown 和测试 teardown 重复关闭。
2. 部分初始化失败后的半关闭状态处理复杂化。

### 4.5 失败隔离

关闭某一个资源失败时，不应阻断其他资源的关闭；但必须记录错误，便于排查。

---

## 5. 目标设计

### 5.1 FastAPI lifespan 设计

建议将 `lifespan` 改为显式的启动与退出结构：

1. 启动阶段创建容器并挂到 `app.state.container`。
2. `yield` 交出控制权。
3. 退出阶段执行容器关闭。
4. 最后清理模块级缓存和 `app.state` 挂载引用。

伪代码：

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    container = await get_container(app.state.settings)
    app.state.container = container
    try:
        yield
    finally:
        await container.shutdown()
        reset_container()
        app.state.container = None
```

这里的关键点是：

1. 关闭动作放在 `finally`，保证异常退出也会尝试 cleanup。
2. `reset_container()` 不再被视为 cleanup，而只是缓存状态复位。

### 5.2 AppContainer 生命周期设计

建议为 `AppContainer` 增加统一异步关闭接口：

```python
class AppContainer:
    async def shutdown(self) -> None:
        ...
```

`shutdown()` 负责：

1. 识别哪些成员具备 `close` / `shutdown` 能力。
2. 按可控顺序调用它们。
3. 聚合异常并输出结构化日志。
4. 保证重复调用安全。

建议收敛顺序：

1. 先停止后台任务或事件消费。
2. 再关闭上层基础设施适配器。
3. 最后关闭 Redis / 数据库连接类资源。

### 5.3 资源关闭协议

建议定义一个轻量约定，而不是马上引入新的抽象基类：

1. 若对象实现 `async shutdown()`，优先调用。
2. 否则若实现 `async close()`，调用它。
3. 否则若实现同步 `close()`，则直接调用。
4. 若对象没有释放接口，则忽略。

这样可以兼容：

1. 现有对象
2. 第三方 client
3. 未来新增的基础设施组件

### 5.4 bootstrap 设计

建议把 `bootstrap.py` 中全局容器缓存的职责限定为：

1. 提供当前进程内复用。
2. 在 shutdown 后可安全 reset。

不建议让 `reset_container()` 负责隐式关闭资源，原因是：

1. 方法名语义偏弱，容易误导调用方。
2. shutdown 与 reset 是两个不同职责。
3. 测试代码可能只想复位缓存，不一定要接管关闭时机。

更清晰的职责边界是：

1. `get_container()` 负责获取或创建。
2. `shutdown_container()` 或 `AppContainer.shutdown()` 负责释放。
3. `reset_container()` 负责清理缓存引用。

### 5.5 Redis / 外部资源适配器设计

建议为当前持有 Redis client 的组件增加显式关闭方法。

建议补充的对象：

1. `RedisBufferedEventBus.close()`
2. `RedisCacheStore.close()`
3. `RedisLockManager.close()`

典型实现目标：

1. 调用 Redis client 的 `aclose()`。
2. 对重复关闭保持安全。
3. 保证关闭失败时能提供足够日志。

对于 `PostgresStore`，当前实现每次操作即时连接、即时释放，短期内不一定需要 close；但如果后续演进成连接池，则应同步纳入容器 shutdown 路径。

---

## 6. TODO 列表

### 6.1 第一阶段：补齐最小 cleanup 闭环

1. 为 `AppContainer` 增加 `shutdown()`。
2. 在 `server.py` 的 `lifespan()` 中使用 `try/finally` 调用 `shutdown()`。
3. 在 shutdown 结束后执行 `reset_container()`。
4. 为现有 Redis 类组件补 `close()`。
5. 增加基础日志，记录 shutdown 开始、结束、失败对象。

验收标准：

1. 应用启动后正常退出时会进入 cleanup。
2. 启用 Redis 配置时 client 能显式关闭。
3. 重复调用 shutdown 不会抛出未处理异常。

### 6.2 第二阶段：统一资源关闭协议

1. 抽出内部通用 helper，例如 `_shutdown_resource(obj, name)`。
2. 统一支持 `shutdown`、异步 `close`、同步 `close` 三类接口。
3. 为新基础设施组件补齐生命周期约束文档。

验收标准：

1. 容器 shutdown 逻辑不依赖每个资源的具体类型判断。
2. 新增资源可以按协议自动接入 cleanup 流程。

### 6.3 第三阶段：测试与可靠性补强

1. 增加容器 shutdown 单元测试。
2. 增加 FastAPI lifespan 集成测试，验证启动和退出都会执行。
3. 增加 Redis 资源 cleanup 测试，覆盖重复关闭和关闭失败。
4. 补充异常场景测试，例如某个资源关闭失败后其他资源仍会继续关闭。

验收标准：

1. cleanup 主路径有明确测试覆盖。
2. 部分资源关闭失败不会中断整体 shutdown。

---

## 7. 建议实现细节

### 7.1 AppContainer.shutdown 建议行为

建议 `AppContainer.shutdown()`：

1. 内部维护 `_is_shutdown` 标记。
2. 如果已经关闭则直接返回。
3. 迭代需要释放的依赖列表。
4. 每个资源单独 try/except。
5. 收集错误并统一打日志。

更具体的顺序建议：

1. `sandbox_manager`
2. `event_bus`
3. `cache_store`
4. `lock_manager`
5. 未来新增的数据库池、HTTP clients、consumer workers

如果某些对象当前没有释放接口，不需要为了 cleanup 人工包装空实现，但应在文档中记录其状态。

### 7.2 日志字段建议

shutdown 日志建议至少包含：

1. `component`
2. `action=shutdown`
3. `outcome=started|succeeded|failed|skipped`
4. `error_type`
5. `error_message`

如果上下文允许，也可以补充：

1. `task_id`
2. `run_id`
3. `sandbox_id`

但应用整体 shutdown 阶段通常更关键的是组件级别日志。

### 7.3 测试建议

建议至少覆盖以下用例：

1. `lifespan` 启动时成功创建容器。
2. `lifespan` 退出时调用 `container.shutdown()`。
3. `container.shutdown()` 多次调用只执行一次真实清理。
4. 一个资源关闭失败时，后续资源仍会继续执行关闭。
5. Redis 组件 `close()` 可以安全重复调用。

---

## 8. 非目标

这轮 cleanup 设计暂时不处理以下内容：

1. 重构整个 DI / 容器体系。
2. 把所有仓储类统一改造成连接池模式。
3. 引入复杂的应用生命周期框架。
4. 一次性重写 event bus、gateway、orchestrator 的资源管理模型。

本轮目标只是补齐一个清晰、可维护、可扩展的退出路径。

---

## 9. 建议执行顺序

1. 先补 `AppContainer.shutdown()` 和 `server.py` 的 `lifespan finally`。
2. 再补 Redis 类组件 `close()`。
3. 然后补单元测试和 lifespan 集成测试。
4. 最后把 shutdown 协议写入工程文档，作为后续基础设施开发约束。

一句话总结：

**当前 SwarmMind API 已有容器初始化路径，但没有对称的资源退出路径；最合理的修复方式是把 cleanup 统一收口到 `AppContainer.shutdown()`，并由 FastAPI `lifespan` 在退出阶段可靠触发。**