# SwarmMind Sandbox Data Analysis Demo

## sandbox 执行
```bash
# 1. 启动 sandbox
uv sync --extra dev
opensandbox-server
```

opensandbox支持的image:
- serverless-registry.cn-hangzhou.cr.aliyuncs.com/functionai/sandbox-all-in-one:v0.9.29
- ghcr.io/agent-infra/sandbox:latest

当前默认统一使用单一 sandbox profile:
- aio -> ghcr.io/agent-infra/sandbox:latest

- 查看容器内
```shell
docker run --security-opt seccomp=unconfined --rm -it -p 3000:8080 ghcr.io/agent-infra/sandbox:latest /bin/sh

docker run --rm -it --entrypoint /bin/bash ghcr.io/agent-infra/sandbox:latest

```
- 支持服务
python-server, gem-server, browser, nginx, websocat, code-server, mcp-server-browser, jupyter, mcp-hub, openbox, tigervnc
```plaintext
1. python3.12
2. pip
3. uv
4. node
5. npm
6.
```


相关文档
- https://github.com/agent-infra/sandbox/tree/main
- https://help.aliyun.com/zh/functioncompute/fc/dynamically-mount-custom-skills-for-sandboxes?spm=a2c4g.11186623.help-menu-2508973.d_3_6_4.d81757bbtTmc9x
- https://www.cnblogs.com/alisystemsoftware/p/19646364
- https://github.com/alibaba/OpenSandbox/blob/main/examples/aio-sandbox/README.md
- https://sandbox.agent-infra.com/zh/guide/start/quick-start


---
## 报告智能体
- cd /home/admin2/proj/SwarmMind/deploy
- docker compose up -d --force-recreate backend