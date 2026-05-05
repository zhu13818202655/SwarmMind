# FlyReport 轻量 LM Chat 规划

> 目标：新增一个非常轻的大模型 Chat 封装。它只负责接收 prompt，异步调用大模型，并返回模型输出。它不是 agent，不关心工具、composer、章节、审计模型或业务流程。

## 1. 背景与当前判断

当前 FlyReport 后续会在若干位置需要调用大模型，例如报告文字润色、内容总结、格式化输出、解释说明等。它们的共同点是：

```text
system prompt + user prompt -> LM 推理 -> output
```

这里需要的是一个最小 LM Chat 能力，而不是 ReAct Agent。调用方只要把字符串传进去，就能直接拿到模型输出；至于这些字符串来自章节、表格、用户输入、拼装后的上下文，LM 层都不需要知道。

因此，本阶段新增的是 **通用轻量 LM Chat 客户端**，不是章节总结器，也不是 composer 的一部分。

## 2. 设计边界

这个 LM 层只做：

- 支持异步调用；
- 支持 `system_prompt`；
- 支持 `user_prompt`；
- 支持可选多轮 `messages`；
- 返回模型原始文本；
- 可选把输出解析成 JSON / Markdown / 普通文本等格式；
- 对接主流 OpenAI-compatible Chat Completions 风格接口。

这个 LM 层不做：

- 不继承 `ReActAgent`；
- 不使用 `OmniAgent`；
- 不使用 `MsgHub`；
- 不使用 `Toolkit`；
- 不使用 `AuditedOpenAIChatModel`；
- 不关心章节、报告、composer、summary、fallback；
- 不管理长期 memory；
- 不做工具调用；
- 不做任务规划或多 agent 协作。

一句话：**LM 就只是 LM**。

## 3. 核心设计原则

1. **调用简单**
   - 最常见路径应该是一行：`await lm.chat(system_prompt=..., user_prompt=...)`。
   - 返回值默认就是字符串，不强迫调用方理解复杂对象。

2. **输入自由**
   - `system_prompt` 和 `user_prompt` 都是字符串。
   - 调用方可以传自然语言、Markdown、JSON 字符串、拼装后的上下文，LM 层不限制。
   - 如果需要多轮上下文，再传 `messages`。

3. **输出自由**
   - 默认返回普通文本。
   - 模型可以输出 JSON、Markdown、纯文本或其他文本格式。
   - LM 层可以提供解析辅助，但不强制限定输出 schema。

4. **异步优先**
   - 所有模型调用都是 async。
   - 后续业务侧如需并发调用，可以直接 `asyncio.gather` 或自行加并发控制。

5. **贴近主流接口**
   - 内部概念尽量靠近 OpenAI-compatible Chat Completions：`model`、`messages`、`temperature`、`max_tokens`、`response_format`。
   - 这样后续切换 OpenAI、DeepSeek、Qwen、Moonshot、OneAPI 等兼容服务时成本低。

6. **少封装**
   - 不为了“平台化”提前加复杂能力。
   - 不做 agent 抽象，不做业务感知，不做审计复用。

## 4. 推荐目录

建议先放在 FlyReport domain 内：

```text
swarmmind/domains/fly_report/lm/
  __init__.py
  client.py
  types.py
  output.py
```

原因：

- 当前需求来自 FlyReport，不需要先上升为全仓库公共 LM 网关；
- 便于按报告业务快速演进；
- 如果后续多个 domain 都需要，再提取到 `swarmmind/lm/` 或 `swarmmind/runtime/lm/`。

## 5. 类型草案

### 5.1 Chat 消息

```python
from typing import Literal

from pydantic import BaseModel


LMRole = Literal["system", "user", "assistant"]


class LMMessage(BaseModel):
    role: LMRole
    content: str
```

### 5.2 输出格式提示

输出格式只是提示，不是业务强约束。

