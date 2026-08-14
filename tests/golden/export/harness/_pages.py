"""Shared page-classification layer for the Golden-Pages probes (Slice 7).

Extracted from :mod:`tests.golden.export.harness.probes` for RULE-04 — the
8 probes share a common foundation (classifying every page by role + grouping
words into visual lines), and that foundation is a cohesive responsibility in
its own right. Keeping it here lets ``probes.py`` own only the probe functions
+ their result dataclasses, each of which builds on this classification.

``PageClass`` + :func:`classify_pages` are language-agnostic: the corpus is
German (the Slice-5 inline probes keyed on the English word ``"Chapter"``,
which would not work here), so classifications key on the fixture's parsed
``chapter_titles`` (the ``<h2>`` headings) + structural cues (blank pages),
never on a language-specific word.

All text extraction goes through the typed boundary accessors in
:mod:`tests.golden.export._typst_probe_helpers`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from tests.golden.export._typst_probe_helpers import (
    TextWord,
    body_text,
    doc_page_count,
    footer_text,
    header_text,
    page_text,
    page_words,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    import pymupdf

#: Vertical tolerance (PDF points) for grouping words into one visual line.
#: Typst places same-line words at identical ``y0``; a small tolerance absorbs
#: sub-pixel rounding. Mirrors the value in the Slice-5 inline probes. Public
#: (no underscore): consumed by ``probes.find_scene_break`` across the module
#: boundary, so pyright's reportPrivateUsage requires a non-private name.
LINE_Y_TOL_PT: float = 2.0

#: Body-text band exclusion (PDF points). Words above ``_BODY_TOP_PT`` are in
#: the running-head band; words below ``page_height - _BODY_BOTTOM_PT`` are in
#: the folio-footer band. Both are furniture, excluded from geometric metrics.
_BODY_TOP_PT: float = 50.0
_BODY_BOTTOM_PT: float = 40.0


@dataclass(frozen=True)
class PageClass:
    """One classified page: its physical number, role, head, folio, body text.

    ``role`` is ``"title"`` (page 1), ``"frontmatter"`` (text page before the
    first chapter opener — the ToC / copyright), ``"blank"`` (no text),
    ``"opener"`` (first body line is a chapter heading), or ``"body"`` (other
    text page at/after the first opener). The frontmatter/body split is
    essential: the running-head probe covers body pages only, and a recto
    frontmatter page legitimately carries NO head (no chapter exists yet).
    Shared by the folio-numbering, running-header, and recto-start probes so
    the three never disagree about what a page IS.
    """

    physical_page: int  # 1-based
    role: str  # "title" | "frontmatter" | "blank" | "opener" | "body"
    head: str  # running-head text ("" when suppressed)
    folio: str  # footer folio text ("" when suppressed)
    body_first_line: str  # first body line ("" when no body text)


def classify_pages(doc: pymupdf.Document, chapter_titles: tuple[str, ...]) -> list[PageClass]:
    """Classify every page by role (language-agnostic — keys on chapter titles).

    Two passes: (1) find the first chapter-opener page (the body-phase
    boundary — the first page after the title whose first body line is a
    chapter heading); (2) classify each page. Pages between the title and the
    first opener are ``frontmatter``; pages at/after the first opener are
    ``opener`` (heading page) or ``body`` (continuation).
    """
    # ── Pre-pass: locate the body-phase boundary (first chapter opener).
    first_opener: int | None = None
    for i in range(1, doc_page_count(doc)):  # skip title (physical page 1)
        whole = page_text(doc[i])
        if not whole.strip():
            continue
        first_line = next(
            (ln.strip() for ln in body_text(doc[i]).splitlines() if ln.strip()),
            "",
        )
        if first_line in chapter_titles:
            first_opener = i + 1  # physical page
            break

    # ── Main pass: classify every page.
    classes: list[PageClass] = []
    for i in range(doc_page_count(doc)):
        physical = i + 1
        whole = page_text(doc[i])
        head = header_text(doc[i])
        folio = footer_text(doc[i])
        first_line = next(
            (ln.strip() for ln in body_text(doc[i]).splitlines() if ln.strip()),
            "",
        )
        if physical == 1:
            role = "title"
        elif not whole.strip():
            role = "blank"
        elif first_opener is not None and physical >= first_opener:
            role = "opener" if first_line in chapter_titles else "body"
        else:
            role = "frontmatter"
        classes.append(
            PageClass(
                physical_page=physical,
                role=role,
                head=head,
                folio=folio,
                body_first_line=first_line,
            )
        )
    return classes


def group_lines(
    words: list[TextWord],
) -> Iterator[tuple[float, list[TextWord]]]:
    """Yield ``(y, words)`` pairs — words grouped into visual lines by ``y0``.

    Centralised here from the duplicated copies in the Slice-5 inline probes.
    Public (no leading underscore) because the geometric probes in
    :mod:`probes` consume it.
    """
    lines: list[tuple[float, list[TextWord]]] = []
    for w in sorted(words, key=lambda word: word.y0):
        placed = False
        for _y, ws in lines:
            if abs(w.y0 - _y) <= LINE_Y_TOL_PT:
                ws.append(w)
                placed = True
                break
        if not placed:
            lines.append((w.y0, [w]))
    for y, ws in sorted(lines, key=lambda entry: entry[0]):
        yield y, sorted(ws, key=lambda word: word.x0)


def body_words(page: pymupdf.Page) -> list[TextWord]:
    """Words inside the body band (excludes running-head + folio bands)."""
    return [w for w in page_words(page) if _BODY_TOP_PT < w.y0 < page.rect.height - _BODY_BOTTOM_PT]
