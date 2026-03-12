# SwarmMind 项目设计方案 v2.0 (Revised)

> 基于 OpenCLAW 架构 + AgentScope 组件的通用任务助手方案

---

## 一、核心定位

| 对比项 | 说明 |
|-------|------|
| **任务类型** | 通用任务助手（邮件/PPT/App/报告/监控等） |
| **Agent 框架** | 使用 AgentScope（不重复造轮子） |
| **工具系统** | 可插拔工具市场（Skills） |
| **记忆机制** | Session + Transcript + 长期记忆 |
| **入口** | CLI + API + Webhook |

---

## 二、架构设计

```
┌─────────────────────────────────────────────────────────────────┐
│                        SwarmMind                                 │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐           │
│  │   CLI       │  │   REST API  │  │  Webhook    │  ← 入口层  │
│  └─────────────┘  └─────────────┘  └─────────────┘           │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Gateway (网关层)                        │   │
│  │  - 任务路由（Task Router）                               │   │
│  │  - 会话管理（Session Manager）                           │   │
│  │  - 认证/限流（Auth + Rate Limit）                       │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Task Orchestrator (任务编排)                  │   │
│  │  - 任务拆解（Task Decomposer）                          │   │
│  │  - 子任务调度（Subtask Scheduler）                       │   │
│  │  - 状态机（Task State Machine）                         │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              AgentScope Layer (使用 AgentScope)           │   │
│  │                                                            │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │   │
│  │  │   MsgHub    │  │  Pipeline   │  │   Agents    │     │   │
│  │  │  (消息总线)  │  │  (编排)     │  │ ReAct等    │     │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘     │   │
│  │                                                            │   │
│  │  ┌─────────────────────────────────────────────────────┐  │   │
│  │  │              Memory (AgentScope 内置)               │  │   │
│  │  │  InMemoryMemory / RedisMemory / SQLAlchemyMemory   │  │   │
│  │  └─────────────────────────────────────────────────────┘  │   │
│  │                                                            │   │
│  │  ┌─────────────────────────────────────────────────────┐  │   │
│  │  │         Tool System (工具注册 + 执行)                │  │   │
│  │  │  ToolRegistry + Tool(AgentScope) + MCP              │  │   │
│  │  └─────────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                   Tool System (业务工具层)                 │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐      │   │
│  │  │ Browser │ │  Bash   │ │ Search  │ │ Skills  │ ...  │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘      │   │
│  │                                                           │   │
│  │  ┌─────────────────────────────────────────────────┐     │   │
│  │  │            Sandbox (沙箱执行环境)                 │     │   │
│  │  │   OpenSandbox Adapter → Docker/K8s              │     │   │
│  │  └─────────────────────────────────────────────────┘     │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                   Memory Layer (记忆层)                    │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │   │
│  │  │   Session     │  │ Transcript   │  │  Long-term    │  │   │
│  │  │ (AgentScope)  │  │  (完整日志)   │  │   (向量库)   │  │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │               Observability (可观测性)                      │   │
│  │  Logging + Tracing + Metrics                             │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 三、AgentScope 组件使用

### 3.1 直接使用的组件

| AgentScope 组件 | 用途 |
|----------------|------|
| `ReActAgent` | 主 Agent（推理 + 工具调用） |
| `MsgHub` | 多 Agent 消息通信 |
| `Pipeline` | 顺序/并行任务编排 |
| `InMemoryMemory` | 短期记忆 |
| `LongTermMemory` | 长期记忆 |
| `Tool` | 工具基类 |
| `Service` | 服务抽象 |

### 3.2 业务层封装

```python
# swarmmind/agents/factories.py
from agentscope import ReActAgent, MsgHub, Pipeline
from agentscope.memory import InMemoryMemory

class AgentFactory:
    """使用 AgentScope 创建 Agent"""

    def create_main_agent(self, config: AgentConfig) -> ReActAgent:
        return ReActAgent(
            name="main",
            model=config.model,
            tools=config.tools,  # 注册的工具
            memory=InMemoryMemory(),
        )

    def create_subagent(self, name: str, tools: list[Tool]) -> ReActAgent:
        return ReActAgent(
            name=name,
            model=self.config.model,
            tools=tools,
            memory=InMemoryMemory(),
        )


