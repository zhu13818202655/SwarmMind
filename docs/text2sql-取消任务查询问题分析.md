# Text2SQL 无法查询"机巢取消任务"问题分析

> 日期：2026-06-04
> 问题来源：用户提问"今天下午、原定用桐琴应消站机巢无人机执行的任务有哪些取消了"，text2sql 回复"数据库中找不到"

---

## 一、背景

Text2SQL 模块（`swarmmind/domains/fly_report/text2sql/`）通过 Vanna 2.0 Agent 将用户自然语言转为 PostgreSQL 查询。当前系统只连接了 PostgreSQL，未接入 TDengine。

用户的问题涉及三个关键要素：
1. **设备维度**：桐琴应消站的机巢 → 机巢绑定的无人机
2. **时间维度**：今天（2026-06-04）下午
3. **状态维度**：任务"取消了"

---

## 二、问题根因分析

### 2.1 查询链路本身是可行的

要回答这个问题，SQL 需要的 JOIN 链如下：

```
t_hangar_device          （通过 device_name 找到"桐琴应消站"机巢）
  → t_dock_drone_rel     （dock_sn 关联，找到该机巢绑定的无人机）
    → t_drone_device     （获取无人机信息）
      → t_missions       （通过 device_sn 找到这些无人机的飞行任务）
        → sys_job_log    （通过 mission_id 查执行记录，检查 status 是否为"取消"）
```

这些表全部是 focus 表，JOIN hints 在 `tables.yaml` 里都有定义。理论上 LLM 能构造出正确 SQL。

### 2.2 缺口一：sys_job_log.status 枚举值未文档化（最关键）✅ 已确认

`tables.yaml` 中 `sys_job_log` 的描述：

```yaml
summary: |
  飞行执行日志，飞行历史的核心表。每次定时任务被触发或人工执飞都会产生一条记录。
  status=执行状态，data_status=数据回传状态。
```

**问题：只说了"执行状态"，没有列出各状态码的含义。** LLM 不知道哪个 status 值代表"取消"。

> **✅ 已确认（2026-06-04，来源：数据库团队）**：`sys_job_log.status` 枚举值如下：
>
> | 值 | 名称 | 含义 |
> |----|------|------|
> | 0 | PREPARE | 待机准备 |
> | 1 | PROGRESS | 进行中 |
> | 2 | SUCCESS | 已完成 |
> | 3 | CANCLE | 已取消（原 API 拼写如此） |
> | 4 | FAILED | 已失败 |

LLM 理论上可以通过 `sys_dict_data` 反查（`dict_type = 'sys_job_log_status'`），但这个用法只在 golden_qa 的"列出最近 24 小时执行失败的飞行日志"例子里一笔带过，LLM 不一定会主动去查。

> **→ 修复方案**：将上述枚举值直接写入 `tables.yaml` 的 `sys_job_log` summary 中，确保 LLM 始终可见。

### 2.3 缺口二：取消的任务可能根本没有 sys_job_log 记录

`sys_job_log` 是**实际执行的飞行日志**——每次定时任务被触发或人工执飞才产生一条记录。

如果任务在执行前就被取消了，可能：
- 根本不会产生 `sys_job_log` 记录
- 取消状态可能记录在 `t_missions.status` 或 `t_mission_record.status` 中

`tables.yaml` 对 `t_missions` 的描述没有提到 `status` 字段：

```yaml
summary: |
  任务管理（飞行/巡检任务定义）。一个任务关联一条航线、一台无人机、一名操作员。
  ⚠️ 部门维度统计请勿使用 t_missions.dept_id...
```

对 `t_mission_record` 的描述也极为简略：

```yaml
summary: 任务执行记录。status=执行状态，start_time/end_time=起止时间。
```

同样没有列出 status 枚举值。

### 2.4 缺口三：golden_qa 没有覆盖"取消任务"场景

