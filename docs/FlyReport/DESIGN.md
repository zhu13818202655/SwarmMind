# 飞行报告智能体（FlyReport）设计文档

> 本版按"线性管线 + 多轮追问"的实现思路撰写，目标是把流程做成一条可清晰回放的链路，
> 不引入通用 Skill / Sandbox 框架。复杂度更高的多智能体并行编排版见 [DESIGN-2.md](DESIGN-2.md)。
>
> 输入参考：[需求文档.md](需求文档.md)、[dikong_api.json](dikong_api.json)。

---

## 1. 流程总览

整体是一条单向链路，每一步只做一件事，状态可追溯、可缓存、可回放：

```
用户自然语言
    │
    ▼
[1] IntentParser    ── LLM(JSON) ─▶ FilterSpec（部门/周期/指标/选项）
    │
    ▼
[2] FilterCompiler  ── 解析+权限校验 ─▶ NormalizedFilter（含 hash）
    │
    ▼
[3] DataFetcher     ── DikongClient ─▶ RawDataset（current + previous，用于同/环比）
    │
    ▼
[4] Analyzer        ── 纯函数 ─▶ AnalysisResult（聚合/对比/同环比/异常/KPI）
    │
    ▼
[5] Composer        ── Jinja2 + LLM 段落 ─▶ ReportContext（章节 + ECharts option）
    │
    ▼
[6] HtmlRenderer    ── Jinja2 + ECharts ─▶ report.html（既是预览，也是后续转换源）
    │
    ▼
[7] Exporter        ── HTML→DOCX / HTML→PPTX ─▶ report.docx / report.pptx
    │
    ▼
[8] Archiver        ── 落库 + 30 天 TTL，返回下载链接
```

报告生成完成后进入 **追问阶段（Follow-up）**：

```
用户："把第二段折线图换成柱状图" / "再多说一下农业局环比"
    │
    ▼
FollowupRouter ── 分类（chart_swap / section_qa / regen_section / preference_update / new_report）
    │
    ├─ chart_swap         → ChartFactory 重生成 option → 增量更新 HTML
    ├─ section_qa         → 基于 ReportContext 做 RAG 式问答（不重新取数）
    ├─ regen_section      → 重跑 Composer 的局部 section
    ├─ preference_update  → 写 UserPreference
    └─ new_report         → 回到 [1]，复用缓存
```

---

## 2. 设计要点

| 要点 | 说明 |
|---|---|
| **唯一渲染源是 HTML** | 所有图表先生成 ECharts option → HTML 预览；DOCX/PPTX 由 HTML 转换得到，避免维护多套模板。 |
| **缓存基于 NormalizedFilter.hash** | 重复条件不重复请求 dikong；调整条件时只增量取差集。 |
| **多轮追问不重启管线** | 大多数 follow-up 仅修改 `ReportContext` / `ChartSpec`，省 LLM、省接口。 |
| **LLM 调用统一走审计层** | 复用 `swarmmind.agents.audited_model`，所有 prompt/响应入审计与计费。 |
| **失败显式分类** | `FilterParseError / PermissionDenied / DikongApiError / RenderError / ExportError`，便于前端展示。 |

---

## 3. 文件清单（新增 / 改动）

新增统一放在 `swarmmind/domains/fly_report/`，与通用 agent / orchestration / sandbox 完全解耦。

### 3.1 入口与编排

| 文件 | 职责 |
|---|---|
| [swarmmind/domains/fly_report/__init__.py](../../swarmmind/domains/fly_report/__init__.py) | 导出 `FlyReportService` |
| [swarmmind/domains/fly_report/service.py](../../swarmmind/domains/fly_report/service.py) | 唯一对外入口：`start_session / send_message / confirm / cancel / get_archive`，串联 8 步管线，发布事件 |
| [swarmmind/domains/fly_report/pipeline.py](../../swarmmind/domains/fly_report/pipeline.py) | 8 步线性管线编排，按 step 写 `state_history`、对外回放为 `ChatTurn` |
| [swarmmind/domains/fly_report/state.py](../../swarmmind/domains/fly_report/state.py) | 会话状态枚举：`PARSING → CLARIFYING → AUTHORIZING → FETCHING → ANALYZING → COMPOSING → RENDERING → EXPORTING → ARCHIVED / FOLLOWUP / CANCELLED / FAILED` |
| [swarmmind/domains/fly_report/errors.py](../../swarmmind/domains/fly_report/errors.py) | 上述错误分类 |
| [swarmmind/domains/fly_report/config.py](../../swarmmind/domains/fly_report/config.py) | 读 `SwarmMindConfig.fly_report`：dikong base_url/token、模板路径、缓存/归档 TTL、导出超时 |

