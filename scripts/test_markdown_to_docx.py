"""Smoke test for direct Markdown-to-DOCX rendering.

Usage:
    python scripts/test_markdown_to_docx.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("OPENAI_MODEL", "gpt-4o")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from swarmmind.domains.fly_report.chart import configure_matplotlib_cjk_font
from swarmmind.domains.fly_report.export import RendererRouter

configure_matplotlib_cjk_font()


OUTPUT_ROOT = ROOT / "data" / "fly_report_artifacts" / "markdown-docx-demo"
ASSET_DIR = OUTPUT_ROOT / "assets"
DOCX_DIR = OUTPUT_ROOT / "docx"


def _make_demo_image(path: Path) -> None:
    fig, ax = plt.subplots(figsize=(6, 2.8))
    ax.set_facecolor("#f8fafc")
    ax.text(
        0.5,
        0.62,
        "Markdown Image",
        ha="center",
        va="center",
        fontsize=22,
        color="#1f4e79",
        weight="bold",
    )
    ax.text(
        0.5,
        0.36,
        "custom width + alignment",
        ha="center",
        va="center",
        fontsize=12,
        color="#64748b",
    )
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_edgecolor("#94a3b8")
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def _make_demo_chart(path: Path) -> None:
    departments = ["资规", "公安", "交通", "建设", "农业"]
    values = [36, 28, 31, 22, 41]
    fig, ax = plt.subplots(figsize=(7, 3.2))
    bars = ax.bar(departments, values, color=["#1f77b4", "#2ca02c", "#ff7f0e", "#9467bd", "#d62728"])
    ax.set_title("部门飞行任务数", color="#1f2937")
    ax.set_ylabel("任务数")
    ax.grid(axis="y", linestyle="--", alpha=0.28)
    for bar in bars:
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.8,
            str(int(bar.get_height())),
            ha="center",
            va="bottom",
            fontsize=9,
        )
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def _build_markdown(image_path: Path, chart_path: Path) -> str:
    return f"""# Markdown 转 Word 效果测试

::: {{align=center}}
这是一段居中的说明文字，包含 [蓝色重点]{'{'}color=#1f4e79{'}'} 和 **加粗内容**。
:::

::: {{align=right}}
这是一段右对齐文字，用来检查段落位置是否能够被 Markdown 控制。
:::

::: {{align=left}}
这是一段左对齐正文，包含 <span style="color:#d62728">红色风险提示</span>，以及 `inline code`。
:::

## 一、标题层级

### 1.1 三级标题

#### 1.1.1 四级标题

普通段落可以混合 **加粗**、*斜体*、`代码片段`，以及 [绿色结论]{'{'}color=#2ca02c{'}'}。

---

## 二、列表

- 支持无序列表
- 支持行内颜色：[需关注]{'{'}color=#ff7f0e{'}'}

1. 支持有序列表第一项
2. 支持有序列表第二项

## 三、表格

::: {{align=left}}
| 左对齐表格 | 本期 | 变化 |
| --- | ---: | ---: |
| 巡查任务 | 82 | +12.3% |
| 异常任务 | 4 | -20.0% |
:::

::: {{align=center}}
| 居中表格 | 本期 | 上期 | 变化 |
| --- | ---: | ---: | ---: |
| 飞行任务数 | 158 | 121 | +30.6% |
| 告警数量 | 46 | 52 | -11.5% |
| 图片采集 | 3,820 | 3,100 | +23.2% |
:::

::: {{align=right}}
| 右对齐表格 | 数值 |
| --- | ---: |
| 处置完成率 | 91.4% |
| 平均响应时间 | 18 分钟 |
:::

### 3.1 同一层级左右并列表格

::: {{.table-pair}}
::: {{align=left}}
| 左侧部门 | 飞行次数 |
| --- | ---: |
| 资规局 | 36 |
| 公安局 | 28 |
:::

::: {{align=right}}
| 右侧指标 | 数值 |
| --- | ---: |
| 告警数量 | 46 |
| 处置完成率 | 91.4% |
:::
:::

## 四、图片尺寸与对齐

![左对齐小图]({image_path}){{width=6cm align=left}}

![居中中图]({image_path}){{width=10cm align=center}}

![右对齐宽图]({image_path}){{width=4.8in align=right}}

## 五、图表与标题

![图表：部门飞行任务数]({chart_path}){{width=14cm align=center}}

::: {{align=center}}
[图表说明]{'{'}color=#64748b{'}'}：上图由脚本动态生成，作为 Markdown 图片插入 Word。
:::
"""


def main() -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    DOCX_DIR.mkdir(parents=True, exist_ok=True)

    image_path = ASSET_DIR / "markdown-demo-image.png"
    chart_path = ASSET_DIR / "department-flight-chart.png"
    markdown_path = OUTPUT_ROOT / "markdown-docx-demo.md"

    _make_demo_image(image_path)
    _make_demo_chart(chart_path)
    markdown = _build_markdown(image_path.resolve(), chart_path.resolve())
    markdown_path.write_text(markdown, encoding="utf-8")

    artifact = RendererRouter().render_markdown_to_docx(
        markdown,
        output_dir=DOCX_DIR,
        filename="markdown-docx-demo.docx",
        template_ref="preset:gov_formal",
        title="Markdown 直转 Word 测试报告",
    )
    print("Markdown source path:", markdown_path.resolve())
    print("DOCX artifact path:", Path(artifact.artifact_path).resolve())


if __name__ == "__main__":
    main()