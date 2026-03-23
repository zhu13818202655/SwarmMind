# SwarmMind Skill 实现对比与改进建议

> 目的：对比当前 SwarmMind 的 Agent skill 实现、OpenAkita 的 skill 系统实现，以及公开的 skill 规范与最佳实践，明确我们可以借鉴什么、应该避免什么。

---

## 1. 本文参考来源

本文基于以下材料整理：

### 1.1 SwarmMind 当前实现

- `swarmmind/agent_skills/*/SKILL.md`
- `swarmmind/agents/factory.py`
- `swarmmind/agents/agent_skill.py`
- `swarmmind/skills/strategy.py`
- `swarmmind/skills/execution_strategy_registry.py`
- `swarmmind/orchestration/execution_runner.py`

### 1.2 OpenAkita 技能系统实现

- `/home/admin2/proj/openakita/src/openakita/skills/parser.py`
- `/home/admin2/proj/openakita/src/openakita/skills/loader.py`
- `/home/admin2/proj/openakita/src/openakita/skills/registry.py`
- `/home/admin2/proj/openakita/src/openakita/skills/catalog.py`
- `/home/admin2/proj/openakita/skills/code-review/SKILL.md`
- `/home/admin2/proj/openakita/skills/skill-creator/SKILL.md`

### 1.3 OpenAkita 设计与使用文档

- `/home/admin2/proj/openakita/docs/skill-loading-architecture.md`
- `/home/admin2/proj/openakita/docs/skill-usage-guide.md`
- `/home/admin2/proj/openakita/docs/skills.md`
- `/home/admin2/proj/openakita/docs/multi-agent-architecture.md`
- `/home/admin2/proj/openakita/docs/agent-org-technical-design.md`

### 1.4 外部规范与权威解释

- Claude 帮助中心《What are Skills?》
- agentskills.io Specification

---

## 2. 先说结论

当前 SwarmMind 已经做对了一件很关键的事：

1. **把 Agent skill 和运行时 execution strategy 分开了。**

这点比很多“把所有东西都叫 skill”的实现更清楚，也更安全。

但如果从 skill 系统完整度来看，SwarmMind 目前还只是：

1. **有了 skill 目录。**
2. **能把 skill 注册给 AgentScope。**
3. **有一批很轻量的 `SKILL.md`。**

而 OpenAkita 已经实现的是一套更完整的 skill 平台能力：

1. skill 解析
2. skill 校验
3. skill 注册中心
4. skill catalog 注入
5. 渐进式披露
6. scripts / references / assets 目录加载
7. allowlist / enable-disable / 来源追踪 / i18n / 环境约束

所以准确判断是：

1. **SwarmMind 当前 skill 体系是“AgentScope native skill 的最小可用接入”。**
2. **OpenAkita skill 体系是“更接近完整产品级 Agent Skills 平台”的实现。**
3. **我们下一步不该回到“把运行时策略也叫 skill”，而是应该补 skill package / catalog / validation / resource loading 这些产品层能力。**

---

## 3. Claude 与公开规范对 Skill 的核心理解

从 Claude 官方说明和 Agent Skills open standard 看，skill 的核心定义其实非常稳定：

1. **skill 是一个目录，而不是单个 prompt 字符串。**
2. **目录里最少包含一个 `SKILL.md`。**
3. `SKILL.md` = YAML frontmatter + Markdown instructions。
4. 可选包含：
   - `scripts/`
   - `references/`
   - `assets/`
5. skill 的价值是：
   - 提供任务型 procedural knowledge
   - 动态按需加载
   - 避免把所有细节都常驻上下文

公开规范强调的几个重点：

### 3.1 触发靠 description，不靠 body

`description` 不是简单摘要，而是：

1. 说明它做什么
2. 说明什么时候应该用它
3. 尽量带触发关键词和适用场景

这意味着 skill 的 frontmatter 不是装饰，而是 skill 检索和触发的主要入口。

