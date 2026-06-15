# 报告智能体（FlyReport）拆分方案

> 生成日期：2026-06-13
> 目标：将 `swarmmind/domains/fly_report/` 从 SwarmMind 单体中拆出，成为独立可部署的项目

---

## 一、现状概览

### 1.1 fly_report 的规模

| 指标 | 数值 |
|------|------|
| Python 文件数 | 52 |
| 子包数 | 10（agents, analyzer, chart, composer, dikong, dikong_sql, export, intent, lm, text2sql, utils） |
| 核心 service.py 行数 | ~2800 行 |
| 自有数据库表 | 6 张（session, chat_turn, interaction, message, artifact, audit） |
| API 端点 | `/v1/fly-reports/*`（SSE 流式对话、报告生成、session 管理、导出等） |

### 1.2 与 SwarmMind 的耦合程度

fly_report 已经是一个**高度自治**的领域：
- ✅ 有自己的状态机（PARSING → CLARIFYING → ... → ARCHIVED）
- ✅ 有自己的 agent 层（intent parser + text2sql）
- ✅ 有自己的数据获取层（dikong REST + dikong_sql 直连 PG/TDengine）
- ✅ 有自己的分析/渲染/导出管线
- ✅ 有自己的持久化（6 张独立表）
- ✅ 不使用 SwarmMind 的核心编排（Gateway/TaskOrchestrator/ExecutionRunner）
- ⚠️ 依赖 7 个 swarmmind 共享模块（详见下文）

---

## 二、需要解耦的依赖（7 个外部 swarmmind 模块）

### 依赖 1：`swarmmind.config.settings.get_settings` + `swarmmind.config.schema.*`

**提供什么：** `SwarmMindConfig`（pydantic-settings BaseSettings），聚合所有配置

**影响的文件：**
- `service.py` → `settings.fly_report.*`, `settings.storage_path`, `settings.agent.model`
- `composer/simple_composer.py` → `settings.storage_path`
- `intent/classifier.py` → 模型配置
- `text2sql/agent.py`, `text2sql/service.py` → text2sql 配置

**涉及的配置模型：**
- `FlyReportConfig`（顶层开关、source 选择）
- `FlyReportDikongConfig`（REST API 连接）
- `FlyReportDikongSqlConfig`、`FlyReportPostgresConfig`、`FlyReportTDengineConfig`（SQL 直连）
- `FlyReportText2SqlConfig`（text2sql 配置）
- `ModelConfig`（LLM 模型配置）

**拆分方案：**
- 将上述配置模型从 `swarmmind/config/schema.py` **复制**到新项目的 `fly_report/config/schema.py`
- 创建独立的 `FlyReportConfig` 顶层类，用 pydantic-settings 加载
- 保留环境变量前缀 `FLY_REPORT_`（去掉 `SWARMMIND_` 前缀）
- 配置文件从 `configs/fly_report.yaml` 迁移

---

### 依赖 2：`swarmmind.repositories.postgres.PostgresStore`

**提供什么：** 异步 PG 包装器（`fetch_one`, `fetch_all`, `execute`），基于 psycopg.AsyncConnection

**影响的文件：**
- `repository.py` → `PostgresFlyReportRepository` 内部使用

**拆分方案：**
- `PostgresStore` 是一个轻量包装（~60 行），直接**内联**到新项目的 `fly_report/repository.py`
- 或者提取为新项目的一个 `db.py` 工具模块
- Alembic 迁移独立管理（见下文"数据库迁移"）

---

### 依赖 3：`swarmmind.models.event.DomainEvent`

**提供什么：** Pydantic 域事件模型（event_id, topic, tenant_id, session_id, payload, occurred_at）

**影响的文件：**
- `observability.py` → 构建 `DomainEvent` 实例发布审计事件

**拆分方案：**
- `DomainEvent` 是简单 Pydantic 模型（~20 行），直接**复制**到新项目
- 如果新项目不需要跨域事件总线，可简化为本地事件

---

### 依赖 4：`swarmmind.models.table.DataTable` + `TableColumn`

**提供什么：** 数据表抽象（DataTable, TableColumn, TableRow），用于聚合分析

**影响的文件：**
- `analyzer/aggregations.py` → 构建 DataTable 实例

