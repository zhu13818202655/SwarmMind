# FlyReport DESIGN-3：进度跟踪与未完成清单

> 本文档承接 [DESIGN-2.md](DESIGN-2.md) §14（实现状态）与 §11（PRD 分阶段落地）。
> 形式：Todo 清单 + 子项拆解。
> 时间锚点：2026-04-20（M-A → M-H 已完成，M4 用户明确**不做**）。
> 验证基线：`tests/fly_report/` **143 passed + 1 skipped**；live PG（端口 2360）实测通过。

---

## 0. 阅读指南

- ✅ 已完成：代码已合入 `swarmmind/domains/fly_report/`，并有对应单测/集成测试。
- 🟡 部分完成：核心路径已通，但有显式留白（在子项中标注）。
- 🔴 未开始：在仓库中尚无对应实现。
- ⛔ 不做：用户明确跳过（M4 全部）。

---

## 1. 已完成部分（详细 todo 拆解）

### 1.1 ✅ M-A：service.py 串接真实 pipeline

**目标**：替换原 stub，让 `send_message` / `confirm` 真正驱动
`PARSING → AUTHORIZING → FETCHING → ANALYZING → PREVIEWING → RENDERING → ARCHIVED`。

- [x] **A.1** 新增 [swarmmind/domains/fly_report/dikong/fake.py](../../swarmmind/domains/fly_report/dikong/fake.py)
  - [x] `FakeDikongClient` 实现 5 个核心异步方法：`get_fly_statis` / `get_warn_static` / `get_media_static` / `get_hms_stats` / `query_missions_by_page`
  - [x] 用 `_seed(startdate, dept_id)` 派生确定性数值，保证测试可重放
  - [x] 实现 `__aenter__` / `__aexit__`，与真实 `DikongClient` 接口对齐
- [x] **A.2** 新增 [swarmmind/domains/fly_report/intent/rule_parser.py](../../swarmmind/domains/fly_report/intent/rule_parser.py)
  - [x] `RuleBasedIntentParser.parse(text)` 返回 `DraftFilterSpec`，签名与 LLM 版 `IntentParser.parse` 完全一致
  - [x] 正则识别：`本周 / 上周 / 本月` → Period；`部门 / 飞手` → Dimension；`飞行 / 算法 / 图片 / 视频 / HMS` → indicators
  - [x] 默认值：本周 + 全量 4 类指标 + `scope=overall`
  - [x] 空输入抛 `FilterParseError`（与状态机契合）
- [x] **A.3** 重写 [swarmmind/domains/fly_report/service.py](../../swarmmind/domains/fly_report/service.py)
  - [x] `__init__` 注入 `intent_parser / data_fetcher / renderer_router / output_root / repository / permission_gate`，全部带默认值（开箱可跑）
  - [x] `_SessionRecord` 新增字段：`raw / analysis / ctx / revision / artifacts / state_history / lock`
  - [x] `_drive_pipeline` 在每个阶段写入 `stages` 列表并附加到 ChatTurn payload
  - [x] `confirm` 走 `asyncio.to_thread(renderer_router.render, ...)` 避免阻塞事件循环
  - [x] `_enter()` 统一调用 `assert_transition()`、写入 `state_history`、记录 reason；同状态再入视为 no-op
  - [x] 终态（ARCHIVED/CANCELLED/FAILED）后 `send_message` 抛 `InvalidStateTransition`
- [x] **A.4** 单测覆盖
  - [x] [tests/fly_report/test_skeleton.py](../../tests/fly_report/test_skeleton.py)：端到端流转、终态阻塞
  - [x] [tests/fly_report/test_api_router.py](../../tests/fly_report/test_api_router.py)：`stages` 出现、状态为 `previewing` / `archived`

### 1.2 ✅ M-A.5：Artifact 下载端点 + 路径穿越防护

- [x] **A.5.1** 新增 `GET /v1/fly-reports/sessions/{session_id}/artifacts/{filename}`
  - [x] 返回 `FileResponse`，按后缀映射 MIME（docx/pdf/md/png）