### 3.2 数据模型与持久化

| 文件 | 职责 |
|---|---|
| [swarmmind/domains/fly_report/schemas.py](../../swarmmind/domains/fly_report/schemas.py) | Pydantic：`FilterSpec / NormalizedFilter / RawDataset / AnalysisResult / ChartSpec / ReportSection / ReportContext / ChatTurn / FollowupRequest` |
| [swarmmind/domains/fly_report/models.py](../../swarmmind/domains/fly_report/models.py) | ORM：`ReportSession / ReportArtifact / UserPreference` |
| [swarmmind/domains/fly_report/repository.py](../../swarmmind/domains/fly_report/repository.py) | `FlyReportRepository`（会话/产物） + `UserPreferenceRepository` |
| [swarmmind/domains/fly_report/cache.py](../../swarmmind/domains/fly_report/cache.py) | `RawDatasetCache`、`ReportContextCache`（key = filter_hash + tenant + version） |

### 3.3 意图解析与多轮对话

| 文件 | 职责 |
|---|---|
| [swarmmind/domains/fly_report/intent/parser.py](../../swarmmind/domains/fly_report/intent/parser.py) | 主意图解析（LLM JSON Schema 强约束）→ `FilterSpec` |
| [swarmmind/domains/fly_report/intent/clarifier.py](../../swarmmind/domains/fly_report/intent/clarifier.py) | 缺失字段追问（最多 N 轮） |
| [swarmmind/domains/fly_report/intent/conflict_checker.py](../../swarmmind/domains/fly_report/intent/conflict_checker.py) | 条件冲突识别（如"下周月报"） |
| [swarmmind/domains/fly_report/intent/followup_router.py](../../swarmmind/domains/fly_report/intent/followup_router.py) | follow-up 意图分类（chart_swap / section_qa / regen_section / preference_update / new_report） |
| [swarmmind/domains/fly_report/intent/section_qa.py](../../swarmmind/domains/fly_report/intent/section_qa.py) | 基于已生成 `ReportContext` 的问答（不再取数） |

### 3.4 数据接入（dikong）

| 文件 | 职责 |
|---|---|
| [swarmmind/domains/fly_report/dikong/client.py](../../swarmmind/domains/fly_report/dikong/client.py) | `httpx.AsyncClient` 封装：token 注入、租户头、重试、超时、限流 |
| [swarmmind/domains/fly_report/dikong/endpoints.py](../../swarmmind/domains/fly_report/dikong/endpoints.py) | 端点常量与签名（基于 `dikong_api.json`） |
| [swarmmind/domains/fly_report/dikong/parsers.py](../../swarmmind/domains/fly_report/dikong/parsers.py) | 响应 → pydantic 模型映射 |

### 3.5 取数 / 分析 / 权限

