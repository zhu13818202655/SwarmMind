# SwarmMind Skill 系统设计

本文记录当前仓库里 skill 的真实约束、数据模型、与 sandbox 的交互方式，以及它如何与 agent / prompt / replay 系统配合。目标不是描述一个理想方案，而是把“现在系统实际上怎么工作”写清楚，便于后续继续演进。

## 1. 设计目标

当前这套 skill 机制主要解决四类问题。

1. 把一类可复用能力沉淀成稳定的本地包，而不是让 agent 每次现写一段临时代码。
2. 让 agent 能在 prompt 中看到有限且可执行的 skill 说明，而不是把整份 `SKILL.md` 无差别塞进上下文。
3. 让 skill 脚本统一走 sandbox 执行链路，具备隔离、日志、回放、产物收集能力。
4. 让失败可以被分类和引导重试，而不是只返回一段裸错误文本。

所以 skill 在 SwarmMind 里不是“提示词插件”，也不是“任意脚本执行入口”，而是一个受约束的本地能力包。

## 2. Skill 包结构

当前内建 skill 的根目录默认位于 `swarmmind/skills/`。每个 skill 目录至少要包含一个 `SKILL.md`。

典型结构如下：

```text
swarmmind/skills/<skill_name>/
  SKILL.md
  scripts/
    ...
  references/
    ...
  assets/
    ...
```

当前资源索引规则是固定的。

1. `scripts/`：可执行脚本清单。
2. `references/`：参考资料，通常供 agent 阅读或提示词摘要使用。
3. `assets/`：静态资源文件。

资源索引由 `build_resource_index()` 扫描，执行时整包文件会被复制进 sandbox。也就是说，当前设计不是“只上传某一个脚本”，而是“把整个 skill 包作为一个最小工作目录带入 sandbox”。

## 3. `SKILL.md` 规范

### 3.1 Frontmatter 基本字段

当前 `SKILL.md` 采用 YAML frontmatter + Markdown body 的结构：

```md
---
name: pptx
description: 生成和处理 PowerPoint 文件
version: 0.1.0
allowed_tools:
  - run_skill_script
required_env:
  - OPENAI_API_KEY
required_bins:
  - python
runtime_requirements:
  python_packages:
    - python-pptx
script_specs:
  - path: scripts/add_slide.py
    runtime: python
    argument_names:
      - unpacked_dir
      - source
    args_schema:
      type: object
      properties:
        unpacked_dir:
          type: string
        source:
          type: string
    artifacts:
      - outputs/result.pptx
---

# Skill body
这里写能力说明、使用注意事项、限制条件。
```

当前模型层支持的核心字段如下。

1. `name`：skill 唯一标识。
2. `description`：短描述，用于 catalog 和触发判断。
3. `version` / `license` / `compatibility` / `source_url` / `source_type`：治理元信息。
4. `disabled`：禁用开关。
5. `allowed_tools`：可选的工具白名单提示。
6. `required_env`：执行 skill 前必须具备的环境变量。
7. `required_bins`：执行 skill 前宿主侧必须可见的二进制依赖。
8. `runtime_requirements`：sandbox 内运行时依赖声明。
9. `script_specs`：每个脚本的声明式执行规格。
10. 其他未建模字段会进入 `extra`，保留扩展空间。

### 3.2 兼容字段与别名

为兼容旧 skill 和不同写法，parser 当前支持一部分别名归一化。

1. 顶层 kebab-case 会转换成 snake_case，例如 `source-url -> source_url`。
2. `required-python-packages`、`python-packages`、`dependencies` 会被提升到 `runtime_requirements.python_packages`。
3. `runtime-requirements`、`script-specs` 这类 kebab-case 顶层键会被识别。
4. `runtime_requirements` 内部也支持 `python-packages`、`node-packages`、`bootstrap-commands` 等 kebab-case 写法。
5. `script_specs` 内部支持 `args-schema`、`argument-names` 等别名。

兼容层的存在是为了平滑迁移，不建议在新增 skill 中继续混用旧字段。

## 4. `runtime_requirements` 规范

过去 skill 只有 `required_python_packages` 这一类 Python 专用字段。现在已经升级为通用运行时约束：

```yaml
runtime_requirements:
  python_packages:
    - defusedxml
  node_packages:
    - playwright
  system_packages:
    - libreoffice
  bootstrap_commands:
    - playwright install chromium
  python_index_url: https://pypi.tuna.tsinghua.edu.cn/simple
  node_registry_url: https://registry.npmmirror.com
```

各字段语义如下。

