# AgentScope: ReActAgent 是怎么把 reasoning 和 acting 串起来的

这篇只讲一个点: `ReActAgent` 在一次 `reply()` 里，如何把 `_reasoning()` 和 `_acting()` 串成一个可退出的执行循环。

## 先说结论

`ReActAgent` 不是简单地“先思考一次，再执行一次”。

它真正做的是一个循环:

1. 先做一次 reasoning。
2. 从 reasoning 结果里提取 `tool_use`。
3. 对每个 `tool_use` 执行 acting。
4. 判断是否已经满足退出条件。
5. 如果还没满足，就继续下一轮 reasoning。

可以把它理解成:

```text
reply()
  -> reasoning
  -> acting
  -> check exit
  -> reasoning
  -> acting
  -> ...
```

## 整体入口在哪

这套串联逻辑发生在 `ReActAgent.reply()` 里。

它在进入循环前，先做三类准备:

1. 把输入消息写进 memory。
2. 从长时记忆和知识库里补上下文。
3. 根据是否需要 `structured_model`，配置 tool 调用策略。

这里最关键的控制变量是 `tool_choice`。

它可能是:

1. `auto`
2. `required`
3. `none`

这个变量决定下一轮 reasoning 时，模型是否允许调用工具、必须调用工具，还是只能出文本。

## 主循环长什么样

`reply()` 的主循环本质上就是:

```python
for _ in range(self.max_iters):
    await self._compress_memory_if_needed()
    msg_reasoning = await self._reasoning(tool_choice)
    structured_outputs = await self._acting(...tool calls...)
    check exit condition
```

这里有三个关键阶段。

## 第一段: `_reasoning()` 负责产出“下一步”

`_reasoning()` 会把当前系统提示词和 memory 一起格式化后送给模型。

它的输出不是单纯字符串，而是一个 `Msg`，其中可能包含:

1. 文本块 `text`
2. 工具调用块 `tool_use`
3. 其他内容块

也就是说，reasoning 的结果本身就已经是在表达“我下一步想说什么”以及“我下一步想调用什么工具”。

这一步的核心不是完成任务，而是产出可执行意图。

## 第二段: `_acting()` 负责执行 reasoning 里声明的动作

`reply()` 会从 `msg_reasoning` 里把所有 `tool_use` 块拿出来，然后逐个传给 `_acting()`。

逻辑上相当于:

```python
for tool_call in msg_reasoning.get_content_blocks("tool_use"):
    await self._acting(tool_call)
```

如果打开了 `parallel_tool_calls=True`，这些调用会并发执行；否则按顺序执行。

所以 `_acting()` 不是自己决定要调什么工具，它只是执行 `_reasoning()` 已经决定好的动作。

这也是 ReAct 拆分的关键边界:

1. `_reasoning()` 负责决定。
2. `_acting()` 负责落地。

## 第三段: `reply()` 负责判断要不要继续下一轮

`ReActAgent` 真正把 reasoning 和 acting 串起来的，不是某个单独方法，而是 `reply()` 在 acting 结束后做的退出判断。

这里分两种情况。

### 情况一: 不要求结构化输出

如果当前没有 `structured_model` 约束，只要这一轮 reasoning 没再产出 `tool_use`，循环就结束。

也就是:

1. reasoning 只输出文本。
2. acting 没有可执行工具。
3. `reply()` 认为任务可以结束。

这时 `msg_reasoning` 本身就会作为最终回复返回。

### 情况二: 要求结构化输出

如果传了 `structured_model`，情况会更严格。

这时 `reply()` 会先把一个名为 `generate_response` 的工具注册进 toolkit，并把 `tool_choice` 设为 `required`。

换句话说，Agent 不是“最好输出结构化结果”，而是“必须通过工具调用产出结构化结果”。

随后分三种分支:

1. 如果 acting 阶段已经拿到了结构化输出，就缓存它。
2. 如果这一轮 reasoning 已经同时给出了文本，就直接复用这段文本作为最终回复。
3. 如果拿到了结构化输出但还没有最终文本，就插入一个 hint，让下一轮 reasoning 只生成文本。

这就是为什么你会看到它在某些分支里把 `tool_choice` 改成 `none`。因为结构化结果已经齐了，下一轮只需要“把话说出来”，不需要再调工具。

## 为什么它能一轮轮收敛

这套设计能工作的关键，不是 `_reasoning()` 或 `_acting()` 单独多强，而是 `reply()` 会不断调整下一轮约束。

典型控制手段有三个:

1. 改 `tool_choice`
2. 往 memory 里插入 hint message
3. 修改 `self._required_structured_model` 的状态

这三件事结合起来，就把“先产出结构化结果，再产出自然语言结果”拆成了多轮可控流程。

## 如果一直收敛不了怎么办

`ReActAgent` 不会无限循环。

它受 `max_iters` 限制。超过上限还没有得到最终回复，就会走 `_summarizing()`，用总结模式生成一个兜底回复。

所以它的整体策略不是“保证一定完成”，而是“在受控迭代次数内尽量完成，否则给出当前状态总结”。

## 和 `ReActAgentBase` 的区别

如果说 `ReActAgentBase` 定义的是抽象协议:

1. 有 reasoning 阶段
2. 有 acting 阶段

那么 `ReActAgent` 补上的就是具体编排逻辑:

1. 什么时候先 reasoning
2. 什么时候执行 acting
3. 什么条件下结束循环
4. 什么时候强制工具调用
5. 什么时候退化成只生成文本

所以真正把两个阶段“串起来”的，是 `ReActAgent.reply()` 这一层调度。

## 一句话结论

`ReActAgent` 的核心不是拥有 `_reasoning()` 和 `_acting()` 两个方法，而是它在 `reply()` 中把这两个阶段放进一个带退出条件、带 hint 调整、带 tool 策略切换的迭代闭环里。