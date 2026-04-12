# SwarmMind Sandbox Data Analysis Demo

## sandbox 执行
```bash
# 1. 启动 sandbox
uv sync --extra dev
opensandbox-server
```

opensandbox支持的image:
- serverless-registry.cn-hangzhou.cr.aliyuncs.com/functionai/sandbox-all-in-one   v0.9.29

当前默认统一使用单一 sandbox profile:
- aio -> serverless-registry.cn-hangzhou.cr.aliyuncs.com/functionai/sandbox-all-in-one:v0.9.29

docker pull enterprise-public-cn-beijing.cr.volces.com/vefaas-public/all-in-one-sandbox:latest

相关文档
- https://github.com/agent-infra/sandbox/tree/main
- https://help.aliyun.com/zh/functioncompute/fc/dynamically-mount-custom-skills-for-sandboxes?spm=a2c4g.11186623.help-menu-2508973.d_3_6_4.d81757bbtTmc9x
- https://www.cnblogs.com/alisystemsoftware/p/19646364
- https://github.com/alibaba/OpenSandbox/blob/main/examples/aio-sandbox/README.md