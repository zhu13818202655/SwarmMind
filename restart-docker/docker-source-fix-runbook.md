# Docker 源修复与重启操作手册（SwarmMind）

> 目标：安全完成 Docker 拉镜像问题修复，并在可控窗口内重启 Docker，确保业务容器可恢复。
> 适用环境：Linux + systemd + Docker Engine。

## 0. 变更范围与风险

本手册会执行以下变更：

1. 修改 `/etc/docker/daemon.json`（镜像源与 DNS）。
2. 重启 Docker daemon：`systemctl restart docker`。

风险说明：

1. Docker daemon 重启期间，容器存在短暂中断。
2. 未配置自动重启策略的容器可能不会自动恢复。
3. `AutoRemove=true` 的容器无法通过 `docker update --restart ...` 修改重启策略。

---

## 1. 执行前准备（必须）

### 1.1 进入工作目录

```bash
cd /home/admin2/proj/SwarmMind
```

### 1.2 记录当前状态（审计留档）

```bash
mkdir -p ops-logs
TS=$(date +%F-%H%M%S)

docker version > "ops-logs/${TS}-docker-version.txt" 2>&1
docker info > "ops-logs/${TS}-docker-info-before.txt" 2>&1
docker ps -a --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}' > "ops-logs/${TS}-docker-ps-before.txt"
```

### 1.3 备份 daemon 配置

```bash
sudo cp /etc/docker/daemon.json "/etc/docker/daemon.json.bak.${TS}" 2>/dev/null || true
```

### 1.4 确认当前重启策略风险容器

```bash
docker ps --format '{{.Names}}\t{{.ID}}' | while IFS=$'\t' read -r n i; do
  p=$(docker inspect -f '{{.HostConfig.RestartPolicy.Name}}' "$i")
  if [ "$p" != "always" ] && [ "$p" != "unless-stopped" ]; then
    echo "$n $p"
  fi
done | sort
```

当前已知应只剩：

1. `practical_chatterjee no`（`AutoRemove=true`，特殊处理）

---

## 2. 写入新的 Docker 源配置

使用以下配置（稳定优先，少量镜像源 + 显式 DNS）：

```bash
sudo tee /etc/docker/daemon.json >/dev/null <<'EOF'
{
  "registry-mirrors": [
    "https://k44hxkx1.mirror.aliyuncs.com",
    "https://docker.m.daocloud.io"
  ],
  "dns": ["223.5.5.5", "119.29.29.29", "8.8.8.8"]
}
EOF
```

可选：检查 JSON 语法是否完整（简单查看）：

```bash
cat /etc/docker/daemon.json
```

---

## 3. 执行 Docker 重启（维护窗口）

```bash
sudo systemctl daemon-reload
sudo systemctl restart docker
```

立即检查 daemon 状态：

```bash
systemctl is-active docker
systemctl status docker --no-pager -n 30
```

`is-active` 期望输出：`active`

---

## 4. 重启后恢复与验证

### 4.1 校验镜像源是否生效

```bash
docker info | sed -n '/Registry Mirrors/,+8p'
```

### 4.2 验证拉镜像能力

```bash
docker pull hello-world
docker pull opensandbox/execd:v1.0.6
docker pull opensandbox/code-interpreter:v1.0.1
```

### 4.3 验证业务容器状态

```bash
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.RunningFor}}'
```

### 4.4 单独处理 `practical_chatterjee`

说明：该容器 `AutoRemove=true`，无法设置 restart policy。若重启后不存在，请手动重建。

1. 先检查是否存在：

```bash
docker ps -a | grep practical_chatterjee || true
```

2. 如果不存在，使用下列命令重建：

```bash
docker run -d --name practical_chatterjee --rm \
  --network bridge \
  -w /git \
  -v jb_devcontainer_sources_37d4623c381f4bb76b13790c8e4e3d4d:/tmp/606df5aa-0f0d-4dc4-8f2d-92602cd4a414 \
  -v 9b6a1f7e5a5de8ba38e217eb65d48c9b4d85e6015a1a88154c253f69416d11f3:/git \
  --entrypoint /bin/sh \
  alpine/git:latest \
  -c 'while sleep 1000; do :; done'
```

3. 验证：

```bash
docker ps | grep practical_chatterjee
```

---

## 5. OpenSandbox 连通性验证（建议）

如果你接下来要跑 OpenSandbox：

1. 启动服务后检查健康：

```bash
curl http://localhost:45698/health
```

2. 期望返回：

```json
{"status":"healthy"}
```

---

## 6. 失败回滚预案

如果重启后异常（daemon 启不来、拉取更差、关键服务异常），按以下回滚：

1. 还原旧配置：

```bash
sudo cp "/etc/docker/daemon.json.bak.${TS}" /etc/docker/daemon.json
```

如果当前 shell 没有 `${TS}`，先列出备份：

```bash
ls -1 /etc/docker/daemon.json.bak.* | tail -n 5
```

再手动替换为最新备份名。

2. 重启 Docker：

```bash
sudo systemctl daemon-reload
sudo systemctl restart docker
```

3. 复核：

```bash
systemctl is-active docker
docker ps --format 'table {{.Names}}\t{{.Status}}'
```

---

## 7. 执行完成判定（DoD）

满足以下条件视为本次变更完成：

1. `docker` 服务为 `active`。
2. `docker info` 显示新镜像源已生效。
3. `docker pull hello-world` 成功。
4. `docker pull opensandbox/execd:v1.0.6` 与 `opensandbox/code-interpreter:v1.0.1` 成功。
5. 关键业务容器恢复正常。
6. `practical_chatterjee` 如有需要已手动拉起。
