# Text2SQL LLM Provider Request Timed Out 问题分析

> 日期：2026-06-04
> 问题来源：text2sql 任务执行过程中出现 "LLM provider request timed out" 错误

---

## 一、背景

Text2SQL 模块使用 Vanna 2.0 Agent 框架，通过多轮工具调用（最多 `max_tool_iterations` 轮）将自然语言转为 SQL 并执行。每轮调用涉及：
1. 一次 LLM 推理请求（生成 SQL 或决定调用什么工具）
2. 可能的 PostgreSQL 查询（`statement_timeout_ms` 已限制为 15s）

当前系统使用的 LLM 是 DeepSeek 系列模型（通过 OpenAI 兼容接口调用），DeepSeek 的推理模型在复杂 SQL 生成场景下响应时间可能较长。

---

## 二、问题根因

### 2.1 超时机制缺失：三层全部没有保护

整个 text2sql 调用链上有三层，**每一层都没有设置超时**：

```
用户请求
  → service.py: asyncio.to_thread(asyncio.run, service.answer(...))
    │               ↑ ① 没有 asyncio.wait_for 包裹
    │
    → Vanna Agent: 多轮循环（最多 max_tool_iterations 轮）
    │               ↑ ② 没有整体超时限制
    │
      → OpenAI() client: 每次 LLM 请求
                          ↑ ③ 没有传 timeout 参数
```

### 2.2 各层详细分析

#### 第一层：OpenAI Client（单次请求超时）

文件：`swarmmind/domains/fly_report/text2sql/agent.py` 第 208-212 行

```python
llm = NoThinkingOpenAILlmService(
    api_key=self._model.api_key,
    base_url=self._model.base_url or None,
    model=self._model.name,
    # ← 没有 timeout 参数
)
```

Vanna 的 `OpenAILlmService.__init__` 接受 `**extra_client_kwargs`，会透传给 `OpenAI()` 构造函数。OpenAI Python SDK 在不传 `timeout` 时**默认超时为 600 秒（10 分钟）**。

- 对于 DeepSeek 等推理模型，复杂 SQL 生成可能需要 30-120 秒，这还算合理
- 但如果 LLM provider 端出现排队、过载或网络抖动，600 秒的默认超时太长了
- 用户端等 10 分钟才报超时，体验极差

#### 第二层：Agent 整体（多轮循环超时）

文件：`swarmmind/domains/fly_report/text2sql/agent.py` 第 310-334 行

```python
async for component in self._agent.send_message(
    request_context=self._request_context,
    message=question,
    conversation_id=cid,
):
    # ... 处理每个 component
```

Vanna Agent 的 `send_message` 内部会循环调用 LLM，最多 `max_tool_iterations` 轮（配置值）。**整个循环没有总超时限制**。

最坏情况：
- `max_tool_iterations` = 10（默认值）
- 每轮 LLM 调用耗时接近 600 秒（默认超时）
- 总耗时 = 10 × 600s = **6000 秒 ≈ 100 分钟**

虽然实际中不太可能每轮都用满 600s，但 3-5 轮 × 60s 的情况（总 3-5 分钟）是完全可能的。

#### 第三层：service.py 调用（外部包裹超时）

文件：`swarmmind/domains/fly_report/service.py` 第 1741-1744 行

```python
answer = await asyncio.to_thread(
    asyncio.run,
    service.answer(interaction.input_text),
    # ← 没有 asyncio.wait_for
)
```

`asyncio.to_thread` 本身不支持超时参数。需要外层套 `asyncio.wait_for(coro, timeout=...)` 才能限制总执行时间。当前没有任何包裹，worker 线程会**无限期阻塞**直到 Vanna Agent 内部完成或报错。

### 2.3 对比：其他模块都有超时

| 模块 | 超时设置 | 配置位置 |
|------|----------|----------|
| 意图分类（IntentClassifier） | 20s | `OpenAICompatibleLMClient(timeout_sec=20.0)` |
| 闲聊（ChitchatLMClient） | 30s | `OpenAICompatibleLMClient(timeout_sec=30.0)` |
| 报告合成（SimpleComposerLMClient） | 100s | `OpenAICompatibleLMClient(timeout_sec=100.0)` |
| Dikong HTTP 数据源 | 15s | `FlyReportDikongConfig.request_timeout_seconds` |
| PostgreSQL 连接池 | 10s | `FlyReportPostgresConfig.pool_timeout_seconds` |
| PostgreSQL 单条语句 | 15s | `FlyReportText2SqlConfig.statement_timeout_ms` |
| TDengine 查询 | 30s | `FlyReportTDengineConfig.timeout_seconds` |
| **Text2SQL LLM 请求** | **无** | **未配置** |
| **Text2SQL Agent 整体** | **无** | **未配置** |

text2sql 是唯一一个 LLM 调用没有超时保护的模块。

### 2.4 ModelConfig 也缺少 timeout 字段

`swarmmind/config/schema.py` 中的 `ModelConfig` 定义了 `provider`, `name`, `api_key`, `base_url`, `temperature`, `max_tokens`, `disable_thinking`，但**没有 `timeout` 字段**。这意味着即使想通过配置文件设置超时，也没有对应的配置项。

---

## 三、解决思路

### 3.1 短期修复：OpenAI Client 加单次请求超时

在 `text2sql/agent.py` 构造 LLM 时，通过 `extra_client_kwargs` 传入 `timeout`：

```python
# swarmmind/domains/fly_report/text2sql/agent.py 第 208-212 行
llm = NoThinkingOpenAILlmService(
    api_key=self._model.api_key,
    base_url=self._model.base_url or None,
    model=self._model.name,
    timeout=120.0,  # 单次 LLM 请求 120 秒超时
)
```