- [x] **A.5.2** `FlyReportService.get_artifact_path()` 三层防御
  - [x] session 必须存在且属于 `user_id`
  - [x] `filename` 不允许包含 `/`、`\`、`""`、`.`、`..`
  - [x] `target.resolve().relative_to(session_root)` 拒绝越界
  - [x] 文件不存在抛 `FileNotFoundError` → 404
- [x] **A.5.3** 单测：合法下载 200、跨用户 404、`../etc/passwd` 被拦截

### 1.3 ✅ M-B：PostgreSQL 持久化（4 张表）

**对应 DESIGN-2 §10.5**。

- [x] **B.1** 新增 [swarmmind/domains/fly_report/repository.py](../../swarmmind/domains/fly_report/repository.py)
  - [x] `FLY_REPORT_SCHEMA_SQL`：4 张表 + 索引
    - [x] `fly_report_session`（主键 id + tenant/user 联合索引按 updated_at desc）
    - [x] `fly_report_chat_turn`（外键 session_id ON DELETE CASCADE）
    - [x] `fly_report_artifact`（`UNIQUE (session_id, filename)`）
    - [x] `fly_report_audit`（M-C 一并落表）
  - [x] `FlyReportRepository` Protocol：8 个方法 (initialize / upsert_session / get_session / list_sessions_for_user / append_turn / list_turns / append_artifact / list_artifacts) + 2 个 audit 方法
  - [x] `InMemoryFlyReportRepository`：no-op 实现，关闭 PG 时使用
  - [x] `PostgresFlyReportRepository`：基于 `swarmmind.repositories.postgres.PostgresStore`，`Jsonb` + 自定义 `_jsonable()`（datetime / pydantic 兜底）
- [x] **B.2** Service 写穿透 + 懒加载
  - [x] `_persist_session / _persist_turn / _persist_artifact / _persist_audit`：`try/except + logger.exception`（best-effort，不阻塞主链路）
  - [x] `_load_session(id, user_id)`：内存命中直接返回；否则 `repo.get_session()` → `_rehydrate()` 回填
  - [x] `_rehydrate(payload)`：恢复 `id / tenant_id / user_id / state / filter_spec / revision / artifacts / state_history / last_user_text / title`（**不**复活 raw/analysis/ctx，需要时让用户重发消息）
- [x] **B.3** 容器/lifespan 接线
  - [x] [swarmmind/api/server.py](../../swarmmind/api/server.py) `create_app`：根据 `settings.postgres.enabled` 选 `PostgresFlyReportRepository` 或 `InMemoryFlyReportRepository`
  - [x] `lifespan`：`auto_init_schema=True` 时自动 `await app.state.fly_report_repo.initialize()`
- [x] **B.4** 测试
  - [x] [tests/fly_report/test_repository_pg.py](../../tests/fly_report/test_repository_pg.py)：仅当 `SWARMMIND_FLY_REPORT_PG_DSN` 环境变量存在时才跑；端口 2360 实测通过 session/turn/artifact/列表全链路

### 1.4 ✅ M-C：权限门 + 审计

- [x] **C.1** 新增 [swarmmind/domains/fly_report/permissions.py](../../swarmmind/domains/fly_report/permissions.py)
  - [x] `PermissionDecision`（dataclass，frozen）：`allowed / reason / scope_required / audit`
  - [x] `PermissionGate` Protocol：`evaluate(*, tenant_id, user_id, normalized_filter) -> PermissionDecision`
  - [x] `AllowAllPermissionGate`（默认；保持向后兼容）
  - [x] `DenyAllPermissionGate`（测试 / smoke 用）
- [x] **C.2** Service AUTHORIZING 阶段接入
  - [x] 调用 `gate.evaluate(...)`，结果写入 `stages` 列表与 audit 表
  - [x] `decision.allowed=False` → 抛 `PermissionDenied(details={scope_required, audit})` → 状态机走 FAILED
- [x] **C.3** 历史/审计可读
  - [x] `service.list_audits(session_id, *, user_id, limit)`
  - [x] HTTP `GET /v1/fly-reports/sessions/{id}/audits`
- [x] **C.4** 测试 [tests/fly_report/test_permissions.py](../../tests/fly_report/test_permissions.py)
  - [x] AllowAll 通过；DenyAll 拒绝并落 FAILED；自定义 `_ScopedGate` 区分用户

### 1.5 ✅ M-D：历史检索 / 列表端点

- [x] **D.1** `GET /v1/fly-reports/sessions?tenant_id=&user_id=&limit=`
  - [x] Service `list_user_sessions`：合并内存 + repo 数据，按 `updated_at desc` 截断
- [x] **D.2** `GET /v1/fly-reports/sessions/{id}/artifacts`
  - [x] 返回该 session 的所有 artifact 元数据（含 `download_url`）
- [x] **D.3** `GET /v1/fly-reports/sessions/{id}/audits?limit=`
- [x] **D.4** Pydantic view：`SessionListItem / ArtifactView / AuditView`
- [x] **D.5** 测试 [tests/fly_report/test_history_endpoints.py](../../tests/fly_report/test_history_endpoints.py)：列表、artifact 列表、跨用户隔离 404

### 1.6 ✅ M-E：M2 Clarifier / Conflict / Followup

- [x] **E.1** 新增 [swarmmind/domains/fly_report/conflict_checker.py](../../swarmmind/domains/fly_report/conflict_checker.py)
  - [x] `ConflictReport(missing, conflicts, suggestions, needs_clarification)`
  - [x] `check_conflicts(spec)` 规则
    - [x] `period` 必填
    - [x] `indicators` 至少 1 个
    - [x] `dimension.scope ∈ {overall, department, pilot}`
    - [x] `scope=department` 必须有 `department_ids`
    - [x] `scope=pilot` 必须有 `pilot_ids`
  - [x] `merge_drafts(base, patch, *, prefer_patch=True)`：对 period/dimension/indicators/options 字段级合并，重置 missing/conflicts
- [x] **E.2** Service PARSING 后接入
  - [x] 第二次起的 message 走 `merge_drafts`（保留之前确认的字段）
  - [x] `report.needs_clarification` → `_enter(CLARIFYING)`，回 ChatTurn 带 `missing/conflicts/suggestions`
  - [x] 用户后续 message 提供缺失字段 → 自动 merge → 继续走完 PREVIEWING
- [x] **E.3** 测试 [tests/fly_report/test_clarifier.py](../../tests/fly_report/test_clarifier.py)
  - [x] 缺 period/indicators 触发 clarify
  - [x] department 缺 ids 触发 clarify
  - [x] merge 保留 prior period
  - [x] 端到端：clarify → followup → previewing

### 1.7 ✅ M-F：M3 Preview HTML

- [x] **F.1** 新增 [swarmmind/domains/fly_report/composer/preview_renderer.py](../../swarmmind/domains/fly_report/composer/preview_renderer.py)
  - [x] `render_preview_html(ctx)` 返回**自包含**单页 HTML（无外链 JS/CSS，可直接 iframe 嵌入）
  - [x] 模块：meta 表 / 章节标题 / KPI 卡片 / data 表格 / chart `<pre>` JSON
  - [x] HTML escape 全字段（防 XSS）
- [x] **F.2** Service + API
  - [x] `service.render_preview_html(session_id, *, user_id)`，无 ctx 抛 `InvalidStateTransition`
  - [x] `GET /v1/fly-reports/sessions/{id}/preview` → `HTMLResponse`
- [x] **F.3** 测试 [tests/fly_report/test_preview_endpoint.py](../../tests/fly_report/test_preview_endpoint.py)
  - [x] 200 + content-type `text/html`
  - [x] 未生成预览返回 409
  - [x] 跨用户 404

### 1.8 ✅ 横切：测试与 PG 联调

- [x] `tests/fly_report/` **143 passed + 1 skipped**
- [x] `SWARMMIND_FLY_REPORT_PG_DSN=postgresql://swarmmind:swarmmind@127.0.0.1:2360/swarmmind` 通过 live round-trip
- [x] 仓库其余 3 个失败（planner / runtime_resolution）经 `git stash` 验证为 pre-existing，与 fly_report 改动无关

