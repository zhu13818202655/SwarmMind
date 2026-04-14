# SwarmMind Skill 编写指南

这份文档面向仓库开发者，目标只有一个：让你能按当前系统的真实约束，稳定地新建一个可被 agent 发现、可在 sandbox 中执行、可被 replay 和 artifact 系统追踪的 skill。

如果你想了解底层机制，先看 [docs/design/skill/skill-system-design.md](/home/admin2/proj/SwarmMind/docs/design/skill/skill-system-design.md)。本文更关注“怎么写”。

## 1. 什么时候应该写成 skill

优先写成 skill 的场景：

1. 这类能力会被重复使用，而不是一次性临时代码。
2. 它依赖一组固定脚本、模板、静态资源或参考资料。
3. 它需要在 sandbox 内稳定地产出真实文件，例如 `.pptx`、`.pdf`、`.docx`。
4. 你希望 agent 通过一个受约束的工具面调用它，而不是任意拼接源码执行。

不建议写成 skill 的场景：

1. 只是一次性调试命令。
2. 只需要读写当前仓库文件，更适合直接用 workspace 工具。
3. 没有稳定接口，仍处在频繁变更和试错阶段。

## 2. 最小目录结构

在 `swarmmind/skills/` 下新建一个目录，例如：

```text
swarmmind/skills/my_skill/
  SKILL.md
  scripts/
    run.py
```

扩展结构通常如下：

```text
swarmmind/skills/my_skill/
  SKILL.md
  scripts/
    run.py
    helper.py
  references/
    usage.md
  assets/
    template.json
    logo.png
```

目录含义：

1. `SKILL.md`：元数据和说明入口，必须有。
2. `scripts/`：所有允许通过 `run_skill_script` 调用的脚本。
3. `references/`：供 agent 理解能力或供人维护的参考文档。
4. `assets/`：模板、图片、静态资源等。

当前系统执行时会把整个 skill 包复制到 sandbox，所以脚本内部可以依赖相对路径访问 `references/` 和 `assets/`。

## 3. 先写一个能跑的最小样例

### 3.1 `SKILL.md`

```md
---
name: my_skill
description: 读取输入 JSON 并生成摘要文件。
runtime_requirements:
  python_packages:
    - pydantic
script_specs:
  - path: scripts/run.py
    runtime: python
    description: 读取输入文件并输出摘要结果。
    argument_names:
      - input_file
      - output_file
    args_schema:
      type: object
      properties:
        input_file:
          type: string
          description: 输入 JSON 文件路径。
        output_file:
          type: string
          description: 输出文本文件路径。
      required:
        - input_file
        - output_file
    examples:
      - script_input:
          input_file: /workspace/input.json
          output_file: /workspace/output/result.txt
    artifacts:
      - output/result.txt
---

# My Skill

## 能力说明

- 读取一个 JSON 文件。
- 提取关键字段。
- 输出文本摘要。

## 使用限制

- 输入必须是 UTF-8 JSON。
- 输出路径必须可写。
```

### 3.2 `scripts/run.py`

```python
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python scripts/run.py <input_file> <output_file>")

    input_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2])

    payload = json.loads(input_file.read_text(encoding="utf-8"))
    summary = payload.get("summary", "")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(summary, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

这个样例已经满足当前系统的三条核心要求：

1. 脚本路径明确声明在 `script_specs` 中。
2. 参数顺序明确，可由 `script_input` 推导。
3. 输出文件路径明确声明在 `artifacts` 中。

## 4. `SKILL.md` 应该怎么写

### 4.1 顶层 frontmatter 必填建议

新增 skill 时，至少写这些字段：

1. `name`
2. `description`
3. `runtime_requirements`
4. `script_specs`

建议视情况补齐这些字段：

1. `version`
2. `license`
3. `required_env`
4. `required_bins`
5. `compatibility`

### 4.2 `description` 怎么写

`description` 的作用是帮助 catalog 展示和 prompt 触发，不是拿来塞依赖说明的。

推荐写法：

1. 说明它处理什么输入和输出。
2. 说明它适合什么触发场景。
3. 长度控制在 1 到 3 句内。

不推荐写法：

1. 把 pip install 命令写进 `description`。
2. 把详细操作手册全塞进去。
3. 写得过于抽象，导致 agent 不知道什么时候该用。

## 5. `runtime_requirements` 怎么写

把“脚本运行前需要准备什么”写进 `runtime_requirements`，而不是散落在 body 文本里让 agent 猜。

### 5.1 Python skill

```yaml
runtime_requirements:
  python_packages:
    - requests
    - pyyaml
```

### 5.2 Node skill

```yaml
runtime_requirements:
  node_packages:
    - playwright
  bootstrap_commands:
    - playwright install chromium
```

### 5.3 系统依赖

```yaml
runtime_requirements:
  system_packages:
    - libreoffice
```

### 5.4 区域网络覆盖

如果你的依赖对镜像源敏感，可以显式指定：

```yaml
runtime_requirements:
  python_packages:
    - some-package
  python_index_url: https://pypi.tuna.tsinghua.edu.cn/simple
```

通常不需要每个 skill 都重复写镜像源，因为系统已经有默认值。只有当某个 skill 对源有特殊要求时才单独覆盖。

## 6. `script_specs` 怎么写

这是当前新增 skill 最关键的一部分。不要只声明一个脚本路径就结束，至少要把参数、运行时和产物写清楚。

### 6.1 推荐字段

每个脚本至少建议包含：

1. `path`
2. `runtime`
3. `description`
4. `argument_names`
5. `args_schema`
6. `examples`
7. `artifacts`

### 6.2 为什么优先写 `argument_names`

当前系统虽然支持 `script_args`，但 agent 更适合传结构化的 `script_input`。要让系统可靠地把 `script_input` 转成位置参数，你必须给出顺序定义。

最稳妥的方式就是显式写：

```yaml
argument_names:
  - input_file
  - output_file
