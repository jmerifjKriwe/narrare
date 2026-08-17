"""pandoc DOCX renderer adapter — co-owner (with ``pandoc_md.py`` /
``pandoc_epub.py``) of the ``pandoc`` binary invocation (RULE-08).

Implements :class:`narrare.export.contracts.ManuscriptRenderer` for
:class:`~narrare.export.options.ExportFormat.DOCX` (C3 — Post-Export
Follow-ups design §6). Spawns pandoc via the shared helper in
:mod:`narrare.export.renderers.pandoc_base` — never calls
``asyncio.create_subprocess_exec`` directly (RULE-08 confinement).

Manuscript format via ``--reference-doc`` (design §6.1, binding)
-----------------------------------------------------------------
The committed ``apps/api/narrare/export/pandoc/reference.docx`` carries the
classic publishing manuscript format — Times 12 pt, 1.5 line spacing, 0.5"
first-line indent, centred chapter headings — and is passed UNCONDITIONALLY.
There is no template toggle: a configurable DOCX template system is
explicitly YAGNI (design §11), mirroring D7's unconditional font policy —
DOCX output never silently falls back to pandoc's default styles. A missing
reference file raises :class:`ExportRenderError` (RULE-11 — the same
no-silent-fallback guard as the EPUB renderer's bundled fonts).

No ``DocxOptions`` model exists BY DESIGN: v1 has zero DOCX-specific
request options. ``isbn`` / ``description`` stay EPUB-only (see
:class:`~narrare.export.options.EpubOptions` — the PDF/MD renderers ignore
them too; D7 precedent). No ``--toc``: a submission manuscript carries no
table of contents (the EPUB renderer's ``--toc`` exists because e-books
navigate).

Empirically verified against pandoc 3.10.1: with a fixed reference.docx the
``word/document.xml`` entry of the output is byte-deterministic across
runs (only ``docProps/core.xml`` — created/modified timestamps — varies) —
the property the C3 golden test pins.

Non-LLM (no ``narrare_core.agents`` / ``narrare_core.prompts`` imports) —
export is a deterministic render pipeline.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from narrare.export.contracts import (
    Artifact,
    ExportFormat,
    ExportOptions,
)
from narrare.export.errors import ExportRenderError
from narrare.export.renderers.pandoc_base import (
    DEFAULT_TIMEOUT_SECONDS,
    run_pandoc,
)

if TYPE_CHECKING:
    from narrare_core.export.contracts import NormalizedManuscript

logger = structlog.get_logger(__name__)

#: The committed manuscript-format reference document (design §6.1),
#: resolved PACKAGE-RELATIVELY (``Path(__file__)``), never via cwd — the
#: background runner may execute with any working directory. ``renderers/``
#: → ``../pandoc/reference.docx`` (the pandoc vendor area — the same
#: package-relative reach the EPUB renderer uses for ``../typst/fonts/``).
#: Read at call time so tests can redirect it (the ``_FONTS_DIR`` pattern).
_REFERENCE_DOC_PATH: Path = Path(__file__).resolve().parent.parent / "pandoc" / "reference.docx"

#: OOXML media type for WordprocessingML documents (the Artifact surface).
_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

#: Fallback filename stem when a manuscript title has no slug-able characters.
_EMPTY_TITLE_SLUG = "manuscript"


def _slugify(title: str) -> str:
    """Reduce a manuscript title to a safe filename stem.

    Mirrors :func:`narrare.export.renderers.pandoc_md._slugify` /
    :func:`narrare.export.renderers.pandoc_epub._slugify` so all three
    pandoc adapters derive identical stems for the same title.
    """
    stem = re.sub(r"[^\w]+", "-", title, flags=re.UNICODE).strip("-").lower()
    return stem or _EMPTY_TITLE_SLUG


def _resolve_reference_doc() -> Path:
    """Resolve the committed reference.docx (manuscript format, §6.1).

    Raises :class:`ExportRenderError` when the file is missing — there is
    never a silent fallback to pandoc's default styles (RULE-11 / the D7
    no-silent-fallback principle applied to document styles).
    """
    if not _REFERENCE_DOC_PATH.is_file():
        raise ExportRenderError(
            f"DOCX reference document missing (manuscript format, no silent "
            f"fallback): {_REFERENCE_DOC_PATH}. Restore the file or reinstall "
            f"the package."
        )
    return _REFERENCE_DOC_PATH


class PandocDocxRenderer:
    """RULE-08 renderer adapter for pandoc DOCX output (manuscript format).

    Structurally satisfies :class:`~narrare.export.contracts.ManuscriptRenderer`
    (no explicit inheritance — matches the repo's adapter convention).
    """

    def __init__(self) -> None:
        # Cached availability probe (RULE-11); refreshable by re-instantiating.
        self._available: bool | None = None

    @property
    def format(self) -> ExportFormat:
        """The format this renderer produces."""
        return ExportFormat.DOCX

    def is_available(self) -> bool:
        """True iff the ``pandoc`` binary is on ``$PATH`` (RULE-11).

        Cached on the instance after the first call; a missing binary degrades
        gracefully (the service reports the format unavailable).
        """
        if self._available is None:
            self._available = shutil.which("pandoc") is not None
        return self._available

    async def render(
        self,
        manuscript: NormalizedManuscript,
        options: ExportOptions,
    ) -> Artifact:
        """Render ``manuscript`` to a DOCX artifact in manuscript format.

        Pandoc writes the docx (a zip) to a temp ``--output`` file rather
        than stdout; the body is piped on stdin. The output is unlinked only
        on render failure (the registry owns cleanup on success).
        """
        reference_doc = _resolve_reference_doc()

        fd, raw_path = tempfile.mkstemp(suffix="-export.docx", prefix="narrare-")
        os.close(fd)  # pandoc overwrites it via --output
        output_path = Path(raw_path)
        try:
            argv: list[str] = [
                "--from=html",
                "--to=docx",
                f"--reference-doc={reference_doc}",
                f"--metadata=title:{manuscript.title}",
                f"--metadata=author:{manuscript.author}",
                f"--metadata=lang:{manuscript.language.value}",
                f"--output={output_path}",
            ]
            await run_pandoc(
                argv,
                manuscript.semantic_html.encode("utf-8"),
                format_label=self.format.value,
                timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
            )
            logger.info(
                "export_docx_rendered",
                bytes=output_path.stat().st_size,
                reference_doc=reference_doc.name,
            )
        except Exception:
            # RULE-11: never leave a partial/corrupt docx on disk; the typed
            # error (from run_pandoc or _resolve_reference_doc) propagates.
            output_path.unlink(missing_ok=True)
            raise

        return Artifact(
            format=self.format,
            path=output_path,
            media_type=_MEDIA_TYPE,
            suggested_filename=f"{_slugify(manuscript.title)}.docx",
        )
