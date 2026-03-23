---
type: todo
date: 2026-03-23
topic: skill-system-refactor
status: in-progress
owner: copilot
---

# Skill System Refactor TODO

> 这份文档用于承接 SwarmMind 后续整套 skill 改造工作，目标是把当前“AgentScope native skill 目录的轻量接入”升级为“有 package、解析、治理、catalog、profile 绑定和评测能力的 skill 系统”，同时保持 runtime execution strategy 与 agent skill 的职责分层。

---

## 1. 目标与边界

这次改造要解决的不是一个单点功能，而是三层职责长期混淆的问题：

1. `swarmmind/agent_skills/` 当前放的是具体 skill 目录。
2. `swarmmind/skills/` 当前放的是 runtime execution strategy。
3. Phase 1 旧草案又打算把 parser / loader / registry 放到 `agent_skills/` 里。

这会导致：

1. skill package 内容资产和 skill 基础设施代码混在一起。
2. `skills` 目录名和 runtime strategy 语义不一致。
3. 后续 profile、catalog、script execution、治理字段都会越来越难放置。

本次改造的总体目标是：

1. 让 skill package、skill infrastructure、runtime execution strategy 三层彻底分开。
2. 让具体 skill 目录最终统一收敛到 `swarmmind/skills/`。
3. 让 skill 解析、校验、加载、注册、catalog 能力放到独立 Python 包中。
4. 保持当前 runtime execution strategy 独立，不回退成“大一统 skill”。

---

## 2. 最终目录规划

目标目录结构：

```text
swarmmind/
  skills/                        # 具体 skill package
    build_app/
      SKILL.md
      scripts/
      references/
      assets/
    review/
    research/
    task_planning/
    verification/
    write_report/

  skill_system/                  # skill 基础设施代码
    __init__.py
    models.py
    parser.py
    validator.py
    loader.py
    registry.py
    catalog.py
    resources.py

  execution_strategies/          # runtime execution strategy
    __init__.py
    strategy.py
    registry.py
    callback_strategy.py
```

职责边界：

1. `swarmmind/skills/` 只放 skill package，不放 parser / loader / registry 这类 Python 代码。
2. `swarmmind/skill_system/` 只放 skill 解析、治理、资源读取、注册、catalog 相关实现。
3. `swarmmind/execution_strategies/` 只放运行时任务执行代码。

---

## 3. 分阶段实施计划

当前进度概览：

1. Phase 0 已完成
2. Phase 1 已完成
3. Phase 2 已完成
4. Phase 3 已完成基础版
5. Phase 4 已完成基础版
6. Phase 5 已完成基础版
7. Phase 6 尚未开始
8. Phase 7 尚未开始
9. Phase 8 尚未开始

当前剩余主线工作可以归并为四块：

1. **Phase 5 收口**
   - `SkillScriptExecutor` 变成正式 service / tool
   - script execution 接入 audit / replay / event
2. **Phase 6 主线**
   - skill 适配 agent 使用
   - profile -> skills -> tools -> policies 关系显式建模
3. **Phase 7 主线**
   - skill lint / eval / benchmark / review
4. **Phase 8 主线**
   - 目录迁移与 import 收口

## Phase 0: 边界对齐与目录冻结

目标：先冻结目录职责，避免 Phase 1 刚开始又把 Python 文件继续塞进 `agent_skills/`。

待做事项：

1. 更新设计文档，明确：
   - `agent skill` = package
   - `execution strategy` = runtime dispatch
   - `tool` = atomic capability
2. 约束后续新增代码：
   - 不再向 `swarmmind/agent_skills/` 新增 `.py`
   - 新增 skill 基础设施代码统一放入 `swarmmind/skill_system/`
3. 约束后续新增 skill：
   - 继续暂放在 `swarmmind/agent_skills/`
   - 但文档明确其临时身份是“未来的 `swarmmind/skills/`”
4. 明确迁移顺序：
   - 先引入 `skill_system/`
   - 再迁移 runtime 目录
   - 最后迁移 skill package 根目录

验收标准：

1. 新文档已统一使用同一套术语。
2. 新增代码路径不再与 skill package 目录混放。

当前状态：已完成。

已完成内容：

1. 设计文档与 todo 已统一 skill / strategy / tool 的边界表述。
2. 新增 Python 基础设施代码已经全部落在 `swarmmind/skill_system/`。
3. 没有继续往 `swarmmind/agent_skills/` 塞新的 `.py` 文件。

## Phase 1: skill package 基础设施

目标：补齐 skill parser / validator / loader / registry / resources 的最小可用闭环。

待做事项：

1. 新建 `swarmmind/skill_system/models.py`
   - `SkillMetadata`
   - `ParsedSkill`
   - `SkillResourceIndex`
   - `SkillEntry`
2. 新建 `swarmmind/skill_system/parser.py`
   - 解析 `SKILL.md` frontmatter
   - 解析 Markdown body
   - 识别 `scripts/`、`references/`、`assets/`
3. 新建 `swarmmind/skill_system/validator.py`
   - 校验 `name`
   - 校验 `description`
   - 校验目录名与 name 一致性
   - 校验 frontmatter 字段
   - 校验相对路径引用存在性