**拆分方案：**
- `DataTable` 是独立数据类（~80 行），直接**复制**到新项目
- 无外部依赖，可直接使用

---

### 依赖 5：`swarmmind.agents.audited_model.AuditedOpenAIChatModel`

**提供什么：** agentscope OpenAIChatModel 的审计子类，发射 LLM 调用审计事件

**影响的文件：**
- `agents/factory.py` → 实例化 `AuditedOpenAIChatModel`

**拆分方案：**
- `AuditedOpenAIChatModel`（~50 行）可**复制**到新项目
- 如果新项目不需要审计，可直接用 agentscope 原生 `OpenAIChatModel`

---

### 依赖 6：`swarmmind.prompt_template.fly_report.*`

**提供什么：** 4 个 prompt 模板常量（INTENT_PARSE_SYSTEM_PROMPT, INTENT_PARSE_USER_PROMPT, CLARIFY_SYSTEM_PROMPT, FOLLOWUP_PATCH_SYSTEM_PROMPT）

**影响的文件：**
- `agents/factory.py` → 导入 3 个 system prompt
- `intent/parser.py` → 导入 user prompt + render_prompt

**拆分方案：**
- 这些 prompt **本身就是 fly_report 专属的**，只是放在了 swarmmind 包里
- 直接**迁移**到新项目的 `fly_report/prompts/` 目录

---

### 依赖 7：`swarmmind.prompt_template.renderer.render_prompt` + `base.PromptTemplate`

**提供什么：** Jinja2 prompt 渲染器 + PromptTemplate 基类

**影响的文件：**
- `intent/parser.py` → 渲染 intent parse 用户 prompt

**拆分方案：**
- `render_prompt` + `PromptTemplate` 合计 ~30 行，直接**复制**到新项目

---

## 三、数据库迁移

### 3.1 fly_report 使用的表

**自有 6 张表（fly_report 独占）：**
```sql
fly_report_session       -- 会话主表
fly_report_chat_turn     -- 对话轮次
fly_report_interaction   -- 流式交互
fly_report_message       -- 流式消息
fly_report_artifact      -- 产物（报告文件等）
fly_report_audit         -- 审计日志
```

**迁移方案：**
- 从 SwarmMind 的 Alembic 迁移中**提取** fly_report 相关的 revision
- 在新项目中建立独立的 Alembic 迁移链
- 原始 DDL 已在 `repository.py` 的 `FLY_REPORT_SCHEMA_SQL` 中定义，可直接使用

### 3.2 共享的 PostgreSQL 实例

当前 fly_report 和 SwarmMind 共享同一个 PostgreSQL 实例。拆分后：
- **方案 A（推荐）：** 独立数据库实例，完全解耦
- **方案 B：** 同一实例不同 schema，通过 search_path 隔离
- **方案 C：** 同一 schema 但独立迁移管理（风险最高）

---

## 四、第三方依赖对比

### fly_report 实际使用的包（精简列表）

| 包 | 用途 | 必需 |
|---|---|---|
| fastapi + uvicorn | Web 框架 | ✅ |
| pydantic + pydantic-settings | 数据模型 + 配置 | ✅ |
| httpx | HTTP 客户端（dikong, TDengine, LLM） | ✅ |
| aiolimiter | 异步限速 | ✅ |
| psycopg + psycopg-pool | PostgreSQL 驱动 | ✅ |
| psycopg2-binary | Vanna 内部依赖 | ✅ |
| agentscope | ReAct Agent 框架 | ✅ |
| vanna | Text-to-SQL Agent | ✅ |
| pandas + numpy | 数据处理 | ✅ |
| jinja2 | 模板渲染 | ✅ |
| python-docx | DOCX 导出 | ✅ |
| matplotlib | 图表渲染 | ✅ |
| pyyaml | YAML 知识库 | ✅ |
| loguru | 日志 | ✅ |

### SwarmMind 声明但 fly_report 不需要的包

| 包 | 原因 |
|---|---|
| opensandbox / agent-sandbox | 沙箱执行（其他领域用） |
| alembic | 迁移工具（需要但应独立配置） |
| qdrant-client / chromadb | 向量存储（其他领域用） |
| redis | 缓存/事件总线（其他领域用） |
| click | CLI 框架（其他领域用） |