```python
from enum import StrEnum


class LMOutputFormat(StrEnum):
    TEXT = "text"
    JSON = "json"
    MARKDOWN = "markdown"
    RAW = "raw"
```

含义：

| 格式 | 含义 |
| --- | --- |
| `text` | 默认普通文本，直接返回字符串 |
| `json` | 希望模型输出 JSON；可尝试解析成 dict/list |
| `markdown` | 希望模型输出 Markdown；仍然返回字符串 |
| `raw` | 返回底层 provider 的原始响应，调试时使用 |

### 5.3 Chat 请求

```python
from typing import Any

from pydantic import BaseModel, Field


class LMChatRequest(BaseModel):
    system_prompt: str | None = None
    user_prompt: str | None = None
    messages: list[LMMessage] | None = None
    output_format: LMOutputFormat = LMOutputFormat.TEXT
    temperature: float | None = None
    max_tokens: int | None = None
    response_format: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
```

规则：

- `messages` 存在时，优先使用 `messages`；
- `messages` 不存在时，由 `system_prompt` 和 `user_prompt` 自动组装消息；
- `user_prompt` 可以是任意字符串；
- `metadata` 只给调用方做关联，不参与模型推理，除非调用方自己拼进 prompt。

### 5.4 Chat 响应

```python
from typing import Any

from pydantic import BaseModel


class LMChatResponse(BaseModel):
    text: str
    output_format: LMOutputFormat = LMOutputFormat.TEXT
    parsed: Any | None = None
    raw: Any | None = None
    model_name: str | None = None
    usage: dict[str, Any] | None = None
```

最简单调用可直接返回 `text`。如果调用方需要更多信息，再使用 `LMChatResponse`。

## 6. 客户端接口草案

### 6.1 最小接口

```python
class LMClient:
    async def chat(
        self,
        *,
        system_prompt: str | None = None,
        user_prompt: str | None = None,
        messages: list[LMMessage] | None = None,
        output_format: LMOutputFormat = LMOutputFormat.TEXT,
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> str:
        ...
```

这是业务侧最常用的方法，返回字符串。

### 6.2 完整接口

```python
class LMClient:
    async def chat_response(
        self,
        request: LMChatRequest,
    ) -> LMChatResponse:
        ...
```

`chat(...)` 可以只是 `chat_response(...)` 的便捷包装：

```python
response = await lm.chat_response(
    LMChatRequest(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        output_format=output_format,
    )
)
return response.text
```

## 7. 实现类草案

```python
class OpenAICompatibleLMClient(LMClient):
    def __init__(
        self,
        *,
        model_name: str,
        api_key: str | None,
        base_url: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1000,
        timeout_sec: float = 30.0,
    ) -> None:
        ...

    async def chat(
        self,
        *,
        system_prompt: str | None = None,
        user_prompt: str | None = None,
        messages: list[LMMessage] | None = None,
        output_format: LMOutputFormat = LMOutputFormat.TEXT,
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> str:
        response = await self.chat_response(
            LMChatRequest(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                messages=messages,
                output_format=output_format,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
            )
        )
        return response.text

    async def chat_response(self, request: LMChatRequest) -> LMChatResponse:
        ...
```

实现细节：

- 使用 async HTTP client 或 OpenAI 官方 async client；
- 请求格式贴近 `/chat/completions`；
- `output_format=json` 时，可以传 `response_format={"type": "json_object"}`，但不强制；
- provider 不支持 `response_format` 时，忽略或降级为 prompt 提示；
- 统一提取 `choices[0].message.content` 作为 `text`。

## 8. 调用示例

### 8.1 普通文本

```python
text = await lm.chat(
    system_prompt="你是一个严谨的中文报告撰写助手。",
    user_prompt="请把下面内容改写成正式报告语气：\n" + content,
)
```

### 8.2 Markdown 输出

