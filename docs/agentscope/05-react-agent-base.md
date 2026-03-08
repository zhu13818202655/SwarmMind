# AgentScope: ReActAgentBase 增加了什么

这篇只讲一个点: `ReActAgentBase` 相比 `AgentBase` 多出来的运行时抽象是什么。

## 定位

`ReActAgentBase` 继承自 `AgentBase`，但它不是一个完整可直接使用的 Agent。

它是为 ReAct 模式准备的中间基类，把 Agent 的内部执行拆成两个明确阶段:

1. `_reasoning()`
2. `_acting()`

## 它比 `AgentBase` 多出来什么

`AgentBase` 只要求你实现“接收消息”和“生成回复”。

`ReActAgentBase` 进一步要求你把“思考”和“执行动作”拆开。

因此它新增了两类抽象方法:

```python
async def _reasoning(...):
    ...

async def _acting(...):
    ...
```

这意味着继承它的类，不只是要回答，还要显式描述:

1. 模型如何产出下一步推理结果。
2. 工具调用或动作执行如何落地。

## 它新增的另一个核心能力: hooks 扩展位点

`ReActAgentBase` 在原有 hooks 基础上，又增加了四种钩子:

1. `pre_reasoning`
2. `post_reasoning`
3. `pre_acting`
4. `post_acting`

这让你可以在不改核心逻辑的情况下，插入:

1. 推理前的上下文修正。
2. 推理后的结果审计。
3. 工具执行前的校验。
4. 工具执行后的回写或观测。

## 初始化时多做了什么

`ReActAgentBase.__init__()` 在调用 `super().__init__()` 之后，还会建立四个实例级 hook 容器:

1. `_instance_pre_reasoning_hooks`
2. `_instance_post_reasoning_hooks`
3. `_instance_pre_acting_hooks`
4. `_instance_post_acting_hooks`

所以它本质上是把 `AgentBase` 的“reply 级运行时”继续细分成“reasoning/acting 级运行时”。

## 应该怎么理解它和 `ReActAgent` 的关系

可以把两者关系理解成:

1. `ReActAgentBase` 定义 ReAct 协议。
2. `ReActAgent` 提供默认实现。

也就是说，`ReActAgentBase` 解决的是“ReAct Agent 该由哪些阶段组成”，不是“这些阶段具体怎么实现”。

## 什么时候应该关注它

只有在下面这些场景里，它才值得单独研究:

1. 你要自定义 ReAct 型 Agent。
2. 你要在 reasoning 或 acting 阶段插 hook。
3. 你想替换默认 `ReActAgent` 的某一段内部流程。

如果你只是想跑一个现成的带工具调用 Agent，通常直接用 `ReActAgent` 就够了。

## 一句话结论

`ReActAgentBase` 的价值不在于“多了几个方法”，而在于它把 `AgentBase` 的单段回复流程，升级成了可插拔的 ReAct 双阶段执行框架。