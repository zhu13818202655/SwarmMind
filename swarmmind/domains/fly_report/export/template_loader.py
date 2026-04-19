"""Template loader for the built-in FlyReport renderer presets.

Resolves a ``template_ref`` of either ``"default"`` or ``"preset:<name>"`` to
a :class:`LoadedTemplate` describing where the renderer should pick up the
template assets. Filesystem layout (DESIGN-2 §4.1.6):

    export/templates/<output_format>/default.<ext>.j2
    export/templates/<output_format>/presets/<name>.<ext>.j2

For the ``docx`` format we do not check binary ``.docx`` files into git;
instead we ship per-preset Python style dicts under
:mod:`swarmmind.domains.fly_report.export.docx_styles`. The loader still
returns a :class:`LoadedTemplate` for docx so renderers can rely on a single
contract; ``path`` then points at a sentinel ``<name>.docx.style`` file that
does not need to exist on disk.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from loguru import logger

from swarmmind.domains.fly_report.schemas import OutputFormat

TemplateSource = Literal["default", "preset"]

# Names of the four built-in presets we ship in M1 (DESIGN-2 §4.1.6.1).
PRESET_NAMES: tuple[str, ...] = (
    "default_zh",
    "gov_formal",
    "dashboard",
    "minimal",
)

_FORMAT_EXTENSIONS: dict[OutputFormat, str] = {
    "markdown": "md.j2",
    "pdf": "html.j2",
    "docx": "docx.style",  # virtual extension; styles live in docx_styles.py
}


@dataclass(frozen=True)
class LoadedTemplate:
    """Resolved template descriptor returned by :class:`TemplateLoader`."""

    source: TemplateSource
    name: str
    output_format: OutputFormat
    path: Path
    format_root: Path  # the per-format dir (loader root for Jinja2 includes)
    template_name: str  # path relative to ``format_root`` (Jinja2 lookup name)

    @property
    def template_ref(self) -> str:
        return "default" if self.source == "default" else f"preset:{self.name}"


class TemplateLoader:
    """Resolve and validate built-in template references.

    Parameters
    ----------
    templates_root:
        Directory containing the per-format template subdirectories. Defaults
        to ``swarmmind/domains/fly_report/export/templates``.
    """

    def __init__(self, *, templates_root: Path | None = None) -> None:
        self._root = templates_root or Path(__file__).parent / "templates"

    # ------------------------------------------------------------------ public
    def list_templates(
        self, output_format: OutputFormat
    ) -> list[LoadedTemplate]:
        """Enumerate the default + every preset for the given format."""

        items: list[LoadedTemplate] = [self._make_default(output_format)]
        for name in PRESET_NAMES:
            path = self._preset_path(output_format, name)
            if output_format == "docx" or path.exists():
                items.append(self._make_preset(output_format, name))
        return items

    def load(
        self,
        *,
        output_format: OutputFormat,
        template_ref: str | None,
    ) -> LoadedTemplate:
        """Resolve ``template_ref`` to a :class:`LoadedTemplate`.

        Falls back to ``default`` (with a warning) if the ref is malformed,
        names an unknown preset, or points at a missing file.
        """

        if not template_ref or template_ref == "default":
            return self._load_default(output_format)

        if not template_ref.startswith("preset:"):
            logger.warning(
                "Unknown template_ref protocol {!r}; falling back to default",
                template_ref,
            )
            return self._load_default(output_format)

        name = template_ref.removeprefix("preset:").strip()
        if name not in PRESET_NAMES:
            logger.warning(
                "Unknown preset {!r}; falling back to default", name
            )
            return self._load_default(output_format)

        path = self._preset_path(output_format, name)
        if output_format != "docx" and not path.exists():
            logger.warning(
                "Preset file missing for {!s}/{!s}; falling back to default",
                output_format,
                name,
            )
            return self._load_default(output_format)

        return self._make_preset(output_format, name)

    # ---------------------------------------------------------------- internal
    def _load_default(self, output_format: OutputFormat) -> LoadedTemplate:
        path = self._default_path(output_format)
        if output_format != "docx" and not path.exists():
            raise FileNotFoundError(
                f"Default template missing for {output_format}: {path}"
            )
        return self._make_default(output_format)

    def _make_default(self, output_format: OutputFormat) -> LoadedTemplate:
        ext = _FORMAT_EXTENSIONS[output_format]
        format_root = self._root / output_format
        return LoadedTemplate(
            source="default",
            name="default",
            output_format=output_format,
            path=format_root / f"default.{ext}",
            format_root=format_root,
            template_name=f"default.{ext}",
        )

    def _make_preset(
        self, output_format: OutputFormat, name: str
    ) -> LoadedTemplate:
        ext = _FORMAT_EXTENSIONS[output_format]
        format_root = self._root / output_format
        return LoadedTemplate(
            source="preset",
            name=name,
            output_format=output_format,
            path=format_root / "presets" / f"{name}.{ext}",
            format_root=format_root,
            template_name=f"presets/{name}.{ext}",
        )

    def _default_path(self, output_format: OutputFormat) -> Path:
        ext = _FORMAT_EXTENSIONS[output_format]
        return self._root / output_format / f"default.{ext}"

    def _preset_path(
        self, output_format: OutputFormat, name: str
    ) -> Path:
        ext = _FORMAT_EXTENSIONS[output_format]
        return self._root / output_format / "presets" / f"{name}.{ext}"