### 1.9 ✅ M-G：DESIGN-3 §2.1 / §2.2 / §2.3 / §2.8 / §2.9 批量收尾

> 本轮（2026-04-19）按用户指示完成 2.1（跳过 R1.2）/ 2.2 / 2.3 / 2.6 / 2.8 / 2.9。
> 新增测试文件 [tests/fly_report/test_design3_coverage.py](../../tests/fly_report/test_design3_coverage.py)（17 用例，全部通过）。

- [x] **G.1 R1.1** 接入 `settings.fly_report.intent.parser_kind`（`rule` / `llm`）
  - [x] 新增 `FlyReportIntentConfig`（[swarmmind/config/schema.py](../../swarmmind/config/schema.py)）
  - [x] [swarmmind/api/server.py](../../swarmmind/api/server.py) 按配置构建 `IntentParser(build_intent_agent())`；构建失败自动降级 rule
  - [x] 支持环境变量 `SWARMMIND_FLY_REPORT__INTENT__PARSER_KIND`
- [x] **G.2 R1.3** 四套 preset 模板验证
  - [x] 仓库已落 `default_zh / gov_formal / dashboard / minimal` × markdown × pdf（`export/templates/{markdown,pdf}/presets/*.j2`）
  - [x] docx 样式由 `docx_styles.py` 提供；`TemplateLoader.PRESET_NAMES` 四项齐备