4. 新建 `swarmmind/skill_system/resources.py`
   - 列 references
   - 读 references
   - 列 scripts
   - 列 assets
5. 新建 `swarmmind/skill_system/loader.py`
   - 扫描 skill 根目录
   - 加载多个 skill package
   - 产出 `SkillEntry`
6. 新建 `swarmmind/skill_system/registry.py`
   - 注册 skill entry
   - 获取 skill entry
   - 列出 skills
7. 增加一个最小校验入口
   - `skills validate <path>`
   - 或内部等价 API / helper

验收标准：

1. 给定一个合法 skill 目录，可以被完整解析并注册。
2. 给定一个非法 skill 目录，可以返回结构化校验错误。
3. skill package 和 skill system 代码目录完全分离。

当前状态：已完成。

已完成内容：

1. 已实现 `models.py / parser.py / validator.py / resources.py / loader.py / registry.py`。
2. 已支持 `SKILL.md` frontmatter + body 解析。
3. 已支持 `scripts/ references/ assets/` 资源索引。
4. 已支持非法 skill 返回结构化错误，而不是直接中断整个扫描。

## Phase 2: AgentFactory 接入新的 skill system

目标：从“仅靠目录存在判断”升级为“通过 skill loader + registry 驱动 AgentScope native skill 注册”。

待做事项：

1. 改造 `resolve_agent_skill_dirs(...)` 周边逻辑：
   - 先通过 `skill_system.loader` 加载
   - 再从 registry 中筛选启用 skill
2. 在 `AgentFactory.create_toolkit()` 中接入：
   - skill root 扫描
   - profile 指定 skill 过滤
   - 注册前校验失败保护
3. 明确接入策略：
   - AgentScope 仍然负责 native skill prompt 注入
   - SwarmMind 自己负责本地 skill 的解析、校验、发现、筛选

验收标准：

1. AgentFactory 不再只依赖“目录存在 + `SKILL.md` 存在”。
2. skill 加载失败时能提供清晰错误，而不是静默跳过。

当前状态：已完成。

已完成内容：

1. `resolve_agent_skill_dirs(...)` 已切换为通过 skill loader / registry 解析有效 skill。
2. `AgentFactory.create_toolkit()` 已通过 registry 驱动 skill 注册，而不是直接按目录存在判断。
3. 无效或不可用 skill 不会被注册进 toolkit。

## Phase 3: catalog 与 progressive disclosure

目标：补上自己的 skill catalog / index，而不是完全依赖 AgentScope 内部 prompt 机制。

待做事项：

1. 新建 `swarmmind/skill_system/catalog.py`
2. 提供两层 catalog 视图：
   - compact index
   - expanded detail
3. 支持按 profile / role / enabled 状态过滤
4. 为 agent 暴露最小 skill 索引，而不是一次性把所有长内容都压进 prompt

验收标准：

1. 可以列出当前安装 skill 的 name + description 索引。
2. 可以按需取回具体 skill body 和资源索引。

当前状态：基础版已完成，后续仍可增强。

已完成内容：

1. 已实现 compact catalog。
2. 已实现 expanded catalog。
3. agent 侧已暴露 compact 和 expanded 两种 catalog 视图。

剩余增强项：

1. 按 role / profile 的更细粒度 catalog 过滤。
2. 更显式的 agent 侧 catalog 消费路径，而不只是挂在 toolkit 上。

## Phase 4: metadata 治理

目标：让 skill 成为可治理对象，而不是只有 `SKILL.md` 文案。

待做事项：

1. 扩展 frontmatter / registry metadata：
   - `version`
   - `license`
   - `compatibility`
   - `source_url`
   - `disabled`
   - `allowed_tools`
   - `required_env`
   - `required_bins`
2. 支持 skill 状态：
   - installed
   - enabled
   - disabled
   - invalid
3. 区分 skill 来源：
   - built-in
   - repo-local
   - downloaded
   - generated

验收标准：

1. registry entry 至少包含治理所需最小字段。
2. 能根据 disabled / compatibility 对 skill 做过滤。

当前状态：基础版已完成，后续仍可增强。

已完成内容：

1. 已支持 `version / license / compatibility / source_url / source_type / disabled / allowed_tools / required_env / required_bins`。
2. 已支持 `enabled / disabled / invalid` 基础状态表达。
3. 已支持 `built-in / repo-local / downloaded / generated` 来源分类。
4. 已支持基于 `disabled / required_env / required_bins / allowed_tools / compatibility` 的可用性过滤。

剩余增强项：

1. 更完整的 installed / enabled / disabled 生命周期管理。
2. 更丰富的来源管理与诊断接口。

## Phase 5: skill scripts 与资源安全执行

目标：让 skill 的 `scripts/` 真正可用，但不绕过现有安全边界。

待做事项：

1. 定义 skill script 执行入口
2. 将 script 执行统一接到 sandbox / tool policy
3. 校验 `required_env`、`required_bins`
4. 收集 stdout / stderr / artifacts
5. 记录 replay / audit 信息

