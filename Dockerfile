# syntax=docker/dockerfile:1.7

FROM python:3.12-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    SWARMMIND_PROJECT_ROOT=/app \
    PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
    PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn

WORKDIR /app

RUN set -eux; \
    sed -i 's@deb.debian.org@mirrors.tuna.tsinghua.edu.cn@g; s@security.debian.org@mirrors.tuna.tsinghua.edu.cn@g' /etc/apt/sources.list.d/debian.sources; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        git \
        pandoc \
        fontconfig \
        fonts-noto-cjk \
        fonts-noto-cjk-extra \
        fonts-wqy-microhei \
        fonts-wqy-zenhei \
        fonts-arphic-uming \
        fonts-arphic-ukai; \
    fc-cache -fv; \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md requirements.txt ./

RUN --mount=type=cache,target=/root/.cache/pip \
    set -eux; \
    export PIP_NO_CACHE_DIR=0; \
    python -m pip install --upgrade pip setuptools wheel; \
    python -m pip install -r requirements.txt

COPY swarmmind ./swarmmind
COPY configs ./configs
COPY alembic.ini ./
COPY alembic ./alembic

RUN set -eux; \
    python -m pip install --no-deps .

EXPOSE 8000

CMD ["swarmmind-api"]