### 3.2 渐进式披露是 skill 的核心特性

规范和 Claude 都明确强调三层：

1. metadata
2. `SKILL.md` body
3. 资源文件按需加载

这和普通 system prompt 最大的区别是：

**skill 不是“把长 prompt 塞进去”，而是“把知识和工作流分层组织起来，并按需取用”。**

### 3.3 scripts / references / assets 是一等公民

权威理解不是只写 instructions：

1. instructions 用来教模型如何做
2. scripts 用来做确定性、重复性强的动作
3. references 用来装大块知识
4. assets 用来装模板和静态资源

所以完整的 skill 系统不应该只有 `SKILL.md`。

---

## 4. OpenAkita 的 Skill 实现是什么样

OpenAkita 的 skill 系统明显不是“只把目录注册给模型”这么简单。

## 4.1 它实现了 skill parser

`openakita/src/openakita/skills/parser.py` 做了这些事：

1. 解析 `SKILL.md` frontmatter
2. 解析 Markdown body
3. 解析并验证 metadata 字段
4. 验证目录名与 skill name 的关系
5. 识别可选目录：
   - `scripts/`
   - `references/`
   - `assets/`

它把 skill 解析成 `ParsedSkill` 和 `SkillMetadata`，说明 OpenAkita 把 skill 当成正式的数据结构，而不是单纯文件夹。

## 4.2 它实现了 skill loader

`loader.py` 做的事情包括：

1. 自动发现多个 skill 目录
2. 批量加载 skill
3. 校验 skill
4. OS compatibility 过滤
5. i18n sidecar 加载
6. allowlist / enable-disable 裁剪
7. 读取脚本内容
8. 运行 skill scripts

这说明 OpenAkita skill 系统已经包含了：

1. 安装后的扫描
2. 生命周期管理
3. 环境适配
4. 资源执行能力

## 4.3 它实现了 skill registry

`registry.py` 里的 `SkillEntry` 不是简单 name/description 结构，而是带了很多产品级字段：

1. `skill_id`
2. `name`
3. `description`
4. `version`
5. `license`
6. `compatibility`
7. `metadata`
8. `allowed_tools`
9. `disable_model_invocation`
10. `supported_os`
11. `required_bins`
12. `required_env`
13. `source_url`
14. i18n 名称/描述
15. `disabled`

这背后的思路很重要：

**skill 不只是提示词资产，而是可治理、可审计、可筛选、可分发的产品对象。**

## 4.4 它实现了 skill catalog

`catalog.py` 会生成 skill list，并把 name + description 组织成系统提示的一部分。

而且它明确区分：

1. 只注入索引
2. 真的要用时再读 body

这就是典型的 progressive disclosure。

## 4.5 它的 demo skill 体现了完整 skill package 思路

### `code-review`

这个 skill 是 instruction-heavy 的典型：

1. frontmatter 明确说明用途和触发场景
2. body 明确 workflow
3. 输出结构和语气也被规范化

### `skill-creator`

这个 skill 更有代表性，因为它展示了完整 package 观念：

1. `SKILL.md`
2. `references/`
3. `scripts/`
4. skill 评测 / benchmark / review viewer / 迭代流程

这说明在 OpenAkita 的理解里，skill 不是一段“任务提示”，而是一套可以被反复迭代、测试、打包和分发的工作流资产。

---

## 5. OpenAkita 文档里如何定义“agent 使用 skill”

只看源码还不够，OpenAkita 的 docs 里其实把“agent 怎么发现、加载、使用 skill”讲得更明确。

## 5.1 skill-loading-architecture.md 的核心设计

这份文档体现了 OpenAkita 对 skill 的系统级理解：

1. Agent 上层并不是直接持有一堆 `SKILL.md` 文件。
2. 它有：
   - `SkillRegistry`
   - `SkillLoader`
   - `SkillCatalog`
   - `HandlerRegistry`
