"""FlyReport renderer export package (DESIGN-2 §4.1.6).

Provides the built-in template system (default + presets), the renderer base
classes, and concrete docx / pdf / markdown renderers.

User-uploaded templates (``user:<id>``) and the skin / style-injection mode
are deferred to a future version; see DESIGN-2 §4.1.6.1.
"""

from swarmmind.domains.fly_report.export.base import (
    BaseRenderer,
    RenderedArtifact,
)
from swarmmind.domains.fly_report.export.docx_renderer import DocxRenderer
from swarmmind.domains.fly_report.export.markdown_renderer import (
    MarkdownRenderer,
)
from swarmmind.domains.fly_report.export.pdf_renderer import PdfRenderer
from swarmmind.domains.fly_report.export.router import RendererRouter
from swarmmind.domains.fly_report.export.template_loader import (
    LoadedTemplate,
    TemplateLoader,
)

__all__ = [
    "BaseRenderer",
    "DocxRenderer",
    "LoadedTemplate",
    "MarkdownRenderer",
    "PdfRenderer",
    "RenderedArtifact",
    "RendererRouter",
    "TemplateLoader",
]
