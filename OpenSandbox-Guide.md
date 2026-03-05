# OpenSandbox 操作指南（启动、资源分配、命令执行）

> 面向 SwarmMind 项目的实操手册：如何把 OpenSandbox 跑起来，并稳定用于“多智能体任务执行环境”。

---

## 1. OpenSandbox 在你的系统里扮演什么角色

OpenSandbox 是 **沙箱控制平面**：
- 负责创建/查询/销毁 sandbox（生命周期 API）
- 把 sandbox 跑在 Docker 或 Kubernetes
- 对 sandbox 内提供命令执行、文件操作、代码执行能力（通过 execd）

建议你在 SwarmMind 内使用“适配层”调用 OpenSandbox，而不是直接写 Docker/K8s 指令。

---

## 2. 运行前准备（Windows 场景）

## 2.1 基础依赖

- Python 3.10+
- `uv`（推荐）或 `pip`
- Docker Desktop（启用 WSL2）
- 如果要上 K8s：可用集群 + `kubectl`

## 2.2 Windows 注意事项

- 官方推荐运行环境是 Linux/macOS，Windows 建议通过 WSL2 使用。
- 若 OpenSandbox Server 在容器中运行，且用 bridge 网络，请设置 `host_ip`（例如 `host.docker.internal`）。

---

## 3. 最快启动（Docker 本地）

## 3.1 安装 server

```powershell
uv pip install opensandbox-server
```

## 3.2 生成配置

```powershell
opensandbox-server init-config ~/.sandbox.toml --example docker
```

## 3.3 编辑配置（最小可用模板）

```toml
[server]
host = "0.0.0.0"
port = 45698
log_level = "INFO"
api_key = "change-me-strong-key"

[runtime]
type = "docker"
execd_image = "opensandbox/execd:v1.0.6"

[docker]
network_mode = "bridge"    # 推荐 bridge；host 模式隔离较弱且并发受限
host_ip = "host.docker.internal"

# 可选安全增强
drop_capabilities = ["AUDIT_WRITE", "MKNOD", "NET_ADMIN", "NET_RAW", "SYS_ADMIN", "SYS_MODULE", "SYS_PTRACE", "SYS_TIME", "SYS_TTY_CONFIG"]
no_new_privileges = true
pids_limit = 512
```

## 3.4 启动服务

```powershell
opensandbox-server --config ~/.sandbox.toml
```

## 3.5 健康检查

```powershell
curl http://localhost:45698/health
```

预期：

```json
{"status":"healthy"}
```

---

## 4. 如何“分配资源”（CPU/内存/GPU）

资源不是在 server 全局配置里固定，而是 **创建 sandbox 时按请求指定**。

## 4.1 生命周期 API 中传资源

`POST /v1/sandboxes` 请求体示例：

```json
{
  "image": {"uri": "python:3.11-slim"},
  "entrypoint": ["python", "-m", "http.server", "8000"],
  "timeout": 3600,
  "resourceLimits": {
    "cpu": "500m",
    "memory": "512Mi",
    "gpu": "1"
  },
  "env": {
    "PYTHONUNBUFFERED": "1"
  },
  "metadata": {
    "task_id": "task-123",
    "agent_id": "coder-agent"
  }
}
```

## 4.2 资源规划建议（给 SwarmMind）

- `py-basic`：`cpu=500m~1`, `memory=512Mi~1Gi`
- `test-heavy`：`cpu=1~2`, `memory=2Gi`
- `browser/GUI`：`cpu>=2`, `memory>=4Gi`
- 每类任务绑定 profile，避免 agent 随意申请资源。

---

## 5. 生命周期 API：完整控制流程

假设 API Key 放在环境变量：

```powershell
$env:OPEN_SANDBOX_API_KEY="change-me-strong-key"
```

Ubuntu/Linux（bash/zsh）：

```bash
export OPEN_SANDBOX_API_KEY="osb_4f9d1c3a7b8e2f6049a1d5e7c2b3f8a6c9d0e1f2a3b4c5d6"
```

## 5.1 创建 sandbox

```bash
curl -X POST "http://localhost:45698/v1/sandboxes" \
  -H "OPEN-SANDBOX-API-KEY: $OPEN_SANDBOX_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "image":{"uri":"python:3.11-slim"},
    "entrypoint":["python","-m","http.server","8000"],
    "timeout":3600,
    "resourceLimits":{"cpu":"500m","memory":"512Mi"}
  }'
```

## 5.2 查询 sandbox

```powershell
curl -H "OPEN-SANDBOX-API-KEY: $env:OPEN_SANDBOX_API_KEY" \
  "http://localhost:45698/v1/sandboxes/<sandbox_id>"
```

## 5.3 获取端口访问地址

```powershell
curl -H "OPEN-SANDBOX-API-KEY: $env:OPEN_SANDBOX_API_KEY" \
  "http://localhost:45698/v1/sandboxes/<sandbox_id>/endpoints/8000"
```

## 5.4 续期（TTL）

```powershell
curl -X POST "http://localhost:45698/v1/sandboxes/<sandbox_id>/renew-expiration" `
  -H "OPEN-SANDBOX-API-KEY: $env:OPEN_SANDBOX_API_KEY" `
  -H "Content-Type: application/json" `
  -d '{"expiresAt":"2026-03-05T15:00:00Z"}'
