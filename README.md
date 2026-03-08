# SwarmMind Sandbox Data Analysis Demo

This project demonstrates a complete flow for sandboxed Python data analysis:

1. Create an ephemeral OpenSandbox container.
2. Prepare environment inside the sandbox.
3. Write and execute analysis code.
4. Read back analysis results.
5. Destroy the sandbox in `finally`.

## Project Layout

- `swarmmind/sandbox/provider.py`: provider abstraction and core models.
- `swarmmind/sandbox/opensandbox_adapter.py`: OpenSandbox SDK implementation.
- `swarmmind/sandbox/profiles.py`: profile-to-resource mapping.
- `swarmmind/services/data_analysis_service.py`: data analysis task service.
- `swarmmind/cli.py`: command-line entrypoint.
- `examples/sales.json`: sample input data.

## Prerequisites

- Python 3.10+
- Running OpenSandbox server (default: `http://localhost:45698`)
- `OPEN_SANDBOX_API_KEY` set in your shell

## Install

```bash
pip install -e .
```

## Environment Variables

```bash
export OPEN_SANDBOX_API_KEY="change-me-strong-key"
export OPEN_SANDBOX_BASE_URL="http://localhost:45698"
export OPEN_SANDBOX_CREATE_RETRIES="3"
export OPEN_SANDBOX_CREATE_BACKOFF_SECONDS="1.0"
```

## Run Example

```bash
python -m swarmmind.cli \
  --input examples/sales.json \
  --task-id task-001 \
  --agent-id data-agent \
  --subtask-id analysis-01 \
  --profile data-medium
```

Expected output is a JSON payload with:

- `sandbox_id`
- `success`
- `stdout` / `stderr`
- `result` (row count, columns, numeric stats, optional `sales_summary`)

## Notes

- The service installs `pandas` and `numpy` in the sandbox on each run.
- For production, use a prebuilt image with dependencies baked in.
- Sandbox cleanup is guaranteed by a `finally` block in the service.


```puml
@startuml
title SwarmMind 数据分析流程（CLI -> OpenSandbox）

actor User
participant "CLI\nswarmmind.cli" as CLI
participant "DataAnalysisService\nservices/data_analysis_service.py" as SVC
participant "OpenSandboxAdapter\nsandbox/opensandbox_adapter.py" as ADP
participant "OpenSandbox SDK\nSandbox" as SDK
participant "Sandbox Container\npython:3.11-slim" as BOX

User -> CLI: python -m swarmmind.cli --input ... --task-id ...
CLI -> CLI: 读取 .env / 参数\nload_settings()
CLI -> SVC: run(DataAnalysisRequest)

SVC -> ADP: create(profile, metadata)
loop 最多 create_retry_count 次
  ADP -> SDK: Sandbox.create(...)\n(resource/connection_config)
  SDK -> BOX: 创建临时容器 + 健康检查
  SDK --> ADP: sandbox(id)
end
ADP --> SVC: SandboxHandle(sandbox_id)

SVC -> ADP: run_command("pip install pandas numpy")
ADP -> SDK: sandbox.commands.run(...)
SDK -> BOX: 安装依赖
SDK --> ADP: Exec result
ADP --> SVC: ExecResult(exit_code, stdout, stderr)

SVC -> ADP: write_files(input.json, run_analysis.py)
ADP -> SDK: sandbox.files.write_files(...)
SDK -> BOX: 写入文件
SDK --> ADP: ok

SVC -> ADP: run_command("python /tmp/run_analysis.py")
ADP -> SDK: sandbox.commands.run(...)
SDK -> BOX: 执行分析脚本
BOX --> SDK: 生成 /tmp/result.json + stdout
SDK --> ADP: execution logs/error
ADP --> SVC: ExecResult

alt exit_code == 0
  SVC -> ADP: read_file("/tmp/result.json")
  ADP -> SDK: sandbox.files.read_file(...)
  SDK -> BOX: 读取结果文件
  SDK --> ADP: json text
  ADP --> SVC: result payload
else exit_code != 0
  SVC -> SVC: 组装失败结果(stderr)
end

SVC -> ADP: kill(sandbox_id)\n(finally 保证执行)
ADP -> SDK: sandbox.kill()
ADP -> SDK: sandbox.close()
SDK -> BOX: 销毁容器 + 释放连接
SDK --> ADP: done

SVC --> CLI: DataAnalysisResult
CLI --> User: 打印 JSON（success/exit_code/result）

@enduml
```