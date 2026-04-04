# issue 12 新的改动

## Role
### role的类别
我已经修改了role的定义，对每个role的职责和输出格式做了更明确的定义，在swarmmind/models/capability.py:L10:L147
你结合项目看下是不是还需要有补充
### role和其他组件的关系
- tool
- tool group
- runtime kind
- skills

之前role也是和这些绑定的，见：swarmmind/agents/profile.py，这里面也需要改,
- runtime kind 这个可以推荐一个默认的，但不强制
- default_strategy 删除

## runtime kind
```
class RuntimeKind(str, Enum):
    """Execution backends available to a subtask attempt."""

    LLM_ONLY = "llm_only"
    HOST_TOOLS = "host_tools"
    SANDBOX = "sandbox"
    BROWSER_AUTOMATION = "browser_automation"
    AGENT_BACKED = "agent_backed"
```
我觉得只需要保留
- LLM_ONLY
- HOST_TOOLS
- SANDBOX

browser_automation不需要，它实际上就是sandbox的一种特殊情况，没必要单独列出来；agent_backed不要，它的定义过于模糊，容易和planner/coordinator本身的agent角色混淆，而且目前也没有明确的实现路径。

## Plan
已经修改了一些，只需要输出："name", "description, "role", "acceptance_criteria"，"dependencies"
然后plan应该是两步骤，
1. 第一步还是以前的输出要求的DAG subtask json
2. 第二步是planner根据第一步的输出，针对每个subtask的role description, ac, dependency等信息, 在利用大模型结合每个role的默认配置推荐，生成符合用户任务下每个subtask的执行配置（execution configuration），包括runtime kind, tool requirements, sandbox profile等信息，这个主要是修改swarmmind/orchestration/planner.py:L92:L122

## ToolGroup
当前
```
class ToolGroup(str, Enum):
    """Groups of atomic tools equipped per subtask."""

    PROJECT_READ = "project_read"
    PROJECT_WRITE = "project_write"
    WEB_SEARCH = "web_search"
    BROWSER_READ = "browser_read"
    SANDBOX_EXEC = "sandbox_exec"
    ARTIFACT_READ = "artifact_read"
    MEMORY_LOOKUP = "memory_lookup"
    TASK_ADMIN = "task_admin"
    MAIL = "mail"
    PRESENTATION = "presentation"
```
这是一组能力的包装，不应该有能力重复，应该是一个能力只能属于一个ToolGroup，目前的定义里就有问题，比如sandbox_exec和browser_read这两组能力其实是有重叠的，建议重新梳理一下tool group的定义，确保每个group是一套互不重叠的能力集合。
建议改成下面：
```
  class ToolGroup(str, Enum):
      """
      基础工具能力组，按「操作介质/环境」划分。
      每个子任务通过组合这些基础组来获得操作物理/数字世界的能力。
      """

      FILE_SYSTEM = "file_system"
      """本地文件系统操作：读文件、写文件、文件存在性检查、目录遍历、文件重命名/删除。"""

      WORKSPACE = "workspace"
      """项目工作区语义操作：基于项目路径的代码搜索(Grep/Glob)、批量编辑、跨文件重构、项目级读写。"""

      WEB_SEARCH = "web_search"
      """公开网络信息检索：搜索引擎查询、获取搜索结果摘要。只负责找信息，不负责浏览详情页。"""

      BROWSER = "browser"
      """浏览器环境操作：打开网页、页面导航、DOM 交互、表单填写、截图、获取页面详情内容。
      与 WEB_SEARCH 的区别：WEB_SEARCH 是『找』，BROWSER 是『看和交互』。"""

      CODE_EXEC = "code_exec"
      """代码执行环境：在隔离沙箱或宿主环境中运行代码/命令、安装依赖、查看执行输出。
      不包含文件读写（需要配合 FILE_SYSTEM 或 WORKSPACE）。"""

      MEMORY = "memory"
      """持久化记忆操作：读取/写入跨会话记忆、读取 CLAUDE.md、获取历史上下文摘要。"""

      ARTIFACT = "artifact"
      """产物/附件操作：读取用户上传的文件、解析 PDF/图片、下载远程资源。"""

      COMMUNICATION = "communication"
      """基础通信能力：发送邮件、调用 Webhook、发送 Slack/IM 消息。"""


  # =============================================================================
  # 不建议放入 ToolGroup 的专用能力（应放在 skill_profiles 或 plugins 中）
  # =============================================================================
  # - presentation/slides 制作 → skill_profile: "create_presentation"
  # - Excel/表格处理 → skill_profile: "spreadsheet_analysis"
  # - 特定 SaaS 集成 (Jira, Notion, GitHub PR) → plugin/mcp

  ---
  关键改动说明

  1. project_read / project_write → 合并为 WORKSPACE

  之前 PROJECT_READ 和 PROJECT_WRITE 是两个 group，而且语义偏"项目"。但实际上：
  - 读文件 = 文件系统操作
  - 写文件 = 文件系统操作
  - Grep/Glob = 工作区语义搜索

  合并为 WORKSPACE 更自然：它代表对代码/项目工作区的整体操作能力。如果你的智能体需要编辑代码、搜索代码、批量重构，就给 WORKSPACE。

  2. browser_read 和 web_search 解耦

  - WEB_SEARCH = 检索层：Google/百度/Bing 搜索，返回链接和摘要
  - BROWSER = 浏览交互层：打开页面、滚动、点击、读 DOM、截图

  这样非常清晰：先 WEB_SEARCH 找到资料，再用 BROWSER 深入阅读。

  3. sandbox_exec 改名为 CODE_EXEC

  sandbox 是一种运行时环境（runtime kind），不应该和 browser/file_system 并列作为 tool group。
  CODE_EXEC 表达的是「执行代码/命令」这个能力本身，至于在 sandbox 还是 host 上跑，由 runtime_kind 决定。

  4. mail / presentation 降级

  Mail 是通信能力，但把它和 file_system 并列很怪。有两种处理方式：
  - 方案 A（推荐）：把 mail 归入 COMMUNICATION 组，作为基础通信工具
  - 方案 B：把 mail 从基础 ToolGroup 中彻底移除，变成 skill_profile: "email_composition" 或专门的 plugin

  PRESENTATION（做 PPT）则强烈建议不要放在基础 ToolGroup，它本质上是一个高阶技能，应该做成 skill_profile: "create_presentation"，底层依赖 FILE_SYSTEM + WORKSPACE 来读写文件。

  5. 删除了 ARTIFACT_READ 的独占性

  ARTIFACT 统管所有「外部产物」：用户上传的文件、PDF、图片、下载的 URL 资源。这样不会和 FILE_SYSTEM 冲突，因为：
  - FILE_SYSTEM 操作的是项目工作目录内的文件
  - ARTIFACT 操作的是用户输入或外部下载的附件
```

## skill repo
目前在swarmmind/skills下已经下载了很多，这些应该是skill_profile的组成部分，我觉得需要对这些进行分类和固化，不能让LLM随意发挥，具体的分类和命名可以再讨论。或者skill需要有一个统一管理