```

## 5.5 删除 sandbox

```powershell
curl -X DELETE \
  -H "OPEN-SANDBOX-API-KEY: $env:OPEN_SANDBOX_API_KEY" \
  "http://localhost:45698/v1/sandboxes/<sandbox_id>"
```

---

## 6. 如何“接收命令并执行”

你有两种方式：

## 6.1 方式 A（推荐）：通过 OpenSandbox SDK

适合 SwarmMind 的 `SandboxProvider` 适配层，最稳定。

```python
import asyncio
from datetime import timedelta
from opensandbox import Sandbox
from opensandbox.models import WriteEntry

async def main():
    sandbox = await Sandbox.create(
        "opensandbox/code-interpreter:v1.0.1",
        entrypoint=["/opt/opensandbox/code-interpreter.sh"],
        timeout=timedelta(minutes=10),
    )

    async with sandbox:
        # 执行命令
        execution = await sandbox.commands.run("echo 'hello from sandbox'")
        print(execution.logs.stdout[0].text)

        # 写文件
        await sandbox.files.write_files([
            WriteEntry(path="/tmp/a.txt", data="hello", mode=644)
        ])

        # 读文件
        content = await sandbox.files.read_file("/tmp/a.txt")
        print(content)

    await sandbox.kill()

asyncio.run(main())
```

> 建议：SwarmMind 的 Agent 不要直接碰 SDK，而是通过你自己的 `run_command/read_file/write_file` 工具封装。

## 6.2 方式 B：直接调用 execd HTTP API

适合你要做“协议级控制”或流式输出（SSE）时使用。

execd 关键接口（官方 specs）：
- `POST /command`：执行 shell 命令（支持流式输出）
- `GET /command/status/{session}`：查会话状态
- `GET /command/output/{session}`：取 stdout/stderr
- `POST /code`：执行代码
- `GET /metrics`：资源指标

认证头为：`X-EXECD-ACCESS-TOKEN`

> 注意：access token 的获取与透传应由生命周期层/SDK 管理，建议优先 SDK 方式，减少你自己维护协议细节的成本。

---

## 7. 网络与安全（生产必做）

## 7.1 API 鉴权

- server 配置 `api_key` 后，除 `/health` `/docs` `/redoc` 外均需 `OPEN-SANDBOX-API-KEY`。
- 生产必须启用非空 key，并放到 Secret 管理系统。

## 7.2 网络模式

- `docker.network_mode=host`：性能优先，但隔离弱、并发受限。
- `docker.network_mode=bridge`：隔离更好，推荐生产；必要时用 proxy endpoint。

## 7.3 外网访问控制（networkPolicy）

- 如需按域名白名单控制 egress，需配置 `[egress].image`。
- 仅 bridge 模式支持 networkPolicy。

## 7.4 安全基线

- 非 root 运行容器
- `no_new_privileges=true`
- `drop_capabilities` 最小化
- 合理 `pids_limit`
- 敏感日志脱敏（token/path/key）

---

## 8. K8s 部署要点（第二阶段）

## 8.1 初始化配置

```powershell
opensandbox-server init-config ~/.sandbox.toml --example k8s
```

## 8.2 关键配置项

```toml
[runtime]
type = "kubernetes"
execd_image = "opensandbox/execd:v1.0.5"

[kubernetes]
kubeconfig_path = "~/.kube/config"
namespace = "opensandbox"
workload_provider = "batchsandbox"  # 或 agent-sandbox
```

## 8.3 生产建议

- 配置 namespace 资源配额（ResourceQuota）
- 按租户打标签并限流
- 接入 OTel 追踪：`task_id/sandbox_id/agent_id`
- 结合 HPA/VPA 做弹性

---

## 9. 给 SwarmMind 的最小落地路径（建议一周内完成）

1. 本地 Docker 模式跑通 server + 创建/删除 sandbox。
2. 封装 `SandboxProvider`（`create/run_command/write/read/kill`）。
3. 把 CoderAgent、TesterAgent 的执行都路由到该 provider。
4. 在每次创建请求写入 `metadata.task_id/agent_id/subtask_id`。
5. 接入 TTL 续期与兜底清理（任务结束必须删除 sandbox）。
6. 增加失败重试：创建失败指数退避 2~3 次。

---

## 10. 常见问题排查

- `401/403`：检查 `OPEN-SANDBOX-API-KEY` 是否与 server 配置一致。
- sandbox 能创建但端口访问不到：bridge 模式下检查 `host_ip` 与 endpoint 解析。
- networkPolicy 不生效：确认 bridge 模式 + 已配置 `[egress].image`。
- 资源超限失败：下调并发或提高 profile 的 CPU/内存上限。
- sandbox 泄漏：启用 TTL + 周期性清理任务 + 任务结束强制 delete。

---

## 11. 你下一步可以直接执行的命令

```powershell
uv pip install opensandbox-server
opensandbox-server init-config ~/.sandbox.toml --example docker
opensandbox-server --config ~/.sandbox.toml
curl http://localhost:45698/health
```

确认健康后，再用第 5 节的 `POST /v1/sandboxes` 创建第一个沙箱。