Vanna 的 `OpenAILlmService.__init__` 会把 `timeout` 透传给 `OpenAI()` 构造函数。OpenAI SDK 的 `timeout` 参数接受 `float`（秒）或 `httpx.Timeout` 对象。

建议值：120 秒。理由：
- DeepSeek 推理模型复杂 SQL 生成通常 30-90 秒
- 留一定余量应对 provider 端抖动
- 比默认 600s 短很多，用户等待体验可接受

### 3.2 短期修复：service.py 加整体超时

在 `service.py` 的 text2sql 调用处包裹 `asyncio.wait_for`：

```python
# swarmmind/domains/fly_report/service.py 第 1741-1744 行
try:
    answer = await asyncio.wait_for(
        asyncio.to_thread(asyncio.run, service.answer(interaction.input_text)),
        timeout=180.0,  # text2sql 整体 3 分钟超时
    )
except asyncio.TimeoutError:
    logger.warning("fly_report.text2sql.timeout", extra={"question": interaction.input_text})
    # 返回友好提示，而不是 500 错误
    answer = Text2SqlAnswer(
        answer_text="抱歉，查询处理时间较长，请稍后重试或尝试简化您的问题。",
        success=False,
        error="agent_timeout",
    )
```

建议值：180 秒（3 分钟）。理由：
- 单次 LLM 请求超时 120s，多轮最多 10 轮，但通常 2-4 轮就能出结果
- 3 分钟覆盖绝大多数正常场景
- 超过 3 分钟基本可以认为是异常情况

### 3.3 中期优化：FlyReportText2SqlConfig 加配置项

在配置 schema 中增加可调超时参数：

```python
# swarmmind/config/schema.py - FlyReportText2SqlConfig
class FlyReportText2SqlConfig(BaseConfig):
    ...
    # 现有字段
    statement_timeout_ms: int = Field(default=15000, ge=100)
    max_tool_iterations: int = Field(default=10, ge=1, le=20)
    max_rows: int = Field(default=200, ge=1)

    # 新增字段
    llm_timeout_seconds: float = Field(
        default=120.0,
        ge=10.0,
        description="单次 LLM 请求超时（秒）",
    )
    agent_timeout_seconds: float = Field(
        default=180.0,
        ge=30.0,
        description="Text2SQL Agent 整体超时（秒）",
    )
```

然后在 `agent.py` 中读取配置：

```python
llm = NoThinkingOpenAILlmService(
    api_key=self._model.api_key,
    base_url=self._model.base_url or None,
    model=self._model.name,
    timeout=self._config.llm_timeout_seconds,  # 从配置读取
)
```

在 `service.py` 中读取配置：

```python
timeout = self._get_text2sql_config().agent_timeout_seconds
answer = await asyncio.wait_for(
    asyncio.to_thread(asyncio.run, service.answer(interaction.input_text)),
    timeout=timeout,
)
```

### 3.4 可选优化：Vanna Agent 层面加总超时

如果 Vanna 框架支持，可以在 `AgentConfig` 中增加 `total_timeout_seconds` 配置，在 `send_message` 内部循环时检查累计耗时。这需要修改 Vanna 框架代码或提交 PR，属于长期优化。

---

## 四、涉及的文件

| 文件 | 需要修改的内容 |
|------|---------------|
| `swarmmind/domains/fly_report/text2sql/agent.py` (第 208-212 行) | LLM 构造加 `timeout` 参数 |
| `swarmmind/domains/fly_report/service.py` (第 1741-1744 行) | text2sql 调用加 `asyncio.wait_for` + 超时处理 |
| `swarmmind/config/schema.py` (第 523 行附近) | `FlyReportText2SqlConfig` 加 `llm_timeout_seconds` 和 `agent_timeout_seconds` |
| `swarmmind/domains/fly_report/text2sql/llm.py` (可选) | `NoThinkingOpenAILlmService` 加 timeout 支持 |

---

## 五、风险与注意事项

| 风险点 | 说明 |
|--------|------|
| 超时值过短 | 如果设太短（如 LLM 30s），正常复杂查询也会被误杀。建议 LLM 120s + 整体 180s |
| 超时后资源泄漏 | `asyncio.wait_for` 超时后会 cancel task，但 `asyncio.to_thread` 中的同步代码不会被中断。Vanna 的 PG 连接可能未正确释放。需要确保 `PostgresRunner` 的连接池有 `max_lifetime` 或 idle 回收机制 |
| worker 线程堆积 | 如果 text2sql 调用频繁超时，`asyncio.to_thread` 的线程池可能被耗尽（默认 `ThreadPoolExecutor` 大小有限）。需要监控线程池使用情况 |
| DeepSeek 推理模式 | 如果未来启用 DeepSeek 的 thinking 模式（当前被 `NoThinkingOpenAILlmService` 禁用），推理时间会更长，超时值可能需要调整 |

---

## 六、总结

| 维度 | 结论 |
|------|------|
| 根本原因 | text2sql 路径上三层（OpenAI client / Agent 循环 / service 调用）全部没有超时设置 |
| 影响 | LLM provider 慢或过载时，用户长时间等待（最长可达 100 分钟），worker 线程被阻塞 |
| 对比 | 其他模块（意图分类 20s、闲聊 30s、报告合成 100s）都有超时，text2sql 是唯一缺失的 |
| 修复优先级 | **高** — 影响用户体验且可能导致线程池资源耗尽 |
| 修复方案 | ① OpenAI client 加 `timeout=120s` ② service.py 加 `asyncio.wait_for(timeout=180s)` ③ 配置化超时参数 |