class TaskPipeline:
    """使用 AgentScope Pipeline 做任务编排"""

    def __init__(self, agents: list[ReActAgent]):
        self.pipeline = Pipeline(agents=agents)

    async def run(self, task: Task) -> Result:
        return await self.pipeline.run(task)
```

---

## 四、核心组件设计

### 4.1 任务入口

```python
# CLI 入口
swarmmind run "帮我写一个股票监控脚本" --output result.json

# API 入口
POST /v1/tasks
{
  "goal": "帮我写一份市场分析报告",
  "constraints": {"format": "pptx", "language": "zh-CN"},
  "context": {...}
}
```

### 4.2 Gateway（网关层）

```python
class Gateway:
    async def route_task(self, request: TaskRequest) -> Session:
        # 1. 创建/恢复 Session
        # 2. 限流检查
        # 3. 路由到 Main Agent
        pass

    async def handle_message(self, session_id: str, message: str) -> Response:
        # 对话式交互
        pass
```

### 4.3 使用 AgentScope 的 Agent 系统

```python
# swarmmind/agents/main_agent.py
from agentscope import ReActAgent
from agentscope.memory import InMemoryMemory

class MainAgent(ReActAgent):
    """主 Agent：使用 AgentScope ReActAgent"""

    def __init__(self, config: AgentConfig):
        super().__init__(
            name="main",
            model=config.model,
            tools=config.tools,
            memory=InMemoryMemory(
                memory_config={"max_session_blocks": 10}
            ),
        )

    async def run(self, goal: str) -> TaskResult:
        # 使用 AgentScope 的 run 方法
        return await self(goal)
```

### 4.4 工具系统（可扩展）

```python
# swarmmind/tools/registry.py
from agentscope import Tool

class ToolRegistry:
    """工具注册中心 - 基于 AgentScope Tool 扩展"""

    def register(self, tool: Tool):
        self._tools[tool.name] = tool

    async def execute(self, tool_name: str, **kwargs) -> ToolResult:
        tool = self._tools[tool_name]
        return await tool.execute(**kwargs)


# 使用 AgentScope 的 @Tool 装饰器
from agentscope import tool

@tool(name="bash", description="Execute command in sandbox")
async def execute_bash(command: str, sandbox_id: str) -> str:
    """沙箱内命令执行"""
    pass


@tool(name="browser", description="Browse webpage")
async def browse(url: str) -> BrowseResult:
    """网页浏览"""
    pass


@tool(name="search", description="Search the web")
async def search(query: str) -> list[SearchResult]:
    """网络搜索"""
    pass


@tool(name="send_mail", description="Send email")
async def send_mail(to: str, subject: str, body: str) -> bool:
    """发送邮件"""
    pass


@tool(name="generate_pptx", description="Generate PowerPoint")
async def generate_pptx(outline: dict) -> str:
    """生成 PPT"""
    pass
```

### 4.5 Sandbox 集成

```python
# swarmmind/sandbox/manager.py
class SandboxManager:
    """沙箱生命周期管理"""

    async def create_execution_env(self, profile: str) -> SandboxHandle:
        """按需创建沙箱"""
        pass

    async def execute_code(self, sandbox_id: str, code: str) -> ExecResult:
        """在沙箱中执行代码"""
        pass

    async def cleanup(self, sandbox_id: str):
        """清理沙箱"""
        pass
```

### 4.6 记忆系统

| 记忆类型 | 使用方式 | 内容 | 生命周期 |
|---------|---------|------|---------|
| **短期记忆** | AgentScope `InMemoryMemory` | 当前任务上下文 | 任务期间 |
| **长期记忆** | AgentScope `LongTermMemory` | 知识库、模式 | 永久 |
| **Transcript** | 自研 | 完整执行日志 | 可配置 |

```python
# swarmmind/memory/manager.py
from agentscope.memory import InMemoryMemory, LongTermMemory

class MemoryManager:
    """记忆管理器 - 基于 AgentScope"""

    def __init__(self, config: MemoryConfig):
        self.short_term = InMemoryMemory(
            memory_config={"max_session_blocks": config.max_blocks}
        )
        self.long_term = LongTermMemory(
            storage_config=config.long_term_config
        )

    async def store_long_term(self, content: str, metadata: dict):
        await self.long_term.add(content, metadata)

    async def retrieve_long_term(self, query: str, top_k: int = 5):
        return await self.long_term.search(query, top_k)
