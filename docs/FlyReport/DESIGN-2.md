# 飞行报告智能体（FlyReport）设计文档

> 本设计基于真实需求 [需求文档.md](需求文档.md) 与真实接口 [dikong_api.json](dikong_api.json)。
>
> 设计要点：
> 1. **支持三种输出格式：`docx` / `pdf` / `markdown`**，由用户在会话中显式指定或走偏好默认值；HTML 仅作渲染中间态/预览
> 2. 支持**部门维度 / 飞手维度 / 多维度对比**
> 3. 支持**周期推送、偏好记忆、模糊指令追问、错误指令引导**
> 4. **数据权限实时校验**（前置硬卡口）
> 5. 数据来源：dikong API 的 `/missions/*`、`/devices/hms/*`、`/achs/*`、`/dashboard/*`、`/algorithmRecord/*` 等
> 6. 报告工作流：**预览 → 确认 → 生成（按所选格式） → 下载 → 后台存档**

---

## 1. 范围与目标

### 1.1 必须实现的能力（来自 PRD）

| 能力 | PRD 章节 |
|---|---|
| 总体维度统计（飞行/算法/图片/视频） | 2.1.1 |
| 部门维度（拆分、合并、对比） | 2.1.2 |
| 飞手维度（个人查询、飞手对比） | 2.1.2 |
| 周期：周报、月报、自定义时间段 | 2.1.1 |
| 智能报告：基础数据填充、图表、趋势分析（同比/环比）、对比分析 | 2.2 |
| 报告操作：预览、生成、下载、后台存档（30 天）、历史报告查询 | 2.2 |
| 输出格式：**docx / pdf / markdown** 三选一 | 2.2 |
| 自然语言交互：意图识别、模糊追问、错误引导、进度反馈、数据概述反馈 | 2.3 |
| 偏好记忆：筛选习惯、报告需求、编辑偏好；偏好的查/改/删 | 2.4 |
| 个性化建议推送：周期提醒、偏好建议、数据建议 | 2.4 |
| 数据权限：实时校验、超权终止、变更审计日志 | 2.5 |

### 1.2 不在本期范围

- 报告内"折线改柱状"等图表热改写（保留接口预留，本期不做 UI）
- PPTX 输出（如需后续追加新的 Renderer 即可，本期三种格式：docx / pdf / markdown）
- 偏好的多模态学习（仅记录显式行为：筛选、对话指令、下载后编辑信号）

---

## 2. 形态定位

仍然采用**垂直 domain 包**：`swarmmind/domains/fly_report/`，不动通用 Agent / orchestration / sandbox。

但内部不是简单 5 步线性 pipeline，而是一个 **以"报告会话"为主体的对话状态机**：

```
ChatSession ──┬─ Turn1: 解析意图 → 权限校验 → 取数 → 分析 → 预览 → 确认/调整
              ├─ Turn2: "改成农业局" → 局部更新 FilterSpec → 复用缓存增量取数 → 重新预览
              ├─ TurnN: "确认生成 pdf"   → 渲染对应格式 → 存档 → 回链
              └─ TurnM: "查上次的8月月报" / "本月飞行涨了20%要不要加分析" → 历史/推送通道
```

### 2.1 与现有基础设施的对齐

| 现有模块 | 复用方式 |
|---|---|
| `swarmmind/agents/audited_model.py` | 全部 LLM 调用统一走，落审计与计费 |
| `swarmmind/events/` | 发 `fly_report.*` 事件（intent_parsed / data_fetched / report_generated / followup_handled） |
| `swarmmind/cache/` | RawDataset、Analysis 缓存（key = filter_hash + tenant + version） |
| `swarmmind/repositories/` | 新增 `FlyReportRepository`、`UserPreferenceRepository`、`PushSubscriptionRepository` |
| `swarmmind/config/` | 新增 `FlyReportSettings`（dikong base_url / token / tenant header / 渲染参数） |
| `swarmmind/api/server.py` | 仅 `include_router(fly_report_router)` 一行 |
| `swarmmind/identity/` | 复用现有用户/部门/权限模型；不重复造轮子 |
| `swarmmind/locks/` | 报告生成串行化（同一会话避免并发覆写）|

---

## 3. 端到端流程

### 3.1 报告生成主链路

```
            ┌────────────────────────────────────────────────────────┐
 user query │  "生成农业局上周的飞行月报，要趋势分析"                  │
            └────────────────────────────────────────────────────────┘
                              │
                              ▼
 [1] IntentParser ─LLM(JSON)─▶ DraftFilterSpec
        │                       (period, scope, dimensions, indicators, options)
        │
        │   ① 含模糊：进入 ClarifyLoop（追问，最多 N 轮）
        │   ② 含冲突：返回冲突点 + 建议修正
        │   ③ 含错误：返回示例指令
        ▼
 [2] PermissionGate (复用 swarmmind/identity)
        │   - 检查 user → 部门/飞手 数据权限
        │   - 不通过 → "无权限" + 审计日志，立即中断
        ▼
 [3] FilterCompiler ─▶ NormalizedFilter（落库可哈希、可缓存）
        │
        ▼
 [4] DataFetcher  ─DikongClient─▶  RawDataset
        │  · 决定调用哪些接口（按 dimension/indicator 矩阵，见 §6）
        │  · 并发 + 分页 + 限流 + 缓存
        │  · 同/环比：再发一组上一周期请求
        ▼
 [5] Analyzer  ─纯函数─▶  AnalysisResult
        │  · 总体/部门/飞手聚合
        │  · 同比 / 环比 / 增长率
        │  · 部门间、飞手间对比（占比、差异、排名）
        │  · 异常检测（电量/告警/失败任务）
        ▼
 [6] Composer ─Jinja2(html)─▶  ReportContext + preview_html
        │  · 章节按 `include_modules` 装配
        │  · 每图表生成 ECharts option（HTML 预览渲染）
        │  · 用户偏好叠加（字段排序、是否含图表、备注栏）
        ▼
 [7] PreviewGate
        │  · 返回 preview_html + 数据概述（"上周飞行 XX 次..."）
        │  · 用户：「确认生成 [docx|pdf|markdown]」/「调整 X」/「取消」
        │     - 调整：回到 [1]，复用缓存增量
        ▼
 [8] RendererRouter → 按 `output_format` 分发
        ├─ DocxRenderer    → report.docx     (docxtpl + matplotlib PNG 嵌入)
        ├─ PdfRenderer     → report.pdf      (预览 HTML → WeasyPrint 渲染，图表同走 PNG)
        └─ MarkdownRenderer→ report.md       (Jinja2 md 模板，图表输出为 PNG 附件 + 相对链接)
        ▼
 [9] Archiver
        │  · 落库 ReportArtifact（user, dept, period, filter, file_path, ttl=30d）
        │  · 触发 PreferenceLearner（被动学习筛选/选项偏好）
        ▼
        返回下载链接 + 数据概述
```

### 3.2 历史报告检索（自然语言）

```
"找一下上次生成的XX部门8月份月报"
        │
        ▼
 HistoryQueryParser ─LLM(JSON)─▶ {dept?, period?, type?, keyword?}
        │
        ▼
 ReportArchiveSearch  → 命中 0/1/N
        │
        ├─ 0 命中：友好回复 + 建议
        ├─ 1 命中：直接给下载链接 + 数据概述
        └─ N 命中：返回候选列表（带摘要），用户选
```

### 3.3 周期推送 / 偏好建议

```
APScheduler (周一 09:00 / 月初 09:00)
        │
        ▼
 PushOrchestrator
        ├─ 拉取所有有"报告订阅"的用户
        ├─ 读取 UserPreference
        ├─ 生成"建议指令"（如"按上次偏好生成农业局本周周报？"）
        └─ 通过 NotificationGateway 推送（站内信 / WebSocket / 钩子）

DataInsightPusher（周期收口）
        ├─ 跑一遍当前周期总体统计
        ├─ 比较同比/环比，命中规则（如增长 ≥ 20%）
        └─ 推送数据建议（"本月飞行较上月+22%，建议加增长分析，是否需要？"）
```

### 3.4 偏好学习闭环

| 信号源 | 学习内容 | 入库 |
|---|---|---|
| 每次确认生成的 FilterSpec | 常用周期、常用部门/飞手、常用维度 | `prefs.filter_history` |
| 对话中显式选项（"加趋势分析"、"隐藏视频"） | report_options | `prefs.report_options` |
| 下载后编辑标记（前端可上报：用户编辑过哪些段落，新增了备注栏） | 模板偏好（备注栏、图表样式） | `prefs.template_hints` |
| "取消重点展示飞行时长" 等显式指令 | 偏好删除 | `prefs.disabled` |

---

## 4. 文件清单（新增 / 改动）

### 4.1 新增目录：`swarmmind/domains/fly_report/`

#### 4.1.1 入口与编排

| 文件 | 职责 |
|---|---|
| `__init__.py` | 导出 `FlyReportService` |
| `service.py` | **唯一对外入口**。`start_session / send_message / confirm / cancel / get_archive`，发布事件、写库、调度后续步骤 |
| `state_machine.py` | 会话状态机：`PARSING → CLARIFYING → AUTHORIZING → FETCHING → ANALYZING → PREVIEWING → RENDERING → ARCHIVED / CANCELLED / FAILED` |
| `errors.py` | `FilterParseError / ClarifyNeeded / PermissionDenied / DikongApiError / RenderError / ExportError` |
| `config.py` | 读 `SwarmMindConfig.fly_report`：dikong url/token、cache TTL、模板路径、归档 TTL（默认 30d）、推送 cron |

#### 4.1.2 数据模型与持久化

| 文件 | 职责 |
|---|---|
| `schemas.py` | Pydantic：`FilterSpec / NormalizedFilter / RawDataset / AnalysisResult / ReportSection / ChartSpec / ReportContext / PreviewPayload / ConfirmPayload / ChatTurn` |
| `models.py` | ORM/SQLModel：`ReportSession / ReportArtifact / UserPreference / PushSubscription / DataPermissionAuditLog` |
| `repository.py` | 三个仓储：`FlyReportRepository`、`UserPreferenceRepository`、`PushSubscriptionRepository` |
| `cache.py` | `RawDatasetCache`（按 NormalizedFilter hash），`PreviewCache` |

