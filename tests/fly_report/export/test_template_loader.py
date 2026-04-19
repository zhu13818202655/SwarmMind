"""Tests for :class:`TemplateLoader` (DESIGN-2 §4.1.6.1)."""

from __future__ import annotations

import pytest

from swarmmind.domains.fly_report.export.template_loader import (
    PRESET_NAMES,
    TemplateLoader,
)


@pytest.fixture
def loader() -> TemplateLoader:
    return TemplateLoader()


@pytest.mark.parametrize("output_format", ["markdown", "pdf", "docx"])
def test_load_default_when_ref_is_none(loader, output_format):
    loaded = loader.load(output_format=output_format, template_ref=None)
    assert loaded.source == "default"
    assert loaded.name == "default"
    assert loaded.output_format == output_format
    assert loaded.template_ref == "default"


@pytest.mark.parametrize("output_format", ["markdown", "pdf", "docx"])
def test_load_default_when_ref_is_default(loader, output_format):
    loaded = loader.load(output_format=output_format, template_ref="default")
    assert loaded.source == "default"


@pytest.mark.parametrize("output_format", ["markdown", "pdf", "docx"])
def test_load_each_preset(loader, output_format):
    for preset in PRESET_NAMES:
        loaded = loader.load(
            output_format=output_format, template_ref=f"preset:{preset}"
        )
        assert loaded.source == "preset"
        assert loaded.name == preset
        assert loaded.template_ref == f"preset:{preset}"


def test_unknown_protocol_falls_back_to_default(loader):
    loaded = loader.load(output_format="markdown", template_ref="user:abc")
    assert loaded.source == "default"


def test_unknown_preset_falls_back_to_default(loader):
    loaded = loader.load(
        output_format="markdown", template_ref="preset:does_not_exist"
    )
    assert loaded.source == "default"


def test_list_templates_includes_default_and_all_presets(loader):
    items = loader.list_templates("markdown")
    refs = [item.template_ref for item in items]
    assert refs[0] == "default"
    for preset in PRESET_NAMES:
        assert f"preset:{preset}" in refs


def test_docx_does_not_require_files_on_disk(loader):
    # docx presets are described in code, not as files.
    loaded = loader.load(output_format="docx", template_ref="preset:gov_formal")
    assert loaded.source == "preset"
    assert loaded.name == "gov_formal"