验收标准：

1. skill script 不会变成未受控 shell 后门。
2. script 执行结果可以被追踪和回放。

当前状态：基础版已完成，后续仍需继续。

已完成内容：

1. 已实现 `SkillScriptExecutor`。
2. 只允许执行 `scripts/` 下已声明的脚本。
3. 执行必须显式 `allow_sandbox_exec=True`。
4. 已通过 `SandboxManager` 在 sandbox 中执行，而不是本地裸 shell。
5. 已支持 `required_env / required_bins` 预检查。
6. 已支持声明式 artifact 收集。

未完成内容：

1. 尚未接成正式 tool / service。
2. 尚未接入完整 audit / replay 事件链路。
3. 尚未成为 agent 或 orchestration 的正式显式调用能力。

## Phase 6: skill 适配 agent 使用

目标：让 skill 不只是 AgentFactory 的一个临时参数，而是 agent capability model 和 agent 执行链的一部分。

待做事项：

1. 引入 `AgentProfile`
2. 增加：
   - `skills`
   - `skill_mode`
   - `tool_policy`
   - `custom_prompt`
3. 明确 profile -> skills -> tools -> policies 的关系
4. 让 planner / coder / tester / reviewer / researcher 有清晰 profile
5. 让 agent 能显式消费：
   - compact skill catalog
   - expanded skill details
   - skill script execution tool / service
6. 明确 agent 使用 skill 的触发与边界：
   - 什么情况下读取 `SKILL.md`
   - 什么情况下读取 `references/`
   - 什么情况下执行 `scripts/`
   - 什么情况下只做 catalog 发现而不执行脚本
7. 让 orchestration 可以把 skill 使用能力明确下发给 agent，而不是仅靠隐式 prompt 注入

验收标准：

1. 不同角色 agent 的 skill 集合和策略边界可显式配置。
2. execution strategy 与 skill profile 继续保持解耦。
3. agent 可以显式读取 skill catalog / details，并在允许时调用 skill execution 能力。

当前状态：未开始。

## Phase 7: 质量体系与评测

目标：让 skill 可持续迭代，而不是只靠人工改文案。

待做事项：

1. 制定 skill 编写规范模板
2. 建 skill lint / validate 流程
3. 建 eval dataset
4. 建 trigger evaluation
5. 建 benchmark / human review loop

验收标准：

1. 新增 skill 时有统一编写模板。
2. skill 触发质量和效果可以被回归验证。

当前状态：未开始。

## Phase 8: 目录迁移收口

目标：把临时目录名迁移到最终状态，彻底消除歧义。

待做事项：

1. 将当前 `swarmmind/skills/` 重命名为 `swarmmind/execution_strategies/`
2. 更新所有 import
3. 更新所有文档中的 runtime strategy 路径引用
4. 将当前 `swarmmind/agent_skills/` 重命名为 `swarmmind/skills/`
5. 更新 `AgentFactory`、skill loader、文档与测试中的 skill root 路径

验收标准：

1. `swarmmind/skills/` 最终只表示 skill package。
2. `swarmmind/execution_strategies/` 最终只表示 runtime strategy。
3. 目录名与概念语义一致，不再需要额外解释。

当前状态：未开始。

---

## 4. 推荐实施顺序

按投入产出比，建议顺序如下：

1. 先做 Phase 0
2. 再做 Phase 1
3. 再做 Phase 2
4. 然后做 Phase 3 和 Phase 4
5. 再做 Phase 5
6. 再做 Phase 6
7. 最后做 Phase 7 和 Phase 8

原因：

1. 先冻结目录职责，能避免继续把代码放错地方。
2. parser / loader / validator 是所有后续能力的基础。
3. 没有 catalog 和 metadata，skill 数量一大就会失控。
4. 目录迁移最好放在基础设施稳定后统一做，避免边开发边频繁重命名。

---

## 5. 当前明确不做的事

这份 TODO 当前不主张：

1. 把 runtime execution strategy 再叫回 skill
2. 把 skill script 做成无约束的 shell 执行入口
3. 把 parser / loader / registry 继续塞进 `swarmmind/agent_skills/`
4. 在基础设施未稳定前，就急着做复杂远程 skill marketplace

---

## 6. Definition of Done

当以下条件成立时，可以认为这轮 skill 改造一期完成：

1. `swarmmind/skills/` 已成为明确的 skill package 根目录。
2. `swarmmind/skill_system/` 已具备 parser / validator / loader / registry 最小闭环。
3. `swarmmind/execution_strategies/` 与 skill package 概念彻底分离。
4. AgentFactory 可以通过 skill system 加载、筛选并注册 skill。
5. skill 至少支持 `SKILL.md` + `references/` + `scripts/` + `assets/` 的基础包结构。
6. skill 变更有基本的校验和回归验证能力。

当前结论：

1. 一期的技术基础已经基本具备。
2. 当前主要未完成项集中在：
   - Phase 5 的正式 tool/service 接入与审计回放
   - Phase 6 的 skill 适配 agent 使用
   - Phase 7 的质量与评测体系
   - Phase 8 的目录迁移收口