现有的 12 条 golden_qa 示例中，没有任何一条涉及：
- 按机巢（hangar）筛选任务
- 按"取消"状态筛选任务
- 组合"设备 + 时间 + 状态"三重条件查询

LLM 缺少 few-shot 示例引导，面对这种复合查询时容易生成错误 SQL 或直接放弃。

### 2.5 是否需要 TDengine？

**不需要。** TDengine 中只有 `st_drone_osd` 表，存储的是无人机 OSD 遥测时序数据（累计飞行时间 `total_flight_time`、累计飞行距离 `total_flight_distance`、累计飞行架次 `total_flight_sorties`）。这些是硬件遥测指标，跟"任务是否取消"的业务状态完全无关。任务状态信息全部在 PostgreSQL 中。

---

## 三、涉及的表和字段汇总

| 表名 | 角色 | 关键字段 | 当前文档状态 |
|------|------|----------|-------------|
| `t_hangar_device` | 机巢设备主表 | `device_sn`(主键), `device_name`(机巢名称) | focus ✓，但未说明 device_name 的命名规则 |
| `t_dock_drone_rel` | 机巢↔无人机绑定 | `dock_sn`, `drone_sn` | focus ✓ |
| `t_drone_device` | 无人机设备主表 | `device_sn`, `device_name`, `dept_id` | focus ✓ |
| `t_missions` | 任务定义 | `id`, `route_id`, `device_sn`, `status`(?) | focus ✓，但 **status 字段未文档化** |
| `t_mission_record` | 任务执行记录 | `mission_id`, `status`, `start_time`, `end_time` | focus ✓，但 **status 枚举未文档化** |
| `sys_job_log` | 飞行执行日志 | `job_log_id`, `mission_id`, `status`, `start_time`, `stop_time` | focus ✓，但 **status 枚举未文档化** |
| `sys_dict_data` | 字典数据 | `dict_type`, `dict_value`, `dict_label` | 辅助表 ✓，用于翻译枚举值 |

---

## 四、解决思路

### 4.1 短期：补充 tables.yaml 中的枚举说明

需要从数据库查询以下字典值并写入 `tables.yaml`：

```sql
-- 查 sys_job_log 的 status 枚举
SELECT dict_value, dict_label
  FROM sys_dict_data
 WHERE dict_type = 'sys_job_log_status'
 ORDER BY dict_value;

-- 查 t_missions 的 status 枚举（如果存在）
SELECT dict_value, dict_label
  FROM sys_dict_data
 WHERE dict_type LIKE '%mission%status%'
 ORDER BY dict_value;

-- 查 t_mission_record 的 status 枚举
SELECT dict_value, dict_label
  FROM sys_dict_data
 WHERE dict_type LIKE '%mission_record%status%'
 ORDER BY dict_value;
```

然后在 `tables.yaml` 中补充类似：

```yaml
- name: sys_job_log
  focus: true
  summary: |
    飞行执行日志，飞行历史的核心表。
    status 枚举值（来自 sys_dict_data dict_type='sys_job_log_status'）：
      1 = 执行成功
      2 = 执行中
      3 = 取消
      4 = 执行失败
    （以上为示例，需以实际查询结果为准）
```

### 4.2 短期：增加 golden_qa 示例

在 `data/fly_report_text2sql/knowledge/golden_qa.yaml` 中增加一条覆盖"按机巢+状态+时间"筛选的示例，例如：