#### 4.1.3 意图与对话

| 文件 | 职责 |
|---|---|
| `intent/parser.py` | 主意图解析（LLM + JSON Schema 强约束） → `DraftFilterSpec` |
| `intent/clarifier.py` | 模糊指令追问：基于缺失字段生成澄清问题；最多 N 轮，超出走"错误引导" |
| `intent/conflict_checker.py` | 检测条件冲突（如"下周的报告"→ 时间未来不可统计）|
| `intent/history_query.py` | 历史报告自然语言检索的解析器 |
| `intent/followup_router.py` | 多轮对话中的意图增量更新（"改成自规局" → patch FilterSpec）|

#### 4.1.4 数据接入（dikong）

| 文件 | 职责 |
|---|---|
| `dikong/client.py` | httpx.AsyncClient 薄封装；token 注入、租户头、重试、超时、限流（aiolimiter）|
| `dikong/endpoints.py` | 关键端点常量（见 §6 矩阵），结构化分组 |
| `dikong/auth.py` | token 获取/刷新（如需）|
| `dikong/parsers.py` | 响应 → pydantic 模型映射（应对字段缺失/未知字段告警）|

#### 4.1.5 领域逻辑

| 文件 | 职责 |
|---|---|
| `data_fetcher.py` | 按 `NormalizedFilter` 决定调哪些 dikong 端点；并发 + 同环比双周期取数；返回 `RawDataset` |
| `analyzer/__init__.py` | 入口 `analyze(raw, filter)` |
| `analyzer/aggregations.py` | 聚合：按部门/飞手/日/任务类型 |
| `analyzer/comparisons.py` | 同比、环比、占比、排名、横向对比 |
| `analyzer/anomalies.py` | 异常事件聚合（HMS、失败任务、误识别率）|
| `analyzer/kpi.py` | KPI 字段定义与计算 |
| `permission/checker.py` | 数据权限校验（部门白名单、飞手归属、维度）|
| `permission/audit.py` | 写 `DataPermissionAuditLog`（PRD 2.5.2 要求）|

#### 4.1.6 渲染与导出

| 文件 | 职责 |
|---|---|
| `composer/composer.py` | 按 `include_modules` 装配 sections，调 LLM 生成章节解读文本（趋势/对比） |
| `composer/section_summarizer.py` | LLM 生成"飞行时长较上月 +20% 因 X" 这类自然语言总结 |
| `composer/preview_renderer.py` | Jinja2 → preview_html（含 ECharts JS）|
| `composer/templates/preview/report.html.j2` | 预览主模板 |
| `composer/templates/preview/sections/*.html.j2` | 各模块（overview / flight / algorithm / media / dept_compare / pilot_compare） |
| `composer/templates/preview/macros.html.j2` | echart_block / kpi_card / table |
| `chart/chart_factory.py` | `(series, chart_type) → ECharts option`（预览用）|
| `chart/matplotlib_renderer.py` | 同一 series → PNG（docx/pdf/markdown 三种导出均嵌入或引用 PNG，统一制图源）|
| `export/router.py` | `RendererRouter`：根据 `output_format` 分发到下面三个 Renderer。唯一对上调用口 |
| `export/base.py` | `BaseRenderer` 抽象：`render(ctx) -> RenderedArtifact{path, mime, format, extras}` |
| `export/docx_renderer.py` | docxtpl 渲染 → `report.docx`；图表以 PNG 插入 |
| `export/pdf_renderer.py` | 复用 `composer/preview_renderer.py` 产出的 HTML，走 WeasyPrint 渲染 → `report.pdf`（中文字体预装） |
| `export/markdown_renderer.py` | Jinja2 markdown 模板 → `report.md`；图表另存为 PNG 资产目录并以相对路径引用 |
| `export/templates/docx/report.docx.j2` | docxtpl 模板（含表格、图表占位、备注栏占位）|
| `export/templates/docx/cover.docx.j2` | docx 封面模板（部门/周期/生成时间）|
| `export/templates/pdf/report.html.j2` | PDF 专用 HTML 模板（可复用预览宏，但面向打印布局：页眉/页脚/分页）|
| `export/templates/markdown/report.md.j2` | Markdown 模板（表格、图片链接、门类标题层级）|

#### 4.1.7 偏好与推送

| 文件 | 职责 |
|---|---|
| `preference/learner.py` | 被动学习：`record_filter / record_options / record_edit_signal` |
| `preference/manager.py` | 偏好 CRUD（自然语言指令最终落到这里）|
| `preference/applier.py` | 在 Composer/Filter 阶段应用偏好（默认值、隐藏字段、模板提示） |
| `push/scheduler.py` | APScheduler 注册周报/月报 cron + 数据洞察 cron |
| `push/orchestrator.py` | 周期推送编排 |
| `push/insight_engine.py` | 数据建议规则引擎（增长阈值、异常突增等）|
| `push/notifier.py` | 站内信 / WebSocket 通道适配 |

#### 4.1.8 提示词（独立目录隔离）

> **隔离原则**：本期 FlyReport 为新增需求，所有 prompt 一律落在仓库已有的 `swarmmind/prompt_template/` 下、新建子包 `swarmmind/prompt_template/fly_report/`，**不与通用 Agent prompt（`planner.py` / `execution.py` / `review.py` 等）混放**，避免命名冲突与跨 domain 污染；domain 包内（`swarmmind/domains/fly_report/`）**不再放 prompt 文件**。Prompt 文件统一通过 `swarmmind/prompt_template/fly_report/__init__.py` 暴露的 `load_prompt(name: str) -> str` 加载（包内资源 / `importlib.resources`），调用方禁止用绝对路径。

目录结构：

```
swarmmind/prompt_template/fly_report/
  __init__.py                  # load_prompt() / 渲染辅助 / few-shot 装载
  intent_parse.md              # DraftFilterSpec 抽取（带 JSON schema 与 few-shot）
  clarify.md                   # 缺失字段追问
  error_hint.md                # 无法识别时的友好引导
  section_summary.md           # 章节文字总结（趋势/对比）
  history_query.md             # 历史报告检索意图
  followup_patch.md            # 增量更新 FilterSpec
  preference_command.md        # 偏好查/改/删指令解析
  _shared/
    json_schemas/              # 与 prompt 配套的 JSON Schema（response_format 用）
      filter_spec.schema.json
      history_query.schema.json
      preference_command.schema.json
    few_shots/                 # few-shot 示例样本（按场景拆分）
      intent_parse.examples.jsonl
      clarify.examples.jsonl
```

| 文件 | 用途 |
|---|---|
| `prompt_template/fly_report/intent_parse.md` | DraftFilterSpec 抽取（带 JSON schema 与 few-shot）|
| `prompt_template/fly_report/clarify.md` | 缺失字段追问 |
| `prompt_template/fly_report/error_hint.md` | 无法识别时的友好引导 |
| `prompt_template/fly_report/section_summary.md` | 章节文字总结（趋势/对比）|
| `prompt_template/fly_report/history_query.md` | 历史报告检索意图 |
| `prompt_template/fly_report/followup_patch.md` | 增量更新 FilterSpec |
| `prompt_template/fly_report/preference_command.md` | 偏好查/改/删指令解析 |
| `prompt_template/fly_report/_shared/json_schemas/*.schema.json` | LLM `response_format=json_schema` 强约束 |
| `prompt_template/fly_report/_shared/few_shots/*.jsonl` | few-shot 样本，与 prompt 解耦便于单测/回归 |

### 4.2 API 路由（已有 vs 新增）

#### 4.2.1 已有 API（不改动，仅复用）

来源：[swarmmind/api/server.py](swarmmind/api/server.py)。FlyReport **不复用任何业务路由**，仅复用其底层基础设施（FastAPI app、`lifespan` 容器注入、统一鉴权/异常处理/`get_container()`）。

| 已有端点 | 用途 | 与 FlyReport 关系 |
|---|---|---|
| `GET /` / `GET /health` | 站点 / 健康检查 | 无关，沿用 |
| `POST /v1/tasks` | 通用 Agent 任务提交 | **不复用**。FlyReport 走自己的会话 API，不进通用 task 队列 |
| `GET /v1/tasks` / `GET /v1/tasks/{id}` / `GET /v1/tasks/{id}/detail` | 任务列表 / 详情 | 无关 |
| `GET /v1/runs/{id}` / `/status` / `/events` / `/stream` | Run 详情 / 流事件 / SSE | 无关 |
| `GET /v1/runs/{id}/subtasks/{sid}/events` / `/artifacts` | 子任务事件 / 工件 | 无关 |
| `GET /v1/runs/{id}/artifacts/{aid}/content` | 工件下载 | 无关（FlyReport 走 `/v1/fly-reports/archive/{id}/download`） |
| `DELETE /v1/tasks/{id}` | 任务删除 | 无关 |

> 结论：现有 12 条业务路由 0 条与 FlyReport 业务语义重叠。FlyReport 仅在 `swarmmind/api/server.py` 里加 **一行** `app.include_router(fly_report_router)`。

#### 4.2.2 新增 API（全部本期新增）

新文件：`swarmmind/api/fly_report_routes.py`，挂载前缀 `/v1/fly-reports`。

**(a) 会话生命周期 / 多轮对话**

| 端点 | 状态 | 说明 |
|---|---|---|
| `POST /v1/fly-reports/sessions` | 🆕新增 | 新建对话会话；body: `{initial_query?}` |
| `POST /v1/fly-reports/sessions/{sid}/messages` | 🆕新增 | 发送一句话；返回结构化 reply（追问 / 数据概述 / 预览链接 / 建议）|
| `POST /v1/fly-reports/sessions/{sid}/confirm` | 🆕新增 | 确认生成；body: `{output_format: "docx"\|"pdf"\|"markdown"}`，缺省取偏好默认 |
| `POST /v1/fly-reports/sessions/{sid}/cancel` | 🆕新增 | 取消当前会话 |
| `GET  /v1/fly-reports/sessions/{sid}` | 🆕新增 | 单会话快照（state、当前 FilterSpec、最近预览）|
| `GET  /v1/fly-reports/sessions/{sid}/preview` | 🆕新增 | 当前预览 HTML |

