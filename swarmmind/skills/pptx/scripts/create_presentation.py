from __future__ import annotations

import json
import sys
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt


ACCENT_GOLD = RGBColor(196, 152, 56)
ACCENT_DARK = RGBColor(24, 28, 39)
ACCENT_TEXT = RGBColor(43, 47, 59)
ACCENT_MUTED = RGBColor(98, 104, 120)
ACCENT_LIGHT = RGBColor(247, 243, 232)


def _parse_deck_spec(raw_value: str) -> dict:
    try:
        deck_spec = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Error: invalid deck_spec JSON: {exc}") from exc
    if not isinstance(deck_spec, dict):
        raise SystemExit("Error: deck_spec must be a JSON object")
    if not isinstance(deck_spec.get("slides"), list) or not deck_spec["slides"]:
        raise SystemExit("Error: deck_spec.slides must be a non-empty array")
    return deck_spec


def _add_title_slide(prs: Presentation, title: str, subtitle: str | None) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = ACCENT_DARK

    band = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.RECTANGLE, 0, 0, prs.slide_width, Inches(0.45))
    band.fill.solid()
    band.fill.fore_color.rgb = ACCENT_GOLD
    band.line.fill.background()

    title_box = slide.shapes.add_textbox(Inches(0.85), Inches(1.2), Inches(10.6), Inches(2.1))
    title_frame = title_box.text_frame
    title_frame.word_wrap = True
    paragraph = title_frame.paragraphs[0]
    paragraph.text = title
    paragraph.font.size = Pt(28)
    paragraph.font.bold = True
    paragraph.font.color.rgb = RGBColor(255, 255, 255)

    subtitle_text = subtitle or "Investment outlook and decision framework"
    subtitle_box = slide.shapes.add_textbox(Inches(0.9), Inches(3.0), Inches(7.2), Inches(1.4))
    subtitle_frame = subtitle_box.text_frame
    subtitle_frame.word_wrap = True
    subtitle_paragraph = subtitle_frame.paragraphs[0]
    subtitle_paragraph.text = subtitle_text
    subtitle_paragraph.font.size = Pt(16)
    subtitle_paragraph.font.color.rgb = RGBColor(230, 231, 235)

    tag = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE, Inches(0.9), Inches(4.9), Inches(2.4), Inches(0.55))
    tag.fill.solid()
    tag.fill.fore_color.rgb = RGBColor(58, 64, 78)
    tag.line.fill.background()
    tag_frame = tag.text_frame
    tag_frame.paragraphs[0].text = "SwarmMind Research Deck"
    tag_frame.paragraphs[0].font.size = Pt(11)
    tag_frame.paragraphs[0].font.color.rgb = RGBColor(255, 255, 255)
    tag_frame.paragraphs[0].alignment = PP_ALIGN.CENTER


