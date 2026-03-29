我已经通过debug启动了（.vscode/launch.json）中的Server和User Test，发现了许多问题。现在我会列举出这些问题，和你一起商讨方案，然后拆分出几个story来解决这些问题。

---
## 问题列表

## 问题1：整体逻辑
planner 只负责：
生成 DAG，定义每个 subtask 的 role、goal、AC、dependency、expected artifacts。

coordinator 只负责：
根据 role 和任务约束，解析 execution profile，不再暴露 strategy 概念。

execution runner 就只有一个执行器 类似 ReActAgent，输入 role、goal、AC、dependency、expected artifacts 就可以了

verifier/reviewer 改为真正的 agent role：
输入 dependency 摘要、artifact 摘要、AC。
输出 VerificationResult 或 ReviewDecision。

### 问题2：ReActAgent
1. _execute_validation_subtask(swarmmind/orchestration/execution_runner.py#L518) 目前是规则引擎，但是这个肯定不是我期望的，我希望有llm主导的，通过了解dependence做的事情和结果，然后还有ac，可以verify。所以目前这个方法是需要优化的
2. #sym:_execute_validation_subtask #sym:_execute_agent_backed_subtask #sym:_execute_inline_runtime_subtask 这三个最后都是构建 ReActAgent , 只是各自的 tool，prompt 不同；那么我觉得这第三个其实也是可以合并，我们最终只是通过role来区分他们对应的输入即可
3. 我希望#sym:_execute_sandbox_subtask 也是构建ReActAgent，不再是单独的一套“命令式分支逻辑”：而是 agent 的运行环境之一。agent 通过 sandbox-aware tools 去执行（目前想到的）。但是可能需要扩展ReActAgent，目前Agentscope不支持里面执行时跨进程的这个我觉得我需要新写一个类，这样我在做subtask就可以去除strategy的概念，只需要role，然后plan告诉我需要哪些role可以干什么，哪些需要验证测试，DAG，然后各自依赖的物料在各自role再做一遍判断，这样更准确

综上，我我需要一个更加全能的ReActAgent(.venv/lib/python3.12/site-packages/agentscope/agent/_react_agent.py)，他的 ToolKit(.venv/lib/python3.12/site-packages/agentscope/tool/_toolkit.py) 能够支持更复杂的工具调用，现在是tool_function mcp_client skill，skill是很单薄的，只有prompt,不知道skill里面怎么执行脚本，我们项目里面其实已经实现了一些skill扩展， skill_profiles，里面就有执行脚本的功能，这个设计是否可以更好，原生根植在新的ReActAgent里面, 我觉得这个全能Agent的设计是非常有必要的, 名字叫做 OmniAgent 吧

你首先先回答我目前这些_execute_agent_backed_subtask是否都可以完成

### 问题3：role
1. 现在的role设计的粒度感觉有点粗了，尤其是验证测试类的role，感觉应该再细化一下，至少应该区分开来，验证类的role和测试类的role应该是不同的，因为他们的输入输出要求是不一样的，验证类的role可能更多的是针对依赖和物料进行验证，而测试类的role可能更多的是针对功能进行测试，所以我觉得在planner里面就应该明确告诉planner需要哪些具体的role，这样在execution runner里面就可以根据这些具体的role来设计对应的执行逻辑和prompt设计，这样可以让整个流程更加清晰和有针对性
2. 我现在能想到的是
  - planner: 负责规划和拆解，输入是功能需求，输出是任务 DAG 和每个 subtask 的 role、goal、AC、dependency、expected artifacts，职责是根据功能需求进行规划和拆解，输出任务 DAG 和每个 subtask 的 role、goal、AC、dependency、expected artifacts
  - coder: 负责编码实现功能，输入是功能需求，输出是代码和相关的物料（比如依赖），那职责是什么：写代码，跑代码、测试代码、修复代码bug，提交代码......
  - researcher: 负责调研和分析，输入是功能需求和相关的物料，输出是查询相关的内容和调研分析结果，职责是根据功能需求和相关的物料进行调研分析，输出调研分析结果和相关的物料
  - designer: 负责设计和架构，输入是功能需求和相关的物料，输出是设计方案和相关的物料，职责是根据功能需求和相关的物料进行设计和架构，输出设计方案和相关的物料
  - verifier: 负责验证依赖和物料，输入是依赖和物料的摘要，输出是验证结果，职责是根据依赖和物料的摘要信息
  - tester: 负责功能测试，输入是功能需求和相关的物料，输出是测试结果，职责是根据功能需求和相关的物料进行测试，输出测试结果，我觉得可能更多E2E的测试（单元测试可能更多是coder的）,还有不仅是代码测试，可能还有功能测试，性能测试，安全测试等等
  - reviewer: 负责代码review，不仅是代码，还包括设计review，需求review等等，输入是相关的内容和物料，输出是review结果，职责是根据相关的内容和物料进行review，输出review结果
  - integrator: 负责集成和部署，输入是相关的内容和物料，输出是集成和部署结果，职责是根据相关的内容和物料进行集成和部署，输出集成和部署结果
  - writer: 负责文档编写，包括大纲设计和内容编写，内容汇总，输入是相关的内容和物料，输出是文档内容，职责是根据相关的内容和物料进行文档编写，输出文档内容

然后目前项目代码的swarmmind/models/capability.py 这里面的 AgentRole ToolGroup RuntimeKind StrategyProfile 可能需要调整，AgentRole 需要调整为上面细化的这些role，ToolGroup 可能需要增加一些新的工具组，这个要往ToolKit这里面靠，RuntimeKind 这个怎么和新修改的在一起修改，StrategyProfile 可能需要去掉，因为我觉得我们不需要暴露strategy的概念了，我们直接通过role来区分不同的执行逻辑和prompt设计就可以了，这样可以让整个流程更加清晰和有针对性

### 问题4：prompt设计
1. 需要修改plan的prompt，去掉对strategy的描述，然后需要加强对role的描述，明确告诉planner每个role能干什么，限制他们只能调用哪些工具，生成的内容需要满足什么样的格式要求（尤其是验证测试类的role，需要明确告诉他输出需要满足什么样的格式要求，包括错误信息的提示，这样可以让后续的错误分析和优化更有针对性）
2. 需要修改execution runner里面的prompt设计，目前是分散在不同方法里面的，我觉得应该统一起来，尤其是针对ReActAgent的prompt设计，应该有一个专门的prompt设计模块来管理这些prompt，这样可以更清晰的看到每个role对应的prompt是什么样子的，方便后续的维护和优化
3. 需要设计针对不同role的prompt模板，尤其是验证测试类的role，需要设计专门的prompt模板来指导他们如何根据依赖和物料进行验证测试，以及如何输出满足格式要求的结果，这样可以提高验证测试的准确性和效率

### 问题5：replay
1. 目前发现只有in-memory, 这样我每次任务调试后的中间结果没有落盘，不方便我定位问题，我觉得需要增加文件落盘的功能，至少在调试阶段可以选择落盘，这样我就可以在调试完成后查看这些中间结果，分析问题所在，进行针对性的优化
2. 我发现任务执行完后，没有log提示，还有就是任务结束标志不明显，我觉得需要增加一些log提示，尤其是在任务执行完成后，应该有一个明显的结束标志，这样可以让用户更清晰的知道任务已经执行完成了，方便后续的操作和分析
3. 目前的replay功能只能回放整个任务的执行过程，我觉得可以增加一个功能，就是可以选择回放某个subtask的执行过程，这样可以更有针对性的分析问题所在，尤其是在调试阶段，可以节省很多时间和精力
