"""Golden-Pages probe for Slice 5d — the narrare-roman table of contents.

Renders a manuscript with the bundled ``narrare-roman`` Typst package and
asserts the two TOC invariants of ADR-081 / IO-001 Slice 5d:

1. **TOC present with correct phase-relative folios** — when
   ``config.include-toc`` is true, the TOC (rendered via ``#toc()`` in the
   frontmatter) lists each chapter with a page number, and that number is
   the *phase-relative folio* — the same value printed in the page footer
   (computed by the shared ``phase-folio`` helper in ``numbering.typ``).
   The TOC and the footers never disagree.
2. **TOC absent when disabled** — when ``config.include-toc`` is false,
   ``#toc()`` renders nothing (the ``_toc-enabled`` gate publishes the
   configured value via document state).

The probe reconstructs each TOC entry from the word-level spatial layout
(PyMuPDF "words" mode: chapter-title words on the left, folio number on
the right, same visual line) and cross-checks the folio against the
footer of the corresponding body chapter page.

The probe invokes ``typst compile`` via subprocess
(``_typst_probe_helpers.compile_typst``); per ADR-081 this is a sanctioned
test-harness invocation, deliberately outside RULE-08 confinement scope
(only the two production render binaries are confined — see
``_typst_probe_helpers.py`` for the full rationale).
"""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

import pymupdf
import pytest