1. `python_packages`：在 sandbox 内通过 `python3 -m pip install` 安装。
2. `node_packages`：在 sandbox 内通过 `npm install --no-save` 安装。
3. `system_packages`：在 sandbox 内通过 `apt-get` 安装。
4. `bootstrap_commands`：在正式执行脚本前先执行的命令，适合补 runtime 初始化逻辑。
5. `python_index_url`：skill 级 pip mirror 覆盖。
6. `node_registry_url`：skill 级 npm registry 覆盖。

### 4.1 镜像源策略

当前默认策略优先解决国内网络环境下的依赖下载失败问题。

1. pip 默认镜像：`https://pypi.tuna.tsinghua.edu.cn/simple`
2. npm 默认镜像：`https://registry.npmmirror.com`

覆盖顺序如下。

1. `runtime_requirements.python_index_url` / `runtime_requirements.node_registry_url`
2. 环境变量：`SWARMMIND_SKILL_PIP_INDEX_URL`、`PIP_INDEX_URL`
3. 环境变量：`SWARMMIND_SKILL_NPM_REGISTRY_URL`、`NPM_CONFIG_REGISTRY`
4. 系统默认值

这意味着区域网络策略已经进入 skill bootstrap 层，而不是依赖 agent 在失败后临时猜测应该换源。

## 5. `script_specs` 规范

`script_specs` 用来把“某个脚本该怎么调用”变成结构化声明，而不是继续只靠 `script_args` 猜。

典型示例：

```yaml
script_specs:
  - path: scripts/add_slide.py
    runtime: python
    description: 向解包后的 PPT 目录插入一页新幻灯片
    argument_names:
      - unpacked_dir
      - source
    args_schema:
      type: object
      properties:
        unpacked_dir:
          type: string
        source:
          type: string
    examples:
      - script_input:
          unpacked_dir: /workspace/unpacked
          source: slideLayout2.xml
    artifacts:
      - outputs/result.pptx
    environment:
      LOG_LEVEL: INFO
```

当前字段含义如下。

1. `path`：脚本相对 skill 根目录的路径，必须是已声明在 `scripts/` 下的文件。
2. `runtime`：脚本运行时，当前支持按 `python`、`node`、`shell`、`executable` 等语义分发。
3. `description`：脚本用途说明。
4. `args_schema`：结构化输入描述。
5. `argument_names`：结构化输入映射到位置参数时的顺序定义。
6. `examples`：给 agent 的调用示例。
7. `artifacts`：脚本执行后预期收集的产物路径。
8. `environment`：该脚本默认携带的环境变量。

### 5.1 `script_input` 与 `script_args`

当前系统支持两种参数传递方式。

1. `script_args`：直接传有序位置参数列表。
2. `script_input`：传结构化对象，再由系统根据 `argument_names` 或 `args_schema.properties` 转换为位置参数。

当前推荐顺序如下。

1. 如果 `script_specs` 定义了 `argument_names` 或可推导的 `args_schema`，优先使用 `script_input`。
2. 只有在脚本接口很简单或已有现成位置参数约定时，才直接传 `script_args`。

系统不会把任意 JSON 自动魔改成 CLI 参数；如果缺少顺序定义，structured input 会直接报错，而不是“猜着跑”。

## 6. Skill 加载、校验与注册

当前 skill 生命周期的前半段如下。

1. `get_skill_package_root()` 确定 skill 根目录，默认是 `swarmmind/skills/`。
2. `iter_skill_dirs()` 扫描包含 `SKILL.md` 的目录。
3. `parse_skill_dir()` 解析 frontmatter 和 Markdown body。
4. `validate_parsed_skill()` 做字段校验。
5. `load_skill_registry()` 把有效或无效 skill 都注册进内存 registry。

校验关注点包括：

1. frontmatter 是否合法。
2. 关键字段是否非空。
3. URL 是否合法。
4. `runtime_requirements` 的类型是否合法。
5. `script_specs.path` 是否引用了真实脚本。
6. `argument_names`、`artifacts`、`environment`、`examples` 格式是否合法。

这一步的目的不是做复杂业务校验，而是尽量在“agent 看见 skill 之前”就把明显的元数据错误拦住。

## 7. Agent 可见的 skill 能力面

agent 不会默认看到整份 `SKILL.md`。当前对 agent 暴露 skill 相关能力时，遵循“先发现，再细化”的原则。

### 7.1 默认给 agent 的内容

在子任务执行 prompt 中，系统默认提供：

1. `skill_profiles_json`：当前子任务选中的 skill profile。
2. `skill_script_inventory_json`：当前可用 skill 的脚本清单。
3. `selected_skill_context_json`：仅对已选中 skill 提供的关键摘要。

