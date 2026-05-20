#!/usr/bin/env bash
# ============================================================================
# 在 amd64 / arm64 开发机上构建 linux/arm64 平台的业务镜像，并导出 tar.gz。
# 用于客户的 arm64 服务器（如 12 服务器）离线 docker load。
#
# 用法：
#   ./build_image_arm64.sh                                  # 默认 tag/输出
#   ./build_image_arm64.sh swarmmind:wuyi-report-v0.2       # 输入基础 tag，脚本会自动追加 -arm64 后缀
#   ./build_image_arm64.sh swarmmind:wuyi-report-v0.2 ./out # 指定输出目录
#
# 镜像 tag 规则：
#   输入 swarmmind:wuyi-report-v0.2  -> 实际构建出 swarmmind:wuyi-report-v0.2-arm64
#   输入 swarmmind                   -> 实际构建出 swarmmind:arm64
#   若输入已包含 -arm64 后缀则原样使用，避免出现 -arm64-arm64
#
# 产物：
#   <out_dir>/<image-name>-<tag>.tar.gz
#   （默认 wuliao/images/swarmmind-wuyi-report-v0.2-arm64.tar.gz）
#
# 依赖：
#   - docker buildx（Docker 20.10+ 自带）
#   - 已注册 binfmt_misc 多架构（脚本会自动尝试注册）
# ============================================================================
set -euo pipefail

INPUT_TAG="${1:-swarmmind:wuyi-report-v0.2.7}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="${2:-${SCRIPT_DIR}/wuliao/images}"

# 自动给 tag 追加 -arm64 后缀，方便客户机区分架构
if [[ "${INPUT_TAG}" == *":"* ]]; then
    REPO="${INPUT_TAG%%:*}"
    TAG="${INPUT_TAG#*:}"
else
    REPO="${INPUT_TAG}"
    TAG=""
fi
if [[ -n "${TAG}" ]]; then
    if [[ "${TAG}" == *"-arm64" || "${TAG}" == *"-aarch64" ]]; then
        IMAGE_TAG="${REPO}:${TAG}"
    else
        IMAGE_TAG="${REPO}:${TAG}-arm64"
    fi
else
    IMAGE_TAG="${REPO}:arm64"
fi

PLATFORM="linux/arm64"
DOCKERFILE="${SCRIPT_DIR}/Dockerfile"

# 输出文件名：把 ':' '/' 转成 '-'
SAFE_NAME="$(echo "${IMAGE_TAG}" | tr ':/' '--')"
OUT_FILE="${OUT_DIR}/${SAFE_NAME}.tar.gz"

mkdir -p "${OUT_DIR}"

echo "=============================================="
echo " SwarmMind 业务镜像 (arm64) 构建"
echo "   tag:        ${IMAGE_TAG}"
echo "   platform:   ${PLATFORM}"
echo "   dockerfile: ${DOCKERFILE}"
echo "   out:        ${OUT_FILE}"
echo "=============================================="

# -------- 1. 检查 buildx --------
if ! docker buildx version >/dev/null 2>&1; then
    echo "ERROR: docker buildx 不可用，请升级 Docker (>=20.10) 或安装 buildx 插件" >&2
    exit 1
fi

# -------- 2. 注册多架构 binfmt（在本机不是 arm64 时尤其需要）--------
HOST_ARCH="$(uname -m)"
if [[ "${HOST_ARCH}" != "aarch64" && "${HOST_ARCH}" != "arm64" ]]; then
    echo "[1/4] 主机架构 ${HOST_ARCH} ≠ arm64，注册 QEMU binfmt ..."
    if ! ls /proc/sys/fs/binfmt_misc/ 2>/dev/null | grep -q qemu-aarch64; then
        sudo docker run --rm --privileged multiarch/qemu-user-static --reset -p yes
    fi
else
    echo "[1/4] 主机本身是 arm64，跳过 QEMU 注册"
fi

# -------- 3. 准备 builder --------
BUILDER_NAME="swarmmind-arm64"
echo "[2/4] 准备 buildx builder: ${BUILDER_NAME}"
if ! docker buildx inspect "${BUILDER_NAME}" >/dev/null 2>&1; then
    docker buildx create --name "${BUILDER_NAME}" --use
else
    docker buildx use "${BUILDER_NAME}"
fi
docker buildx inspect --bootstrap >/dev/null

# -------- 4. 构建并 --load 到本机 docker images --------
echo "[3/4] docker buildx build (${PLATFORM}) ..."
docker buildx build \
    --platform "${PLATFORM}" \
    -f "${DOCKERFILE}" \
    -t "${IMAGE_TAG}" \
    --load \
    "${SCRIPT_DIR}"

# 校验真的是 arm64
ARCH="$(docker image inspect "${IMAGE_TAG}" --format '{{.Os}}/{{.Architecture}}')"
if [[ "${ARCH}" != "linux/arm64" ]]; then
    echo "ERROR: 镜像架构 ${ARCH} ≠ linux/arm64，构建未生效" >&2
    exit 1
fi
echo "  built ${IMAGE_TAG}  arch=${ARCH}"

# -------- 5. 导出 tar.gz --------
echo "[4/4] docker save | gzip -> ${OUT_FILE}"
docker save "${IMAGE_TAG}" | gzip > "${OUT_FILE}"
ls -lh "${OUT_FILE}"

cat <<EOF

=============================================
✅ 构建完成

下一步在客户机（arm64，如 172.188.8.12）上：

  scp ${OUT_FILE} root@<host>:/root/
  ssh root@<host>

  cd /path/to/deploy
  # 注意：12 服务器上 docker-compose.yaml 里 migrate / backend 的
  #       image: 字段需要改成 ${IMAGE_TAG}
  sudo docker-compose -p swarmmind stop backend migrate
  sudo docker-compose -p swarmmind rm -f backend migrate
  sudo docker load -i /root/$(basename "${OUT_FILE}")
  sudo docker image inspect ${IMAGE_TAG} --format '{{.Os}}/{{.Architecture}}'
  # 期望: linux/arm64
  sudo docker-compose -p swarmmind up -d
  sudo docker logs -f swarmmind-migrate
=============================================
EOF