3. skill 被分成：
   - 系统技能
   - 外部技能

系统技能和外部技能的差别，在 OpenAkita 里不是文案差别，而是执行路径差别：

1. **系统技能**
   - 绑定 Python handler
   - 使用原始 tool name
   - 走专用处理器
2. **外部技能**
   - 以 skill 包形式存在
   - 通常通过脚本执行
   - tool name 会做 skill 包装

这个设计很值得我们注意，因为它把 skill 分成了两类：

1. capability exposure
2. execution implementation

这比单纯“都叫 skill”更接近真正的平台实现。

## 5.2 skill-usage-guide.md 的核心观念

这份文档从用户和 agent 使用角度强调了几件事：

1. skill 是模块化能力扩展机制
2. agent 启动时会加载技能
3. agent 根据上下文自动匹配 skill
4. skill 可以：
   - 本地加载
   - 外部安装
   - 动态生成

虽然这份文档有明显“产品说明”色彩，但它反映出 OpenAkita 的目标不是“支持 skill 格式”而已，而是：

**把 skill 做成可发现、可安装、可调用、可维护的用户能力系统。**

## 5.3 multi-agent-architecture.md 里 agent 使用 skill 的方式

这份文档对我们更有借鉴价值，因为它把 skill 放到了多 agent profile 体系里。

里面的关键点是：

1. `AgentProfile` 有 `skills`
2. `AgentProfile` 有 `skills_mode`
   - `ALL`
   - `INCLUSIVE`
   - `EXCLUSIVE`
3. `AgentFactory` 会根据 profile 对 skill 做过滤和应用

这意味着在 OpenAkita 的设计里，skill 不只是“某个 agent 可以读的说明目录”，而是：

**agent profile 的一部分。**

也就是说，agent 和 skill 的关系是显式建模的，而不是零散拼接的。

## 5.4 agent-org-technical-design.md 带来的启发

这份文档虽然不是专门讲 skill，但它揭示了 OpenAkita 更大的架构意图：

1. Agent 组织化
2. 节点级身份/权限
3. 节点级工具授权
4. 动态申请额外工具

这对 skill 的启发是：

**skill 最终不是孤立资产，它应该和 agent profile、tool policy、权限边界一起工作。**

如果 skill 不和 profile / policy / tools 形成闭环，就很难进入真正的组织级使用场景。

---

## 6. OpenAkita 文档与源码之间还有一个重要现象

OpenAkita 文档并不是完全一致的，这一点对我们很重要，因为它说明“什么值得借鉴”需要分层判断。

## 6.1 docs/skills.md 还保留了旧的 Python class 风格

`docs/skills.md` 里仍然展示了这种风格：

1. `BaseSkill`
2. `SkillResult`
3. `registry.register(MySkill())`

这更像旧式插件 / 类注册模型。

## 6.2 但当前源码主线已经是目录式 `SKILL.md`

从当前 `src/openakita/skills/` 的实现看，主线已经明显转向：

1. `SKILL.md`
2. parser / loader / registry / catalog
3. scripts / references / assets

这更贴近 Claude 和 agentskills.io 的方向。

## 6.3 这对我们的启示

我们不能把 OpenAkita 所有文档都当作“当前最佳实践”。

更准确的理解应该是：

1. `docs/skills.md` 代表了较旧的 class-based skill 思路
2. `skill-loading-architecture.md` 和当前源码代表了较新的 directory-based skill 思路

所以我们真正应该借鉴的是：

1. 目录式 skill package
2. progressive disclosure
3. skill registry / catalog / loader
4. agent profile 与 skill 的显式绑定

而不是回到 class-based skill 插件模型。

---

## 7. SwarmMind 当前实现是什么样

SwarmMind 当前 skill 体系的核心在两处：

1. `swarmmind/agent_skills/*/SKILL.md`
2. `AgentFactory.create_toolkit()` 里调用 `toolkit.register_agent_skill(...)`

