# SwarmMind arm64 镜像构建与部署指南

> 适用场景：开发机为 amd64（Ubuntu 24.04 + docker.io 27.5.1），目标客户机为 arm64
> （如 12 服务器 `172.188.8.12`），需要把 `swarmmind:wuyi-report-v0.2-arm64`
> 业务镜像离线交付到客户机部署。

---

## 1. 一次性环境准备（首次执行 / 换机器时再做）

### 1.1 安装 docker buildx 插件（不重启 daemon）

Ubuntu 默认 `docker.io` 包不带 buildx，**直接放二进制**最安全，不影响现有容器：

```bash
mkdir -p ~/buildx-install && cd ~/buildx-install

BUILDX_VER="v0.17.1"
# 国内可用 gh-proxy 加速；本机 Clash/mihomo 已在 7890 也可直接走代理
curl -fsSL -o docker-buildx \
  "https://gh-proxy.com/https://github.com/docker/buildx/releases/download/${BUILDX_VER}/buildx-${BUILDX_VER}.linux-amd64"

sudo install -m 0755 -o root -g root docker-buildx /usr/libexec/docker/cli-plugins/docker-buildx
docker buildx version   # 期望: github.com/docker/buildx v0.17.1
```

### 1.2 注册 QEMU binfmt（让 amd64 主机能跑 arm64 容器）

```bash
sudo docker run --rm --privileged multiarch/qemu-user-static --reset -p yes
ls /proc/sys/fs/binfmt_misc/ | grep qemu-aarch64   # 期望能看到
```

> ⚠️ 宿主机重启后 binfmt 会失效，需要重跑这条命令。如要持久化，写一个 systemd unit。

### 1.3 创建带代理的 buildx builder

本机 Clash (mihomo) 监听 `127.0.0.1:7890`。buildx 默认用 `docker-container`
驱动跑在独立容器里，必须显式注入代理才能访问 GitHub / Docker Hub：

```bash
docker buildx rm swarmmind-arm64 2>/dev/null || true

docker buildx create \
  --name swarmmind-arm64 \
  --driver docker-container \
  --driver-opt network=host \
  --driver-opt env.http_proxy=http://127.0.0.1:7890 \
  --driver-opt env.https_proxy=http://127.0.0.1:7890 \
  --driver-opt "env.no_proxy=localhost|127.0.0.1" \
  --use

docker buildx inspect --bootstrap
```

> 注意：`no_proxy` 必须用 `|` 分隔，逗号会被 buildx CLI 解析成多 driver-opt。

> ⚠️ **代理环境变量只在 `docker buildx create` 时注入，事后无法用 `update` 补加**。
> 如果 builder 早先是不带 `--driver-opt env.*_proxy=...` 创建的（例如此前手动跑过
> 一遍 `create` 没带代理），构建第一步拉 `docker/dockerfile:1.7` 时会直接报
> `failed to fetch anonymous token: ... read: connection reset by peer`。
> 处理方式：`docker buildx rm swarmmind-arm64` 后按上面命令完整重建一次即可，
> 历史 layer 缓存丢失没关系，下一次构建会重新建立。

---

## 2. 日常构建（代码每次改动后做这个）

只要源码 / Dockerfile 改了，重新跑构建脚本即可，**不需要重新做第 1 节**：

```bash
cd /home/admin2/proj/SwarmMind
./build_image_arm64.sh
```

脚本行为（见 [build_image_arm64.sh](../../build_image_arm64.sh)）：

- 默认 tag：`swarmmind:wuyi-report-v0.2-arm64`
- 自动复用 `swarmmind-arm64` builder（已存在则 `use`，不会重建）
- 利用 buildx layer 缓存：仅修改 Python 代码时，apt + pip 层会全部命中缓存，
  通常 1~3 分钟出包；第一次构建因为要拉 base image + 装依赖，需要 10~20 分钟
- 构建完会校验镜像架构必须是 `linux/arm64`，再 `docker save | gzip` 输出 tar.gz

产物：

```
wuliao/images/swarmmind-wuyi-report-v0.2-arm64.tar.gz
```

### 2.1 自定义 tag / 输出目录

```bash
# 指定 tag（脚本会自动追加 -arm64 后缀，已含则不再追加）
./build_image_arm64.sh swarmmind:v1.1
# 实际产出: swarmmind:v1.1-arm64

# 指定输出目录
./build_image_arm64.sh swarmmind:wuyi-report-v0.2 ./out
```