其中 `selected_skill_context_json` 目前包含：

1. `name`
2. `description`
3. `runtime_requirements`
4. `script_specs` 的精简摘要
5. `body_excerpt`

这一步是为了控制上下文污染。agent 需要知道“有哪些可用脚本、每个脚本大概怎么调”，但不需要每轮都吃进整份长文档。

### 7.2 agent 访问 skill 详情的方式

当前 agent 可通过三个工具与 skill 系统交互。

1. `list_skill_scripts(skill_name)`：列出技能包中已声明脚本。
2. `get_skill_details(skill_name)`：获取完整扩展视图。
3. `run_skill_script(...)`：执行已声明脚本。

这里的关键约束是：`run_skill_script` 只接受已声明脚本路径，不允许把一段内联 Python / Shell 源码塞进 `script` 字段冒充 skill 脚本。

## 8. `run_skill_script` 的调用契约

当前 `run_skill_script` 的契约可以概括成：

1. 必须指明 `skill_name + script_path`，或使用别名 `skill + script`。
2. 真正执行时必须设置 `allow_sandbox_exec=true`。
3. `script_path` 必须指向 skill 包里真实存在且已声明的脚本。
4. 环境变量、产物路径、参数、structured input 都通过显式字段传入。

当前工具层还兼容多种嵌套参数形态，例如：

1. 直接顶层参数。
2. `args.arguments`
3. `args.input`
4. `args.tool_input`
5. `args.kwargs`

这是为了兼容不同模型或中间层产生的 tool-call 包装差异，但最终都会归一化为统一 policy。

## 9. Skill 与 sandbox 的交互模型

当前 skill 执行统一走 `SkillExecutionService -> SkillScriptExecutor -> SandboxManager` 这条链。

### 9.1 执行主流程

1. 通过 `SkillExecutionService.get_skill_entry()` 加载并校验目标 skill。
2. 解析目标脚本路径，必要时用文件名或 stem 做轻量容错。
3. 发布 `skill.script.started` 事件。
4. `SkillScriptExecutor` 校验：
   - `allow_sandbox_exec` 必须为真。
   - skill 必须有效且未禁用。
   - 脚本必须位于已声明的 `scripts/` 清单中。
   - `required_env` / `required_bins` 必须满足。
5. 创建 sandbox lease，默认 profile 是 `aio`。
6. 把整个 skill 包复制到 sandbox 内的 `sandbox_root/<skill_name>`，默认是 `/workspace/skill/<skill_name>`。
7. 根据 `runtime_requirements` 生成 bootstrap preamble。
8. 根据 `script_specs` 和 policy 生成最终命令。
9. 在 skill 根目录下执行脚本。
10. 收集产物。
11. 无论成功失败，都销毁 sandbox。
12. 返回标准化执行结果，并发布完成或失败事件。

### 9.2 为什么保留“整包复制到 sandbox”

当前设计明确保留整包复制，而不是让 agent 直接拼源码执行，原因有三个。

1. skill 往往不是一个单脚本，可能依赖 `references/`、`assets/`、相对导入或模板文件。
2. 整包复制后，脚本在 sandbox 中拥有稳定的相对路径语义，减少路径错配。
3. 审计和回放时可以明确知道“执行的是哪一个已注册 skill 包”，而不是一段瞬时生成源码。

这也是当前 skill 和通用 `sandbox_exec` 的本质区别：skill 是“已注册能力包的受控执行”，不是裸命令入口。

## 10. 命令构建规则

当前命令构建顺序如下。

1. 先注入脚本级环境变量。
2. 再串接 runtime bootstrap preambles。
3. 如有产物目录声明，先 `mkdir -p`。
4. 最后执行脚本本体。

脚本本体的调用规则由 `runtime` 或文件后缀决定。

1. `python` / `.py` -> `python3 <script>`
2. `node` / `.js` / `.ts` -> `node <script>`
3. `shell` / `.sh` -> `sh <script>`
4. `executable` -> `./<script>`

如果 `script_specs.artifacts` 存在，而调用方没有显式传 `artifact_paths`，系统会自动把它作为默认产物路径。

如果调用方传了 `script_input`，而没有显式传 `script_args`，系统会基于 `script_specs` 推导参数顺序并自动转换。

## 11. 产物、事件与回放

skill 执行不是黑盒命令，它会进入现有 replay / artifact 体系。

### 11.1 事件

当前 skill 执行会发以下主题事件。

1. `skill.script.started`
2. `skill.script.completed`
3. `skill.script.failed`

事件中会带上以下关键字段。