这里有一个需要单独强调的点：

**`swarmmind/agent_skills/` 目前本质上是“skill package 存储目录”，不应该继续往里面塞 parser / loader / registry 这类 Python 基础设施代码。**

当前行为链路是：

1. 根据 `skill_profiles` 找到本地 skill 目录
2. 目录里必须存在 `SKILL.md`
3. 用 AgentScope 的 `register_agent_skill()` 注册目录
4. AgentScope 把这些 skill 变成 system prompt 中的一段“可用技能说明”

当前具备的能力：

1. 本地目录化 skill
2. 和 AgentScope 原生 skill 机制对接
3. 基础 `SKILL.md` 内容编写

当前还没有的能力：

1. skill parser
2. skill validator
3. skill catalog 服务
4. scripts / references / assets 按需装载
5. skill metadata 扩展治理
6. enable / disable
7. 来源追踪
8. 安装/分发/打包机制
9. skill 评测基线
10. skill 资源读取工具链封装

所以当前 SwarmMind 的 skill 更准确地说是：

**AgentScope native skill directory 的轻量接入层。**

从目录职责角度看，当前状态的最大问题不是功能少，而是：

1. `swarmmind/agent_skills/` 这个名字像是在说“这里放 skill 本体”
2. 但 Phase 1 旧草案里又把 parser / loader / validator 这些 Python 实现也计划放进这里

这会把“skill package 数据”和“skill 系统代码”混在一起。

---

## 8. SwarmMind 与 OpenAkita / Claude 规范的差异

## 8.1 定位差异

### SwarmMind 当前

- skill 主要是 Agent 的说明目录
- execution strategy 是另一条运行时链
- skill 还不是独立产品对象

### OpenAkita / Claude 规范

- skill 是正式的一等资产
- 有 metadata、目录结构、资源、治理、加载策略
- 可被检索、显示、启停、执行脚本、打包、评测

## 8.2 结构差异

### SwarmMind 当前

当前 skill 基本只有：

1. `SKILL.md`

### OpenAkita / 规范

标准 skill 是：

1. `SKILL.md`
2. `scripts/`
3. `references/`
4. `assets/`

SwarmMind 目前缺的是后 3 类资源支持。

## 8.3 触发与发现差异

### SwarmMind 当前

- 依赖 AgentScope 内部的 native skill 提示机制
- 没有自己的 skill catalog
- 没有自己的 skill 索引、过滤、启停逻辑

### OpenAkita

- 有 skill catalog
- 有 compact / full index
- 有 disabled 过滤
- 有 allowlist 控制

## 8.4 治理能力差异

### SwarmMind 当前

- skill 基本无额外元数据治理
- 没有 license / compatibility / source_url / required bins / required env

### OpenAkita

- 把这些都纳入 metadata 层

这意味着 OpenAkita 更适合团队/平台场景，SwarmMind 当前更适合内部研发试验阶段。

## 8.5 资源执行差异

### SwarmMind 当前

- 没有 skill 脚本执行层
- skill 本身不能附带确定性 helper scripts 并被统一调度

### OpenAkita / 规范

- skill 可以带 scripts
- loader 能读取、列出、执行脚本

这一点对复杂工作流很重要，因为很多 skill 最终都需要：

1. 一部分由模型决定
2. 一部分由脚本稳定完成

## 8.6 评测与迭代差异

### SwarmMind 当前

- skill 没有自己的标准评测流程
- 没有 skill benchmark / trigger eval / review loop

### OpenAkita demo

- `skill-creator` 已经把 skill 创作、测试、review、benchmark、迭代、包装变成 workflow

这意味着 OpenAkita 已经开始把“如何写好一个 skill”本身也 skill 化了。

---

## 9. 我们当前有哪些地方是正确的

虽然差距明显，但 SwarmMind 当前也有几个非常重要的优点，不应因为要借鉴外部方案而丢掉。

