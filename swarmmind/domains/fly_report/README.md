## Debug Server 端的完整套路

Snapshot 故意只返回**会话状态**（state / filter / counts），**真正的执行轨迹**分散在 4 个端点 + 文件系统里。下面是一张「我现在到底跑了什么、产物在哪」的对照表。

### 1. 看程序到底执行了哪些阶段 → `/turns`

每个 assistant turn 的 `payload.stages` 就是 pipeline 流水帐，带每个阶段的关键指标：

```bash
SID=<session_id>
curl -s "http://127.0.0.1:8000/v1/fly-reports/sessions/$SID/turns?user_id=u1" \
  | python -m json.tool
```

返回里能看到（实测刚才的输出）：
```json
"stages": [
  {"stage":"parsing",     "period":"2026年第15周","scope":"overall","indicators":["flight"]},
  {"stage":"authorizing", "decision":"allow","reason":"allow-all"},
  {"stage":"fetching",    "current_keys":["fly_statis"],"previous_keys":["fly_statis"]},
  {"stage":"analyzing",   "kpi_count":5,"anomaly_count":0,"comparison_count":5},
  {"stage":"previewing",  "revision":1,"sections":[{"id":"flight","title":"飞行概览","kpis":5}]}
]
```

### 2. 看产物在哪 → `/artifacts` 或 confirm 的返回

```bash
# 列表
curl -s "http://127.0.0.1:8000/v1/fly-reports/sessions/$SID/artifacts?user_id=u1" | python -m json.tool

# confirm 时直接返回（注意 user_id 在 body 里！）
curl -s -X POST "http://127.0.0.1:8000/v1/fly-reports/sessions/$SID/confirm" \
  -H 'content-type: application/json' \
  -d '{"user_id":"u1","output_format":"docx"}' | python -m json.tool

# 字段：artifact_path / chart_paths / download_url / filename
# 服务端实际目录（默认 tempdir）：
ls -la /tmp/fly_report_artifacts_*/$SID/
```

> ⚠️ 你刚才 `/confirm` 一直没生效，是因为 `user_id` 必须放 **body**，不能放 query string，服务端返回了 422 但你 `>/dev/null` 没看见。

### 3. 看权限审计 → `/audits`

```bash
curl -s "http://127.0.0.1:8000/v1/fly-reports/sessions/$SID/audits?user_id=u1" | python -m json.tool
# decision / reason / scope_required / payload(filter_hash / tenant_id / user_id)
```

### 4. 看时延和成败计数 → `/metrics`

```bash
curl -s http://127.0.0.1:8000/v1/fly-reports/metrics | python -m json.tool
# stage_counts / stage_durations(秒) / render_success / render_failure / clarify_rounds
```

### 5. 看预览 HTML（最直观）→ `/preview`

```bash
curl -s "http://127.0.0.1:8000/v1/fly-reports/sessions/$SID/preview?user_id=u1" > /tmp/preview.html
xdg-open /tmp/preview.html
```

### 6. 把产物固化到稳定目录（不再用临时目录）

服务端 `output_root` 默认 `tempfile.mkdtemp("fly_report_artifacts_")`，每次重启路径都不一样。要固定路径，启动前 export：

```bash
export FLY_REPORT_OUTPUT_ROOT=/home/admin2/proj/SwarmMind/data/fly_report_artifacts
```

（如果当前 service 不读这个变量，就在 server.py 里把 `FlyReportService(...)` 的 `output_root=` 改成 `Path(os.getenv("FLY_REPORT_OUTPUT_ROOT", ...))` —— 一行就够。）

### 7. 让服务端日志更吵 → uvicorn `--log-level debug` + Python logger

```bash
SWARMMIND_POSTGRES__ENABLED=true \
SWARMMIND_POSTGRES__DSN=postgresql://swarmmind:swarmmind@127.0.0.1:2360/swarmmind \
PYTHONUNBUFFERED=1 \
.venv/bin/python -m uvicorn swarmmind.api.server:create_app \
  --factory --host 127.0.0.1 --port 8000 --log-level debug
```

service.py 已经在每个阶段调 `logger.exception` / event bus。建议再开一个：
```python
import logging
logging.getLogger("swarmmind.domains.fly_report").setLevel(logging.DEBUG)
```
丢到 server.py 顶部即可临时开。

### 8. 直接接 PG 查持久化数据

服务挂了也能从 PG 复原现场：