1. `skill_name`
2. `script_path`
3. `sandbox_id`
4. `exit_code`
5. `failure_category`
6. `retry_suggestions`

### 11.2 产物

如果调用上下文带有 `run_id` 且注入了 `ArtifactRepository`，skill 产物会被持久化。

产物收集逻辑遵循声明式路径，而不是自动搜整个工作目录。也就是说，系统只会收集：

1. 调用时显式传入的 `artifact_paths`
2. 或 `script_specs.artifacts` 推导出的默认产物路径

这样做的好处是边界清晰，坏处是脚本如果写了文件但没声明路径，系统默认不会替你猜。

## 12. 失败分类与重试指导

当前 skill 失败不只返回 stderr，还会做面向 agent 的失败分类。主要分类如下。

1. `script_not_found`
2. `input_mismatch`
3. `environment_missing`
4. `missing_artifacts`
5. `bootstrap_failed`
6. `script_failed`

对应引导大致如下。

1. 路径错：先调用 `list_skill_scripts` 查看已声明脚本。
2. 参数错：先调用 `get_skill_details` 查看 `script_specs` / `examples`。
3. 环境错：检查 `required_env`、`required_bins`、`runtime_requirements`。
4. 产物缺失：检查 `artifact_paths` 和 `script_specs.artifacts`。
5. 下载超时：检查镜像源策略和区域网络设置。

这里的目标不是自动无限重试，而是把“下一步怎么修”显式返回给 agent。

## 13. Skill 与 agent 的协作边界

### 13.1 Skill 不是万能替代品

当任务属于以下情况时，优先考虑 skill：

1. 已经有稳定的脚本和资源目录。
2. 需要真实文件产物，例如 `.pptx`、`.pdf`、`.docx`。
3. 需要在 sandbox 中重复执行同一类流程。

当任务属于以下情况时，应优先考虑其他工具：

1. 只是一次性的临时代码验证。
2. 没有合适 skill，且任务更适合通用 `sandbox_exec` 或工作区编辑。
3. 需要直接读写仓库文件，而不是执行一个封装好的能力包。

### 13.2 Agent 的推荐动作顺序

当前 prompt 明确引导 agent 按以下顺序使用 skill。

1. 先看系统给出的 `skill_script_inventory_json`。
2. 不确定时调用 `list_skill_scripts`。
3. 需要精确参数说明时调用 `get_skill_details`。
4. 确认无误后调用 `run_skill_script`。
5. 失败后根据 `failure_category` 做定向修正，而不是盲重试。

这保证了 agent 的 ReAct 链路里，skill 不是黑箱，而是一个可探索、可解释、可回放的工具面。

## 14. 当前约束与已知边界

当前 skill 体系仍然有明确边界，不应误解为一个通用插件平台。

1. skill 来源目前主要是本地内建包，远程分发和版本治理还比较薄。
2. `script_specs` 目前本质上还是 CLI 调用声明，不是完整工作流 DSL。
3. 结构化输入最终仍会转换为位置参数，暂未直接映射成 stdin / config file / env file。
4. `required_bins` 的检查当前发生在宿主侧 `shutil.which()`，它更像预检查，不是 sandbox 内的精确探测。
5. 产物收集依赖显式路径声明，没有声明就不会自动归档。
6. 失败分类是启发式规则，不是完整诊断引擎。

这些边界需要在后续继续收敛，但目前已经足够支持“已注册 skill 包 + sandbox 执行 + agent 可控调用 + replay 可追踪”这一主链路。

## 15. 推荐编写原则

如果后续继续新增 skill，建议遵循下面的规则。

1. `description` 只写发现和触发所需的简短语义，不要再把依赖安装说明硬塞进描述文本。
2. 能进入 `runtime_requirements` 的依赖，就不要放进 body 里让 agent 猜。
3. 能进入 `script_specs` 的脚本调用约定，就不要只靠自然语言描述。
4. 真实文件产物一定要在 `artifacts` 中声明。
5. 需要结构化输入的脚本，显式给出 `argument_names` 和 `examples.script_input`。
6. 优先让 skill 自己形成稳定包结构，不要把核心逻辑散落在 prompt 临时生成代码里。

## 16. 总结

当前 SwarmMind 的 skill 机制可以概括成一句话：

skill 是一个带声明式元数据的本地能力包，agent 通过有限工具面发现和调用它，系统把整个 skill 包复制进 sandbox 执行，并把结果、产物和失败分类纳入统一回放体系。

这套设计的重点不在“让 agent 什么都能跑”，而在“让 agent 只运行已经被声明、可追踪、可复用的能力”。