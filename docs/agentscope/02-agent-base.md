# AgentScope: AgentBase 是什么

这篇只讲一个点: `AgentBase` 在 AgentScope 运行时里扮演什么角色。

## 定位

`AgentBase` 是 AgentScope 异步 Agent 的基础类。

它本身不定义业务行为，但把一个 Agent 在框架中运行所需的公共机制先搭好。

从当前版本实现看，它主要提供这些能力:

1. Agent 唯一 `id`。
2. `__call__()` 到 `reply()` 的统一调用入口。
3. `MsgHub` 所需的订阅与广播机制。
4. `print()` 输出能力。
5. reply 中断处理。
6. hook 注册与清理。
7. 消息队列与流式输出控制。

## 它不负责什么

`AgentBase` 不负责回答“这个 Agent 怎么思考”。

它只负责把运行时外壳搭起来。真正的业务逻辑仍然由子类实现，最核心的是:

1. `reply()`
2. `observe()`
3. `handle_interrupt()`

## 调用链要怎么理解

你平时写的是:

```python
await agent(msg)
```

但实际先进入的是 `AgentBase.__call__()`，不是直接进入 `reply()`。

这个调用入口会统一处理三件事:

1. 记录当前 reply 任务。
2. 调用子类实现的 `reply()`。
3. 在结束时把消息广播给订阅者。

可以把它理解成:

```text
agent(...) -> AgentBase.__call__() -> reply()
```

如果 reply 过程中被取消，还会转去走 `handle_interrupt()`。

## 为什么所有子类都要先 `super().__init__()`

因为 `AgentBase.__init__()` 初始化的是运行时必需结构，而不是可有可无的默认值。

它会建立:

1. `_reply_task` 和 `_reply_id`
2. 各类 instance hooks 容器
3. `_stream_prefix`
4. `_subscribers`
5. 控制台输出与消息队列开关

如果漏掉 `super().__init__()`，Agent 看起来可能能实例化，但在真实运行期很容易因为内部状态缺失而出错。

## `observe()` 和 `reply()` 的分工

这是理解 AgentBase 最重要的边界之一。

### `observe()`

只接收消息，不生成输出。

典型用途是:

1. 被 `MsgHub` 广播动接收别的 Agent 的消息。
2. 手动把外部消息塞进当前 Agent 上下文。

### `reply()`

负责真正生成响应。

通常会做:

1. 接收输入消息。
2. 更新 memory。
3. 组织上下文。
4. 调用模型或规则逻辑。
5. 返回 `Msg`。

## 中断机制为什么重要

`AgentBase` 自带 `interrupt()` 机制。

外部如果取消当前 reply，对应任务会收到 `CancelledError`，然后 `__call__()` 会转去执行 `handle_interrupt()`。

这就是为什么自定义子类时，`handle_interrupt()` 不是“可选美化项”，而是实际运行链路的一部分。

## 一句话结论

`AgentBase` 是 AgentScope 的运行时外壳。

它负责调度、广播、打印、中断和 hooks；子类负责具体智能行为。