```bash
PGPASSWORD=swarmmind psql -h 127.0.0.1 -p 2360 -U swarmmind -d swarmmind -c \
"SELECT id, state, revision, updated_at FROM fly_report_session ORDER BY updated_at DESC LIMIT 5;"

PGPASSWORD=swarmmind psql -h 127.0.0.1 -p 2360 -U swarmmind -d swarmmind -c \
"SELECT role, left(text, 60), payload->'stages' FROM fly_report_chat_turn WHERE session_id='$SID' ORDER BY id;"

PGPASSWORD=swarmmind psql -h 127.0.0.1 -p 2360 -U swarmmind -d swarmmind -c \
"SELECT filename, artifact_path, output_format FROM fly_report_artifact WHERE session_id='$SID';"

PGPASSWORD=swarmmind psql -h 127.0.0.1 -p 2360 -U swarmmind -d swarmmind -c \
"SELECT decision, reason, payload FROM fly_report_audit WHERE session_id='$SID' ORDER BY id;"
```

### 9. VS Code 单步调试

`launch.json` 已有「Debug FastAPI」（你刚才编辑过），断点设在：
- service.py 的 `_drive_pipeline` 入口和每个 `_enter(...)` 调用
- api.py 各 handler

然后 F5 启动 → 用 curl 触发一个 request，就能逐行看变量了。

### 一键看「这次到底干了啥」的小套路

```bash
SID=...
echo "=== STATE ==="    && curl -s "http://127.0.0.1:8000/v1/fly-reports/sessions/$SID?user_id=u1"           | python -m json.tool
echo "=== STAGES ==="   && curl -s "http://127.0.0.1:8000/v1/fly-reports/sessions/$SID/turns?user_id=u1"     | python -c 'import sys,json;[print(t["role"], json.dumps(t.get("payload",{}).get("stages",[]),ensure_ascii=False,indent=2)) for t in json.load(sys.stdin)]'
echo "=== ARTIFACTS ===" && curl -s "http://127.0.0.1:8000/v1/fly-reports/sessions/$SID/artifacts?user_id=u1" | python -m json.tool
echo "=== AUDITS ==="   && curl -s "http://127.0.0.1:8000/v1/fly-reports/sessions/$SID/audits?user_id=u1"    | python -m json.tool
echo "=== METRICS ===" && curl -s  http://127.0.0.1:8000/v1/fly-reports/metrics                              | python -m json.tool
```

要的话我可以把它包成 `scripts/fly_report_debug.sh` 或在 fly_report_chat.py 里加一个 `/trace` 命令一次性把这 5 个接口拉出来——告诉我哪种顺手。

---

Request failed, retried with Autopilot

