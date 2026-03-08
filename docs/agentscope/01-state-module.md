# AgentScope: StateModule 是什么

这篇只讲一个点: `StateModule` 在 AgentScope 里负责什么。

## 它解决的问题

`StateModule` 是 AgentScope 里所有可序列化运行时对象的基础模块。

它的职责不是处理消息，也不是调用模型，而是把对象当前状态整理成可保存、可恢复的结构。

在当前环境里，`AgentBase` 就是继承自 `StateModule` 的，因此 Agent 的很多“可追踪状态”能力，底层都建立在它上面。

## 它提供的三项核心能力

1. 自动识别嵌套的 `StateModule` 子对象。
2. 允许显式注册普通属性为状态字段。
3. 提供 `state_dict()` 和 `load_state_dict()` 做序列化与恢复。

## 关键机制

### 1. `__setattr__`

当你给对象赋值时，如果值本身也是一个 `StateModule`，它会被自动记录到 `_module_dict`。

这意味着嵌套模块可以递归进入状态树。

### 2. `register_state()`

普通属性不会自动进状态字典，必须显式注册。

例如:

```python
from agentscope.module import StateModule


class Counter(StateModule):
    def __init__(self) -> None:
        super().__init__()
        self.name = "counter"
        self.value = 0
        self.register_state("name")
        self.register_state("value")
```

这样 `name` 和 `value` 才会出现在 `state_dict()` 结果里。

### 3. `state_dict()`

`state_dict()` 会做两件事:

1. 递归收集所有嵌套 `StateModule` 的状态。
2. 收集所有通过 `register_state()` 注册过的属性。

### 4. `load_state_dict()`

`load_state_dict()` 会按相同结构把状态写回对象。

如果 `strict=True`，缺字段会直接抛错；如果 `strict=False`，缺失字段会被跳过。

## 使用时最容易踩的坑

### 必须先调用 `super().__init__()`

这是最关键的一点。

因为 `_module_dict` 和 `_attribute_dict` 都是在 `StateModule.__init__()` 里初始化的。如果你在这之前就给对象挂一个 `StateModule` 子对象，会直接报错。

### 默认要求属性可 JSON 序列化

如果你注册的属性不是原生可 JSON 序列化的数据，需要给 `register_state()` 提供自定义转换函数。

例如:

```python
self.register_state(
    "config",
    custom_to_json=lambda value: value.to_dict(),
    custom_from_json=lambda raw: Config.from_dict(raw),
)
```

## 什么时候该想到它

如果你要做下面这些事，就该先想到 `StateModule`:

1. 保存 Agent 运行时状态。
2. 恢复某个 Agent 的工作上下文。
3. 给自定义 Agent、memory、tool 容器增加可持久化字段。

## 一句话结论

`StateModule` 是 AgentScope 运行时对象的“状态骨架”。

它不负责智能决策，但负责让对象状态可递归记录、可恢复、可检查。