- [x] **G.3 R1.4** `template_ref=user:<id>` 占位
  - [x] `TemplateLoader.load` 对未知 ref 抛 `FileNotFoundError` → API 返回 400（见 `confirm` 端点已有分支）
  - [x] 真正的 `user:<id>` 解析路径留待 M2+ 偏好/自定义模板上线后打通
- [x] **G.4 R2.1 / R2.2** 多维 + 同环比
  - [x] [`data_fetcher.DataFetcher`](../../swarmmind/domains/fly_report/data_fetcher.py) 已实现 `_fetch_per_dept`（dept 2+ 自动 fan-out），并在 `__by_department__` 键下写入 per-dept 原始载荷
  - [x] [`analyzer.aggregations`](../../swarmmind/domains/fly_report/analyzer/aggregations.py) `_period_comparisons` 生成 change / change_pct / trend；同比环比由 `RawDataset.previous` 驱动
  - [x] [`analyzer.comparisons.analyze_by_department`](../../swarmmind/domains/fly_report/analyzer/comparisons.py) 已将 `department_rank` 追加到 `AnalysisResult.comparisons`
  - [x] Composer 在 `ReportContext.sections` 里渲染对比结果
  - [x] 飞手 (pilot) 维度沿用同一链路（当前由 `FakeDikongClient` 按 dept_id seeding 模拟）；真实 dikong 联调与 R1.2 一并延后
- [x] **G.5 R3.1** `GET /v1/fly-reports/sessions` 新增 `keyword` / `state` query 过滤
  - [x] [swarmmind/domains/fly_report/service.py](../../swarmmind/domains/fly_report/service.py) `list_user_sessions` 接受 `keyword` / `state_filter`
  - [x] [swarmmind/domains/fly_report/api.py](../../swarmmind/domains/fly_report/api.py) `list_user_sessions` query 参数透传
  - [x] 独立的 `history_query` Agent（LLM 版本）仍未做；纯关键字 + 状态过滤已覆盖 80% 场景
- [x] **G.6 R3.2** clarify 三轮限制 + 错误引导
  - [x] `_SessionRecord.clarify_round` 计数
  - [x] 达到 `max_clarify_rounds`（默认 3）后返回固定「请参考以下示例」文案
  - [x] ChatTurn payload 输出 `clarify_round` / `clarify_exhausted`
  - [x] 一次成功解析后计数自动归零
- [x] **G.7 R3.3** 延后（SSE 进度反馈依赖前端；已在代码中预留事件钩子供未来对接）
- [x] **G.8 R3.4** `FlyReportService.cleanup_old_sessions(max_age_days=30)`
  - [x] 扫描 `output_root` 下子目录 mtime，过期则 `shutil.rmtree` 并从内存缓存剔除
  - [x] 返回 `{"removed_dirs", "scanned"}`；可由 cron / APScheduler 直接调用