```yaml
- question: "今天下午桐琴应消站机巢绑定的无人机有哪些任务取消了？"
  sql: |
    SELECT m.id AS mission_id,
           m.name AS mission_name,
           m.device_sn,
           dd.device_name AS drone_name,
           hd.device_name AS hangar_name,
           jl.status,
           d.dict_label AS status_label,
           jl.start_time
      FROM t_hangar_device hd
      JOIN t_dock_drone_rel rel ON rel.dock_sn = hd.device_sn
      JOIN t_drone_device dd   ON dd.device_sn = rel.drone_sn
      JOIN t_missions m        ON m.device_sn  = dd.device_sn
      LEFT JOIN sys_job_log jl ON jl.mission_id = m.id
      LEFT JOIN sys_dict_data d
             ON d.dict_type = 'sys_job_log_status'
            AND d.dict_value = jl.status::text
     WHERE hd.device_name LIKE '%桐琴%'
       AND jl.start_time::timestamp >= '2026-06-04 12:00:00'
       AND jl.start_time::timestamp <  '2026-06-04 18:00:00'
       AND jl.status = {取消状态码}
     ORDER BY jl.start_time DESC;
  tags: [t_hangar_device, t_dock_drone_rel, t_drone_device, t_missions, sys_job_log, hangar_filter, status_filter]
  verified_by: TODO
  verified_at: 2026-06-04
```

> ⚠️ 注意：上述 SQL 是示例模板，`{取消状态码}` 需替换为实际值。如果取消任务不在 `sys_job_log` 而在 `t_mission_record` 中，则需要调整 JOIN 链。

### 4.3 中期：考虑 t_mission_record vs sys_job_log 的分工

需要确认：
- **取消的任务**到底记录在哪张表？
  - 如果在 `sys_job_log`：直接用上面的方案
  - 如果在 `t_mission_record`：需要把 JOIN 链改为 `t_missions → t_mission_record`，并在 tables.yaml 和 golden_qa 中体现
  - 如果两张表都有：需要明确什么场景用哪张表

建议执行以下 SQL 来确认：

```sql
-- 确认"取消"状态在哪张表有数据
SELECT 'sys_job_log' AS tbl, COUNT(*) AS cnt
  FROM sys_job_log
 WHERE status = {可能的取消状态码}
UNION ALL
SELECT 't_mission_record' AS tbl, COUNT(*) AS cnt
  FROM t_mission_record
 WHERE status = {可能的取消状态码};
```

### 4.4 长期（可选）：Text2SQL 接入 TDengine

当前不需要，但如果未来用户问的是"某机巢无人机的实际飞行时长/距离"这类硬件遥测问题，则需要让 text2sql agent 也能查询 TDengine 的 `st_drone_osd` 表。这需要：
- 在 `tools.py` 中增加一个 `RunTdSqlTool`
- 在 prompt 中增加 TDengine 表的 schema 说明
- 处理两种 SQL 方言的差异（PostgreSQL vs TDengine/SQL）

---

## 五、待确认事项

| # | 问题 | 确认方式 |
|---|------|---------|
| 1 | `sys_job_log.status` 的取消状态码是多少？ | ✅ **已确认**：3 = 已取消 (CANCLE)，来源：数据库团队 |
| 2 | `t_missions` 是否有 `status` 字段？取消值是什么？ | 查 `information_schema.columns` + `sys_dict_data` |
| 3 | `t_mission_record.status` 的枚举含义？ | 查 `sys_dict_data` WHERE `dict_type LIKE '%mission_record%'` |
| 4 | 取消的任务是否一定有 `sys_job_log` 记录？ | 抽样对比 `t_missions` 和 `sys_job_log` |
| 5 | "桐琴应消站"在 `t_hangar_device.device_name` 中的实际值？ | `SELECT device_name FROM t_hangar_device WHERE device_name LIKE '%桐琴%'` |

---

## 六、总结

| 维度 | 结论 |
|------|------|
| 是否需要 TDengine？ | **不需要**，任务状态信息全在 PostgreSQL |
| 根本原因 | `sys_job_log` / `t_missions` / `t_mission_record` 的 status 枚举值未文档化，LLM 不知道"取消"对应什么值 |
| 次要原因 | golden_qa 缺少"按机巢+状态+时间"的复合查询示例 |
| 修复优先级 | ~~先查清枚举值~~ ✅ 已确认 → **补充 tables.yaml → 增加 golden_qa** |