```python
markdown = await lm.chat(
    system_prompt="你擅长输出结构清晰的 Markdown。",
    user_prompt=prompt,
    output_format=LMOutputFormat.MARKDOWN,
)
```

### 8.3 JSON 输出

```python
text = await lm.chat(
    system_prompt="只输出 JSON，不要输出解释。",
    user_prompt=prompt,
    output_format=LMOutputFormat.JSON,
    response_format={"type": "json_object"},
)
```

### 8.4 需要解析结果

```python
response = await lm.chat_response(
    LMChatRequest(
        system_prompt="只输出 JSON，不要输出解释。",
        user_prompt=prompt,
        output_format=LMOutputFormat.JSON,
    )
)

data = response.parsed
```

### 8.5 多轮消息

```python
text = await lm.chat(
    messages=[
        LMMessage(role="system", content="你是一个中文写作助手。"),
        LMMessage(role="user", content="先记住这个背景：..."),
        LMMessage(role="assistant", content="已了解。"),
        LMMessage(role="user", content="现在请生成最终文本。"),
    ]
)
```

## 9. 输出处理建议

LM 层可以提供轻量解析工具，但不应该把业务 schema 固定进去。

```python
def parse_lm_output(text: str, output_format: LMOutputFormat) -> Any | None:
    if output_format == LMOutputFormat.JSON:
        return parse_json_best_effort(text)
    return None
```

JSON 解析可以做 best-effort：

- 先尝试 `json.loads(text)`；
- 再尝试提取 fenced JSON code block；
- 再尝试截取第一个 `{` 到最后一个 `}`；
- 解析失败时 `parsed=None`，不强制抛错。

Markdown 和普通文本不需要解析，直接返回字符串。

## 10. 错误处理

定义少量通用异常即可：

```python
class LMError(Exception): ...
class LMConfigError(LMError): ...
class LMRequestError(LMError): ...
class LMTimeoutError(LMError): ...
class LMProviderError(LMError): ...
```

建议行为：

- 配置缺失：启动或构造 client 时明确报错；
- 网络超时：抛 `LMTimeoutError`；
- provider 4xx/5xx：抛 `LMProviderError`，保留状态码和简短错误信息；
- 输出解析失败：默认不抛错，只让 `parsed=None`。

## 11. 配置来源

不新增 FlyReport 专属 LM 配置，直接复用仓库已有的通用模型配置，例如 `settings.agent.model`：

```yaml
agent:
    model:
        provider: litellm
        name: gpt-5.2-chat
        api_key: ${OPENAI_API_KEY}
        base_url: ${OPENAI_BASE_URL}
        temperature: 1.0
        max_tokens: 4096
```

轻量 LM client 可以提供 `from_model_config(settings.agent.model)` 之类的便捷构造方式，但 settings 里不再新增 `fly_report.lm` 字段。

## 12. 测试建议

第一版测试只覆盖 LM 行为本身：

- `system_prompt + user_prompt` 能组装成 messages；
- 显式 `messages` 优先级高于 prompt；
- `chat(...)` 返回字符串；
- `chat_response(...)` 返回 `LMChatResponse`；
- JSON 输出可解析到 `parsed`；
- Markdown / text 输出保持原文；
- provider 超时转换为 `LMTimeoutError`；
- provider 错误转换为 `LMProviderError`。

不测试章节、不测试 composer、不测试报告渲染。

## 13. 当前结论

这次要做的是一个贴近主流 Chat Completions 设计的异步 LM client：

```text
LMClient.chat(system_prompt, user_prompt) -> str
LMClient.chat_response(LMChatRequest) -> LMChatResponse
```

它的定位是：

- 输入可以是任意字符串；
- 输出可以是普通文本、JSON、Markdown 或其他文本格式；
- JSON 解析只是可选辅助；
- 不绑定 FlyReport 章节；
- 不绑定 composer；
- 不绑定审计模型；
- 不提供 agent 行为。
