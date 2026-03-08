# Docker 源修复与重启全流程记录（注意事项版）

## 1. 本次目标

1. 修复 Docker 拉镜像不稳定问题。
2. 在可控风险下重启 Docker。
3. 恢复原有容器/镜像可见性（`data-root`）。
4. 修复 `unknown or invalid runtime name: nvidia` 问题。

---

## 2. 关键现象与根因

### 2.1 镜像拉取失败的实际原因

1. 部分镜像源不可用或受限：
- `docker.mirrors.ustc.edu.cn`、`hub-mirror.c.163.com` 在当前环境 DNS 解析失败。
- 部分镜像源对特定仓库有白名单限制（会出现 `allowlist` 或 `forbidden`）。

2. 回退到官方仓库时网络超时：
- `registry-1.docker.io` 在当前网络下出现 `Client.Timeout exceeded while awaiting headers`。

### 2.2 为什么会出现“镜像好像被清空”

1. 核心原因不是 `docker restart` 本身，而是 `daemon.json` 中临时丢失了历史 `data-root` 配置。
2. Docker 启动后读取了另一个数据目录（默认是 `/var/lib/docker`），看起来像“容器和镜像都没了”。
3. 把 `data-root` 改回原路径（本次是 `/disk1/docker`）并重启后，历史对象重新可见。

---

## 3. 本次最终有效配置要点

`/etc/docker/daemon.json` 需要同时包含三类信息：

1. `data-root`：
- 必须和历史环境一致（本次为 `/disk1/docker`）。

2. `registry-mirrors`：
- 仅保留当前可用源，减少无效回退。

3. `runtimes.nvidia`：
- 让使用 GPU runtime 的容器可以正常启动。

建议结构（示意）：

```json
{
  "data-root": "/disk1/docker",
  "registry-mirrors": [
    "https://docker.1ms.run",
    "https://hub.rat.dev",
    "https://docker.1panel.live"
  ],
  "dns": ["223.5.5.5", "119.29.29.29", "8.8.8.8"],
  "runtimes": {
    "nvidia": {
      "path": "nvidia-container-runtime",
      "runtimeArgs": []
    }
  }
}
```

---

## 4. 重启前后必须做的检查

### 4.1 重启前

1. 备份 `daemon.json`（可回滚）。
2. 记录 `docker info`、`docker ps -a` 快照。
3. 处理重启策略风险：
- 运行中容器尽量使用 `always` 或 `unless-stopped`。

### 4.2 重启后

1. 检查 Docker 服务状态为 `active`。
2. 检查 `DataRoot` 是否正确。
3. 检查 `Runtimes` 是否包含 `nvidia`。
4. 做拉取验证（基础镜像 + 业务关键镜像）。
5. 抽查关键业务容器状态。

---

## 5. 容器重启策略实践结论

1. `docker update --restart unless-stopped <container>` 一般不会中断当前容器，可用于降低 daemon 重启风险。
2. `AutoRemove=true` 的容器无法更新 restart policy，需要按原参数重新创建。
3. 对 compose 管理的容器，后续应把 `restart:` 写回 compose 文件，避免下次 `up` 覆盖。

---

## 6. `practical_chatterjee` 的特殊说明

1. 该容器是 `AutoRemove=true`，不能直接改 restart policy。
2. 缺少 compose 标签，属于临时 `docker run` 风格容器。
3. 若 Docker 重启后消失，需要按反推参数手动重建。

---

## 7. 常见误区（这次已踩过）

1. 只改镜像源，不保留历史 `data-root`。
2. 只看 `daemon.json` 内容，不核对 `docker info` 实际生效值。
3. 忽略 `nvidia` runtime，导致业务容器启动报错。
4. 一次性加太多镜像源，反而引入无效/限流源。

---

## 8. 后续建议（稳定性）

1. 固化一份标准 `daemon.json` 模板（含 `data-root`、`runtimes`、镜像源、DNS）。
2. 每次变更前自动备份并写入时间戳。
3. 维护一份“可用镜像源白名单”，定期健康检查。
4. 把关键容器改为 `unless-stopped` 或 `always`。
5. 对 GPU 业务机器，安装/升级 Docker 后都要复核 `Runtimes`。

---

## 9. 一句话总结

这次问题本质是三件事叠加：镜像源可用性不稳定 + `data-root` 配置丢失 + `nvidia runtime` 未注册；三者都修正后，环境才能稳定恢复。