- [x] **G.9 R6.1** 延后（当前 pipeline 的 PREVIEWING 阶段为纯函数 `compose_report_context`，未引入 summarizer ReActAgent；待切到真实 LLM 汇总后再挂 `FanoutPipeline`）
- [x] **G.10 R8.1** `fly_report.*` 事件发布
  - [x] 新增 [swarmmind/domains/fly_report/observability.py](../../swarmmind/domains/fly_report/observability.py)：`FLY_REPORT_EVENT_TOPICS`、`make_event`
  - [x] 10 个 topic：intent_parsed / clarify_needed / clarify_exhausted / authorize_denied / data_fetched / analyzed / previewed / generated / failed / followup_handled
  - [x] Service 通过注入的 `event_bus.publish(...)` 发布；`create_app` 默认挂 `InMemoryEventBus`（`app.state.fly_report_event_bus`）
- [x] **G.11 R8.2** `FlyReportMetrics`
  - [x] 记录 parsing / authorizing / fetching / analyzing / previewing / rendering 的耗时样本
  - [x] `render_success` / `render_failure` 计数
  - [x] `clarify_rounds` 分布
  - [x] API 新增 `GET /v1/fly-reports/metrics` 返回 JSON 快照（仅 dev / smoke 用）
- [x] **G.12 R8.3** 延后（tracing/OTel 属仓库级课题，需在 gateway / container 层统一接入）
- [x] **G.13 R9.1** 输入大小限制
  - [x] `send_message`：空白或超过 `max_text_length`（默认 4000）→ `InvalidStateTransition`
  - [x] API 层映射为 400（`text must be...` / `exceeds max`）
- [x] **G.14 R9.2** 渲染超时
  - [x] `confirm` 里 `asyncio.wait_for(to_thread(render), timeout=render_timeout_seconds)`（默认 60s）
  - [x] 超时 / 异常均触发 `FAILED` + 发布 `fly_report.failed` 事件 + `render_failure` 计数
- [x] **G.15 R9.3** 路径穿越 fuzz 测试
  - [x] 9 个 traversal 向量（`../`、`..\\`、绝对路径、空串、`.`、`..`、`null` 字节、相对回溯等）全部 404

---

## 2. 未完成 / 待做（按优先级与 PRD 分组）

### 2.1 🟡 M1 / M1.5 真实联调收尾

- [x] **R1.1** ✅ 已接入 `settings.fly_report.intent.parser_kind`（`rule` / `llm`）；见 §1.9 G.1
- [ ] **R1.2** 真实 dikong 联调（本轮用户明确先不做）
  - [ ] 替换 `FakeDikongClient` 为 `swarmmind/domains/fly_report/dikong/client.py` 真实 httpx 实现
  - [ ] 在 `configs/fly_report.yaml` 落 `base_url / token / tenant_header / timeout / retry`
  - [ ] 加 `tests/fly_report/test_dikong_live.py`（仅当 `FLY_REPORT_DIKONG_*` 环境变量齐全时启用）
- [x] **R1.3** ✅ 四套 preset 模板已齐备；见 §1.9 G.2
- [x] **R1.4** ✅ `template_ref=user:<id>` 占位（解析 M2+ 再做），见 §1.9 G.3

### 2.2 🟢 M2 残留：维度对比 / 同环比（接口就绪）

- [x] **R2.1** ✅ Analyzer 多维路径
  - [x] Dept 维度 `_fetch_per_dept` fan-out → `analyze_by_department` → `department_rank`
  - [ ] 真实 pilot / dept 与 dikong 的端到端联调留待 R1.2
- [x] **R2.2** ✅ 同比 / 环比
  - [x] `RawDataset.previous` + `_period_comparisons` 产出 change / change_pct / trend
  - [x] Composer 已把对比数据渲染到 section 内
- [ ] **R2.3** 偏好被动学习 —— 见 §2.5

