"""Export format + options models for the manuscript export pipeline.

Extracted from :mod:`narrare.export.contracts` to keep file sizes under the
RULE-04 limit (mirrors the ``analysis/options`` + ``contracts`` split pattern
elsewhere in the repo). These are the per-request option shapes consumed by the
renderers and service; the Protocols and job/artifact models stay in
:mod:`narrare.export.contracts`.

Non-LLM call-out (see :mod:`narrare.export.contracts`): this module defines no
agent, no prompt, no LLM surface — export is a deterministic render pipeline.
"""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID  # noqa: TC003 — needed at runtime for Pydantic

from pydantic import BaseModel


class ExportFormat(StrEnum):
    """Output format produced by a renderer."""

    PDF = "pdf"
    EPUB = "epub"
    MARKDOWN = "md"


class PaperSize(StrEnum):
    """Paper sizes narrare-roman supports. CUSTOM carries width/height in mm."""

    B_FORMAT_129_198 = "b-format-129x198"  # default (ADR-081)
    A5 = "a5"
    A4 = "a4"
    LETTER = "letter"
    CUSTOM = "custom"


class MirroredMargins(BaseModel):
    """Mirrored Satzspiegel (inside/outside, not left/right). Units: mm."""

    inside_mm: float
    outside_mm: float
    top_mm: float
    bottom_mm: float


class PdfOptions(BaseModel):
    """PDF-specific options. Maps 1:1 to NarrareRomanConfig keys."""

    paper_size: PaperSize = PaperSize.B_FORMAT_129_198
    margins: MirroredMargins | None = None  # None → narrare-roman default for the paper
    body_size_pt: float = 11.0
    leading_ratio: float = 1.2
    drop_caps: bool = False  # OPTIONAL, default OFF (D5)
    include_toc: bool = True


class EpubOptions(BaseModel):
    """EPUB-specific options (pandoc).

    Libertinus Serif (the bundled OFL font — the same files PDF uses, D3) is
    embedded **unconditionally** via pandoc ``--epub-embed-font``
    (regular/italic/bold/bolditalic). There is intentionally NO
    ``embed_fonts`` flag: PDF embeds the font structurally (Typst compiles it
    in — no toggle), and EPUB matches that one-font-policy structure so there is
    a single, footgun-free embedding model across both binary formats. A v1
    toggle would only reintroduce the silent-fallback failure mode the
    no-silent-fallback principle exists to prevent (D7). Markdown is plain text
    and carries no font.
    """

    cover_image_path: str | None = None  # user-provided; no cover generator
    css: str | None = None


class MarkdownOptions(BaseModel):
    """Markdown-specific options (pandoc)."""

    chapter_heading_level: int = 1  # H1 for chapters
    include_front_matter: bool = True


class ExportOptions(BaseModel):
    """Per-export request options. Only the block matching ``format`` is consumed."""

    format: ExportFormat
    volume_id: UUID | None = None  # None = all volumes
    include_front_matter: bool = True
    include_back_matter: bool = True
    include_summaries: bool = False  # v1: may be False-only (fast-follow)
    include_character_list: bool = False
    include_location_glossary: bool = False
    pdf_options: PdfOptions | None = None
    epub_options: EpubOptions | None = None
    markdown_options: MarkdownOptions | None = None
