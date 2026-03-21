# OpenSandbox ReadTimeout 错误记录（2026-03-15 12:10）

## 错误名称

`opensandbox-httpx-read-timeout`

## 现象

在任务执行链中调用 OpenSandbox 创建沙箱时抛出：

```text
httpx.ReadTimeout
```

调用栈落在 `httpx/_client.py` 的异步请求发送路径，表现为请求等待超时。

## 影响

- `ExecutionRunner` 在 `sandbox_manager.acquire()` 阶段失败
- 子任务无法进入实际执行
- run/task 进入失败分支或重试消耗较长时间

## 原因分析

1. OpenSandbox SDK `ConnectionConfig` 默认 `request_timeout=30s`
2. 在镜像拉取较慢、Docker 资源紧张或服务端响应慢时，30 秒不足
3. 请求在 SDK 的 HTTP 层先超时，导致业务链路直接失败

## 解决方案（已实施）

### 1) 新增可配置请求超时

文件：`swarmmind/config/schema.py`

新增字段：
- `sandbox.request_timeout_seconds`（默认 180）
- 支持环境变量：`OPEN_SANDBOX_REQUEST_TIMEOUT_SECONDS`

### 2) 默认配置加入超时参数

文件：`configs/default.yaml`

```yaml
sandbox:
  request_timeout_seconds: 180
```

### 3) 配置透传到 OpenSandboxAdapter

文件：`swarmmind/app/container.py`

- 在构建 `OpenSandboxAdapter` 时注入：
  - `request_timeout_seconds=settings.sandbox.request_timeout_seconds`

### 4) 适配器连接配置应用超时

文件：`swarmmind/sandbox/opensandbox_adapter.py`

- `OpenSandboxAdapter.__init__` 新增参数：`request_timeout_seconds`
- `_build_connection_config(...)` 增加 `request_timeout=timedelta(seconds=...)`
- 设置最小下限 30 秒，避免误配过小

## 验证建议

1. 重启 API，确保新配置生效
2. 使用 opensandbox provider 提交任务
3. 如仍偶发超时，逐步提高：
   - `OPEN_SANDBOX_REQUEST_TIMEOUT_SECONDS=300`

## 关联改动

- `swarmmind/config/schema.py`
- `configs/default.yaml`
- `swarmmind/app/container.py`
- `swarmmind/sandbox/opensandbox_adapter.py`

## 后续建议

1. 对 `ReadTimeout` 做分类日志（记录当前 timeout 配置与重试次数）
2. 增加 OpenSandbox 慢启动场景的集成测试
3. 在提交脚本中提供 opensandbox 连通性预检查命令
