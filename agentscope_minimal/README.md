# AgentScope Minimal Multi-Agent Demo

这个目录用于完成 Phase 0 的第二个目标：跑通 AgentScope 最小多 Agent。

## 文档索引

1. [../docs/agentscope/README.md](../docs/agentscope/README.md): AgentScope 完整文档主索引。
2. [../docs/agentscope/01-foundations/01-overview.md](../docs/agentscope/01-foundations/01-overview.md): AgentScope 的总体设计与学习主线。
3. [../docs/agentscope/01-foundations/04-agent-runtime.md](../docs/agentscope/01-foundations/04-agent-runtime.md): `AgentBase`、`ReActAgentBase` 与 `ReActAgent` 的执行框架。
4. [../docs/agentscope/02-capabilities/01-tools-mcp-skills.md](../docs/agentscope/02-capabilities/01-tools-mcp-skills.md): 工具、MCP、技能与工具中间件。
5. [../docs/agentscope/03-workflows/01-conversation-and-pipeline.md](../docs/agentscope/03-workflows/01-conversation-and-pipeline.md): `MsgHub`、Conversation、Routing、Handoffs 与 Pipeline。
6. [../docs/agentscope/01-state-module.md](../docs/agentscope/01-state-module.md): `StateModule` 类级专题细读。
7. [../docs/agentscope/06-react-agent-loop.md](../docs/agentscope/06-react-agent-loop.md): `ReActAgent` reasoning/acting 闭环专题细读。

## 目标

验证以下能力在当前本地环境可用：

1. `agentscope.init()` 可以正常初始化。
2. 可以创建多个 Agent。
3. 可以通过 `MsgHub` 自动广播消息。
4. 多 Agent 可以围绕同一个任务完成一次最小协作。

这个示例不依赖模型 API，也不依赖外部网络。为了先打通框架链路，示例使用两个规则型 Agent：

1. `PlannerAgent`：根据用户目标生成三步计划。
2. `ReviewerAgent`：读取计划并给出审查结论。

## 文件说明

1. `demo.py`：可直接运行的最小多 Agent 示例。
2. `logs/`：AgentScope 本地运行日志目录，运行后自动生成。

## 安装

如果当前环境还没安装 AgentScope：

```bash
pip install -e .[agents]
```

## 运行

在项目根目录执行：

```bash
/home/admin2/proj/SwarmMind/.venv/bin/python agentscope_minimal/demo.py \
  --goal "实现一个返回两个数和的函数，并补一个最小 pytest 用例。"
```

预期输出为一段 JSON，包含：

1. `goal`
2. `plan`
3. `review`
4. `transcript`

## 验收点

满足以下条件即可认为“最小多 Agent”跑通：

1. 脚本成功退出。
2. `PlannerAgent` 输出计划。
3. `ReviewerAgent` 能看到 Planner 的消息并输出 review。
4. `agentscope_minimal/logs/` 下生成 AgentScope 日志文件。

## 后续扩展建议

下一步可以在这个最小示例基础上继续演进：

1. 把规则型 Agent 替换成 LLM Agent。
2. 增加第三个 `CoderAgent`。
3. 接入 `SandboxProvider`，让 Agent 输出真正进入 sandbox 执行。
4. 把 `MsgHub` 之外的串联改造成更明确的 orchestrator 状态机。