**(b) 历史对话检索 / 流水**（按需求新增的"历史对话搜索 + 列表"）

| 端点 | 状态 | 说明 |
|---|---|---|
| `GET /v1/fly-reports/sessions` | 🆕新增 | **历史对话列表 / 搜索**。query：`q`（关键词，命中最近用户消息 / 当前 FilterSpec.title / 部门名）、`state`（`previewing`/`archived`/`failed`/...）、`from`/`to`（按 `updated_at`）、`department_id`、`period_kind`（weekly/monthly/custom）、`has_artifact`（bool，仅返回已生成报告的会话）、`page`/`page_size`、`sort`（`updated_at_desc`/`created_at_desc`）。返回每条：`{session_id, state, title, last_user_text, filter_summary, last_message_at, created_at, artifact_ref?}` |
| `GET /v1/fly-reports/sessions/{sid}/messages` | 🆕新增 | **单会话历史消息分页**。query：`before_id`/`after_id`（游标）、`limit`（默认 50，最大 200）、`role`（可选过滤）。返回 `ChatTurn` 列表 + 下一页游标。完整流水从 PG `report_chat_turn` 读，Redis 仅缓存最近 N 轮（见 §10.6.4） |
| `DELETE /v1/fly-reports/sessions/{sid}` | 🆕新增 | 软删除会话（仅置 `state=cancelled` + 设短 TTL，不立即物理删；归档报告独立保留） |

**(c) 报告归档（已生成的报告文件）**

| 端点 | 状态 | 说明 |
|---|---|---|
| `GET  /v1/fly-reports/archive` | 🆕新增 | 归档列表查询；query：`q`/`dept`/`pilot`/`period`/`from`/`to`/`output_format`/`page`/`page_size` |
| `GET  /v1/fly-reports/archive/{report_id}` | 🆕新增 | 归档元信息（FilterSpec、摘要、关联 session_id、过期时间） |
| `GET  /v1/fly-reports/archive/{report_id}/download` | 🆕新增 | 下载报告（鉴权 + 审计；Content-Type 随 docx/pdf/markdown） |
| `POST /v1/fly-reports/archive/{report_id}/edit-signal` | 🆕新增（M4） | 前端上报"用户编辑了哪些段落"，喂给 `PreferenceLearner` |

**(d) 偏好与推送**

| 端点 | 状态 | 说明 |
|---|---|---|
| `GET   /v1/fly-reports/preferences` | 🆕新增 | 获取当前用户偏好 |
| `PATCH /v1/fly-reports/preferences` | 🆕新增 | 偏好增/改/删（也可由对话间接触发） |
| `GET   /v1/fly-reports/push/subscriptions` | 🆕新增 | 推送订阅查询 |
| `PUT   /v1/fly-reports/push/subscriptions` | 🆕新增 | 订阅 / 更新周报 / 月报推送 |