## 9.1 我们已经把 runtime 和 skill 拆开了

这是当前最正确的设计决策之一。

如果把 execution strategy 和 agent skill 混在一起，会出现：

1. prompt knowledge
2. runtime dispatch
3. deterministic execution

三层语义全部混淆。

SwarmMind 当前已经把：

1. AgentScope native skill
2. ExecutionStrategyRegistry

拆成两层，这一点应该保留。

## 9.2 我们已经接入了官方 native skill 机制

这避免了自造一套“假 skill 协议”。

也就是说，SwarmMind 不是完全偏离生态，而是：

1. 在 Agent 层靠 AgentScope native skill
2. 在 runtime 层保留 execution strategy

这个方向是对的。

---

## 10. 我们可以借鉴和改进的地方

下面这些是我认为最值得借鉴的内容，按优先级排序。

## 10.1 第一优先级：补 skill package 能力，而不是再改 runtime 命名

最值得做的不是继续改 execution strategy 的命名，而是把 skill 从“只有 `SKILL.md`”提升到“完整 package”。

建议新增：

1. `scripts/`
2. `references/`
3. `assets/`

并且在 `SKILL.md` 中明确告诉 agent：

1. 什么时候读 references
2. 什么时候执行 scripts
3. 什么时候使用 assets/templates

这是最直接能提升 skill 实用性的改进。

## 10.2 第二优先级：给 skill 加 parser + validator

当前 SwarmMind skill 目录只做了“目录存在 + `SKILL.md` 存在”的最低校验。

建议补一个本地 parser/validator，至少校验：

1. `name`
2. `description`
3. 目录名与 name
4. frontmatter 格式
5. 可选字段合法性
6. 相对路径引用是否存在

这能避免 skill 目录越写越乱。

## 10.3 第三优先级：补 skill catalog / index 层

现在我们完全依赖 AgentScope 的 skill prompt 生成。

建议增加自己的 skill catalog 视图，用于：

1. 列出当前安装的 skills
2. 给 agent 一个精简 index
3. 按需再加载详细 body / references

这能让后续 skill 数量增长时更稳。

进一步说，借鉴 OpenAkita 的方式，catalog 最少应该分两层：

1. **compact index**：只放 name + description
2. **expanded detail**：在 agent 真要用 skill 时再加载 body / references

## 10.3.1 更进一步：把 agent 和 skill 的绑定做显式建模

OpenAkita 的 `AgentProfile.skills` / `skills_mode` 给了一个非常值得借鉴的思路。

SwarmMind 现在虽然有 `AgentConfig.skill_profiles`，但它更像是“创建 agent 时附带一组 native skill 目录”，还不是一个完整的 profile 体系。

建议后续补：

1. `AgentProfile`
2. `agent_profile_id`
3. `skill_mode`
4. profile -> skills -> tools -> policies 的明确关系

这样 skill 才不会只是“agent 工厂的一个参数”，而会成为 agent 能力模型的一部分。

## 10.3.2 目录规划也需要调整

这一点我认为应该明确改，不然 Phase 1 一落地，目录语义会立即变乱。

我现在更推荐的拆分方式是三层：

1. **skill package 目录**：存放具体 skill
2. **skill infrastructure 目录**：存放 parser / loader / registry / validator
3. **runtime execution 目录**：存放 execution strategy

推荐目录结构：

```text
swarmmind/
   skills/                        # 只放具体 skill package
      build_app/
         SKILL.md
         scripts/
         references/
         assets/
      write_report/
      review/
      research/
      ...

   skill_system/                  # skill 基础设施代码
      __init__.py
      models.py
      parser.py
      validator.py
      loader.py
      registry.py
      catalog.py
      resources.py

   execution_strategies/          # 运行时任务执行策略
      __init__.py
      strategy.py
      registry.py
      callback_strategy.py
```

这样分层以后，语义就很清楚：