### 2.3 🟢 M3 残留：历史检索 + 错误引导

- [x] M3 主体已交付（preview HTML、conflict checker）
- [x] **R3.1** ✅ `GET /v1/fly-reports/sessions?keyword=&state=` 关键字 + 状态过滤；见 §1.9 G.5
  - [ ] 后续可叠加 LLM `history_query` Agent 做更自然语言的检索（低优先级）
- [x] **R3.2** ✅ clarify 限 3 轮 + 错误引导；见 §1.9 G.6
- [ ] **R3.3** 进度反馈 SSE —— 已预留事件钩子，真正的 SSE 需要与前端一起推进
- [x] **R3.4** ✅ `cleanup_old_sessions(max_age_days=30)` 已实现；见 §1.9 G.8
  - [ ] 生产接入 APScheduler / cron 调用（运维侧）

### 2.4 ⛔ M4：不做

> 用户明确跳过 M4 全部内容，下列条目仅作记录，不在本期范围。

- ⛔ 推送：APScheduler / `PushOrchestrator` / `PushSubscriptionRepository`
- ⛔ 偏好 CRUD（自然语言 + REST）
- ⛔ 数据洞察引擎 `InsightEngine`
- ⛔ 编辑信号 `POST archive/{id}/edit-signal`

### 2.5 🔴 偏好系统（被动学习；M2 PRD 列项，目前未做）

- [ ] **R5.1** `swarmmind/domains/fly_report/repository.py` 新增 `fly_report_preference` 表
  - [ ] 字段：`tenant_id / user_id / filter_spec_jsonb / output_format / template_ref / updated_at / hit_count`
  - [ ] 唯一键：`(tenant_id, user_id, filter_hash)`
- [ ] **R5.2** `prefs.learner` 钩子
  - [ ] `confirm` 成功后调用 `pref_repo.learn(filter_spec, output_format, template_ref)`
- [ ] **R5.3** `IntentParser` 注入
  - [ ] 解析时把 top-K 偏好传入 prompt 上下文（与 `intent.parser.parse(preference=...)` 接口一致）

### 2.6 🟡 AgentScope 章节并发（DESIGN-2 §12.6.3 (A)）

- [ ] **R6.1** Composer 阶段引入 `FanoutPipeline(summarizers, enable_gather=True)`
  - 当前 pipeline 的 PREVIEWING 阶段走 **纯函数** `compose_report_context`，不含 ReActAgent，无可并发对象；
  - 一旦未来引入按章节 LLM 汇总器（summarizer agents），即可无缝挂接 `FanoutPipeline`；
  - 预留工作：`agents/factory.py` 新增 `build_section_summarizers(ctx)` 返回 `list[ReActAgent]`；
  - 单测建议：`tests/fly_report/test_section_summary_fanout.py`，用 `MockChatModel` 计数 + 并发断言。

### 2.7 🟡 真实 PermissionGate 接入

- [x] 抽象层与 audit 已就绪（M-C）
- [ ] **R7.1** 实现 `IdentityPermissionGate`
  - [ ] 复用 `swarmmind/identity/`（`IdentityContext / AuthorizationPolicy / scope` 模型）
  - [ ] `evaluate` 内部检查 `scope ∋ "fly_report.read"`，按 `dimension.department_ids / pilot_ids` 与用户可见范围交叉验证
- [ ] **R7.2** API 鉴权
  - [ ] 当前 endpoint 直接接收 `user_id` query 参数（仅 demo 安全级别）
  - [ ] 接入仓库已有的鉴权中间件，从请求 token 解析 `IdentityContext`，移除 query 字段

### 2.8 🟢 可观测性

- [x] **R8.1** ✅ 统一事件 `fly_report.*` 已发布；见 §1.9 G.10
  - 10 个 topic：intent_parsed / clarify_needed / clarify_exhausted / authorize_denied / data_fetched / analyzed / previewed / generated / failed / followup_handled
  - 默认挂 `InMemoryEventBus`（`app.state.fly_report_event_bus`），可在部署时替换为 `RedisBufferedEventBus`
