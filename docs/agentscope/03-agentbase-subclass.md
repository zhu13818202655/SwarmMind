# AgentScope: 如何实现一个最小 AgentBase 子类

这篇只讲一个点: 基于 `AgentBase` 写出一个最小可运行子类时，最低要求是什么。

## 最小实现面

一个能工作的 `AgentBase` 子类，至少要实现这三个方法:

1. `observe()`
2. `reply()`
3. `handle_interrupt()`

同时在构造函数里必须先调用 `super().__init__()`。

## 最小骨架

```python
from agentscope.agent import AgentBase
from agentscope.message import Msg


class MyAgent(AgentBase):
    def __init__(self) -> None:
        super().__init__()
        self.name = "Friday"

    async def observe(self, msg: Msg | list[Msg] | None) -> None:
        return None

    async def reply(self, msg: Msg | list[Msg] | None = None) -> Msg:
        return Msg(
            name=self.name,
            content="你好，我是 Friday。",
            role="assistant",
        )

    async def handle_interrupt(
        self,
        *args: object,
        **kwargs: object,
    ) -> Msg:
        return Msg(
            name=self.name,
            content="我被打断了，请继续告诉我你要做什么。",
            role="assistant",
        )
```

## 每个方法到底负责什么

### `__init__()`

初始化 Agent 自己的运行依赖，比如 `name`、`memory`、`model`、`formatter`。

这里最重要的不是你设置了什么字段，而是你有没有先执行 `super().__init__()`。

### `observe()`

接收消息但不回复。

最常见的实现是把消息写进 memory:

```python
async def observe(self, msg: Msg | list[Msg] | None) -> None:
    if msg is not None:
        await self.memory.add(msg)
```

### `reply()`

生成真正的回复，返回值必须是 `Msg`，不是字符串。

### `handle_interrupt()`

当当前 reply 被取消时，给出一个兜底回复。

建议签名写宽一点，直接兼容 `*args, **kwargs`，因为 `AgentBase.__call__()` 会把原始调用参数原样转给它。

## 一个实用判断标准

如果你的子类满足下面四点，通常就算进入“可用”状态了:

1. 能被 `await agent(...)` 正常调用。
2. `reply()` 返回的是合法 `Msg`。
3. 被 `MsgHub` 广播消息时，`observe()` 不会报错。
4. 中断时 `handle_interrupt()` 可以兜住。

## 常见错误

### 把 `reply()` 写成返回 `str`

这会破坏 AgentScope 后续的消息处理链路。应当始终返回 `Msg`。

### 漏掉 `super().__init__()`

这会让 hooks、订阅关系、流式输出缓存等基础运行时结构没有初始化。

### `handle_interrupt()` 签名写得过窄

如果只写 `self`，中断时很容易因为参数不匹配而抛错。

## 一句话结论

自定义 `AgentBase` 子类时，真正的最低门槛不是“能返回一句话”，而是要完整接上 AgentScope 的调用、观察和中断契约。