1. `skills/` 是数据和内容资产
2. `skill_system/` 是理解和管理这些资产的代码
3. `execution_strategies/` 是运行时调度执行代码

## 10.3.3 为什么我建议改名，而不是继续沿用当前目录

因为当前名字已经开始产生误导：

1. `swarmmind/skills/` 里面其实放的不是通用 skill 系统，而是 runtime execution strategy
2. `swarmmind/agent_skills/` 里面放的是具体 skill 目录
3. 如果再把 `parser.py`、`loader.py` 放进 `agent_skills/`，会让目录既像数据目录又像代码包

这会导致三个问题：

1. 新人会误以为 `agent_skills/` 里既要放 skill 内容又要放 skill 引擎实现
2. 后续 `import` 路径会越来越难理解
3. 文档里说的 skill / strategy 分层，在目录上又重新混掉了

所以我认为中长期应该明确迁移为：

1. `swarmmind/agent_skills/` -> `swarmmind/skills/`
2. `swarmmind/skills/` -> `swarmmind/execution_strategies/`
3. 新增 `swarmmind/skill_system/` 作为 skill 解析与治理基础设施目录

如果想分两步做，也可以：

1. **短期**：先保留 `swarmmind/agent_skills/` 存放 skill package，不往里面放 `.py`
2. **短期**：新增 `swarmmind/skill_system/` 放 Phase 1 的 Python 代码
3. **中期**：再把 `swarmmind/skills/` 重命名为 `swarmmind/execution_strategies/`
4. **中期**：最后把 `swarmmind/agent_skills/` 重命名为 `swarmmind/skills/`

这样可以避免一次性大迁移带来的改动面过大。

## 10.4 第四优先级：补 metadata 治理字段

建议给 skill frontmatter 和内部注册对象扩展这些字段：

1. `license`
2. `compatibility`
3. `metadata.author`
4. `metadata.version`
5. `allowed-tools`
6. `required_env`
7. `required_bins`

这样 skill 才能进入团队协作和平台治理场景。

## 10.5 第五优先级：给 skill 增加 enable/disable 和来源追踪

OpenAkita 的一个很实用点是：

1. skill 可以 disabled
2. skill 有 `source_url`

SwarmMind 未来如果要支持：

1. 内置 skill
2. 项目 skill
3. 外部下载 skill

这些能力会非常必要。

## 10.6 第六优先级：建立 skill 编写规范

现在我们的 `SKILL.md` 普遍偏短、偏概念化，缺少以下内容：

1. 触发场景写法
2. 输出格式约束
3. 输入输出示例
4. 边界条件
5. 何时读 references
6. 何时运行 scripts

建议参考 Claude / agentskills / OpenAkita demo，总结一份团队规范，至少要求：

1. `description` 必须写“做什么 + 什么时候用”
2. body 尽量用 workflow + examples 结构
3. 大文档放 references，不堆进主文件
4. 确定性流程优先抽成 scripts

## 10.7 第七优先级：给 skill 建测试与评估流程

OpenAkita `skill-creator` 最值得借鉴的不是文案，而是评测闭环：

1. 测试 prompt
2. with-skill / baseline 对照
3. benchmark
4. 人工 review
5. 迭代优化

SwarmMind 现在完全缺这一层。

如果后续我们要扩 skill 数量，这个能力会非常重要，否则 skill 质量会漂。

---

## 11. 我建议的演进路线

## Phase 0: 明确边界与统一术语

目标：先把 skill、strategy、tool、profile 四层边界彻底定下来，避免后面边做边改名。

建议做：

1. 明确术语定义：
   - skill = Agent procedural knowledge package
   - execution strategy = runtime dispatch unit
   - tool = atomic executable capability
   - strategy profile / agent profile = capability bundle
2. 输出一份 `skills/README` 或内部规范文档，明确：
   - skill 不等于 tool
   - skill 不等于 execution strategy
   - skill 目录要遵循什么格式
