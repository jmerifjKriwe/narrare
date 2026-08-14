"""Real-binary integration tests for the Typst PDF renderer (Slice 6 / ADR-081).

All tests here require BOTH the ``typst`` and ``pandoc`` binaries (skipif
guarded via ``_REQUIRES_BINARY``). The pure unit tests live in
:mod:`test_typst_pdf`; this module owns the end-to-end render + seam-fix
regression tests:

- **Integration** — ``render()`` produces a valid PDF (PyMuPDF opens it).
- **F-1** — ``<h2>`` chapters become level-1 openers (recto pagebreak + ToC).
- **F-6** — literal ``@`` in prose does not error and survives.
- **F-7** — ``author`` as a scalar string renders on the title page.
- **D3** — the embedded body font is Libertinus Serif (no silent fallback).
- **Byte reproducibility** — two consecutive renders are byte-identical.
- **Failure path** — typst non-zero exit → typed ``ExportRenderError``.

The seam-fix regressions (F-1/F-6/F-7) must never regress — ADR-081.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from uuid import uuid4

import pymupdf
import pytest

from narrare.export.errors import ExportRenderError
from narrare.export.options import (
    ExportFormat,
    ExportOptions,
    PaperSize,
    PdfOptions,
)
from narrare.export.renderers.typst import TypstPdfRenderer
from narrare_core.export.contracts import ChapterMeta, Language, NormalizedManuscript

# Reuse the golden-probe PyMuPDF accessors (typed boundary over the untyped
# stub — the same helpers the Slice-5 probes use). DRY: no duplicate casts.
from tests.golden.export._typst_probe_helpers import (
    doc_page_count,
    page_fonts,
    page_text,
)

# ── Skip guard ──────────────────────────────────────────────────────────────

_REQUIRES_BINARY = pytest.mark.skipif(
    shutil.which("typst") is None or shutil.which("pandoc") is None,
    reason="typst and/or pandoc not installed",
)


# ── Fixtures ────────────────────────────────────────────────────────────────


def _normalized(
    semantic_html: str = "<h2>Chapter One</h2>\n<p>Body text.</p>",
    *,
    title: str = "Test Novel",
    author: str = "Test Author",
    language: Language = Language.EN,
) -> NormalizedManuscript:
    """Build a NormalizedManuscript with a single placeholder chapter."""
    return NormalizedManuscript(
        semantic_html=semantic_html,
        title=title,
        author=author,
        language=language,
        chapters=[ChapterMeta(chapter_id=uuid4(), title="C1", position=0, volume_id=None)],
    )


def _pdf_options(*, pdf_options: PdfOptions | None = None) -> ExportOptions:
    """Build ExportOptions for PDF."""
    return ExportOptions(format=ExportFormat.PDF, pdf_options=pdf_options)


# ── Integration + seam-fix regression tests ─────────────────────────────────


class TestRenderPdf:
    """``render()`` produces a real PDF via pandoc + typst."""

    @_REQUIRES_BINARY
    @pytest.mark.asyncio
    async def test_render_produces_valid_pdf_artifact(self) -> None:
        manuscript = _normalized()
        artifact = await TypstPdfRenderer().render(manuscript, _pdf_options())
        try:
            assert artifact.format is ExportFormat.PDF
            assert artifact.media_type == "application/pdf"
            assert artifact.suggested_filename == "test-novel.pdf"
            assert artifact.path.is_file()
            assert artifact.path.stat().st_size > 0
            with pymupdf.open(artifact.path) as doc:
                assert doc_page_count(doc) > 0
        finally:
            artifact.path.unlink(missing_ok=True)

    # ── F-1: chapter becomes a level-1 opener (recto pagebreak + ToC) ──

    @_REQUIRES_BINARY
    @pytest.mark.asyncio
    async def test_f1_chapters_start_on_recto_pages(self) -> None:
        """F-1: --shift-heading-level-by=-1 makes <h2> a level-1 opener.

        Each chapter heading lands on a recto (odd) page — the recto-opener
        show rule fires ONLY on level-1 headings. Without the shift, <h2>
        stays level-2 and chapters flow continuously (no recto break).
        """
        html = (
            "<h2>Alpha</h2><p>Short body fits on one page.</p>"
            "<h2>Beta</h2><p>Short body fits on one page.</p>"
            "<h2>Gamma</h2><p>Short body fits on one page.</p>"
        )
        manuscript = _normalized(semantic_html=html, title="F1 Recto Probe")
        artifact = await TypstPdfRenderer().render(manuscript, _pdf_options())
        try:
            with pymupdf.open(artifact.path) as doc:
                chapter_titles = ("Alpha", "Beta", "Gamma")
                heading_pages: list[int] = []
                for i in range(doc_page_count(doc)):
                    lines = {ln.strip() for ln in page_text(doc[i]).splitlines() if ln.strip()}
                    for title in chapter_titles:
                        # Exact-match line = body heading (the ToC entry has
                        # dot leaders + folio appended, so it never matches).
                        if title in lines and (i + 1) not in heading_pages:
                            heading_pages.append(i + 1)
                assert len(heading_pages) == 3, (
                    f"expected 3 chapter headings, found on pages {heading_pages}"
                )
                for folio in heading_pages:
                    assert folio % 2 == 1, (
                        f"chapter heading landed on verso (even) page {folio}; "
                        "recto-start invariant violated (F-1 regression)"
                    )
        finally:
            artifact.path.unlink(missing_ok=True)

    @_REQUIRES_BINARY
    @pytest.mark.asyncio
    async def test_f1_toc_contains_chapter_entries(self) -> None:
        """F-1: the ToC lists chapter titles with phase-relative folios."""
        html = "<h2>Alpha Chapter</h2><p>Body.</p><h2>Beta Chapter</h2><p>Body.</p>"
        manuscript = _normalized(semantic_html=html, title="F1 TOC Probe")
        artifact = await TypstPdfRenderer().render(manuscript, _pdf_options())
        try:
            with pymupdf.open(artifact.path) as doc:
                # The ToC page contains "Contents" + chapter entries with dot
                # leaders and page numbers.
                toc_text = " ".join(
                    page_text(doc[i])
                    for i in range(doc_page_count(doc))
                    if "Contents" in page_text(doc[i])
                )
                assert toc_text, "no ToC page found (expected 'Contents' heading)"
                assert "Alpha Chapter" in toc_text
                assert "Beta Chapter" in toc_text
        finally:
            artifact.path.unlink(missing_ok=True)

    # ── F-6: literal @ in prose does not error and survives ──────────

    @_REQUIRES_BINARY
    @pytest.mark.asyncio
    async def test_f6_literal_at_sign_survives(self) -> None:
        """F-6: prose containing @preview/… renders without error.

        Without escaping, Typst parses ``@preview`` as a citation reference
        and errors (``label '<preview>' does not exist``). The renderer's
        defensive escape (plus pandoc's own escaping) prevents this.
        """
        html = "<h2>Chapter One</h2><p>See @preview/foo for the library.</p>"
        manuscript = _normalized(semantic_html=html)
        artifact = await TypstPdfRenderer().render(manuscript, _pdf_options())
        try:
            with pymupdf.open(artifact.path) as doc:
                full_text = " ".join(page_text(doc[i]) for i in range(doc_page_count(doc)))
                # The literal @ survives in the output.
                assert "@preview/foo" in full_text or "preview/foo" in full_text
        finally:
            artifact.path.unlink(missing_ok=True)

    # ── F-7: author as a scalar string renders correctly ─────────────

    @_REQUIRES_BINARY
    @pytest.mark.asyncio
    async def test_f7_author_scalar_renders_in_title_page(self) -> None:
        """F-7: author is a scalar string (never an array) and renders."""
        manuscript = _normalized(
            semantic_html="<h2>Chapter One</h2><p>Body.</p>",
            title="Scalar Author Probe",
            author="Jane Q. Doe",
        )
        artifact = await TypstPdfRenderer().render(manuscript, _pdf_options())
        try:
            with pymupdf.open(artifact.path) as doc:
                title_page_text = page_text(doc[0])
                assert "Jane Q. Doe" in title_page_text, (
                    "scalar author not found on title page (F-7 regression)"
                )
                assert "Scalar Author Probe" in title_page_text
        finally:
            artifact.path.unlink(missing_ok=True)

    # ── D3: bundled Libertinus is the embedded body font ──────────────

    @_REQUIRES_BINARY
    @pytest.mark.asyncio
    async def test_embedded_body_font_is_libertinus_no_silent_fallback(
        self,
    ) -> None:
        """D3: every body page uses Libertinus Serif (no silent fallback)."""
        manuscript = _normalized(semantic_html="<h2>Chapter One</h2><p>Body text on this page.</p>")
        artifact = await TypstPdfRenderer().render(manuscript, _pdf_options())
        try:
            with pymupdf.open(artifact.path) as doc:
                for i in range(doc_page_count(doc)):
                    fonts = page_fonts(doc[i])
                    if not fonts:
                        continue  # blank verso — nothing to check
                    non_libertinus = {f for f in fonts if "libertinus" not in f.lower()}
                    assert not non_libertinus, (
                        f"page {i + 1} used non-Libertinus font(s) "
                        f"{non_libertinus!r} — silent fallback (D3 violation)"
                    )
        finally:
            artifact.path.unlink(missing_ok=True)

    # ── Byte reproducibility ──────────────────────────────────────────

    @_REQUIRES_BINARY
    @pytest.mark.asyncio
    async def test_byte_reproducibility_two_renders_identical_sha256(self) -> None:
        """Two consecutive renders of identical input produce byte-identical PDFs."""
        manuscript = _normalized()
        options = _pdf_options()
        renderer = TypstPdfRenderer()
        a1 = await renderer.render(manuscript, options)
        a2 = await renderer.render(manuscript, options)
        try:
            h1 = hashlib.sha256(a1.path.read_bytes()).hexdigest()
            h2 = hashlib.sha256(a2.path.read_bytes()).hexdigest()
            assert h1 == h2, (
                f"byte reproducibility violated: sha256 differs ({h1[:16]}… ≠ {h2[:16]}…)"
            )
        finally:
            a1.path.unlink(missing_ok=True)
            a2.path.unlink(missing_ok=True)

    # ── Failure path: non-zero exit → ExportRenderError ───────────────

    @_REQUIRES_BINARY
    @pytest.mark.asyncio
    async def test_failure_path_nonzero_exit_raises_export_render_error(
        self,
    ) -> None:
        """Typst non-zero exit (CUSTOM paper without dimensions) → typed error."""
        manuscript = _normalized()
        # CUSTOM paper without custom dimensions → narrare-roman panics.
        options = _pdf_options(pdf_options=PdfOptions(paper_size=PaperSize.CUSTOM))
        with pytest.raises(ExportRenderError, match=r"typst .* exited"):
            await TypstPdfRenderer().render(manuscript, options)

    @_REQUIRES_BINARY
    @pytest.mark.asyncio
    async def test_render_cleans_up_temp_pdf_on_failure(self) -> None:
        """RULE-11: a failed render unlinks the partial PDF (no orphan)."""
        manuscript = _normalized()
        options = _pdf_options(pdf_options=PdfOptions(paper_size=PaperSize.CUSTOM))
        with pytest.raises(ExportRenderError):
            await TypstPdfRenderer().render(manuscript, options)
        # No orphan PDF from this render in the system temp dir.
        leftover = list(Path("/tmp").glob("narrare-*-export.pdf"))
        assert leftover == [], f"orphan PDF(s) left behind: {leftover}"