| 文件 | 职责 |
|---|---|
| [swarmmind/domains/fly_report/data_fetcher.py](../../swarmmind/domains/fly_report/data_fetcher.py) | 按 `NormalizedFilter` 决定调哪些端点；并发 + 同环比双周期 → `RawDataset` |
| [swarmmind/domains/fly_report/analyzer/aggregations.py](../../swarmmind/domains/fly_report/analyzer/aggregations.py) | 按部门/飞手/日聚合 |
| [swarmmind/domains/fly_report/analyzer/comparisons.py](../../swarmmind/domains/fly_report/analyzer/comparisons.py) | 同比、环比、占比、排名 |
| [swarmmind/domains/fly_report/analyzer/anomalies.py](../../swarmmind/domains/fly_report/analyzer/anomalies.py) | 异常事件聚合（HMS 告警、失败任务等） |
| [swarmmind/domains/fly_report/analyzer/kpi.py](../../swarmmind/domains/fly_report/analyzer/kpi.py) | KPI 字段定义与计算 |
| [swarmmind/domains/fly_report/permission/checker.py](../../swarmmind/domains/fly_report/permission/checker.py) | 部门/飞手数据权限校验（前置） |
| [swarmmind/domains/fly_report/permission/audit.py](../../swarmmind/domains/fly_report/permission/audit.py) | 写权限审计日志（PRD 2.5.2） |

### 3.6 渲染与导出（核心：HTML 是唯一中间产物）