Read [](file:///home/admin2/proj/SwarmMind/swarmmind/domains/fly_report/api.py#155-155), lines 155 to 300

Read [](file:///home/admin2/proj/SwarmMind/swarmmind/domains/fly_report/service.py#240-240), lines 240 to 520

I now have the full picture. Let me give a structured tour of every file the request touches.

## 用户 query 进来后的完整调用链 — 文件级 trace

以 `POST /v1/fly-reports/sessions  body={initial_query:"生成农业局上周飞行周报"}` 为例。

### 第 0 层：HTTP 入口

| 文件 | 关键符号 | 作用 |
|---|---|---|
| server.py | `create_app()` / `lifespan` | 装配 FastAPI；按配置选 `IntentParser`（rule/llm）、`PermissionGate`、`FlyReportRepository`（内存/PG）、`event_bus`、`output_root`，构造 `FlyReportService`，挂载 `create_fly_report_router(service)` |
| api.py | `create_fly_report_router` 内的 `start_session` / `send_message` / `confirm` / `cancel` / `get_session` / `list_turns` / `download_artifact` | **唯一**的 HTTP 适配层；只做：Pydantic 校验入参 → 调 `service.xxx()` → 把 domain 异常翻成 HTTP 状态码 |

> 一句话：**api.py 不做业务，只做 dispatch 和状态码翻译**。所有真正的处理都在 service.py。

### 第 1 层：业务编排核心（看这一个文件就够 80%）

📌 **service.py** — `FlyReportService`

`start_session()` 内部直接调 `_drive_pipeline()`，它是整个 PRD 状态机的具象化：

```
PARSING → CLARIFYING(可选)? → AUTHORIZING → FETCHING → ANALYZING → PREVIEWING → (用户 confirm) → RENDERING → ARCHIVED
```

每个 `# ----- XXX -----` 注释对应一个阶段，每段都是相同 4 件事：
1. `self._enter(record, SessionState.X, reason)` — 状态机推进（写 `state_history`）
2. `t0=time.perf_counter()` → 调依赖 → `self._metrics.observe_stage(...)`
3. `stages.append({...})` — 写到 turn payload，让 `/turns` 看得到
4. `await self._emit("fly_report.xxx", ...)` — 发事件到 event_bus

异常路径全部在 `except FlyReportError / Exception:` 里，统一进 `FAILED` + `fly_report.failed`。

`confirm()` 是同样模板的精简版：`PREVIEWING → RENDERING → ARCHIVED`，多了一个 `asyncio.wait_for(to_thread(render), timeout=...)`。

### 第 2 层：每个阶段调谁（按 pipeline 顺序）

| 阶段 | 调用 | 文件 | 干什么 |
|---|---|---|---|
| **PARSING** | `self._intent_parser.parse(text)` | intent/rule_parser.py（默认）<br>intent/parser.py（LLM 版） | 自然语言 → `DraftFilterSpec`（period/dimension/indicators） |
| **CLARIFY 检查** | `check_conflicts(spec)` / `merge_drafts(...)` | conflict_checker.py | 检查必填字段；多轮 follow-up 字段级合并 |
| **AUTHORIZING** | `self._permission_gate.evaluate(...)` | permissions.py | `AllowAll` / `DenyAll` / 待接 `IdentityPermissionGate` |
| **FETCHING** | `self._data_fetcher.fetch(normalized)` | data_fetcher.py → dikong/fake.py | 拉 5 个 dikong 接口；多 dept 自动 fan-out |
| **ANALYZING** | `analyze(raw, normalized)` | analyzer/__init__.py → analyzer/aggregations.py / analyzer/comparisons.py | 算 KPI、同比环比、部门排名、异常 |
| **PREVIEWING** | `compose_report_context(...)` | composer/context.py | 把 analysis 拼成 `ReportContext`（章节 + 章节内 KPI/表格/图表 spec） |
| **RENDERING** | `renderer_router.render(...)` | export/renderer_router.py → docx/pdf/markdown 三个 renderer | 真正出稿；写文件到 `output_root/<sid>/<fmt>/` |

### 第 3 层：状态 / 数据模型（要看字段定义就来这）

| 文件 | 关键类 |
|---|---|
| state.py | `SessionState` 枚举、`assert_transition()` 状态机、`is_terminal` |
| models.py | `FilterSpec` / `DraftFilterSpec` / `Period` / `Dimension` / `NormalizedFilter`（带 `hash`）/ `RawDataset` / `AnalysisResult` / `ReportContext` / `ChatTurn` |
| exceptions.py | `FlyReportError` / `SessionNotFound` / `InvalidStateTransition` / `PermissionDenied` / `FilterParseError` |

### 第 4 层：横切（持久化 / 观测）

| 文件 | 何时被调 |
|---|---|
| repository.py | service 里的 `_persist_session / _persist_turn / _persist_artifact / _persist_audit / _load_session` 全部走它；4 张 PG 表的 CRUD 都在这里 |
| observability.py | `_emit()` 走 `event_bus.publish(make_event(...))`；`FlyReportMetrics` 收 `observe_stage` / `record_clarify_round` |
| postgres.py | `PostgresStore` 给 repository 提供 `execute / fetchone / fetchall`；`initialize()` 现在转发到 alembic |

### 一张「打断点」推荐图

如果你用 VS Code F5 调试，这 5 个断点能覆盖 95% 场景：

1. api.py `start_session` 第一行 — 看 HTTP 入参
2. service.py `_drive_pipeline` 开头（`stages: list[dict]...`）— 看每个阶段循环
3. service.py `# ----- PARSING -----` 后面 `draft = await self._intent_parser.parse(text)` — 看意图解析结果
4. service.py `# ----- FETCHING -----` 后面 `record.raw = await self._data_fetcher.fetch(normalized)` — 看从 dikong 拉到的原始数据
5. service.py `confirm()` 里 `asyncio.wait_for(to_thread(...))` 之前 — 看 ctx + template，之后看 result

### 阅读顺序建议（半小时上手）

1. 先读 api.py（150~250 行），知道有哪些端点
2. 再读 service.py 的 `_drive_pipeline`（约 250~520 行）一气呵成 —— 这是**唯一需要精读**的函数
3. 想细看某阶段，就跳到对应的 intent / data_fetcher / analyzer / composer / export 文件
4. 想调试时按上一条「五合一 curl 脚本」配合看 `payload.stages`Continued with Autopilot: Task not yet complete给出了用户 query 在服务端的完整处理路径：HTTP 入口在 api.py（仅做 dispatch + 状态码翻译），核心编排在 service.py 的 `_drive_pipeline()`（PARSING→CLARIFY?→AUTHORIZING→FETCHING→ANALYZING→PREVIEWING→RENDERING→ARCHIVED 七阶段），每阶段的实现分别在 intent/ + conflict_checker.py + permissions.py + data_fetcher.py + analyzer/ + composer/ + export/，状态/数据模型在 state.py + models.py，横切持久化与可观测在 repository.py + observability.py，并附了 5 个 VS Code 断点位置和半小时阅读顺序。