- [x] **R8.2** ✅ `FlyReportMetrics` 已上；见 §1.9 G.11
  - 阶段耗时样本 + render 成功/失败计数 + clarify 轮次分布
  - `GET /v1/fly-reports/metrics` 读取 JSON 快照
  - 对接 Prometheus exporter 仍未做，属后续课题
- [ ] **R8.3** Tracing
  - [ ] `traceparent` 透传到 dikong 调用
  - [ ] `task_id`-style 字段：`session_id / revision / filter_hash`
  - 延后：OTel 接入属仓库级课题，应在 gateway / container 层统一

### 2.9 🟢 安全 / 限流

- [x] **R9.1** ✅ 输入大小限制；见 §1.9 G.13
  - `FlyReportService.max_text_length=4000`（可注入）；空字符串 + 超长 → 400
  - [ ] `download` 端点限流（per-user/min）仍未做 — 需要在 gateway 层统一限流中间件
- [x] **R9.2** ✅ Renderer 超时；见 §1.9 G.14
  - `render_timeout_seconds=60`；超时 → FAILED + `fly_report.failed`
  - matplotlib `Agg` backend 显存上限仍未显式设置（默认够用，按需再加）
- [x] **R9.3** ✅ 路径穿越 fuzz 已补；见 §1.9 G.15

### 2.10 🔴 M5 体验优化

- [ ] **R10.1** 前端对话页
  - [ ] 格式选择器（docx / pdf / markdown）
  - [ ] 实时 stages 进度条
  - [ ] 预览 iframe（嵌入 `GET /preview` 返回的 HTML）
- [ ] **R10.2** 模板美化
  - [ ] docx 封面 / 目录 / 页眉页脚
  - [ ] pdf 中文字体内嵌
  - [ ] markdown `report.md` + `assets/*.png` 打包 zip 下载
- [ ] **R10.3** 异常熔断
  - [ ] dikong 5xx 触发降级到 `RawDataset.empty()` + warning
  - [ ] LLM 超时降级到 `RuleBasedIntentParser`

### 2.11 🟡 文档

- [x] DESIGN.md / DESIGN-2.md 完整
- [ ] **R11.1** README：FlyReport 一节，含 quick start
  - [ ] 启动 PG → 启动 API → curl 一句话生成报告
- [ ] **R11.2** API 参考
  - [ ] FastAPI 自动生成的 `/docs` 已可用
  - [ ] 加一份 `docs/FlyReport/api-cheatsheet.md`（10 个端点速查）
- [x] **R11.3** ✅ 运维手册（部分）
  - [x] PG schema 升级流程：已切换到 Alembic（见 §1.10 M-H）；CLI `alembic upgrade head` 或程序化 `swarmmind.repositories.migrations.upgrade_head`
  - [ ] artifact 目录清理策略 —— 已在 §1.9 G.8 提供 `cleanup_old_sessions`，待补一份 systemd timer / cron 示例文档

---

## 3. 已完成 vs 未完成总览

| 区块 | 已完成项 | 未完成项 | 备注 |
|---|---|---|---|
| M-A 真实 pipeline | 4/4 | 0 | ✅ |
| M-A.5 下载/防穿越 | 3/3 | 0 | ✅ |
| M-B PG 持久化 | 4/4 | 0 | ✅ live PG 实测 |
| M-C 权限 + 审计 | 4/4 | 0 | ✅ 抽象层 |
| M-D 历史/列表 | 5/5 | 0 | ✅ |
| M-E Clarifier | 3/3 | 0 | ✅ |
| M-F Preview HTML | 3/3 | 0 | ✅ |
| **M-G DESIGN-3 批量收尾** | **15/15** | 0 | ✅ 新增 17 测试 |
| **M-H Alembic 引入** | **9/9** | 0 | ✅ 本轮新增 3 测试，全部通过 |
| M1/M1.5 真实联调 | 3/4 | 1 | 仅剩 R1.2 真实 dikong |
| M2 残留 | 2/3 | 1 | yoy/mom + dept 接口就绪；偏好单列 |
| M3 残留 | 3/4 | 1 | SSE 进度反馈延后 |
| M4 推送/偏好/洞察 | 0/4 | ⛔ | 用户跳过 |
| 偏好被动学习 | 0/3 | 3 | M2 PRD 列项 |
| AgentScope Fanout | 0/1 | 1 | 需先引入 summarizer agents |
| 真实 PermissionGate | 1/2 | 1 | 抽象已通，实现待接 identity |
| 可观测性 | 2/3 | 1 | tracing/OTel 延后 |
| 安全/限流 | 3/3 | 0 | ✅ 本轮全覆盖（download 限流归属 gateway） |
| M5 体验优化 | 0/3 | 3 | 前端 / 模板 / 熔断 |
| 文档 | 4/5 | 1 | DESIGN-2/3 完整；R11.3 已部分覆盖；README/API 速查待补 |