---

## 五、拆分后的目标项目结构

```
fly-report/                          # 新项目根目录
├── pyproject.toml                   # 独立的包定义和依赖
├── Dockerfile                       # 独立镜像
├── docker-compose.yaml              # 独立部署（PG + backend + nginx）
├── alembic.ini                      # 独立迁移配置
├── alembic/                         # 独立迁移脚本
│   └── versions/
│       └── 0001_baseline.py         # 6 张 fly_report 表
├── configs/
│   └── fly_report.yaml              # 配置文件
├── .env.example                     # 环境变量模板
├── data/
│   └── fly_report_text2sql/         # text2sql 知识库
│       ├── tables.yaml
│       ├── metrics.yaml
│       └── golden_qa.yaml
├── fly_report/                      # 主包
│   ├── __init__.py
│   ├── main.py                      # FastAPI app 工厂（替代 server.py 中的接线代码）
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py              # FlyReportConfig（独立 pydantic-settings）
│   │   └── schema.py                # 配置模型
│   ├── api/
│   │   ├── __init__.py
│   │   └── router.py                # FastAPI 路由（从 api.py 迁移）
│   ├── agents/                      # 从 swarmmind/domains/fly_report/agents/ 整体迁移
│   ├── analyzer/                    # 整体迁移
│   ├── chart/                       # 整体迁移
│   ├── composer/                    # 整体迁移
│   ├── dikong/                      # 整体迁移
│   ├── dikong_sql/                  # 整体迁移
│   ├── export/                      # 整体迁移（含 templates/）
│   ├── intent/                      # 整体迁移
│   ├── lm/                          # 整体迁移
│   ├── text2sql/                    # 整体迁移
│   ├── prompts/                     # prompt 模板（从 swarmmind.prompt_template.fly_report 迁移）
│   ├── models/                      # 共享模型（DomainEvent, DataTable 等）
│   │   ├── event.py
│   │   └── table.py
│   ├── db.py                        # PostgresStore（从 swarmmind.repositories.postgres 内联）
│   ├── repository.py                # 持久化（整体迁移）
│   ├── service.py                   # 核心服务（整体迁移，修改 import）
│   ├── schemas.py                   # 整体迁移
│   ├── state_machine.py             # 整体迁移
│   ├── errors.py                    # 整体迁移
│   ├── data_fetcher.py              # 整体迁移
│   ├── conflict_checker.py          # 整体迁移
│   ├── observability.py             # 整体迁移
│   ├── permissions.py               # 整体迁移
│   └── utils/                       # 整体迁移
├── scripts/                         # 相关脚本
│   ├── seed_mock_data.py
│   ├── test_data_fetcher.py
│   └── ...
├── tests/                           # 测试
└── docs/                            # 文档
```

---

## 六、迁移步骤（建议分 5 个阶段）

### 阶段 1：准备 — 提取共享依赖（1-2 天）

1. 创建新项目骨架 `fly-report/`
2. 复制/内联 4 个共享模块：
   - `PostgresStore` → `fly_report/db.py`
   - `DomainEvent` → `fly_report/models/event.py`
   - `DataTable/TableColumn` → `fly_report/models/table.py`
   - `AuditedOpenAIChatModel` → `fly_report/agents/audited_model.py`
3. 复制 prompt 模板 + renderer → `fly_report/prompts/`
4. 复制配置模型 → `fly_report/config/schema.py`
5. 编写独立的 `FlyReportConfig`（pydantic-settings）

### 阶段 2：迁移业务代码（1-2 天）

1. 将 `swarmmind/domains/fly_report/` 下所有子包复制到新项目
2. **批量替换 import 路径：**
   - `from swarmmind.config.settings import get_settings` → `from fly_report.config.settings import get_settings`
   - `from swarmmind.config.schema import ...` → `from fly_report.config.schema import ...`
   - `from swarmmind.repositories.postgres import PostgresStore` → `from fly_report.db import PostgresStore`
   - `from swarmmind.models.event import DomainEvent` → `from fly_report.models.event import DomainEvent`
   - `from swarmmind.models.table import ...` → `from fly_report.models.table import ...`
   - `from swarmmind.agents.audited_model import ...` → `from fly_report.agents.audited_model import ...`
   - `from swarmmind.prompt_template.fly_report import ...` → `from fly_report.prompts import ...`
   - `from swarmmind.prompt_template.renderer import ...` → `from fly_report.prompts.renderer import ...`
