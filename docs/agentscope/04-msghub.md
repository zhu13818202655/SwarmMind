# AgentScope: MsgHub 是怎么工作的

这篇只讲一个点: `MsgHub` 如何把多个 Agent 串成一个自动广播的协作会话。

## 定位

`MsgHub` 是 AgentScope 里的消息广播上下文管理器。

它的核心价值不是“替你调模型”，而是帮你管理一组 Agent 之间的订阅关系，让某个 Agent 的回复可以自动广播给其他参与者。

## 你可以把它理解成什么

如果没有 `MsgHub`，三个 Agent 协作时，你通常要手动写很多这样的代码:

```python
msg = await agent1(...)
await agent2.observe(msg)
await agent3.observe(msg)
```

`MsgHub` 做的就是把这套广播动作收拢成统一上下文。

## 最小使用方式

```python
async with MsgHub(participants=[alice, bob, moderator]):
    await alice(Msg("user", "请先给出方案。", "user"))
    await bob(Msg("user", "请给出不同观点。", "user"))
```

在这个上下文里，参与者的回复会自动广播给其他参与者。

## 它在进入上下文时做了什么

`MsgHub.__aenter__()` 里会先调用 `_reset_subscriber()`。

这一步会遍历所有参与者，并对每个 Agent 执行:

```python
agent.reset_subscribers(self.name, self.participants)
```

而 `AgentBase.reset_subscribers()` 会把“除了自己之外的其他参与者”记录到当前 Agent 的 `_subscribers` 中。

结果就是:

1. 每个 Agent 都知道同一个 hub 里的其他成员是谁。
2. 后续只要某个 Agent 完成 `reply()`，它的输出就能在 `AgentBase.__call__()` 的结尾被广播出去。

## 自动广播是在哪一步发生的

自动广播不在 `MsgHub` 主循环里，而是在 `AgentBase.__call__()` 的 `finally` 阶段。

也就是说，真实链路是:

1. `MsgHub` 负责先把订阅关系装好。
2. 某个 Agent 执行 `reply()`。
3. `AgentBase.__call__()` 调用 `_broadcast_to_subscribers()`。
4. 其他参与者通过 `observe()` 收到消息。

这也是为什么 `MsgHub` 能做到“你只调用一个 Agent，其他 Agent 也能看到结果”。

## 什么时候不该把所有人都放进去

如果某个 Agent 不应该自动看到所有上下文，就不该放在同一个 `MsgHub` 里。

当前仓库里的 `demo2.py` 就是一个典型例子: `alice` 和 `bob` 在 hub 里辩论，而主持人额外单独调用，这样主持人的判断不会再反向污染辩论者的记忆。

## 手动广播也可以

如果你只想用它做一次性广播，可以:

1. 传入 `announcement`
2. 调 `broadcast()`
3. 或关闭 `enable_auto_broadcast`

这样它就不再负责 reply 完成后的自动扩散。

## 一句话结论

`MsgHub` 的本质不是“多 Agent 调度器”，而是“参与者订阅关系管理器 + 自动广播上下文”。