3. 明确哪些字段属于：
   - skill metadata
   - runtime strategy metadata
   - agent profile metadata
4. 明确目录职责：
   - `skills/` 只放 skill package
   - `skill_system/` 只放 skill 基础设施 Python 代码
   - `execution_strategies/` 只放 runtime strategy

这是后续所有实现的前提。

建议在 Phase 0 就完成至少一半目录调整：

1. 不再把任何新的 Python 文件放入 `swarmmind/agent_skills/`
2. 新增 `swarmmind/skill_system/`
3. 更新文档和内部术语，明确 `agent_skills/` 当前只是 skill package root

## Phase 1: 补 skill package 基础设施

目标：把 skill 从目录接入升级到 package 接入。

建议做：

1. skill metadata model
   - `SkillMetadata`
   - `ParsedSkill`
   - `SkillResourceIndex`
2. skill parser
   - 解析 frontmatter
   - 解析 body
   - 识别 `scripts/ references/ assets/`
3. skill validator
   - name/description 校验
   - 目录名一致性校验
   - 相对引用存在性校验
   - frontmatter 字段白名单/长度校验
4. skill loader
   - 扫描本地 skill 根目录
   - 加载目录 skill
   - 生成内存中的 skill registry entry
5. references/scripts/assets 目录支持
   - 列 references
   - 读 references
   - 列 scripts
   - 执行 scripts
   - 列 assets
6. 加一个 `skills validate <path>` 或等价内部校验命令

交付物建议：

1. `swarmmind/skill_system/models.py`
2. `swarmmind/skill_system/parser.py`
3. `swarmmind/skill_system/validator.py`
4. `swarmmind/skill_system/loader.py`
5. `swarmmind/skill_system/registry.py`
6. `swarmmind/skill_system/resources.py`

注意这里我不再建议把这些文件放进 `swarmmind/agent_skills/`。

`swarmmind/agent_skills/` 如果继续使用，应该只承担“skill package root”的职责；如果后续做目录迁移，则更推荐改名成 `swarmmind/skills/`。

## Phase 2: 补治理能力

目标：让 skill 能管理、分发、筛选。

建议做：

1. enabled/disabled
2. source_url
3. license / compatibility
4. required_env / required_bins
5. allowed-tools

进一步展开：

1. skill registry entry 建议至少包含：
   - `skill_id`
   - `name`
   - `description`
   - `version`
   - `license`
   - `compatibility`
   - `source_url`
   - `disabled`
   - `allowed_tools`
   - `required_env`
   - `required_bins`
2. 支持 skill 状态管理：
   - installed
   - enabled
   - disabled
   - invalid
3. 支持来源分类：
   - built-in
   - repo-local
   - downloaded
   - generated
4. 记录 skill 变更审计：
   - 何时安装
   - 何时启用/禁用
   - 谁修改了 skill

如果想进一步靠近 OpenAkita 的产品能力，还可以补：

1. i18n 名称/描述
2. repo 级 skill 配置清单
3. 用户级 skill 开关

## Phase 3: 补质量体系

目标：让 skill 可评估、可持续迭代。

建议做：

1. skill 编写模板
2. skill lint / validate 命令
3. skill eval dataset
4. trigger evaluation
5. benchmark / human review loop

进一步展开：

1. skill 编写模板中固定要求：
   - frontmatter
   - when to use
   - workflow
   - examples
   - edge cases
   - references/scripts/assets usage notes
2. 为每个 skill 支持：
   - smoke evals
   - trigger evals
   - regression evals
3. 建 skill benchmark 目录结构：
   - `evals/`
   - `benchmarks/`
   - `feedback/`
4. 做一个简单版人工 review viewer 或至少统一 review JSON 格式

## Phase 4: 补 agent 使用 skill 的显式模型

目标：让 agent 使用 skill 的方式从“工厂参数”升级为“能力配置模型”。

建议做：