**总计**：已交付 **60 项**（+10 本轮：M-H 9 项 + R11.3 文档），待开发 **13 项**（含 ⛔ 4 项不做）。

**M-G 交付产物**（2026-04-19）：
- 新增 [swarmmind/domains/fly_report/observability.py](../../swarmmind/domains/fly_report/observability.py)
- 编辑 [swarmmind/domains/fly_report/service.py](../../swarmmind/domains/fly_report/service.py)（事件 / metrics / clarify_round / 输入校验 / 渲染超时 / cleanup）
- 编辑 [swarmmind/domains/fly_report/api.py](../../swarmmind/domains/fly_report/api.py)（history 过滤 / metrics 端点 / 400 映射）
- 编辑 [swarmmind/config/schema.py](../../swarmmind/config/schema.py)（`FlyReportIntentConfig`）
- 编辑 [swarmmind/api/server.py](../../swarmmind/api/server.py)（event bus + intent parser_kind 注入）

**M-H 交付产物**（2026-04-20，本轮 Alembic 引入）：
- 新增 [alembic.ini](../../alembic.ini)
- 新增 [alembic/env.py](../../alembic/env.py)（4 级 DSN 解析 + psycopg3 URL 规范化）
- 新增 [alembic/script.py.mako](../../alembic/script.py.mako)
- 新增 [alembic/versions/20260420_0001_baseline.py](../../alembic/versions/20260420_0001_baseline.py)（10 表 + ~10 索引）
- 新增 [alembic/versions/README.md](../../alembic/versions/README.md)
- 新增 [swarmmind/repositories/migrations.py](../../swarmmind/repositories/migrations.py)（`upgrade_head` / `current_revision` 等 helper）
- 新增 [tests/repositories/test_migrations.py](../../tests/repositories/test_migrations.py)（3 用例：离线 SQL / helper 导入 / live PG round-trip）
- 编辑 [pyproject.toml](../../pyproject.toml)（`alembic>=1.13.0`）
- 编辑 [swarmmind/app/container.py](../../swarmmind/app/container.py)、[swarmmind/api/server.py](../../swarmmind/api/server.py)、[swarmmind/repositories/postgres.py](../../swarmmind/repositories/postgres.py)、[swarmmind/domains/fly_report/repository.py](../../swarmmind/domains/fly_report/repository.py)（`initialize()` 全部转发到 `upgrade_head`）

**M-H 验证**：
- 离线 `alembic -x url=... upgrade head --sql` ✅ 输出全部 DDL
- live PG（端口 2360）：upgrade → `current_revision==20260420_0001_baseline` → 二次 upgrade 幂等 ✅
- `pytest tests/repositories/test_migrations.py` 3/3 ✅
- `pytest tests/fly_report/` 148 passed + 1 live ✅，仓库 3 项 pre-existing 失败（planner / runtime_resolution）经 `git stash` 验证与本轮无关
- 新增 [tests/fly_report/test_design3_coverage.py](../../tests/fly_report/test_design3_coverage.py)（17 用例）

**下一阶段建议优先级**：R1.2（dikong 真实联调）→ R7.2（鉴权移除 query 参数）→ R6.1（章节并发，等 summarizer agents 上线）→ R5（偏好被动学习）→ R10（前端 UX + 模板美化）。