from tests.golden.export._typst_probe_helpers import (
    PACKAGE_IMPORT,
    TextWord,
    body_text,
    compile_typst,
    footer_text,
    is_typst_available,
    page_text,
    page_words,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

# ── Skip guard: nothing in this module runs without the typst binary ──────
pytestmark = [
    pytest.mark.golden_pages,
    pytest.mark.skipif(
        not is_typst_available(),
        reason="typst not installed (install via scripts/install_export_toolchain.sh)",
    ),
]

#: The three chapter headings in the fixture (level-1 headings in the body).
CHAPTER_TITLES: tuple[str, ...] = ("Chapter One", "Chapter Two", "Chapter Three")

#: Vertical tolerance for grouping words into visual lines (PDF points).
#: Typst places same-line words at identical y0; a small tolerance absorbs
#: sub-pixel rounding in PyMuPDF's coordinate extraction.
_LINE_Y_TOL_PT = 2.0


def _group_lines(words: list[TextWord]) -> Iterator[tuple[float, list[TextWord]]]:
    """Yield ``(y, words)`` pairs — words grouped into visual lines by y0.

    Words whose ``y0`` is within :data:`_LINE_Y_TOL_PT` of an existing line's
    y are appended to that line; otherwise a new line starts. Lines are
    yielded sorted top-to-bottom, words sorted left-to-right within each.
    """
    lines: list[tuple[float, list[TextWord]]] = []
    for w in sorted(words, key=lambda word: word.y0):
        placed = False
        for _y, ws in lines:
            if abs(w.y0 - _y) <= _LINE_Y_TOL_PT:
                ws.append(w)
                placed = True
                break
        if not placed:
            lines.append((w.y0, [w]))
    for y, ws in sorted(lines, key=lambda entry: entry[0]):
        yield y, sorted(ws, key=lambda word: word.x0)


def _extract_toc_entries(page: pymupdf.Page) -> dict[str, str]:
    """Extract ``{chapter_title: folio_str}`` from a TOC page.

    Reconstructs each entry from the word layout: a TOC entry line starts
    with ``"Chapter"`` (the first non-dot word) and ends with a number (the
    folio). Dot-leader words (``"."``) are filtered. The chapter title is
    the join of all non-dot, non-number words on the line.
    """
    entries: dict[str, str] = {}
    for _y, ws in _group_lines(page_words(page)):
        texts = [w.text for w in ws if w.text != "."]
        if not texts:
            continue
        # A TOC entry: first word "Chapter", last word is the folio number.
        if texts[0] == "Chapter" and texts[-1].strip().isdigit():
            title = " ".join(texts[:-1])
            entries[title] = texts[-1]
    return entries


def _body_chapter_folios(doc: pymupdf.Document) -> dict[str, str]:
    """Map each chapter title to its printed folio (from the body footer).

    A chapter-opener page is a body page whose first body line is the
    chapter heading (same classification as the running-heads probe). The
    folio comes from :func:`footer_text` — the same ``phase-folio`` value
    the TOC entry shows, proving the two agree.
    """
    result: dict[str, str] = {}
    for i in range(doc.page_count):
        folio = footer_text(doc[i])
        if not folio:
            continue
        body = body_text(doc[i])
        first_line = body.splitlines()[0].strip() if body else ""
        for title in CHAPTER_TITLES:
            if first_line == title and title not in result:
                result[title] = folio
    return result


def test_toc_present_with_phase_relative_folios(typst_workdir: Path) -> None:
    """Slice 5d invariant: TOC lists chapters with folios matching the footers.

    Renders a title page + frontmatter(TOC) + 3-chapter body and asserts:
    the TOC page lists all three chapters, each with a folio that exactly
    matches the printed footer folio on that chapter's body page.
    """
    doc_path = typst_workdir / "toc.typ"
    pdf_path = typst_workdir / "toc.pdf"
    doc_path.write_text(
        textwrap.dedent(
            f"""\
            #import "{PACKAGE_IMPORT}": narrare-roman, title-page, frontmatter, body, toc

            #show: narrare-roman.with(
              config: (
                paper-size: "b-format-129x198",
                title: "TOC Probe",
                author: "Slice 5d",
                language: "en",
                include-toc: true,
              ),
            )

            #title-page[Title Page]

            #frontmatter[
              #toc()
            ]

            #body[
              = Chapter One

              Chapter one content.

              = Chapter Two

              Chapter two content.

              = Chapter Three

              Chapter three content.
            ]
            """,
        ),
        encoding="utf-8",
    )

    result = compile_typst(doc_path, pdf_path)
    assert result.returncode == 0, (
        f"typst compile failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert pdf_path.exists(), "typst produced no PDF"

    with pymupdf.open(pdf_path) as doc:
        # ── Find the TOC page (the frontmatter page carrying "Contents").
        toc_page = None
        for i in range(doc.page_count):
            if "Contents" in page_text(doc[i]):
                toc_page = doc[i]
                break
        assert toc_page is not None, "no page contains the TOC 'Contents' heading"

        # ── Extract TOC entries and body chapter folios.
        toc_entries = _extract_toc_entries(toc_page)
        body_folios = _body_chapter_folios(doc)

        # ── (1) TOC lists all three chapters.
        assert set(toc_entries) == set(CHAPTER_TITLES), (
            f"TOC entries {set(toc_entries)!r} ≠ expected {set(CHAPTER_TITLES)!r}"
        )

        # ── (2) Body folios found for all three chapters.
        assert set(body_folios) == set(CHAPTER_TITLES), (
            f"body chapter folios found {set(body_folios)!r} ≠ expected {set(CHAPTER_TITLES)!r}"
        )

        # ── (3) Each TOC folio matches the printed footer folio.
        for title in CHAPTER_TITLES:
            toc_folio = toc_entries[title]
            body_folio = body_folios[title]
            assert toc_folio == body_folio, (
                f"TOC folio for {title!r} is {toc_folio!r} but the printed "
                f"footer folio is {body_folio!r} — they must match "
                "(phase-folio is the shared source of truth)"
            )

        # ── (4) The folios are the expected phase-relative sequence.
        # Each short chapter ends on its opener recto, leaving a blank verso
        # before the next recto opener — so folios advance by 2 (1, 3, 5).
        expected = {"Chapter One": "1", "Chapter Two": "3", "Chapter Three": "5"}
        for title, folio in expected.items():
            assert toc_entries[title] == folio, (
                f"TOC folio for {title!r} is {toc_entries[title]!r}, expected {folio!r}"
            )


def test_toc_absent_when_disabled(typst_workdir: Path) -> None:
    """Slice 5d invariant: TOC renders nothing when ``include-toc`` is false.

    The ``_toc-enabled`` gate (published by the entry point) suppresses the
    outline; no page carries the "Contents" heading or the chapter entries.
    """
    doc_path = typst_workdir / "no_toc.typ"
    pdf_path = typst_workdir / "no_toc.pdf"
    doc_path.write_text(
        textwrap.dedent(
            f"""\
            #import "{PACKAGE_IMPORT}": narrare-roman, title-page, frontmatter, body, toc

            #show: narrare-roman.with(
              config: (
                paper-size: "b-format-129x198",
                title: "No TOC Probe",
                language: "en",
                include-toc: false,
              ),
            )

            #title-page[Title Page]

            #frontmatter[
              #toc()
            ]

            #body[
              = Chapter One

              Content.

              = Chapter Two

              Content.
            ]
            """,
        ),
        encoding="utf-8",
    )

    result = compile_typst(doc_path, pdf_path)
    assert result.returncode == 0, (
        f"typst compile failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    with pymupdf.open(pdf_path) as doc:
        for i in range(doc.page_count):
            text = page_text(doc[i])
            # The "Contents" heading is generated ONLY by #toc(). Its
            # absence on every page proves the gate suppressed the outline.
            assert "Contents" not in text, (
                f"page {i + 1} contains 'Contents' — TOC must be absent when include-toc is false"
            )