```

---

## 五、目录结构

```
SwarmMind/
├── swarmmind/
│   ├── __init__.py
│   │
│   ├── gateway/                    # 网关层
│   │   ├── __init__.py
│   │   ├── gateway.py
│   │   ├── router.py
│   │   ├── auth.py
│   │   └── rate_limit.py
│   │
│   ├── orchestration/              # 任务编排
│   │   ├── __init__.py
│   │   ├── task_orchestrator.py
│   │   ├── task_decomposer.py
│   │   ├── scheduler.py
│   │   └── state_machine.py
│   │
│   ├── agents/                    # Agent 层（AgentScope 封装）
│   │   ├── __init__.py
│   │   ├── factory.py             # AgentFactory
│   │   ├── main_agent.py          # 主 Agent 封装
│   │   ├── sub_agent.py           # 子 Agent
│   │   └── config.py              # Agent 配置
│   │
│   ├── tools/                     # 工具系统
│   │   ├── __init__.py
│   │   ├── registry.py            # 工具注册中心
│   │   ├── sandbox_tools.py       # 沙箱工具
│   │   ├── browser_tools.py       # 浏览器工具
│   │   ├── search_tools.py        # 搜索工具
│   │   ├── mail_tools.py          # 邮件工具
│   │   └── pptx_tools.py         # PPT 工具
│   │
│   ├── sandbox/                   # 沙箱层
│   │   ├── __init__.py
│   │   ├── provider.py           # 抽象接口
│   │   ├── opensandbox_adapter.py
│   │   ├── profiles.py
│   │   └── manager.py            # 沙箱管理器
│   │
│   ├── memory/                    # 记忆层
│   │   ├── __init__.py
│   │   ├── manager.py            # 记忆管理器
│   │   ├── transcript.py         # Transcript 记录
│   │   └── long_term.py          # 长期记忆（扩展）
│   │
│   ├── models/                    # 数据模型
│   │   ├── __init__.py
│   │   ├── task.py
│   │   ├── message.py
│   │   └── config.py
│   │
│   ├── runtime/                   # 运行时
│   │   ├── __init__.py
│   │   └── model_client.py       # LLM 客户端
│   │
│   └── cli.py                     # CLI 入口
│
├── configs/                       # 配置文件
│   ├── default.yaml
│   └── profiles/
│       ├── py-basic.yaml
│       ├── fullstack.yaml
│       └── secure-offline.yaml
│
├── examples/                      # 示例
│   ├── write_email.json
│   ├── build_app.json
│   └── monitor_stock.json
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── pyproject.toml
└── README.md
```

---

## 六、实现路线

### Phase 1：核心骨架（1 周）

```
1. Gateway + Session 系统
2. AgentScope 集成 + AgentFactory
3. 3-5 个核心工具（Bash, File, Search）
4. Sandbox 集成
5. CLI 入口
```

**验收**：能用 CLI 提交任务，AgentScope Agent 执行并返回结果

### Phase 2：工具扩展（1 周）

```
1. Browser 工具
2. Mail 工具
3. Pptx 工具
4. 工具注册中心完善
5. Skills 抽象
```

**验收**：能完成"写报告"等多步骤任务

### Phase 3：记忆 + 可观测（1 周）

```
1. Transcript 记录
2. 长期记忆集成
3. 日志/Tracing/Metrics
4. 错误处理 + 重试
```

**验收**：完整执行链路可追溯

### Phase 4：扩展（持续）

```
1. API 完善
2. Webhook 支持
3. Skills 市场
4. K8s 部署
```

---

## 七、关键技术决策

| 决策点 | 选择 | 理由 |
|-------|------|------|
| **Agent 框架** | AgentScope | 不重复造轮子 |
| **LLM 客户端** | AgentScope 内置 | 支持多模型 |
| **短期记忆** | AgentScope `InMemoryMemory` | 开箱即用 |
| **长期记忆** | AgentScope `LongTermMemory` | 支持向量检索 |
| **工具系统** | AgentScope `Tool` + 自研扩展 | 灵活可扩展 |
| **Sandbox** | OpenSandbox | 已有基础 |
| **任务存储** | JSON 文件（开发）→ PostgreSQL | 简单→生产 |

---

## 八、版本历史

- **v2.1** (2026-03-12): 基于 OpenCLAW 架构 + AgentScope 组件
- **v2.0** (2026-03-12): 基于 OpenCLAW 架构参考设计
- **v1.0** (2026-03-07): 初始方案，专注代码/数据分析