3. 编写 `fly_report/main.py`（FastAPI app 工厂，从 server.py 提取接线代码）

### 阶段 3：数据库独立（0.5-1 天）

1. 提取 fly_report 的 Alembic 迁移到新项目
2. 编写 baseline 迁移（6 张表的 CREATE TABLE）
3. 配置独立的 alembic.ini
4. 测试迁移 up/down

### 阶段 4：配置与部署（0.5-1 天）

1. 编写 `pyproject.toml`（仅含 fly_report 需要的依赖）
2. 编写 `Dockerfile`（CJK 字体 + pandoc + uvicorn）
3. 编写 `docker-compose.yaml`（PG + backend + nginx）
4. 迁移 `.env.example`
5. 迁移 `configs/fly_report.yaml`

### 阶段 5：验证与清理（1 天）

1. 运行所有 scripts/ 测试脚本验证功能
2. 端到端测试：对话 → 报告生成 → 导出
3. 从 SwarmMind 主项目中：
   - 删除 `swarmmind/domains/fly_report/`
   - 删除 `swarmmind/prompt_template/fly_report/`
   - 清理 `swarmmind/api/server.py` 中的 fly_report 接线代码
   - 清理 `swarmmind/config/schema.py` 中的 FlyReport 配置模型
   - 清理 `pyproject.toml` 中 fly_report 独有的依赖（如果其他领域不用）
4. 更新文档

---

## 七、风险与注意事项

### 7.1 低风险（大部分依赖都很轻量）

- 需要内联的模块都很小（PostgresStore ~60 行, DomainEvent ~20 行, DataTable ~80 行, render_prompt ~30 行）
- prompt 模板本身就是 fly_report 专属的
- 配置模型本身就是 fly_report 专属的

### 7.2 中等风险

- **agentscope 版本锁定：** fly_report 使用 `agentscope >=1.0.16,<2.0.0`，需确认与其他依赖无冲突
- **vanna 版本锁定：** 使用 `vanna >=2.0.2,<3.0.0`，vanna 的内部依赖（如 psycopg2）需注意
- **Text2SQL 知识库路径：** 当前通过 `settings.fly_report.text2sql.knowledge_path` 配置，需确保迁移后路径正确

### 7.3 需要特别注意

- **AuditedOpenAIChatModel 的审计事件：** 当前通过注入的 `event_bus` 发布。拆分后如果不需要跨域事件，可简化为本地日志
- **Alembic 迁移基线：** 需要从现有迁移中精确提取 fly_report 相关的 DDL，不能遗漏
- **环境变量前缀变更：** 从 `SWARMMIND_FLY_REPORT__*` 改为 `FLY_REPORT_*`，部署配置需同步更新

---

## 八、工作量估算

| 阶段 | 工作量 | 备注 |
|------|--------|------|
| 1. 提取共享依赖 | 1-2 天 | 4 个小模块 + 配置系统 |
| 2. 迁移业务代码 | 1-2 天 | 主要是 import 替换 + main.py |
| 3. 数据库独立 | 0.5-1 天 | Alembic 迁移提取 |
| 4. 配置与部署 | 0.5-1 天 | Dockerfile + compose |
| 5. 验证与清理 | 1 天 | 端到端测试 |
| **总计** | **4-7 天** | 1 人全职 |

---

## 九、拆分后的收益

1. **独立部署：** fly_report 可以独立发布、独立扩缩容，不影响 SwarmMind 主系统
2. **依赖精简：** 去掉 redis、qdrant、chromadb、opensandbox 等不需要的依赖，镜像更小
3. **代码清晰：** 配置、路由、服务都在一个项目内，新人更容易理解
4. **独立演进：** 可以独立升级 agentscope/vanna 版本，不受 SwarmMind 约束
5. **测试简化：** 不需要启动整个 SwarmMind 来测试报告功能