```

如果只写 `args_schema` 而不写 `argument_names`，系统会尝试按 `properties` 顺序推导，但这比显式定义更脆弱。

### 6.3 `artifacts` 一定要写真实相对路径

正确示例：

```yaml
artifacts:
  - output/result.txt
```

不推荐：

```yaml
artifacts:
  - result
  - summary file
```

原因很简单：artifact 收集是按路径进行的，不是按语义猜测的。

## 7. 脚本编写约定

skill 脚本本质上就是 sandbox 内运行的普通程序，但为了让它更稳定，建议遵循这些约定。

### 7.1 明确入口和参数校验

1. 不要依赖隐式全局状态。
2. 启动时先校验参数数量和格式。
3. 参数错误时输出明确 usage，而不是静默失败。

### 7.2 主动创建输出目录

虽然系统会为声明的 artifact 目录提前 `mkdir -p`，脚本里仍建议自己做一次输出目录保障。这样脚本单独调试时也更稳。

### 7.3 使用相对路径访问 skill 内资源

因为整个 skill 包会复制到 sandbox，所以脚本里可以安全地通过当前 skill 根目录下的相对路径访问资源。不要把资源路径硬编码成宿主机绝对路径。

### 7.4 错误信息写给人看

skill 失败后，agent 会依据 stderr 和失败分类来决定下一步。错误信息如果过于含糊，会直接降低修复成功率。

推荐：

1. 报错时指出缺了哪个参数。
2. 报错时指出哪个输入文件不存在。
3. 报错时指出哪个依赖没有准备好。

## 8. 如何让 agent 更容易正确调用

你不能假设 agent 会自动理解脚本怎么用。你需要通过声明把调用路径做得尽量低歧义。

### 8.1 给出 `examples.script_input`

这是最有效的方式之一。一个好的例子比一大段自然语言描述更有约束力。

### 8.2 在 body 里写清限制条件

`SKILL.md` body 不应该堆依赖安装说明，但应该写：

1. 这个 skill 适合什么任务。
2. 输入输出的约束。
3. 哪些常见误用要避免。

### 8.3 不要让一个脚本承担过多分支语义

比起“一个超复杂脚本 + 十几个可选参数”，更推荐：

1. 保持单脚本职责单一。
2. 为不同阶段拆成多个脚本。
3. 每个脚本的输入输出都尽量稳定。

这不仅更利于 agent 调用，也更利于失败分类和产物收集。

## 9. 常见反例

### 9.1 反例：把依赖写进 `description`

错误方向：

```yaml
description: Run this skill after installing defusedxml and python-pptx and some other packages...
```

正确方向：

```yaml
runtime_requirements:
  python_packages:
    - defusedxml
    - python-pptx
```

### 9.2 反例：让 `script` 传入源码

错误方向：

```json
{
  "skill": "pptx",
  "script": "python -c 'print(123)'"
}
```

正确方向：

1. 把脚本放进 `scripts/`。
2. 在 `script_specs` 中声明它。
3. 调用时传声明路径，例如 `scripts/run.py`。

### 9.3 反例：有输出文件但不声明 `artifacts`

如果脚本会生成真实文件，而你没在 `artifacts` 里声明路径，系统默认不会帮你猜测要收集哪个文件。

### 9.4 反例：只写 `script_args` 约定，不写 `script_specs`

这种写法能让人类维护者勉强记住，但 agent 很容易调错参数顺序。当前规范已经不鼓励这种写法。

## 10. 新建一个 skill 的推荐流程

### 第一步：搭空目录

```text
swarmmind/skills/<skill_name>/
  SKILL.md
  scripts/
```

### 第二步：先写一个最小可执行脚本

目标不是一步到位，而是先有一个：

1. 输入明确。
2. 输出明确。
3. 可在本地单独运行。

### 第三步：补 `runtime_requirements`

把依赖和 bootstrap 明确放进 frontmatter。

### 第四步：补 `script_specs`

把运行时、参数顺序、示例、产物路径写清楚。

### 第五步：补 body 说明

只写对 agent 和维护者真正有帮助的说明，不要重复 frontmatter 中已经结构化表达的内容。

### 第六步：做一次调用自检

至少检查：

1. 脚本路径是否确实位于 `scripts/`。
2. `argument_names` 与脚本实际接收顺序是否一致。
3. `artifacts` 路径是否真会被写出来。
4. 相对路径资源是否能在 sandbox 中访问。

## 11. 交付前检查清单

新 skill 提交前，建议逐项确认：

1. `SKILL.md` frontmatter 可被 YAML 正常解析。
2. `name` 唯一且稳定。
3. `description` 没有滥塞依赖或冗长手册。
4. 所有会执行的脚本都位于 `scripts/`。
5. `runtime_requirements` 没有遗漏关键依赖。
6. 每个脚本都有 `script_specs`。
7. 需要结构化输入的脚本都写了 `argument_names`。
8. 需要真实文件输出的脚本都写了 `artifacts`。
9. body 中写明了限制条件和典型用途。
10. 错误信息对人类和 agent 都足够可读。

## 12. 总结

写一个好的 skill，不是“把脚本丢进目录里”这么简单。你真正要交付的是三层东西：

1. 稳定的能力包结构。
2. 可被系统执行的声明式元数据。
3. 可被 agent 正确理解和调用的低歧义接口。

只要把这三层写清楚，skill 才能真正成为可复用能力，而不是下一次排障时的隐患来源。