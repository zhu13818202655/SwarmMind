"""Docx style presets for the FlyReport renderer.

We do not check binary ``.docx`` files into git. Instead each "template" is a
:class:`DocxStyle` dictionary describing fonts, sizes, colors and metadata
that :class:`~swarmmind.domains.fly_report.export.docx_renderer.DocxRenderer`
applies via ``python-docx`` when building the document programmatically.

Adding a new preset:
1. Append its name to ``PRESET_NAMES`` in ``template_loader.py``.
2. Add a matching :class:`DocxStyle` entry to :data:`DOCX_STYLES` below.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DocxStyle:
    """Per-preset style knobs consumed by ``DocxRenderer``."""

    title_font: str
    body_font: str
    title_size_pt: int
    heading_size_pt: int
    body_size_pt: int
    title_color_rgb: tuple[int, int, int]
    heading_color_rgb: tuple[int, int, int]
    table_header_bg_hex: str  # background color of table header row
    table_header_color_rgb: tuple[int, int, int]
    page_margin_cm: float
    section_prefix: str  # prepended to each H2 (e.g. "一、" or "")


_DEFAULT = DocxStyle(
    title_font="FangSong",
    body_font="FangSong",
    title_size_pt=22,
    heading_size_pt=14,
    body_size_pt=11,
    title_color_rgb=(34, 34, 34),
    heading_color_rgb=(68, 68, 68),
    table_header_bg_hex="F3F3F3",
    table_header_color_rgb=(34, 34, 34),
    page_margin_cm=2.0,
    section_prefix="",
)


DOCX_STYLES: dict[str, DocxStyle] = {
    "default": _DEFAULT,
    "default_zh": DocxStyle(
        title_font="FangSong",
        body_font="FangSong",
        title_size_pt=24,
        heading_size_pt=15,
        body_size_pt=11,
        title_color_rgb=(0, 51, 102),
        heading_color_rgb=(0, 51, 102),
        table_header_bg_hex="003366",
        table_header_color_rgb=(255, 255, 255),
        page_margin_cm=2.0,
        section_prefix="",
    ),
    "gov_formal": DocxStyle(
        title_font="FangSong",
        body_font="FangSong",
        title_size_pt=22,
        heading_size_pt=14,
        body_size_pt=11,
        title_color_rgb=(0, 0, 0),
        heading_color_rgb=(0, 0, 0),
        table_header_bg_hex="E8E8E8",
        table_header_color_rgb=(0, 0, 0),
        page_margin_cm=2.5,
        section_prefix="",
    ),
    "dashboard": DocxStyle(
        title_font="FangSong",
        body_font="FangSong",
        title_size_pt=20,
        heading_size_pt=13,
        body_size_pt=11,
        title_color_rgb=(239, 35, 60),
        heading_color_rgb=(43, 45, 66),
        table_header_bg_hex="2B2D42",
        table_header_color_rgb=(255, 255, 255),
        page_margin_cm=1.5,
        section_prefix="",
    ),
    "minimal": DocxStyle(
        title_font="FangSong",
        body_font="FangSong",
        title_size_pt=18,
        heading_size_pt=12,
        body_size_pt=11,
        title_color_rgb=(85, 85, 85),
        heading_color_rgb=(119, 119, 119),
        table_header_bg_hex="FFFFFF",
        table_header_color_rgb=(153, 153, 153),
        page_margin_cm=2.5,
        section_prefix="",
    ),
}


def get_style(name: str) -> DocxStyle:
    """Return the style for ``name`` (falls back to ``default``)."""

    return DOCX_STYLES.get(name, _DEFAULT)
