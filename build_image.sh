#!/usr/bin/env bash
set -euo pipefail

IMAGE_TAG="${1:-swarmmind:wuyi-report-v0.2.7.5}"

if docker buildx version >/dev/null 2>&1; then
	echo "Using BuildKit cache build: ${IMAGE_TAG}"
	DOCKER_BUILDKIT=1 docker build -t "${IMAGE_TAG}" .
else
	echo "docker buildx is unavailable; using legacy build: ${IMAGE_TAG}"
	DOCKER_BUILDKIT=0 docker build -f Dockerfile.legacy -t "${IMAGE_TAG}" .
fi