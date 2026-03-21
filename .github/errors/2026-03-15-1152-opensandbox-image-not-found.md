# OpenSandbox 镜像不存在错误记录（2026-03-15 11:52）

## 错误名称

`opensandbox-image-not-found`

## 现象

在 OpenSandbox 创建沙箱过程中出现镜像检查告警，核心日志如下：

```text
WARNING: 2026-03-15 11:52:22+0800 ...
action=inspect image opensandbox/code-interpreter:v1.0.1 ...
error=404 Client Error ... No such image: opensandbox/code-interpreter:v1.0.1
```

## 影响

- 使用 `opensandbox/code-interpreter:v1.0.1` 时，运行时可能无法找到本地镜像或无法从对应源正确拉取
- 沙箱创建失败，导致任务执行链在 `Sandbox.create()` 阶段中断

## 原因分析

1. 默认 profile 镜像使用了 `opensandbox/code-interpreter:v1.0.1`，与当前运行环境的可用镜像源不匹配
2. 官方可用示例镜像为：
   - `sandbox-registry.cn-zhangjiakou.cr.aliyuncs.com/opensandbox/code-interpreter:v1.0.1`
3. 适配器兜底策略此前只偏向公共镜像名，缺少对官方示例镜像源的优先尝试

## 解决方案（已实施）

### 1) Profile 默认镜像切换到官方示例镜像源

文件：`swarmmind/sandbox/profiles.py`

- 新增常量：
  - `DEFAULT_INTERPRETER_IMAGE = "sandbox-registry.cn-zhangjiakou.cr.aliyuncs.com/opensandbox/code-interpreter:v1.0.1"`
- `py-basic/py-full/node-basic/secure-offline` 默认镜像统一改为上述地址
- 按官方样例补充环境变量：
  - `PYTHON_VERSION=3.11`（Python profile）
- 保留标准 entrypoint：
  - `[/opt/opensandbox/code-interpreter.sh]`

### 2) 适配器创建兜底增强

文件：`swarmmind/sandbox/opensandbox_adapter.py`

新增兜底镜像顺序：
1. `sandbox-registry.cn-zhangjiakou.cr.aliyuncs.com/opensandbox/code-interpreter:v1.0.1`
2. `opensandbox/code-interpreter:v1.0.1`

在 `_create_sandbox()` 中按变体尝试：
- image + entrypoint + resource
- image + entrypoint（无 resource）

确保不同运行时/registry 可用性下更稳健。

## 验证建议

1. 重启 SwarmMind API（确保加载新 profile）
2. 提交一个最小任务（例如“写一个 hello world”）
3. 观察日志中 `Sandbox.create` 是否仍报 `No such image`
4. 若仍失败，检查 opensandbox-server 所在机器的镜像拉取权限和网络访问

## 关联改动

- `swarmmind/sandbox/profiles.py`
- `swarmmind/sandbox/opensandbox_adapter.py`

## 后续建议

1. 增加配置项覆盖默认镜像（环境变量/配置文件）
2. 在适配器异常中输出最终失败镜像列表与失败原因摘要
3. 增加 opensandbox provider 集成测试（create/run/kill）