| 文件 | 职责 |
|---|---|
| [swarmmind/domains/fly_report/composer/composer.py](../../swarmmind/domains/fly_report/composer/composer.py) | 装配 sections，调 LLM 生成"趋势/对比"自然语言段落 |
| [swarmmind/domains/fly_report/composer/section_summarizer.py](../../swarmmind/domains/fly_report/composer/section_summarizer.py) | 单 section 文字总结 |
| [swarmmind/domains/fly_report/chart/chart_factory.py](../../swarmmind/domains/fly_report/chart/chart_factory.py) | `(series, chart_type) → ECharts option`；follow-up 切换图表类型也走这里 |
| [swarmmind/domains/fly_report/render/html_renderer.py](../../swarmmind/domains/fly_report/render/html_renderer.py) | Jinja2 → `report.html`（嵌入 ECharts JS） |
| [swarmmind/domains/fly_report/render/templates/report.html.j2](../../swarmmind/domains/fly_report/render/templates/report.html.j2) | 报告主模板（封面 + 概览 + 各模块） |
| [swarmmind/domains/fly_report/render/templates/sections/*.html.j2](../../swarmmind/domains/fly_report/render/templates/sections/) | 子模块：overview / flight / algorithm / media / dept_compare / pilot_compare |
| [swarmmind/domains/fly_report/render/templates/macros.html.j2](../../swarmmind/domains/fly_report/render/templates/macros.html.j2) | `kpi_card / table / echart_block` 宏 |
| [swarmmind/domains/fly_report/export/docx_exporter.py](../../swarmmind/domains/fly_report/export/docx_exporter.py) | HTML → DOCX（推荐 `htmldocx` 或 Pandoc CLI；图表通过 chart_factory 同步出 PNG 嵌入） |
| [swarmmind/domains/fly_report/export/pptx_exporter.py](../../swarmmind/domains/fly_report/export/pptx_exporter.py) | HTML → PPTX（按 section 切片为页；复用 PPTX skill 也可，但默认走纯 python-pptx） |
| [swarmmind/domains/fly_report/export/chart_image.py](../../swarmmind/domains/fly_report/export/chart_image.py) | ECharts option → PNG（`pyecharts.render` 或 matplotlib 同义重画），供 DOCX/PPTX 嵌入 |

### 3.7 偏好（可与 v2 共用一份实现）

| 文件 | 职责 |
|---|---|
| [swarmmind/domains/fly_report/preference/learner.py](../../swarmmind/domains/fly_report/preference/learner.py) | 被动学习：每次确认生成时记录 filter / options |
| [swarmmind/domains/fly_report/preference/manager.py](../../swarmmind/domains/fly_report/preference/manager.py) | 偏好 CRUD（自然语言指令最终落到这里） |
| [swarmmind/domains/fly_report/preference/applier.py](../../swarmmind/domains/fly_report/preference/applier.py) | 在 IntentParser/Composer 中应用偏好 |

### 3.8 提示词

| 文件 | 用途 |
|---|---|
| [swarmmind/domains/fly_report/prompts/intent_parse.md](../../swarmmind/domains/fly_report/prompts/intent_parse.md) | 主意图抽取（含 JSON Schema + few-shot） |
| [swarmmind/domains/fly_report/prompts/clarify.md](../../swarmmind/domains/fly_report/prompts/clarify.md) | 缺失字段追问 |
| [swarmmind/domains/fly_report/prompts/error_hint.md](../../swarmmind/domains/fly_report/prompts/error_hint.md) | 无法识别时引导 |
| [swarmmind/domains/fly_report/prompts/section_summary.md](../../swarmmind/domains/fly_report/prompts/section_summary.md) | 章节文字总结（趋势/对比） |
| [swarmmind/domains/fly_report/prompts/followup_classify.md](../../swarmmind/domains/fly_report/prompts/followup_classify.md) | follow-up 意图分类 |
| [swarmmind/domains/fly_report/prompts/section_qa.md](../../swarmmind/domains/fly_report/prompts/section_qa.md) | 基于报告上下文的问答 |

### 3.9 API 路由

新增：[swarmmind/api/fly_report_routes.py](../../swarmmind/api/fly_report_routes.py)

| 端点 | 说明 |
|---|---|
| `POST /v1/fly-reports/sessions` | 新建会话；body: `{initial_query?}` |
| `POST /v1/fly-reports/sessions/{sid}/messages` | 发送一句话；返回 `ChatTurn`（追问 / 数据概述 / 预览链接 / follow-up 结果） |
| `POST /v1/fly-reports/sessions/{sid}/confirm` | 确认生成最终产物，body: `{format: "html"\|"docx"\|"pptx"}` |
| `POST /v1/fly-reports/sessions/{sid}/cancel` | 取消 |
| `GET  /v1/fly-reports/sessions/{sid}` | 会话快照（state、当前 FilterSpec、最近预览） |
| `GET  /v1/fly-reports/sessions/{sid}/preview` | 返回当前 `report.html` |
| `GET  /v1/fly-reports/archive` | 历史报告检索（支持 `q/dept/period/from/to`） |
| `GET  /v1/fly-reports/archive/{report_id}/download?format=docx` | 下载（鉴权 + 审计） |
| `GET/PATCH /v1/fly-reports/preferences` | 偏好查/改 |

### 3.10 配置与测试

| 文件 | 说明 |
|---|---|
| [configs/fly_report.yaml](../../configs/fly_report.yaml) | dikong base_url/token/tenant_header/timeout、缓存/归档 TTL、导出后端选择 |
| `tests/fly_report/unit/*` | 每个模块单测（mock LLM + respx mock dikong） |
| `tests/fly_report/integration/test_pipeline_flow.py` | 8 步管线全链路（mock dikong+LLM）|
| `tests/fly_report/integration/test_followup_chart_swap.py` | 折线→柱状增量更新 |
| `tests/fly_report/integration/test_followup_section_qa.py` | 报告问答 |
| `tests/fly_report/e2e/test_generate_weekly_report.py` | 跑出真实 `report.html / report.docx` |

---

## 4. 现有代码改动位置（最小侵入）

| 现有文件 | 改动 |
|---|---|
| [swarmmind/api/server.py](../../swarmmind/api/server.py) | 新增一行：`app.include_router(fly_report_router)` |
| [swarmmind/config/schema.py](../../swarmmind/config/schema.py) | 新增 `FlyReportSettings` 字段，挂入 `SwarmMindConfig` |
| [swarmmind/config/settings.py](../../swarmmind/config/settings.py) | 加载 `configs/fly_report.yaml` 合并到 `SwarmMindConfig` |
| [swarmmind/app/bootstrap.py](../../swarmmind/app/bootstrap.py) | 容器注册 `DikongClient / FlyReportService / FlyReportRepository / UserPreferenceRepository / Cache`；启动时无后台调度（线性版不需要 APScheduler） |
| [swarmmind/repositories/__init__.py](../../swarmmind/repositories/__init__.py) | 导出两个新 repository |
| [pyproject.toml](../../pyproject.toml) | 新增依赖：`jinja2`、`httpx`（如缺）、`aiolimiter`、`pyecharts`、`htmldocx` 或 `pypandoc`、`python-docx`、`python-pptx`、`respx`（test） |
| [front/task_show/](../../front/task_show/)（可选） | 新增飞行报告对话页：左侧聊天、右侧 `report.html` iframe、底部确认/下载/换图按钮 |

> 通用 Agent 链路（`swarmmind/agents/`、`swarmmind/orchestration/`、`swarmmind/sandbox/`、`swarmmind/skill_system/`、`swarmmind/tools/`）**完全不动**。

---

## 5. 关键 Schema（草稿）

```python
# schemas.py
class Period(BaseModel):
    kind: Literal["weekly", "monthly", "custom"]
    start: datetime
    end: datetime
    label: str

class Dimension(BaseModel):
    scope: Literal["overall", "department", "pilot"]
    department_ids: list[str] = []
    pilot_ids: list[str] = []
    compare_with: list[str] = []   # 横向对比目标 id

Indicator = Literal["flight", "algorithm", "media_image", "media_video", "device_health"]

class ReportOptions(BaseModel):
    include_charts: bool = True
    include_trend: bool = True
    include_compare: bool = True
    notes_section: bool = False
    output_format: Literal["html", "docx", "pptx"] = "html"  # 预览默认 html
    locale: str = "zh-CN"

class FilterSpec(BaseModel):
    period: Period
    dimension: Dimension
    indicators: list[Indicator]
    options: ReportOptions
    missing: list[str] = []      # clarifier 用
    conflicts: list[str] = []

class NormalizedFilter(FilterSpec):
    hash: str

class ChartSpec(BaseModel):
    id: str
    title: str
    chart_type: Literal["line", "bar", "pie", "stacked_bar", "heatmap"]
    series: list[dict]            # 原始序列：换图表类型时复用
    echarts_option: dict          # 当前渲染态

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
    html_path: str | None = None
    exports: dict[str, str] = {}   # {"docx": "...", "pptx": "..."}

class FollowupRequest(BaseModel):
    kind: Literal["chart_swap", "section_qa", "regen_section",
                  "preference_update", "new_report"]
    target_section_id: str | None = None
    target_chart_id: str | None = None
    new_chart_type: str | None = None
    question: str | None = None
    payload: dict = {}

class ChatTurn(BaseModel):
    role: Literal["user", "assistant", "system"]
    text: str
    payload: dict | None = None    # preview_url / clarify_questions / qa_answer / chart_diff
```

---

## 6. dikong 端点矩阵（MVP 核心）

`DataFetcher` 按 `indicators × dimension` 选择端点（基于 `dikong_api.json`）：

| 用途 | 端点 |
|---|---|
| 飞行任务统计 | `GET /missions/getFlyStatis` |
| 任务统计 | `GET /missions/getMissionStatis` |
| 设备运行统计 | `GET /missions/getDeviceStatis` |
| 媒体（图片/视频）统计 | `GET /missions/getMediaStatic` |
| 算法告警统计 | `GET /missions/getWarnStatic` |
| 任务明细 | `GET /missions/queryByPage` |
| 月任务总览 | `GET /flight-task/calendar/overview` |
| 飞行历史 | `GET /job/log/list`（飞手维度二次聚合） |
| 设备健康 | `GET /devices/hms/stats`、`GET /devices/hms/page` |
| 成果中心 | `GET /achs/pics`、`GET /achs/videos`、`GET /achs/storage/stats` |
| AI 算法事件 | `GET /algorithmRecord/queryByPageWarn`、`GET /algorithmRecord/queryByPage` |
| 部门字典 | `GET /devices/manage/listDept`、`GET /devices/manage/drone/bound` |
| Dashboard 兜底 | `GET /dashboard/stats/{task,running,resource,achievement}` |

> 同/环比策略：每个端点用当前周期参数发一次、上一周期再发一次，分别落 `RawDataset.current` / `previous`。

---

## 7. Follow-up 多轮交互细则

| 用户意图 | 内部动作 | 是否回调 dikong | 是否调 LLM |
|---|---|---|---|
| "把第二段的折线图换成柱状图" | `chart_swap` → `chart_factory.rebuild(series, "bar")` → 替换 `ChartSpec.echarts_option` → 增量重渲 HTML 段 | 否 | 否 |
| "环比涨了 22% 是什么原因？" | `section_qa` → 用 `ReportContext` 拼上下文 → LLM 回答 | 否 | 是 |
| "再把农业局对比这一段重写一下" | `regen_section` → `composer.regen(section_id)` → 重写 `summary_md` | 否 | 是 |
| "以后默认都加备注栏" | `preference_update` → `preference.manager.set("notes_section", True)` | 否 | 否 |
| "顺便也帮我生成自规局的本周报告" | `new_report` → 起新 session 并预填 FilterSpec | 是 | 是 |

每次 follow-up 都会写入 `state_history`、产生新的 `revision`，前端可按 revision 拉增量 diff。

---

## 8. 与 DESIGN-2 的差异点

| 维度 | 本方案（线性） | DESIGN-2（多智能体并行） |
|---|---|---|
| 编排模型 | 8 步线性管线 + follow-up router | 完整状态机 + 多 agent 协作 |
| 主输出 | HTML（再转 DOCX/PPTX） | DOCX 唯一输出 |
| 推送/订阅 | **不在本期范围**（M2 再加 APScheduler） | 内置 |
| 偏好系统 | 仅显式触发 + 被动记录最近 N 次 | 含 template_hints/编辑信号 |
| 适用阶段 | MVP 快速跑通 | 二期增强 |

---

## 9. 落地阶段

**M1（最短闭环 - 单轮线性管线 → HTML/DOCX）**
- `schemas / models / repository / config / cache`
- `dikong/client` + 5 个核心端点（getFlyStatis / getMediaStatic / getWarnStatic / hms/stats / queryByPage）
- `intent/parser`（无 clarifier 简化版）+ `permission/checker`（最小白名单）
- `data_fetcher / analyzer.aggregations / composer / chart_factory / html_renderer / docx_exporter`
- API：`sessions / messages / confirm / preview / download`
- DoD：CLI 提交"生成农业局上周飞行周报" → 落 `report.html` + `report.docx`

**M2（追问 + PPTX + 偏好）**
- `intent/clarifier / conflict_checker / followup_router / section_qa`
- `pptx_exporter` + `chart_image`
- `preference/*`
- DoD：会话内能完成"换柱状图"、"再问一句"、"按偏好改默认"

**M3（推送 + 高级分析）**
- 引入 APScheduler，与 DESIGN-2 的推送模块合并
- `analyzer/comparisons / anomalies / kpi` 完整化、横向部门对比

---

## 10. 风险与对策

| 风险 | 对策 |
|---|---|
| HTML→DOCX 兼容性差（样式丢失） | 默认走 Pandoc CLI，`htmldocx` 作为纯 Python 兜底；图表统一用 PNG 嵌入而非 SVG |
| HTML→PPTX 排版混乱 | 不直接转 HTML，按 `ReportSection` 重新拼 PPTX 母版，`chart_image` 输出 PNG |
| dikong 接口字段不稳定 | 在 `dikong/parsers.py` 集中适配，未知字段记 warning 不报错 |
| LLM 输出 JSON 不合规 | 用 `pydantic` 严格校验 + 一次性自动重试 + 回退到 clarifier |
| 图表换类型时数据语义不匹配（如饼图换折线） | `chart_factory` 维护 `(from, to)` 兼容矩阵，不兼容时回提示 |

---

## 11. Definition of Done（M1）

1. `POST /v1/fly-reports/sessions` 提交"生成农业局上周飞行周报" → 自动跑完 8 步 → 返回 `preview_url`。
2. `POST /confirm {format: "docx"}` 落出可下载的 `report.docx`。
3. 同一 session 再发"把飞行时长趋势图改成柱状图" → 收到新的 `preview_url`，HTML 中对应图表已切换。
4. 失败路径有清晰错误码（`PermissionDenied / DikongApiError / FilterParseError`）。
5. 所有 LLM 调用、dikong 调用都能在审计/事件流中按 `session_id` 检索回放。