### 2.2 强制重建（忽略缓存）

通常不用。除非依赖（apt / pip）变更但 Dockerfile 行没改导致缓存命中错了：

```bash
# 临时跑一遍 --no-cache
docker buildx build --builder swarmmind-arm64 --platform linux/arm64 \
  --no-cache -t swarmmind:wuyi-report-v0.2-arm64 --load .
# 然后再 save
docker save swarmmind:wuyi-report-v0.2-arm64 \
  | gzip > wuliao/images/swarmmind-wuyi-report-v0.2-arm64.tar.gz
```

---

## 3. 交付到 12 服务器

### 3.1 传输

```bash
scp wuliao/images/swarmmind-wuyi-report-v0.2-arm64.tar.gz root@172.188.8.12:/root/
```

### 3.2 12 服务器上离线导入并切换

```bash
ssh root@172.188.8.12
cd /path/to/deploy   # 含 docker-compose.yaml 的目录

# 1) 停掉当前 backend / migrate（保留 backend_data 卷）
sudo docker-compose -p swarmmind stop backend migrate
sudo docker-compose -p swarmmind rm -f backend migrate

# 2) 导入新镜像（同名 tag 会被覆盖指向新 image id，旧 layer 变成 dangling，
#    不会影响别的容器）
sudo docker load -i /root/swarmmind-wuyi-report-v0.2-arm64.tar.gz

# 3) 校验
sudo docker image inspect swarmmind:wuyi-report-v0.2-arm64 \
  --format '{{.Os}}/{{.Architecture}}'
# 期望: linux/arm64

# 4) 重新拉起
sudo docker-compose -p swarmmind up -d
sudo docker logs -f swarmmind-migrate   # 看到 alembic upgrade 完成
sudo docker logs -f swarmmind-backend
sudo docker ps                          # backend 进入 healthy 即成功

# 5) 可选：清理旧 dangling 镜像
sudo docker image prune -f
```

> ⚠️ [wuliao/deploy/12-server/docker-compose.yaml](../../wuliao/deploy/12-server/docker-compose.yaml)
> 中 `migrate` / `backend` 的 `image:` 字段必须等于本次构建的 tag
> （`swarmmind:wuyi-report-v0.2-arm64`），否则 12 服务器会找不到镜像。

---

## 4. 故障速查

| 症状 | 原因 | 处理 |
|---|---|---|
| `docker buildx: 'buildx' is not a docker command` | buildx 未安装 | 见 1.1 |
| `failed to resolve source metadata for docker.io/...: i/o timeout` | builder 容器没走代理 | 见 1.3，重建 builder |
| `failed to fetch anonymous token: ... read: connection reset by peer`（拉 `docker/dockerfile:1.7` 时） | builder 是早先无代理参数创建的，`*_proxy` 没生效 | `docker buildx rm swarmmind-arm64` 后按 1.3 完整重建（不能 `update` 补代理） |
| `invalid value "127.0.0.1", expecting k=v` | `no_proxy` 用了逗号 | 改成 `\|` 分隔，见 1.3 |
| 12 上 `exec /usr/local/bin/python: exec format error` | 镜像还是 amd64 | 确认 12 上 `docker image inspect` 是 `linux/arm64`，重新 load |
| 12 上 backend 起不来，migrate 退出 255 | DSN 连不上 PG / 密码错 | 在 12 上跑 `docker run --rm --platform linux/arm64 postgres:16-alpine psql "<DSN>" -c "select 1"` 验证 |
| 重启宿主机后构建报 `exec format error: docker/dockerfile:1.7` | binfmt 注册丢失 | 重跑 1.2 |

---

## 5. TL;DR — 日常一条命令

源码改完 → 出包 → 推到 12：

```bash
cd /home/admin2/proj/SwarmMind \
  && ./build_image_arm64.sh \
  && scp wuliao/images/swarmmind-wuyi-report-v0.2-arm64.tar.gz root@172.188.8.12:/root/
```

12 服务器上：

```bash
cd /path/to/deploy \
  && sudo docker-compose -p swarmmind stop backend migrate \
  && sudo docker-compose -p swarmmind rm -f backend migrate \
  && sudo docker load -i /root/swarmmind-wuyi-report-v0.2-arm64.tar.gz \
  && sudo docker-compose -p swarmmind up -d \
  && sudo docker logs -f swarmmind-migrate
```