def _coerce_lines(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _add_content_slide(prs: Presentation, slide_spec: dict, index: int) -> None:
    title = str(slide_spec.get("title") or f"Slide {index}").strip()
    bullets = _coerce_lines(slide_spec.get("bullets"))
    summary = str(slide_spec.get("summary") or "").strip()
    highlight = str(slide_spec.get("highlight") or "").strip()
    source = str(slide_spec.get("source") or "").strip()

    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = RGBColor(255, 255, 255)

    top_bar = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.RECTANGLE, 0, 0, prs.slide_width, Inches(0.28))
    top_bar.fill.solid()
    top_bar.fill.fore_color.rgb = ACCENT_GOLD
    top_bar.line.fill.background()

    title_box = slide.shapes.add_textbox(Inches(0.75), Inches(0.52), Inches(8.8), Inches(0.7))
    title_frame = title_box.text_frame
    title_frame.word_wrap = True
    title_paragraph = title_frame.paragraphs[0]
    title_paragraph.text = title
    title_paragraph.font.size = Pt(24)
    title_paragraph.font.bold = True
    title_paragraph.font.color.rgb = ACCENT_TEXT

    body_panel = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE, Inches(0.7), Inches(1.45), Inches(7.4), Inches(4.8))
    body_panel.fill.solid()
    body_panel.fill.fore_color.rgb = ACCENT_LIGHT
    body_panel.line.color.rgb = RGBColor(234, 226, 206)

    body_box = slide.shapes.add_textbox(Inches(1.0), Inches(1.75), Inches(6.7), Inches(4.2))
    body_frame = body_box.text_frame
    body_frame.word_wrap = True
    if summary:
        summary_paragraph = body_frame.paragraphs[0]
        summary_paragraph.text = summary
        summary_paragraph.font.size = Pt(16)
        summary_paragraph.font.bold = True
        summary_paragraph.font.color.rgb = ACCENT_TEXT
    else:
        body_frame.paragraphs[0].text = ""

    for bullet in bullets:
        paragraph = body_frame.add_paragraph()
        paragraph.text = f"• {bullet}"
        paragraph.level = 0
        paragraph.font.size = Pt(15)
        paragraph.font.color.rgb = ACCENT_TEXT
        paragraph.space_after = Pt(8)

    if not summary and not bullets:
        body_frame.paragraphs[0].text = "Add supporting data, evidence, and clear takeaways for this section."
        body_frame.paragraphs[0].font.size = Pt(15)
        body_frame.paragraphs[0].font.color.rgb = ACCENT_TEXT

    insight_panel = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE, Inches(8.35), Inches(1.45), Inches(4.1), Inches(2.55))
    insight_panel.fill.solid()
    insight_panel.fill.fore_color.rgb = ACCENT_DARK
    insight_panel.line.fill.background()

    insight_box = slide.shapes.add_textbox(Inches(8.65), Inches(1.72), Inches(3.45), Inches(2.0))
    insight_frame = insight_box.text_frame
    insight_frame.word_wrap = True
    kicker = insight_frame.paragraphs[0]
    kicker.text = "Key Takeaway"
    kicker.font.size = Pt(11)
    kicker.font.bold = True
    kicker.font.color.rgb = ACCENT_GOLD

    insight = insight_frame.add_paragraph()
    insight.text = highlight or summary or (bullets[0] if bullets else "No highlight provided.")
    insight.font.size = Pt(18)
    insight.font.bold = True
    insight.font.color.rgb = RGBColor(255, 255, 255)
    insight.space_before = Pt(10)

    source_panel = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE, Inches(8.35), Inches(4.2), Inches(4.1), Inches(1.35))
    source_panel.fill.solid()
    source_panel.fill.fore_color.rgb = RGBColor(250, 250, 250)
    source_panel.line.color.rgb = RGBColor(225, 225, 225)

    source_box = slide.shapes.add_textbox(Inches(8.6), Inches(4.42), Inches(3.55), Inches(0.95))
    source_frame = source_box.text_frame
    source_frame.word_wrap = True
    source_title = source_frame.paragraphs[0]
    source_title.text = "Source"
    source_title.font.size = Pt(10)
    source_title.font.bold = True
    source_title.font.color.rgb = ACCENT_MUTED
    source_text = source_frame.add_paragraph()
    source_text.text = source or "Add a source or evidence note here."
    source_text.font.size = Pt(10)
    source_text.font.color.rgb = ACCENT_MUTED
    source_text.space_before = Pt(6)


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: create_presentation.py '<deck_spec_json>' output_file")

    deck_spec = _parse_deck_spec(sys.argv[1])
    output_path = Path(sys.argv[2])
    output_path.parent.mkdir(parents=True, exist_ok=True)

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    _add_title_slide(prs, str(deck_spec.get("title") or "Presentation").strip(), str(deck_spec.get("subtitle") or "").strip() or None)

    for index, slide_spec in enumerate(deck_spec["slides"], start=1):
        if not isinstance(slide_spec, dict):
            raise SystemExit(f"Error: deck_spec.slides[{index - 1}] must be an object")
        _add_content_slide(prs, slide_spec, index)

    prs.save(output_path)
    print(f"Created presentation at {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())