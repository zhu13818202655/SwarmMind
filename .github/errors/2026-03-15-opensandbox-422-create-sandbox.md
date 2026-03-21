# OpenSandbox 422 创建沙箱错误记录（2026-03-15）

## 问题摘要

在 SwarmMind 的执行链路中，`ExecutionRunner -> SandboxManager -> OpenSandboxAdapter` 调用 OpenSandbox 创建沙箱时连续失败：

- 错误类型：`SandboxApiException`
- 接口行为：`Create sandbox failed: HTTP 422`
- 影响范围：使用 `opensandbox` provider 时，子任务无法创建沙箱，执行链中断

## 现场报错

典型报错：

```text
Failed to create sandbox with image: opensandbox/code-interpreter:python3.11
...
opensandbox.exceptions.sandbox.SandboxApiException: Create sandbox failed: HTTP 422
```

## 影响评估

- `subtask.assigned` 后续无法进入实际命令执行
- `run` 可能停在失败路径（取决于重试与收敛逻辑）
- 依赖 OpenSandbox 的真实执行场景不可用

## 原因分析

结合 OpenSandbox 文档和当前适配器实现，422 主要由**创建参数与服务端 schema 不兼容**引起，重点包括：

1. 镜像标签兼容性
   - 原配置使用：`opensandbox/code-interpreter:python3.11`（及其衍生 tag）
   - 目标服务对该 tag 不接受或不可用时，会触发参数校验失败

2. `entrypoint` 结构不兼容
   - 原 `SandboxProfile.entrypoint` 定义为字符串
   - OpenSandbox 常见创建示例使用列表（如 `[/opt/opensandbox/code-interpreter.sh]`）

3. `resourceLimits` 值格式不兼容
   - 原配置为整数（如 `cpu: 2, memory: 2048`）
   - OpenSandbox 生命周期 API 常用字符串资源格式（如 `1000m`, `1024Mi`）

## 解决方案（已落地）

### 1) 标准化 profile 参数

文件：`swarmmind/sandbox/profiles.py`

- `entrypoint` 从 `str` 改为 `list[str] | None`
- `resource_limits` 从 `dict[str, int] | None` 改为 `dict[str, str] | None`
- 默认镜像统一调整为文档可用值：`opensandbox/code-interpreter:v1.0.1`
- 默认 entrypoint 调整为：`["/opt/opensandbox/code-interpreter.sh"]`
- 资源值改为字符串规格（例如 `1000m` / `1024Mi`）

### 2) 增加创建兜底变体

文件：`swarmmind/sandbox/opensandbox_adapter.py`

在 `_create_sandbox()` 中加入多变体兼容重试逻辑（按序尝试）：

1. profile 原样（image + entrypoint + resource）
2. profile 去掉 resource
3. fallback 镜像/entrypoint（`v1.0.1` + 标准 entrypoint）+ resource
4. fallback 镜像/entrypoint 去掉 resource

目的：规避不同 OpenSandbox Server 版本对字段校验差异导致的单点失败。

## 验证方式

1. 语法/可执行性检查
   - 使用 `py_compile` 检查更新文件可导入

2. 功能验证（建议）
   - 启动 API
   - 提交简单 goal（例如“写一个 hello world”）
   - 观察是否仍出现 `Create sandbox failed: HTTP 422`

## 回归风险与注意事项

1. 如果服务端 schema 与当前 SDK 存在更深层不兼容，仍可能 422
2. 兜底变体会提升成功率，但不是对未知 schema 的绝对保证
3. 若仍失败，需要抓取服务端响应 body（而不只 status code）继续对齐

## 后续改进建议

1. 在 `OpenSandboxAdapter` 中记录最后一次失败请求参数摘要（脱敏）
2. 在异常中附带响应 body 关键字段，提升定位效率
3. 增加一条集成测试：在 opensandbox provider 下完成最小 create/run/kill 验证

## 关联代码

- `swarmmind/sandbox/profiles.py`
- `swarmmind/sandbox/opensandbox_adapter.py`
- `swarmmind/sandbox/manager.py`
- `swarmmind/orchestration/execution_runner.py`
