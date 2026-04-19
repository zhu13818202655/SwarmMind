"""Tests for the markdown / pdf / docx renderers."""

from __future__ import annotations

from pathlib import Path

import pytest

from swarmmind.domains.fly_report.export import (
    DocxRenderer,
    MarkdownRenderer,
    PdfRenderer,
    RendererRouter,
    TemplateLoader,
)
from swarmmind.domains.fly_report.export.template_loader import PRESET_NAMES

from .conftest import make_context


@pytest.fixture
def loader() -> TemplateLoader:
    return TemplateLoader()


# ----------------------------------------------------------------- markdown


def test_markdown_default_renders_kpi_table(tmp_path: Path, loader):
    renderer = MarkdownRenderer(template_loader=loader)
    artifact = renderer.render(make_context(), output_dir=tmp_path)

    assert artifact.output_format == "markdown"
    assert artifact.template_ref == "default"
    assert artifact.warnings == []

    content = Path(artifact.artifact_path).read_text(encoding="utf-8")
    assert "飞行报告" in content
    assert "飞行任务数" in content
    assert "+25.49%" in content
    # KPI with no previous value should render an em dash, not crash.
    assert "算法告警" in content


@pytest.mark.parametrize("preset", PRESET_NAMES)
def test_markdown_each_preset_renders(tmp_path: Path, loader, preset):
    renderer = MarkdownRenderer(template_loader=loader)
    artifact = renderer.render(
        make_context(),
        output_dir=tmp_path,
        template_ref=f"preset:{preset}",
    )
    assert artifact.template_ref == f"preset:{preset}"
    content = Path(artifact.artifact_path).read_text(encoding="utf-8")
    assert "飞行" in content


# ----------------------------------------------------------------- pdf


def test_pdf_falls_back_to_html_when_weasyprint_missing(
    tmp_path: Path, loader, monkeypatch
):
    # Force the optional import to fail even if weasyprint happens to be
    # installed, so the test asserts the documented fallback.
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "weasyprint":
            raise ImportError("simulated absence")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    renderer = PdfRenderer(template_loader=loader)
    artifact = renderer.render(make_context(), output_dir=tmp_path)

    assert artifact.output_format == "pdf"
    assert artifact.artifact_path.endswith(".html")
    assert any("WeasyPrint" in w for w in artifact.warnings)
    html = Path(artifact.artifact_path).read_text(encoding="utf-8")
    assert "<h1>" in html
    assert "飞行任务数" in html


@pytest.mark.parametrize("preset", PRESET_NAMES)
def test_pdf_each_preset_renders_html(tmp_path: Path, loader, monkeypatch, preset):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "weasyprint":
            raise ImportError("simulated absence")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    renderer = PdfRenderer(template_loader=loader)
    artifact = renderer.render(
        make_context(),
        output_dir=tmp_path,
        template_ref=f"preset:{preset}",
    )
    assert artifact.template_ref == f"preset:{preset}"
    html = Path(artifact.artifact_path).read_text(encoding="utf-8")
    assert "飞行" in html


# ----------------------------------------------------------------- docx


def test_docx_default_writes_valid_file(tmp_path: Path, loader):
    from docx import Document

    renderer = DocxRenderer(template_loader=loader)
    artifact = renderer.render(make_context(), output_dir=tmp_path)

    assert artifact.output_format == "docx"
    assert artifact.template_ref == "default"
    out = Path(artifact.artifact_path)
    assert out.exists() and out.stat().st_size > 0

    doc = Document(str(out))
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "飞行报告" in text
    # KPI table should have rendered.
    assert any(
        "飞行任务数" in cell.text
        for table in doc.tables
        for row in table.rows
        for cell in row.cells
    )


@pytest.mark.parametrize("preset", PRESET_NAMES)
def test_docx_each_preset_writes_valid_file(tmp_path: Path, loader, preset):
    from docx import Document

    renderer = DocxRenderer(template_loader=loader)
    artifact = renderer.render(
        make_context(),
        output_dir=tmp_path,
        template_ref=f"preset:{preset}",
    )
    assert artifact.template_ref == f"preset:{preset}"
    doc = Document(artifact.artifact_path)
    assert any("飞行报告" in p.text for p in doc.paragraphs)


# ----------------------------------------------------------------- router


def test_router_dispatches_by_output_format(tmp_path: Path):
    router = RendererRouter()
    md = router.render(
        make_context(), output_format="markdown", output_dir=tmp_path
    )
    assert md.artifact_path.endswith(".md")

    docx = router.render(
        make_context(),
        output_format="docx",
        output_dir=tmp_path,
        template_ref="preset:minimal",
    )
    assert docx.artifact_path.endswith(".docx")
    assert docx.template_ref == "preset:minimal"


def test_router_rejects_unknown_format(tmp_path: Path):
    router = RendererRouter()
    with pytest.raises(ValueError, match="Unsupported output_format"):
        router.render(
            make_context(),
            output_format="xls",  # type: ignore[arg-type]
            output_dir=tmp_path,
        )