1. 引入 `AgentProfile`
2. 为 agent profile 增加：
   - `skills`
   - `skill_mode`
   - `custom_prompt`
   - `tool_policy`
3. 让 `AgentFactory` 支持从 profile 构建 agent
4. 让不同角色 agent 的 skill 集合显式化：
   - planner profile
   - coder profile
   - tester profile
   - reviewer profile
   - researcher profile
5. 让 profile 和 execution strategy 解耦：
   - agent profile 决定“知识和工具边界”
   - execution strategy 决定“运行时走哪条执行逻辑”

这是 SwarmMind 走向真正多 agent 技能系统的重要一步。

## Phase 5: 补资源执行与安全策略

目标：让 skill 自带脚本和资源可安全地被使用。

建议做：

1. skill script 执行器
2. script allowlist
3. required env / bins 检查
4. sandbox 中执行 skill scripts
5. 将 `allowed-tools` 和 tool policy 结合

要点是：

1. 不能让 skill script 直接绕过现有 sandbox / tool policy
2. 也不能把 scripts 执行做成完全不受约束的 shell 捷径

建议落地方式：

1. skill script 只允许通过统一 execution adapter 调用
2. adapter 负责：
   - 环境检查
   - 参数校验
   - sandbox 派发
   - stdout/stderr/artifact 收集
   - replay 记录

## Phase 6: 补分发、安装与生态能力

目标：让 SwarmMind skill 能从“repo 内目录”走向“可安装资产”。

建议做：

1. skill install
2. skill reload
3. skill uninstall
4. source_url/source_repo 记录
5. skill package 导入导出

进一步可做：

1. 支持从 Git repo 安装
2. 支持 repo-local 与 user-local skill 根目录
3. 支持 generated skill 导出

## Phase 7: 补组织级使用能力

目标：让 skill 不只是单 agent 的辅助目录，而是能进入团队/组织工作流。

建议做：

1. skill 与 user/org policy 结合
2. skill 与 role/profile 结合
3. skill 与 memory / replay / audit 结合
4. skill 的组织级默认启用策略

这一步可以参考 OpenAkita 在多 agent / org 设计里体现出来的方向，但不需要一开始就做成完整组织系统。

建议最小实现：

1. repo-level enabled skills config
2. role-based default skill sets
3. 审计日志中记录 skill 激活与资源读取

---

## 12. 最终判断

最终结论可以概括成 5 句话：

1. **Claude 与 Agent Skills 规范对 skill 的理解是：目录化、渐进式披露、以 procedural knowledge 为核心。**
2. **OpenAkita 基本已经实现了一个产品级 skill 系统雏形，而不是仅仅“支持 SKILL.md”。**
3. **SwarmMind 当前 skill 能力仍偏轻，只是 AgentScope native skill 的最小接入。**
4. **SwarmMind 当前最值得保留的优点，是已经把 Agent skill 和 runtime execution strategy 分层。**
5. **SwarmMind 下一步最值得投入的方向，不是继续纠结命名，而是分阶段补齐 skill package、catalog、validation、resource loading、profile binding、evaluation 这些能力。**

## 13. 实施顺序建议

如果按“投入产出比最高”的顺序，我建议是：

1. **先做 Phase 1**
   - skill parser
   - skill validator
   - references/scripts/assets 支持
2. **再做 Phase 4 的一半**
   - agent profile 最小模型
   - profile -> skills 显式绑定
3. **然后做 Phase 2**
   - metadata 治理
   - enabled/disabled
4. **再做 Phase 5**
   - skill scripts 的安全执行
5. **最后做 Phase 3**
   - benchmark / trigger eval / human review

原因是：

1. 没有 parser/validator，skill 规模一大就会混乱。
2. 没有 profile binding，skill 永远只是目录，不会真正进入 agent 能力模型。
3. 没有 scripts/references/assets，skill 的上限太低。
4. 没有 eval，skill 质量无法持续收敛，但 eval 可以稍后补，不必先做。