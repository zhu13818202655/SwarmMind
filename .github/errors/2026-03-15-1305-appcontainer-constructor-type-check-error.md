# AppContainer 构造参数类型检查误报（2026-03-15 13:05）

## 错误名称

`appcontainer-constructor-type-check-error`

## 现象

在 `swarmmind/app/container.py` 中实例化 `AppContainer(...)` 时，编辑器/类型检查器报错：

```text
No parameter named "settings"
No parameter named "event_bus"
No parameter named "cache_store"
No parameter named "long_term_memory"
...
```

将关键字参数改为位置参数后，仍可能出现：

```text
Expected 0 positional arguments
```

## 影响

- 代码可运行，但静态检查持续报错，影响开发体验
- 容易误判为调用方参数错误，增加排查成本

## 原因分析

该问题不是调用处参数名错误，而是类型检查器未正确推导 `AppContainer` 的构造签名，表现为把 `AppContainer` 识别成“无参数构造”。

在该场景下，所有命名参数都会被误报，不仅是 `long_term_memory`。

## 解决方案（已实施）

文件：`swarmmind/app/container.py`

### 1) 为 `AppContainer` 提供显式 `__init__`

- 不再依赖隐式构造签名推导
- 明确声明全部参数类型与赋值逻辑
- 保留 `__slots__` 约束字段集合

### 2) 保持调用处使用关键字参数

- `build_container()` 内 `AppContainer(...)` 继续使用可读性更高的关键字传参
- 显式 `__init__` 后，类型检查器可正确识别参数名

## 验证结果

对 `swarmmind/app/container.py` 运行诊断后：

```text
No errors found
```

## 关联改动

- `swarmmind/app/container.py`

## 后续建议

1. 如果其他“容器类/配置类”也出现相同误报，优先采用显式 `__init__` 方案
2. 对依赖 dataclass 推导签名的关键模块，建议在 CI 中补一条类型检查回归
3. 若后续切换检查器版本，优先验证 `dataclass + Protocol 类型字段` 场景