> **历史对话搜索说明**（与归档检索的边界）：
> - `GET /v1/fly-reports/sessions` 面向 **"我之前跟报告助手聊过什么"**，召回单位是会话，无论是否已生成报告（含半途取消、卡在追问的会话）。
> - `GET /v1/fly-reports/archive` 面向 **"我之前生成过哪些报告文件"**，召回单位是已落盘的 `report_artifact`。
> - 两者数据源不同（`report_session` vs `report_artifact`），可通过 `session_id` 互链；实现上各走一个仓储方法，不共用 SQL。
> - 实现要点：列表查询统一走 `(tenant_id, user_id, updated_at DESC)` 索引，关键词命中走 PG `tsvector`（[§10.5.2](#1052-表设计ddl-草案) 已为 `report_artifact` 建 `search_vec`，`report_session` 需追加 `last_user_text TEXT` + `search_vec TSVECTOR` + GIN 索引）。

#### 4.2.3 配套 Schema 变更（落到 §10.5.2）

`report_session` 表追加列以支撑历史对话搜索：

```sql
ALTER TABLE fly_report.report_session
  ADD COLUMN title           TEXT,                    -- 由首条用户消息或 FilterSpec 自动生成
  ADD COLUMN last_user_text  TEXT,                    -- 冗余最近一条用户消息，列表页一眼可读
  ADD COLUMN last_message_at TIMESTAMPTZ,             -- 排序用，避免 join chat_turn
  ADD COLUMN search_vec      TSVECTOR;
CREATE INDEX idx_session_search ON fly_report.report_session USING GIN (search_vec);
CREATE INDEX idx_session_user_updated ON fly_report.report_session (tenant_id, user_id, last_message_at DESC NULLS LAST);
```

### 4.3 新增：配置与模板资产

| 文件 | 说明 |
|---|---|
| `configs/fly_report.yaml` | dikong base_url / token / tenant_header / api_timeout / cache_ttl / archive_ttl / push.weekly_cron / push.monthly_cron / insight.thresholds / export.default_format |
| `swarmmind/domains/fly_report/export/templates/docx/report.docx.j2` | docx 母版（手工产出，存仓） |
| `swarmmind/domains/fly_report/export/templates/pdf/report.html.j2` | PDF 打印布局 HTML 模板 |
| `swarmmind/domains/fly_report/export/templates/markdown/report.md.j2` | Markdown 模板 |
| `swarmmind/domains/fly_report/composer/templates/preview/*.html.j2` | 预览模板 |

### 4.4 新增：测试

```
tests/fly_report/
  unit/
    test_intent_parser.py             # mock LLM 输出，覆盖 happy/模糊/冲突/错误
    test_clarifier.py
    test_conflict_checker.py
    test_history_query_parser.py
    test_followup_patch.py
    test_filter_compiler.py
    test_permission_checker.py
    test_dikong_client.py             # respx mock
    test_data_fetcher_routing.py      # filter → endpoints 矩阵断言
    test_aggregations.py
    test_comparisons.py
    test_anomalies.py
    test_chart_factory.py
    test_matplotlib_renderer.py       # 仅断言生成 PNG 字节
    test_preview_renderer.py          # snapshot
    test_docx_renderer.py             # 断言关键占位被替换
    test_pdf_renderer.py              # 断言生成 pdf 且页数 > 0
    test_markdown_renderer.py         # 断言 .md 含预期章节与图片链接
    test_renderer_router.py           # 按 output_format 分发正确
    test_preference_learner.py
    test_preference_applier.py
    test_insight_engine.py
  integration/
    test_session_flow.py              # 对话状态机全路径（mock dikong + LLM）
    test_archive_search.py
    test_push_scheduler.py            # 时间冻结
  e2e/
    test_generate_weekly_report_docx.py     # 生成 docx
    test_generate_weekly_report_pdf.py      # 生成 pdf
    test_generate_weekly_report_markdown.py # 生成 md
```

### 4.5 改动现有文件（依旧最小侵入）

| 文件 | 改动 |
|---|---|
| `swarmmind/api/server.py` | `app.include_router(fly_report_router)`，**单行** |
| `swarmmind/config/schema.py` | 增 `FlyReportSettings` 字段挂入 `SwarmMindConfig` |
| `swarmmind/config/settings.py` | 加载 `configs/fly_report.yaml` 合并 |
| `swarmmind/app/container.py` | 注册 `DikongClient` / `FlyReportService` / 三个 Repository / `PushScheduler` 的生命周期 |
| `swarmmind/repositories/__init__.py` | 暴露三个新 repo |
| `swarmmind/app/bootstrap.py` | 启动时调 `PushScheduler.start()`、关闭时 `stop()` |
| `pyproject.toml` | 新增依赖：`jinja2`、`docxtpl`、`python-docx`、`weasyprint`、`matplotlib`、`httpx`（如缺）、`aiolimiter`、`apscheduler`、`respx`（test）|
| `front/task_show/`（可选 P2）| 飞行报告对话页：左侧聊天 + 右侧预览 iframe + 确认/下载按钮 |

> 通用 Agent 链路（`agents/`、`orchestration/`、`sandbox/`、`tools/`、`skill_system/`）**不动**。

---

## 5. 关键 Schema（草稿）

```python
# schemas.py
class Period(BaseModel):
    kind: Literal["weekly","monthly","custom"]
    start: datetime
    end: datetime
    label: str  # "2026年第15周" / "2026年4月" / "2026-04-01 ~ 2026-04-15"

class Dimension(BaseModel):
    scope: Literal["overall","department","pilot"]
    department_ids: list[str] = []   # scope=department/overall 都可带
    pilot_ids: list[str] = []        # scope=pilot
    compare_with: list[str] = []     # 横向对比目标 id 列表

Indicator = Literal[
    "flight",        # 次数/时长/里程/航点/告警
    "algorithm",     # 识别次数/目标数/准确率/误报率/类目占比
    "media_image",   # 张数/标注/场景分布
    "media_video",   # 数量/时长
    "device_health", # HMS 告警/异常
]

class ReportOptions(BaseModel):
    include_charts: bool = True
    include_trend: bool = True   # 同比环比文本
    include_compare: bool = True
    notes_section: bool = False  # 备注栏（受偏好影响）
    locale: str = "zh-CN"
    output_format: Literal["docx","pdf","markdown"] = "docx"  # 输出格式

class FilterSpec(BaseModel):
    period: Period
    dimension: Dimension
    indicators: list[Indicator]
    options: ReportOptions
    # 模糊缺失时为 None；clarifier 会基于此追问
    missing: list[str] = []
    conflicts: list[str] = []

class NormalizedFilter(FilterSpec):
    """已解决所有歧义、可哈希、可缓存。"""
    hash: str

class RawDataset(BaseModel):
    current: dict[str, Any]   # endpoint_key -> raw payload
    previous: dict[str, Any]  # 上一周期（同环比用）

class AnalysisResult(BaseModel):
    overall: dict
    by_department: dict[str, dict] = {}
    by_pilot: dict[str, dict] = {}
    comparisons: list[dict] = []
    anomalies: list[dict] = []
    kpis: list[dict] = []

class ChartSpec(BaseModel):
    id: str
    title: str
    chart_type: Literal["line","bar","pie","stacked_bar","heatmap"]
    echarts_option: dict
    series: list[dict]            # 原始序列，docx 渲染 PNG 用
    data_ref: str

class ReportSection(BaseModel):
    id: str
    title: str
    summary_md: str
    kpis: list[dict]
    tables: list[dict]
    charts: list[ChartSpec]

class ReportContext(BaseModel):
    session_id: str
    filter: NormalizedFilter
    sections: list[ReportSection]
    revision: int = 1
    generated_at: datetime
    preview_html_path: str | None = None
    artifact_path: str | None = None      # 最终输出文件路径（docx/pdf/md）
    artifact_format: Literal["docx","pdf","markdown"] | None = None

class ChatTurn(BaseModel):
    role: Literal["user","assistant","system"]
    text: str
    payload: dict | None = None   # preview_url / clarify_questions / archive_hits / data_brief

class SessionState(str, Enum):
    PARSING = "parsing"
    CLARIFYING = "clarifying"
    AUTHORIZING = "authorizing"
    FETCHING = "fetching"
    ANALYZING = "analyzing"
    PREVIEWING = "previewing"
    RENDERING = "rendering"
    ARCHIVED = "archived"
    CANCELLED = "cancelled"
    FAILED = "failed"
```

---

## 6. dikong 接口映射矩阵

`DataFetcher` 根据 `NormalizedFilter.indicators × dimension` 选择端点。下表是 MVP 必接的核心集合（基于 `dikong_api.json` 实际存在的端点）：

| Indicator / 用途 | 端点 | 备注 |
|---|---|---|
| 飞行任务统计 | `GET /missions/getFlyStatis` | 飞行次数/时长/里程 |
| 任务统计 | `GET /missions/getMissionStatis` | 计划/执行情况 |
| 设备运行统计 | `GET /missions/getDeviceStatis` | 设备维度 |
| 媒体（图片/视频）统计 | `GET /missions/getMediaStatic` | 拍摄成果 |
| 算法告警统计 | `GET /missions/getWarnStatic` | 算法告警 |
| 任务列表（明细） | `GET /missions/queryByPage` | 异常事件下钻 |
| 月度任务总览 | `GET /flight-task/calendar/overview` | 月报趋势 |
| 单日任务详情 | `GET /flight-task/calendar/detail` | 异常日下钻 |
| 飞行历史 | `GET /job/log/list` | 飞手/部门归属落到 jobLog |
| 设备健康统计 | `GET /devices/hms/stats` | HMS 概览 |
| 设备健康列表 | `GET /devices/hms/page` | HMS 明细 |
| 成果中心｜图片列表 | `GET /achs/pics` | 图片维度 |
| 成果中心｜视频列表 | `GET /achs/videos` | 视频维度 |
| 成果中心｜存储统计 | `GET /achs/storage/stats` | 存储成果 |
| AI 算法事件 | `GET /algorithmRecord/queryByPageWarn` | 误报率/识别详情 |
| AI 复核事件 | `GET /algorithmRecord/queryByPage` | 准确率核算 |
| 部门字典/归属 | `GET /devices/manage/listDept`, `GET /devices/manage/drone/bound` | 设备-部门映射 |
| Dashboard 概览 | `GET /dashboard/stats/{task,running,resource,achievement}` | 兜底统计 |
| 天气预警统计（可选） | `GET /weatherwarn/getWeatherStats` | 异常关联因素 |

> 同环比策略：每个所选端点用 `Period` 当前区间发一次，用上一周期参数再发一次，分别落到 `RawDataset.current` / `previous`。

> 飞手维度：dikong 没有"按飞手聚合"的现成端点，**通过 `job/log/list` 的飞手字段在 Analyzer 内做二次聚合**（如有更合适端点，后续替换 endpoint 映射，无需动上层）。

---

## 7. 状态机与会话语义

```
              start_session
                   │
                   ▼
              ┌─────────┐ user msg ┌──────────────┐
              │ PARSING │─────────▶│ CLARIFYING   │ (缺失/冲突)
              └────┬────┘          └────┬─────────┘
                   │ 解析完成 / 用户补全     │ 补全
                   ▼                     ▼
              ┌────────────┐      ┌──────────────┐
              │AUTHORIZING │◀─────┤ (回到上面)    │
              └────┬───────┘
        失败       │ 通过
       ────────┐  ▼
       │  ┌────────┐    ┌──────────┐    ┌─────────────┐    ┌─────────────┐
       │  │FETCHING│───▶│ANALYZING │───▶│ PREVIEWING  │───▶│  RENDERING  │
       │  └────────┘    └──────────┘    └────┬────────┘    └────┬────────┘
       │                                     │ 调整                │
       │                                     ▼                    ▼
       │                                 (回到 PARSING)       ┌──────────┐
       │                                     │ 取消              │ARCHIVED  │
       │                                     ▼                  └──────────┘
       └─────────────────────────────▶  ┌──────────┐
                                         │CANCELLED │
                                         └──────────┘
                                  任意阶段错误 → FAILED
```

每次状态切换：
- 写 `ReportSession.state_history`
- 发 `fly_report.state_changed` 事件
- 通过 `messages` 接口对外回放为 `ChatTurn`（含进度文本，对应 PRD 2.3 反馈要求）

---

## 8. 偏好系统数据模型

```python
class UserPreference(BaseModel):
    user_id: str
    filter_history: list[FilterSpec]      # 最近 N 次（去重压缩）
    favored_periods: dict[str, int]       # weekly:12, monthly:5
    favored_departments: dict[str, int]
    favored_indicators: dict[Indicator, int]
    report_options_default: ReportOptions
    template_hints: dict                  # {"notes_section": True, "chart_style": "..."}
    disabled: list[str] = []              # 显式禁用项
    updated_at: datetime
```

应用时机：
- IntentParser：作为 prompt 中的"用户偏好上下文"
- FilterCompiler：未指定字段时用偏好默认值
- Composer：决定章节顺序、是否含备注栏、图表样式

---

## 9. 推送系统

| 触发 | 内容 | 实现 |
|---|---|---|
| 每周一 09:00 | "您订阅了周报，是否按上次偏好生成 XX 部门本周周报？" | APScheduler cron → `PushOrchestrator` |
| 每月 1 日 09:00 | 同上，月报 | 同 |
| 数据洞察规则命中 | "本月飞行较上月 +22%，建议加增长分析" | `InsightEngine` 周期跑 + 阈值 |
| 用户响应 | 点确认 → 复用 `start_session` + 预填 FilterSpec 一键到 `confirm` | `notifier` 回链 |

---

## 10. 权限与审计

- `PermissionGate` 在 `AUTHORIZING` 阶段执行，校验：
  - dimension.department_ids ⊂ user 可见部门
  - dimension.pilot_ids ⊂ user 可见飞手（管理员/部门管理员/飞手本人）
  - indicators 是否被角色限制
- 失败：写 `DataPermissionAuditLog{user, attempted_filter, reason}` + 立即返回标准化错误
- 成功：同样写"权限使用记录"（PRD 2.5.2"权限追溯"）

---

## 10.5 持久化方案（PostgreSQL）

> 选型：**PostgreSQL 15+** 作为唯一关系型存储；用 `asyncpg` + `SQLAlchemy 2.x async` + `Alembic` 做 ORM 与迁移。所有 FlyReport domain 的会话、偏好、归档、审计、推送订阅一律落 PG。

### 10.5.1 选型理由

| 维度 | 选择 | 说明 |
|---|---|---|
| 主库 | PostgreSQL 15+ | JSONB / 数组 / 全文检索 / 分区表一站式满足；与现有 SwarmMind 仓储约定对齐 |
| 驱动 | `asyncpg` | 高性能异步驱动，配合 FastAPI |
| ORM | `SQLAlchemy 2.x` (async) + `SQLModel`（已在用） | 与现有 `swarmmind/repositories/` 统一风格 |
| 迁移 | `Alembic` | 多 env（dev/staging/prod）+ 自动生成迁移脚本 |
| 连接池 | `asyncpg` 内置池，应用层 `pool_size=10, max_overflow=20`（按服务实例） | 配置见 `configs/fly_report.yaml` |
| 分区 | `report_artifacts`、`data_permission_audit_log` 按 `created_at` 月分区 | 归档过期清理与审计长期保存 |
| 全文检索 | `tsvector + GIN`（中文用 `pg_jieba` 或前置应用层 jieba 分词） | 历史报告的自然语言检索 |

> 与现有架构保持一致：通过 `swarmmind/app/container.py` 注入 `AsyncEngine` / `async_sessionmaker`，仓储类只持有 `AsyncSession`。**不引入新的 DB 中间件**（如 PgBouncer 仅在生产部署阶段评估）。

### 10.5.2 表设计（DDL 草案）

> Schema：`fly_report`。所有表共用 `tenant_id + user_id` 作为隔离维度。

```sql
CREATE SCHEMA IF NOT EXISTS fly_report;

-- 1) 报告会话（对话主表）
CREATE TABLE fly_report.report_session (
    id              UUID PRIMARY KEY,
    tenant_id       TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    state           TEXT NOT NULL,                      -- SessionState
    filter_spec     JSONB,                              -- 当前 FilterSpec
    normalized_hash TEXT,                               -- NormalizedFilter.hash
    revision        INT  NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at      TIMESTAMPTZ                          -- 闲置过期清理（默认 7d）
);
CREATE INDEX idx_session_user      ON fly_report.report_session (tenant_id, user_id, updated_at DESC);
CREATE INDEX idx_session_state     ON fly_report.report_session (state);
CREATE INDEX idx_session_hash      ON fly_report.report_session (normalized_hash);

-- 2) 会话消息（ChatTurn）
CREATE TABLE fly_report.report_chat_turn (
    id           BIGSERIAL PRIMARY KEY,
    session_id   UUID NOT NULL REFERENCES fly_report.report_session(id) ON DELETE CASCADE,
    role         TEXT NOT NULL,                          -- user/assistant/system
    text         TEXT NOT NULL,
    payload      JSONB,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_chat_session ON fly_report.report_chat_turn (session_id, id);

-- 3) 状态机历史
CREATE TABLE fly_report.report_state_history (
    id           BIGSERIAL PRIMARY KEY,
    session_id   UUID NOT NULL REFERENCES fly_report.report_session(id) ON DELETE CASCADE,
    from_state   TEXT,
    to_state     TEXT NOT NULL,
    reason       TEXT,
    extra        JSONB,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_state_session ON fly_report.report_state_history (session_id, id);

-- 4) 报告归档（30 天 TTL，按月分区）
CREATE TABLE fly_report.report_artifact (
    id             UUID NOT NULL,
    tenant_id      TEXT NOT NULL,
    user_id        TEXT NOT NULL,
    session_id     UUID,
    title          TEXT NOT NULL,
    period_label   TEXT NOT NULL,
    period_start   DATE NOT NULL,
    period_end     DATE NOT NULL,
    department_ids TEXT[] NOT NULL DEFAULT '{}',
    pilot_ids      TEXT[] NOT NULL DEFAULT '{}',
    indicators     TEXT[] NOT NULL DEFAULT '{}',
    output_format  TEXT NOT NULL,                       -- docx/pdf/markdown
    file_path      TEXT NOT NULL,
    file_size      BIGINT NOT NULL,
    checksum       TEXT,
    filter_spec    JSONB NOT NULL,
    summary        TEXT,                                 -- 用于检索摘要
    search_vec     TSVECTOR,                             -- 全文检索向量
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at     TIMESTAMPTZ NOT NULL,                 -- 默认 created_at + 30d
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

CREATE INDEX idx_artifact_user      ON fly_report.report_artifact (tenant_id, user_id, created_at DESC);
CREATE INDEX idx_artifact_period    ON fly_report.report_artifact (tenant_id, period_start, period_end);
CREATE INDEX idx_artifact_dept_gin  ON fly_report.report_artifact USING GIN (department_ids);
CREATE INDEX idx_artifact_pilot_gin ON fly_report.report_artifact USING GIN (pilot_ids);
CREATE INDEX idx_artifact_search    ON fly_report.report_artifact USING GIN (search_vec);

-- 5) 用户偏好（每用户单行 + JSONB）
CREATE TABLE fly_report.user_preference (
    tenant_id   TEXT NOT NULL,
    user_id     TEXT NOT NULL,
    preference  JSONB NOT NULL,                          -- UserPreference 完整结构
    version     INT  NOT NULL DEFAULT 1,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, user_id)
);

-- 6) 偏好事件流（学习信号；保留 90 天）
CREATE TABLE fly_report.preference_event (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   TEXT NOT NULL,
    user_id     TEXT NOT NULL,
    kind        TEXT NOT NULL,                           -- filter_confirmed / option_set / disabled / edit_signal
    payload     JSONB NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_pref_event_user ON fly_report.preference_event (tenant_id, user_id, created_at DESC);

-- 7) 推送订阅
CREATE TABLE fly_report.push_subscription (
    id          UUID PRIMARY KEY,
    tenant_id   TEXT NOT NULL,
    user_id     TEXT NOT NULL,
    kind        TEXT NOT NULL,                           -- weekly / monthly / insight
    cron        TEXT,                                    -- 覆盖默认 cron
    filter_spec JSONB,                                   -- 预设 FilterSpec
    enabled     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_push_user ON fly_report.push_subscription (tenant_id, user_id, kind);

-- 8) 数据权限审计日志（按月分区，长期保存）
CREATE TABLE fly_report.data_permission_audit_log (
    id              BIGSERIAL,
    tenant_id       TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    action          TEXT NOT NULL,                       -- query / generate / download
    attempted_filter JSONB NOT NULL,
    granted         BOOLEAN NOT NULL,
    deny_reason     TEXT,
    ip              INET,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- 9) Dikong 原始数据缓存（可选；与 Redis 缓存互补，做"持久化兜底"）
CREATE TABLE fly_report.raw_dataset_cache (
    hash        TEXT PRIMARY KEY,                        -- NormalizedFilter.hash
    payload     JSONB NOT NULL,
    bytes       INT  NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at  TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_raw_cache_expires ON fly_report.raw_dataset_cache (expires_at);
```

### 10.5.3 仓储分层

| 仓储类 | 表 | 备注 |
|---|---|---|
| `FlyReportSessionRepository` | `report_session` + `report_chat_turn` + `report_state_history` | 一个会话一条主记录；turn/history 追加写 |
| `FlyReportArchiveRepository` | `report_artifact` | 列表查询、关键字检索、下载鉴权 |
| `UserPreferenceRepository` | `user_preference` + `preference_event` | 偏好读写 + 事件流追加 |
| `PushSubscriptionRepository` | `push_subscription` | CRUD |
| `PermissionAuditRepository` | `data_permission_audit_log` | 仅追加，不可更新 |
| `RawDatasetCacheRepository` | `raw_dataset_cache` | 仅在 Redis miss 时回退使用（可选启用） |

### 10.5.4 迁移与运维

- 所有 DDL 通过 `alembic/versions/*_fly_report_init.py` 管理；CI 上跑 `alembic upgrade head` 后启动测试。
- 分区表（`report_artifact` / `data_permission_audit_log`）：用 `pg_partman` 或一个轻量 cron job（`worker/tasks/partition_maintenance.py`）每月预创建下两个月分区。
- 归档清理：每天 02:00 跑 `DELETE FROM report_artifact WHERE expires_at < now()`，同时通过对象存储 SDK 删除 `file_path` 文件。
- 备份：PG 物理备份（pg_basebackup + WAL 归档），归档报告文件存对象存储（MinIO/OSS），DB 仅存 `file_path` 与元数据，避免大文件挤压 PG。
- 慢查询：开 `pg_stat_statements`，对 `report_artifact` 列表查询单独建覆盖索引。

### 10.5.5 配置示例

```yaml
# configs/fly_report.yaml
fly_report:
  database:
    dsn: "postgresql+asyncpg://swarmmind:***@pg-host:5432/swarmmind"
    pool_size: 10
    max_overflow: 20
    pool_recycle: 1800
    echo: false
    schema: fly_report
  storage:
    artifact_root: "/data/fly_report/artifacts"   # 或 s3://bucket/fly_report
    artifact_ttl_days: 30
```

---

## 10.6 记忆中间件方案

> FlyReport 涉及两类"记忆"：**(A) 用户长期偏好**（跨会话，必须可解释、可手动管理）；**(B) 会话上下文**（多轮对话窗口、缓存、增量重算）。两类使用不同中间件，避免混用。

### 10.6.1 记忆分层与中间件选型

| 层 | 用途 | 存储 | 生命周期 | 备注 |
|---|---|---|---|---|
| L0 - 进程内 | 单次请求里跨步骤共享（FilterSpec、AnalysisResult） | Python 对象（`contextvars`） | 单请求 | 不持久 |
| L1 - 会话短期记忆 | 多轮对话窗口、当前预览、未确认 FilterSpec | **Redis 7+**（hash + TTL）| 会话有效期（默认 24h，刷新滑动） | 主战场 |
| L2 - 缓存（数据/分析） | `RawDataset`、`AnalysisResult`、preview HTML | **Redis 7+**（key = NormalizedFilter.hash） | TTL（默认 30 分钟）+ LRU | miss 后回 PG `raw_dataset_cache` |
| L3 - 用户偏好长期记忆 | `UserPreference` 主表 + 偏好事件流 | **PostgreSQL**（`user_preference` + `preference_event`） | 永久（用户可清空） | 强一致、可审计、可手改 |
| L4 - 知识检索（可选 / 后续） | 历史报告语义检索、相似偏好推荐 | **Qdrant**（collection: `fly_report_artifact`，payload 关联 `report_artifact.id`） | 跟随归档 30d，与 PG 主表同步软删 | 独立向量服务，按需启用 |

> **不引入** Mem0 / Zep / LangMem 等"记忆框架"。理由：
> 1. FlyReport 的偏好语义高度结构化（FilterSpec / ReportOptions），用 JSONB + 事件流即可表达，无需向量化压缩；
> 2. 偏好必须可被用户"查改删"（PRD 2.4 硬要求），框架式黑盒记忆与之冲突；
> 3. 现有仓储/容器/审计体系已成型，避免再引入第三方记忆服务的运维负担。

### 10.6.2 Redis 键空间约定

```
fr:sess:{session_id}                  HASH    会话快照（state, filter_spec, last_preview_path）  TTL=24h(滑动)
fr:sess:{session_id}:turns            LIST    最近 N 轮 ChatTurn（截断窗口；完整流水仍写 PG）    TTL=24h
fr:cache:raw:{normalized_hash}        STRING  RawDataset(JSON+gzip)                              TTL=30m
fr:cache:analysis:{normalized_hash}   STRING  AnalysisResult(JSON+gzip)                          TTL=30m
fr:cache:preview:{session_id}:{rev}   STRING  preview HTML 路径                                  TTL=2h
fr:lock:session:{session_id}          STRING  分布式锁（防并发渲染覆写），用 swarmmind/locks      TTL=60s
fr:push:dedup:{user_id}:{kind}:{ymd}  STRING  推送去重标记                                       TTL=24h
```

> 复用 `swarmmind/cache/` 与 `swarmmind/locks/` 现有抽象，不直接写 `redis-py` 调用。

### 10.6.3 偏好记忆的写入与召回

**写入路径**（学习闭环，参考 §3.4）：
1. 用户每次 `confirm` 成功 → `PreferenceLearner.record_filter_confirmed(filter_spec)`：
   - 追加一行到 `preference_event(kind='filter_confirmed', payload=filter_spec)`
   - 用滑动窗口（最近 30 条）+ 频次衰减算法重算 `user_preference.preference`，UPSERT 主表
2. 显式偏好指令（"以后默认隐藏视频"）→ `PreferenceManager.apply_command()` 直接修改主表 + 写事件
3. 编辑信号（前端上报）→ `record_edit_signal(report_id, hints)` → 仅写事件，达到阈值后才折算入主表

**召回路径**：
1. `IntentParser` 启动前从 PG 读 `UserPreference`（带短 TTL Redis 缓存：`fr:pref:{user_id}` 60s）
2. 注入 prompt 上下文："用户常用周期=monthly, 常看部门=[农业局], 默认输出=docx, 禁用模块=[notes]"
3. `FilterCompiler` 用偏好填充未指定字段
4. `Composer` 应用模板提示

### 10.6.4 会话短期记忆策略

- **窗口**：Redis 中只缓存最近 12 轮 `ChatTurn`，超出的早期消息走 PG 流水补读
- **滑动 TTL**：每次消息进出都 `EXPIRE 24h`，会话静默 24h 自动清理（PG 主表保留 7d 后清理）
- **断电恢复**：服务重启或 Redis miss → 从 PG `report_session + report_chat_turn` 还原
- **跨节点一致**：写操作先 PG（事务）→ 再回写 Redis；读优先 Redis，miss 回 PG

### 10.6.5 关于"语义记忆 / 向量"

- **本期不启用**。所有偏好都是结构化字段，不需要 embedding。
- **预留扩展位**：归档报告生成 embedding 后写入 **Qdrant** collection `fly_report_artifact`（vector size 由所选 embedding 模型决定，如 1024），payload 至少包含 `{report_id, tenant_id, user_id, period_start, period_end, department_ids, indicators}` 以支持过滤召回；PG `report_artifact` 仅保存 `embedding_status`、`qdrant_point_id` 两列做关联，不在 PG 内存放向量。
- 如未来引入 RAG 风格记忆，加 `swarmmind/memory/vector_store.py` 适配层，后端统一走 **Qdrant**（gRPC/HTTP），由 `swarmmind/app/container.py` 注入 `QdrantClient`；归档过期清理时同步删除对应 point。
- 配置项新增 `fly_report.qdrant.{url, api_key, collection, vector_size, distance}`，默认 `distance=Cosine`；本地开发用 docker-compose 起单节点 Qdrant，生产走集群部署。

### 10.6.6 与 SwarmMind 现有 memory 模块的关系

- 复用 `swarmmind/memory/`：FlyReport 在其中新增 `fly_report_session_memory.py`（封装 L1 Redis 操作）与 `preference_memory.py`（封装 L3 PG 操作），对外暴露统一接口给 `intent/` 与 `composer/`。
- 不在 domain 内直接写 Redis/PG 客户端代码，保持"domain 调 memory，memory 调底层"的单向依赖。

### 10.6.7 配置示例

```yaml
# configs/fly_report.yaml（续）
fly_report:
  redis:
    url: "redis://redis-host:6379/3"
    session_ttl_seconds: 86400
    cache_ttl_seconds: 1800
    preview_ttl_seconds: 7200
  memory:
    chat_window_turns: 12
    preference_cache_ttl_seconds: 60
    preference_event_retention_days: 90
```

---

## 11. 分阶段落地（按 PRD 优先级）

**M1（最短闭环 - 单轮对话生成报告，默认 docx）**
- `schemas / models / repository / config`
- `intent/parser`（不含 clarifier）+ `permission/checker` 直通 + `dikong/client`（核心 5 端点：getFlyStatis / getMediaStatic / getWarnStatic / hms/stats / queryByPage）
- `data_fetcher / analyzer.aggregations / composer / export.router + export.docx_renderer`
- `POST sessions / messages / confirm` + `GET archive` + 下载
- 验收：一句话 → 一份 docx，覆盖"总体周报"

**M1.5 - 补齐另外两种输出格式**
- `export.pdf_renderer`（WeasyPrint）+ `export.markdown_renderer`
- `confirm` 接收 `output_format`；偏好默认值
- e2e：同一 ReportContext 分别导 docx / pdf / md 均成功

**M2 - 部门 / 飞手 / 对比 / 同环比**
- `dimension.department/pilot` 路径全通
- `analyzer.comparisons` + 章节模板加 dept/pilot compare
- `intent/clarifier` + `conflict_checker`
- `prefs.learner`（被动写入）

**M3 - 预览 / 历史检索 / 模糊追问 / 错误引导**
- `composer/preview_renderer` + `preview` 接口
- `intent/history_query` + `archive` 高级检索
- 完整状态机 + 进度反馈文本
- 偏好读：在 IntentParser 注入

**M4 - 推送 / 偏好管理 / 数据洞察**
- APScheduler / `PushOrchestrator` / `InsightEngine`
- 偏好 CRUD（自然语言 + REST）
- 编辑信号上报接口（`POST archive/{id}/edit-signal`）

**M5 - 体验优化**
- 前端对话页（含格式选择器）
- docx / pdf / markdown 模板美化、封面、目录
- 异常熔断、限流细化

---

## 12. 关键风险与对策

| 风险 | 对策 |
|---|---|
| dikong 无飞手聚合端点 | 通过 `job/log` 在 Analyzer 内聚合；建立"飞手归属"快照表，定时刷新 |
| docx 中文 / 图表 | docxtpl + matplotlib 全栈纯 Python；CI 跑导出 smoke test，断言段落与图片数 |
| pdf 中文字体 / 分页 | WeasyPrint + 预装中文字体（Noto/Source Han）；CI smoke 验证页数 ≥ 1、无乱码 |
| markdown 图片迁移 | 产物以"一报告一目录"输出（`report.md` + `assets/*.png`）；引用用相对路径，下载时打包 zip |
| 模糊指令死循环 | Clarifier 限 3 轮，超出转入"错误引导" + 推荐示例 |
| 偏好误学习 | 仅记录"确认生成"那次的 FilterSpec；显式指令最高权重；提供"清空我的偏好" |
| 数据权限被绕过 | `PermissionGate` 是状态机硬卡口；所有 `dikong/client` 调用必须带 user 上下文 |
| 推送疲劳 | 用户级开关 + 频率限制 + 同窗口去重 |
| 大数据量超时 | DataFetcher 分页 + 并发 + 超时；`NormalizedFilter` 强制时间窗 ≤ 92 天（除非显式扩展）|
| LLM JSON 不稳 | 用 response_format=json_schema；失败兜底返回澄清问题 |

---

## 12.5 本期范围与 AgentScope 串联方案

### 12.5.1 本期不启用的能力（明确边界）

| 能力 | 是否启用 | 说明 |
|---|---|---|
| `swarmmind/skill_system/` & `swarmmind/skills/` | ❌ **不启用** | FlyReport 不暴露/消费任何 Skill；不注册到 `AgentSkillCatalog`；不复用 `agent_skill.py` 的解析路径 |
| `swarmmind/sandbox/` & OpenSandbox | ❌ **不启用** | 不创建 sandbox、不调用 `run_command/write_files`；所有 LLM 输出通过结构化 JSON 校验后直接喂给纯 Python 函数（`Analyzer/Composer/Renderer`），无需任何代码执行隔离 |
| 通用 `OmniAgent` / `OmniRunner` 编排 | ❌ **不复用** | FlyReport 不进通用 task 队列；不走 `Planner→Coder→Reviewer` 链路 |
| `tools/` 通用 toolkit（web_search, browser, ...） | ❌ **不启用** | FlyReport agent 的 `Toolkit` 仅注册本 domain 的 `dikong.*` 与 `analysis.*` 工具，与全局 `ToolRegistry` 物理隔离 |
| AgentScope 多 Agent + `MsgHub` | ✅ **启用** | 用作 IntentParser / Clarifier / SectionSummarizer / HistoryQueryParser 等 LLM 节点的载体（详见 §12.5.2） |
| `swarmmind/agents/audited_model.py`（`AuditedOpenAIChatModel`） | ✅ **复用** | 所有 FlyReport 的 LLM 调用强制走它，统一审计/计费/事件 |
| `swarmmind/memory/` | ✅ **复用底座** | 在其下加 `fly_report_session_memory.py`（L1 Redis）+ `preference_memory.py`（L3 PG），不直接用 `InMemoryMemory` |

### 12.5.2 AgentScope 串联拓扑（"以状态机为骨架，Agent 只做 LLM 节点"）

> 与通用 SwarmMind 链路（Planner/Coder/Tester 形成自由对话）**完全不同**：FlyReport 是 **强结构化领域** —— 输入/输出 schema 固定、流程固定、副作用必须可审计。所以采用 **"状态机驱动 + 多个轻量 ReActAgent"** 模式：
> - 状态机（`state_machine.py`）是 master，负责状态流转、写库、发事件、调外部接口（dikong / Qdrant / 渲染）。
> - AgentScope 的 `ReActAgent` 仅承担 **LLM 推理节点**（解析意图 / 追问 / 总结章节 / 解析历史检索），每个节点都是单步 `await agent(msg)` 调用，不做长程对话循环。
> - `MsgHub` 仅在 **同一会话内** 用作消息广播总线，让 `IntentParser` 与 `Clarifier` / `FollowupRouter` 共享上下文（最近 N 轮 user/assistant 消息），不跨会话、不跨用户。

```
ReportSession (state machine, master)
   │
   ├── MsgHub("session:{sid}")  # 仅本会话广播
   │     ├─ IntentParserAgent     (ReActAgent, JSON-only, no tools)
   │     ├─ ClarifierAgent        (ReActAgent, JSON-only, no tools)
   │     ├─ FollowupRouterAgent   (ReActAgent, JSON-only, no tools)
   │     ├─ HistoryQueryAgent     (ReActAgent, JSON-only, no tools)
   │     └─ SectionSummarizerAgent(ReActAgent, JSON-only, no tools)
   │
   ├── DikongClient            (httpx, 非 Agent)
   ├── Analyzer                (纯函数, 非 Agent)
   ├── Composer + RendererRouter (Jinja2/docxtpl/WeasyPrint, 非 Agent)
   └── Repositories            (PG/Redis/Qdrant, 非 Agent)
```

**关键约束**：
1. 所有 Agent 都用 `response_format=json_schema`（参 [§4.1.8 prompt 配套 schema](#418-提示词独立目录隔离)），LLM 直接吐合法 JSON，Python 端 `pydantic.model_validate_json` 即可，**Agent 不带任何 tool**。
2. 同一会话的多次 LLM 调用复用同一个 `MsgHub`，参与者动态加入；调用结束后不解散，留作下一轮 followup。
3. 跨会话 / 跨用户严格隔离：每个 session 一个 `MsgHub` 实例，session 结束 → `await hub.delete(...)` 清理，避免上下文串扰。

### 12.5.3 文件与依赖

新增 `swarmmind/domains/fly_report/agents/`（domain 内私有，不污染通用 `swarmmind/agents/`）：

| 文件 | 职责 |
|---|---|
| `agents/__init__.py` | 暴露 `build_session_hub() / get_intent_agent() / ...` |
| `agents/factory.py` | 用 `AuditedOpenAIChatModel` + 共享 `OpenAIChatFormatter` 装配各 ReActAgent；**Toolkit 始终为空** |
| `agents/intent_parser_agent.py` | `IntentParserAgent`：sys prompt 来自 `prompt_template/fly_report/intent_parse.md`，输出 `DraftFilterSpec` JSON |
| `agents/clarifier_agent.py` | `ClarifierAgent`：基于 `missing/conflicts` 生成澄清问题 |
| `agents/followup_router_agent.py` | `FollowupRouterAgent`：把 "改成农业局" patch 到现有 FilterSpec |
| `agents/history_query_agent.py` | `HistoryQueryAgent`：自然语言 → `{dept?, period?, type?, keyword?}` |
| `agents/section_summarizer_agent.py` | `SectionSummarizerAgent`：把 `AnalysisResult` 段落 → 自然语言总结 |
| `agents/session_hub.py` | 每会话一个 `MsgHub` 的工厂 + 生命周期 |

> 这些 Agent 都是 **`ReActAgent` 子类的最小化用法**：`tools=Toolkit()`（空）、`memory=InMemoryMemory()`、`max_iters=1`（一次推理就出 JSON 结果，不进入工具循环）。

### 12.5.4 Demo：核心串联代码（可直接落到仓库的最小可运行骨架）

> 下列代码与现有 `swarmmind/agents/factory.py`、`swarmmind/agents/audited_model.py` 的接口对齐，可作为 M1 阶段的起步实现。

#### (a) `agents/factory.py` —— 最小 Agent 工厂

```python
# swarmmind/domains/fly_report/agents/factory.py
from __future__ import annotations
from agentscope.agent import ReActAgent
from agentscope.formatter import OpenAIChatFormatter
from agentscope.memory import InMemoryMemory
from agentscope.tool import Toolkit

from swarmmind.agents.audited_model import AuditedOpenAIChatModel
from swarmmind.prompt_template.fly_report import load_prompt
from swarmmind.domains.fly_report.config import FlyReportSettings


def _build_model(settings: FlyReportSettings, *, event_publisher=None):
    cfg = settings.llm
    return AuditedOpenAIChatModel(
        model_name=cfg.model_name,
        api_key=cfg.api_key,
        event_publisher=event_publisher,
        generate_kwargs={
            "temperature": 0.1,                       # 全部低温保证 JSON 稳定
            "max_tokens": cfg.max_tokens,
            "response_format": {"type": "json_object"},
        },
        client_kwargs={"base_url": cfg.base_url},
    )


def build_intent_agent(settings, *, event_publisher=None) -> ReActAgent:
    return ReActAgent(
        name="fly_report.intent_parser",
        sys_prompt=load_prompt("intent_parse.md"),
        model=_build_model(settings, event_publisher=event_publisher),
        formatter=OpenAIChatFormatter(),
        memory=InMemoryMemory(),
        toolkit=Toolkit(),                            # 关键：无 tool，纯 LLM
        max_iters=1,
    )


def build_clarifier_agent(settings, *, event_publisher=None) -> ReActAgent:
    return ReActAgent(
        name="fly_report.clarifier",
        sys_prompt=load_prompt("clarify.md"),
        model=_build_model(settings, event_publisher=event_publisher),
        formatter=OpenAIChatFormatter(),
        memory=InMemoryMemory(),
        toolkit=Toolkit(),
        max_iters=1,
    )

# build_followup_router_agent / build_history_query_agent /
# build_section_summarizer_agent 同上模式。
```

#### (b) `agents/session_hub.py` —— 每会话一个 MsgHub

```python
# swarmmind/domains/fly_report/agents/session_hub.py
from __future__ import annotations
from contextlib import asynccontextmanager
from agentscope.pipeline import MsgHub          # AgentScope 提供
from agentscope.message import Msg

from .factory import (
    build_intent_agent, build_clarifier_agent,
    build_followup_router_agent, build_section_summarizer_agent,
)


class FlyReportSessionHub:
    """单会话内的 MsgHub + Agents 容器。会话结束时显式 close。"""

    def __init__(self, session_id: str, settings, event_publisher=None):
        self.session_id = session_id
        self.intent       = build_intent_agent(settings, event_publisher=event_publisher)
        self.clarifier    = build_clarifier_agent(settings, event_publisher=event_publisher)
        self.followup     = build_followup_router_agent(settings, event_publisher=event_publisher)
        self.summarizer   = build_section_summarizer_agent(settings, event_publisher=event_publisher)
        self._hub: MsgHub | None = None

    async def __aenter__(self) -> "FlyReportSessionHub":
        self._hub = MsgHub(
            participants=[self.intent, self.clarifier, self.followup, self.summarizer],
            announcement=Msg(
                "system",
                f"FlyReport session {self.session_id} started.",
                role="system",
            ),
        )
        await self._hub.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        assert self._hub is not None
        await self._hub.__aexit__(exc_type, exc, tb)
        self._hub = None
```

#### (c) `service.py` —— 状态机如何调用 Agent（核心串联示例）

```python
# swarmmind/domains/fly_report/service.py（节选）
from agentscope.message import Msg
from .schemas import DraftFilterSpec, FilterSpec, ChatTurn, SessionState
from .agents.session_hub import FlyReportSessionHub
from .state_machine import transition


class FlyReportService:
    def __init__(self, settings, repos, dikong, analyzer, composer, renderer_router,
                 events, locks):
        self.settings, self.repos, self.dikong = settings, repos, dikong
        self.analyzer, self.composer, self.renderer = analyzer, composer, renderer_router
        self.events, self.locks = events, locks

    async def send_message(self, session_id: str, user_text: str, user) -> ChatTurn:
        # 1) 加锁，串行化同一会话
        async with self.locks.acquire(f"fly_report:session:{session_id}"):
            session = await self.repos.session.get(session_id, user)
            await self.repos.session.append_turn(session_id, role="user", text=user_text)

            # 2) 拉起本会话 hub（每个请求重建即可，状态全在 PG/Redis）
            async with FlyReportSessionHub(session_id, self.settings, self.events) as hub:
                # 2.1 PARSING：解析意图
                if session.state in (SessionState.PARSING, SessionState.CLARIFYING):
                    pref = await self.repos.pref.load(user)
                    raw = await hub.intent(
                        Msg("user", user_text, role="user",
                            metadata={"preference": pref.dict(), "now": session.now()}),
                    )
                    draft = DraftFilterSpec.model_validate_json(raw.content)

                    if draft.missing or draft.conflicts:
                        # 2.2 CLARIFYING：让 clarifier 生成追问
                        q = await hub.clarifier(
                            Msg("system",
                                "missing+conflicts payload",
                                role="system",
                                metadata={"draft": draft.model_dump()}),
                        )
                        await transition(session, SessionState.CLARIFYING, repos=self.repos)
                        return await self._reply(session_id, "assistant", q.content,
                                                 payload={"clarify": True})

                # 2.3 跑权限 → 取数 → 分析（纯 Python，无 Agent）
                normalized = await self._compile_filter(draft, user)
                await self._authorize(normalized, user)
                raw_ds  = await self.dikong.fetch(normalized)
                result  = self.analyzer.analyze(raw_ds, normalized)

                # 2.4 PREVIEWING：让 summarizer 写章节文本
                ctx = self.composer.assemble(normalized, result)
                for section in ctx.sections:
                    s = await hub.summarizer(
                        Msg("system",
                            "summarize this section",
                            role="system",
                            metadata={"section": section.model_dump()}),
                    )
                    section.summary_md = s.content

                preview_html = self.composer.render_preview(ctx)
                await self.repos.session.save_preview(session_id, ctx, preview_html)
                await transition(session, SessionState.PREVIEWING, repos=self.repos)
                return await self._reply(
                    session_id, "assistant", "已生成预览，回复『确认生成 docx/pdf/markdown』继续",
                    payload={"preview_path": preview_html, "data_brief": ctx.brief()},
                )

    async def confirm(self, session_id: str, output_format: str, user) -> ChatTurn:
        async with self.locks.acquire(f"fly_report:session:{session_id}"):
            session = await self.repos.session.get(session_id, user)
            ctx = await self.repos.session.load_preview(session_id)
            artifact = await self.renderer.render(ctx, output_format=output_format)
            await self.repos.archive.save(artifact, ctx, user)
            await self.repos.pref.learn_filter_confirmed(user, ctx.filter)  # 偏好被动学习
            await transition(session, SessionState.ARCHIVED, repos=self.repos)
            return await self._reply(
                session_id, "assistant", f"已生成 {output_format}",
                payload={"download_url": artifact.download_url},
            )
```

#### (d) followup 增量更新（"改成农业局" 这种 patch 场景）

```python
# 调用 hub.followup 而不是重新跑 intent
patch_msg = await hub.followup(
    Msg("user", user_text, role="user",
        metadata={"current_filter": session.filter_spec, "history_turns": last_n_turns}),
)
patch = FilterPatch.model_validate_json(patch_msg.content)
new_filter = apply_patch(session.filter_spec, patch)
```

### 12.5.5 单测约定（Agent 层）

- 所有 Agent 单测用 `agentscope.model.MockChatModel`（或自写 `_StubChatModel` 直接返回 JSON 字符串）替换 `AuditedOpenAIChatModel`，**禁止真调 LLM**。
- 关键断言：
  1. 输入特定 user_text → Agent 输出 JSON 通过对应 pydantic schema 校验。
  2. 同一 `MsgHub` 内多个 Agent 调用共享 announcement / 历史，但不跨 hub 实例泄漏。
  3. `Toolkit` 始终为空（防止后续误加 tool 引发副作用）。

---

## 12.6 关于 AgentScope Pipeline 的取舍

> 参考：[AgentScope Task Pipeline](https://doc.agentscope.io/tutorial/task_pipeline.html)，源码 [.venv/lib/python3.12/site-packages/agentscope/pipeline](.venv/lib/python3.12/site-packages/agentscope/pipeline)（`_class.py` / `_functional.py` / `_msghub.py` / `_chat_room.py`）。

### 12.6.1 Pipeline 实际能力（读源码后的事实）

`agentscope.pipeline` 只暴露三类原语，能力面非常窄：

| 原语 | 行为 | FlyReport 是否需要 |
|---|---|---|
| `sequential_pipeline(agents, msg)` / `SequentialPipeline` | `for agent in agents: msg = await agent(msg)`，**仅在 Agent 之间串接 Msg**；agent 必须是 `AgentBase` 子类；无分支、无条件、无非 Agent 步骤 | 局部可用 |
| `fanout_pipeline(agents, msg, enable_gather=True)` / `FanoutPipeline` | `asyncio.gather(*[agent(deepcopy(msg)) for agent in agents])`，同输入扇出到多个 agent，可串行 | **强需要**（章节并行总结） |
| `stream_printing_messages(agents, coroutine)` | 给 agent 装一个共享 `asyncio.Queue`，把 `agent.print(...)` 的内容流式吐回外部 | 后续做 SSE 时用 |
| `MsgHub` / `ChatRoom` | 多 agent 共享广播总线（已经在 §12.5 里启用） | 已用 |

### 12.6.2 为什么不能用 Pipeline 做主流程编排

FlyReport 主链路 [§3.1](#31-报告生成主链路) 的步骤里，只有 **3 个**是 LLM agent 节点（`IntentParser` / `SectionSummarizer` / `Clarifier`），其余 **6 个**全是非 Agent 操作：

| 步骤 | 类型 | 是否能塞进 Pipeline |
|---|---|---|
| `IntentParser` | Agent | ✅ |
| `PermissionGate` | 纯 Python + 写审计表 | ❌ 不是 `AgentBase`；强行包装会丢失结构化错误与权限审计字段 |
| `FilterCompiler` | 纯函数 | ❌ |
| `DikongClient.fetch` | httpx 调外部 + 缓存读写 + 重试 | ❌ 需要重试/超时/限流策略，包成 Agent 反而难治理 |
| `Analyzer` | 纯函数 | ❌ |
| `Composer.assemble` | 模板装配 | ❌ |
| `SectionSummarizer × N` | Agent（多个章节并发） | ✅ **最佳契合点** |
| `PreviewRenderer / DocxRenderer / ...` | I/O + 模板 | ❌ |
| `Archiver` | DB 写 + 文件存储 | ❌ |
| 状态机转移 / 写 `state_history` / 发事件 / 加锁 | 横切关注点 | ❌ Pipeline 不提供 hook |

而且 Pipeline 的能力面里**没有**：
- 条件分支（"若 `missing/conflicts` 非空 → 跳到 Clarifier，否则继续"）
- 失败重试 / 跳步 / 回滚
- 与 PG 事务 / Redis 锁 / 事件总线的 hook
- 状态持久化与中断恢复（FlyReport 依赖 `report_session.state` 在多个 HTTP 请求间跨进程恢复）

把这些塞进 Pipeline 等于 **把主控逻辑藏进"假 Agent"包装类**，反而比当前"状态机 master + 直接 `await agent(msg)`"更难审计、更难单测。所以 **整体流程仍由 [§7](#7-状态机与会话语义) 的状态机驱动**，不替换为 Pipeline。

### 12.6.3 在哪些子链路引入 Pipeline（**收益明确**）

#### (A) `FanoutPipeline` 用于章节并发总结 —— **强烈建议引入**

预览阶段需要给每个 `ReportSection` 调一次 `SectionSummarizerAgent`，N 个章节默认是串行 N 次 RTT。换成 `FanoutPipeline` 一次扇出，在不改 Agent 实现的前提下就能拿到接近 1 次 RTT 的延迟。

修订 [§12.5.4 (c)](#1254-demo核心串联代码可直接落到仓库的最小可运行骨架) 的 PREVIEWING 段落示例：

```python
# swarmmind/domains/fly_report/service.py（PREVIEWING 段落改写）
from agentscope.pipeline import FanoutPipeline
from agentscope.message import Msg

# 每个 section 一个一次性 summarizer agent（共享同一 model 实例即可）
summarizers = [hub.summarizer for _ in ctx.sections]   # 或为每个 section new 一个
fanout = FanoutPipeline(agents=summarizers, enable_gather=True)

# Pipeline 要求所有 agent 收到"同一 Msg"，所以把 section 数据放进 metadata
# 用 list 输入（fanout_pipeline 的 deepcopy 会保留 metadata）
results = await fanout(
    Msg("system", "summarize", role="system",
        metadata={"sections": [s.model_dump() for s in ctx.sections]}),
)
for section, reply in zip(ctx.sections, results):
    section.summary_md = reply.content
```

> 注意：`FanoutPipeline` 默认对所有 agent 喂**同一份 Msg**（`deepcopy`），所以 prompt 设计上 summarizer 必须接受 `metadata.sections + metadata.section_index` 让自己挑出对应 section，或者反向 —— 给每个 section 起一个 ad-hoc summarizer agent，把那段 section 数据塞进它的 sys prompt。当前推荐**后者**：每个 section 一个临时 agent，sys_prompt 里 inject 该 section 的 markdown，避免一个 prompt 处理 N 段引发的"串台"。

#### (B) `SequentialPipeline` 仅在"真线性子段"使用 —— **可选**

唯一两段可能纯线性的子链：

1. **历史报告检索**：`HistoryQueryAgent → ArchiveSearchAgent`（如果未来把 SQL 检索也包成 agent）。本期 `ArchiveSearch` 是纯 SQL，不必拉 agent，所以**当前不引入**。
2. **Followup 改写**：`FollowupRouterAgent → IntentParserAgent`（先 patch 再重解析）。但 followup 的输出是结构化 patch，与 IntentParser 的输入语义不同（`Msg.content` 是自然语言），直接 `SequentialPipeline` 串接需要中间一个 adapter agent，反而比"状态机里两次 `await`"更绕，**不引入**。

#### (C) `stream_printing_messages` —— **后续做 SSE 时引入**

未来 `POST /v1/fly-reports/sessions/{sid}/messages` 想给前端推流式进度（"正在解析意图…" → "正在取数…" → "正在汇总章节…"），可以让各 Agent 用 `await self.print(...)`，外层用 `stream_printing_messages` 把内部进度合并到一个 SSE stream。这是 [§7 状态机](#7-状态机与会话语义) "进度反馈文本"诉求的合理实现路径，但属于 M3 之后的体验优化项，本期不强制。

### 12.6.4 修订后的拓扑

```
ReportSession (state machine, master)            ← 仍是 master
   │
   ├── MsgHub("session:{sid}")                   ← 共享上下文
   │     ├─ IntentParserAgent
   │     ├─ ClarifierAgent
   │     ├─ FollowupRouterAgent
   │     ├─ HistoryQueryAgent
   │     └─ SectionSummarizerAgent (×N, on demand)
   │
   ├── FanoutPipeline(summarizers, enable_gather=True)   ← 新增，仅用于章节并发
   ├── (后续) stream_printing_messages(...)              ← 仅用于 SSE
   │
   ├── DikongClient / Analyzer / Composer / RendererRouter / Repos  ← 非 Agent，状态机直接调
```

### 12.6.5 落地清单（对 §12.5 的增量）

- `agents/section_summarizer_agent.py`：保持单 agent 实现，但 `factory.py` 增 `build_section_summarizers(ctx)`，返回 `list[ReActAgent]`，每个 agent 的 sys_prompt 注入对应 section。
- `service.py` PREVIEWING 段落：用 `FanoutPipeline(summarizers, enable_gather=True)` 替换 `for section in ctx.sections: await hub.summarizer(...)` 的串行循环。
- 单测新增：`test_section_summary_fanout.py`，断言 N 个 section 的 LLM 调用数量与 `asyncio.gather` 并发执行（用 `MockChatModel` 计数）。
- 不动的部分：状态机、Permission、Dikong、Analyzer、Renderer、Archive、Repo —— 一律不包成 Agent，不进 Pipeline。

> **结论一句话**：FlyReport 用 **状态机做主编排 + AgentScope `MsgHub` 做会话级广播 + `FanoutPipeline` 做章节并发**；不上 `SequentialPipeline` 做主流程，避免把强结构化、强副作用的非 Agent 步骤伪装成 Agent。

---

## 13. 立即执行计划

1. 落 `swarmmind/domains/fly_report/` 骨架（空文件 + `schemas.py` 完整版 + `service.py` 桩 + `errors.py` + `agents/`：`factory.py`/`session_hub.py`/`intent_parser_agent.py` 三个最小 Agent，参 §12.5.4 demo）
2. 写 `dikong/client.py` + `dikong/endpoints.py`（先把 §6 矩阵 5 个核心端点接好，配 respx 测试）
3. 写 `intent/parser.py` + `swarmmind/prompt_template/fly_report/intent_parse.md`，配 mock LLM 单测 5 个场景（总体周报 / 部门月报 / 飞手个人 / 部门对比 / 自定义周期）
4. 写 `data_fetcher.py` + `analyzer/aggregations.py` 跑通"总体飞行周报"的 RawDataset → AnalysisResult
5. 实现 `export/router.py` + `export/base.py`，并按顺序落三个 Renderer：
   - `export/docx_renderer.py` + `export/templates/docx/report.docx.j2`（最小母版：封面 + KPI 表 + 一段落 + 一张图）
   - `export/pdf_renderer.py` + `export/templates/pdf/report.html.j2`（WeasyPrint）
   - `export/markdown_renderer.py` + `export/templates/markdown/report.md.j2`
6. 写 `chart/matplotlib_renderer.py`（三种格式共用），跑通 e2e：mock dikong + 真 LLM → 分别产出 docx / pdf / md
7. 把 M1/M1.5 路由挂上 `api/server.py`，`confirm` 接收 `output_format`，开一次端到端冒烟
8. 进入 M2：加部门/飞手维度与对比

确认方向 OK 我就按 1→8 落地，并把当前真实 dikong base_url / token 传给我接通联调。
