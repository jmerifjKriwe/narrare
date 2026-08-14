"""PyMuPDF probe library for the Golden-Pages acceptance test (Slice 7).

Eight probes, each an objective metric or invariant check over a rendered PDF.
The first five + ``scene_break_present`` consolidate the logic already proven
in the Slice-5 inline probes (``test_geometric_spine``,
``test_running_heads``, ``test_numbering``, ``test_scene_break``); the four
drift-quality metrics (``byte_reproducibility``, ``right_edge_max_error``,
``word_gap_stdev``, ``text_layer_tounicode``) promote the bake-off PyMuPDF
probes into a committed, baselined gate.

Each probe is a **pure extractor** over an open :class:`pymupdf.Document`: it
returns an objective metric or a structured result. The test
(:mod:`tests.golden.export.test_golden_pages`) asserts the result against a
fixed invariant or a committed baseline value. This separation keeps the probe
logic reusable — the ``--golden-update`` path runs the same extractors to
capture baselines.

Page classification (the shared :class:`~tests.golden.export.harness._pages.PageClass`
+ :func:`~tests.golden.export.harness._pages.classify_pages` foundation that
six of the eight probes build on, plus the ``group_lines`` / ``body_words``
geometry helpers) lives in :mod:`tests.golden.export.harness._pages`, extracted
for RULE-04. It is **language-agnostic**: the corpus is German (the inline
probes keyed on the English word ``"Chapter"``, which would not work here), so
classifications key on the fixture's parsed ``chapter_titles`` (the ``<h2>``
headings) + structural cues (blank pages, the ``Contents`` ToC heading), never
on a language-specific word.

All text extraction goes through the typed boundary accessors in
:mod:`tests.golden.export._typst_probe_helpers`.
"""

from __future__ import annotations

import hashlib
import re
import statistics
from dataclasses import dataclass, field
from itertools import pairwise
from typing import TYPE_CHECKING

from tests.golden.export._typst_probe_helpers import (
    MM_TO_PT,
    doc_page_count,
    page_text,
    page_words,
)
from tests.golden.export.harness._pages import (
    LINE_Y_TOL_PT,
    body_words,
    classify_pages,
    group_lines,
)

if TYPE_CHECKING:
    import pymupdf

#: Minimum words on a line for it to count as a justified body line (word-gap
#: metric). Short lines (paragraph endings, the ornament) are not justified.
_MIN_JUSTIFIED_LINE_WORDS: int = 4

#: Horizontal tolerance (PDF points) for "the scene-break ornament is centred".
#: Mirrors :data:`tests.golden.export.test_scene_break._CENTER_TOL_PT`.
_CENTER_TOL_PT: float = 20.0

#: Maximum shortfall (mm) for a line to count as a "justified" line (vs. a
#: paragraph-ending last line). A justified line ends near the right margin
#: (shortfall < ~5 mm — the expansion gap Typst cannot fill without glyph
#: expansion); a last line ends well short (often 50+ mm). The 15 mm cut
#: cleanly separates the two populations on a B-format sheet (≈95 mm text
#: width) while tolerating font-metric drift. Lines above this cut are
#: excluded from :func:`right_edge_max_error_mm` so the metric measures
#: justification quality, not paragraph-ending raggedness.
_JUSTIFIED_LINE_MAX_SHORTFALL_MM: float = 15.0

#: Minimum gap (PDF points) between ornament and body left margin — the
#: decisive "ornament, not literal body text" check.
_MIN_ORNAMENT_MARGIN_GAP_PT: float = 30.0

#: Lowercase roman-numeral / arabic folio matchers (the printed footer text).
_ROMAN_RE = re.compile(r"^[ivxlcdm]+$")
_ARABIC_RE = re.compile(r"^\d+$")


# ── (1) byte_reproducibility ───────────────────────────────────────────────


def sha256_of_path(path: object) -> str:
    """Hex sha256 digest of the file at ``path`` (the golden anchor).

    The decisive Typst property: two consecutive renders of identical input
    produce byte-identical PDFs. The test renders twice and asserts equality;
    the *absolute* sha256 is also baselined so a rendering change surfaces as
    drift (not just a reproducibility break).
    """
    import pathlib

    return hashlib.sha256(pathlib.Path(str(path)).read_bytes()).hexdigest()


# ── (2) text_layer_tounicode ───────────────────────────────────────────────


def extract_full_text(doc: pymupdf.Document) -> str:
    """Concatenate every page's text layer (the ToUnicode extraction path).

    PyMuPDF ``get_text("text")`` decodes glyphs via the PDF ToUnicode CMap. A
    correct CMap yields the original codepoints; a broken one (the SILE
    failure the bake-off disqualified) yields garbled text. The test asserts
    each fixture's ``tounicode_words`` appear verbatim — a ToUnicode regression
    surfaces as a missing substring.
    """
    return "\n".join(page_text(doc[i]) for i in range(doc_page_count(doc)))


def tounicode_missing_words(doc: pymupdf.Document, expected_words: tuple[str, ...]) -> list[str]:
    """Words from ``expected_words`` NOT found verbatim in the text layer.

    Empty = pass; non-empty = ToUnicode regression.
    """
    full_text = extract_full_text(doc)
    return [w for w in expected_words if w not in full_text]


# ── (3) folio_numbering ────────────────────────────────────────────────────


@dataclass(frozen=True)
class FolioNumbering:
    """4-phase folio result. The test asserts every property holds."""

    title_page_suppressed: bool  # title page carries no folio
    frontmatter_all_roman: bool  # every frontmatter folio is lowercase roman
    body_all_arabic: bool  # every body folio is arabic
    body_starts_at_one: bool  # first body folio is "1" (counter resets)
    has_frontmatter: bool  # at least one frontmatter page exists
    has_body: bool  # at least one body page exists


def extract_folio_numbering(
    doc: pymupdf.Document, chapter_titles: tuple[str, ...]
) -> FolioNumbering:
    """Classify pages by phase (via :func:`classify_pages`) and check folios.

    Frontmatter pages (``"frontmatter"`` role) carry roman folios; body pages
    (``"opener"`` + ``"body"`` roles) carry arabic folios. Blank pages are
    skipped (their folio is suppressed and they are not counted in either
    phase).
    """
    classes = classify_pages(doc, chapter_titles)
    title_suppressed = classes[0].folio == "" if classes else True

    frontmatter_folios = [c.folio for c in classes if c.role == "frontmatter" and c.folio]
    body_folios = [c.folio for c in classes if c.role in ("opener", "body") and c.folio]

    return FolioNumbering(
        title_page_suppressed=title_suppressed,
        frontmatter_all_roman=bool(frontmatter_folios)
        and all(_ROMAN_RE.match(f) is not None for f in frontmatter_folios),
        body_all_arabic=bool(body_folios)
        and all(_ARABIC_RE.match(f) is not None for f in body_folios),
        body_starts_at_one=bool(body_folios) and body_folios[0] == "1",
        has_frontmatter=bool(frontmatter_folios),
        has_body=bool(body_folios),
    )


# ── (4) running_header ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class RunningHeaders:
    """Running-head result. Properties are conditional (see each docstring)."""

    body_recto_heads: frozenset[str] = field(default_factory=frozenset[str])
    body_verso_heads: frozenset[str] = field(default_factory=frozenset[str])
    opener_heads: frozenset[str] = field(default_factory=frozenset[str])
    blank_heads: frozenset[str] = field(default_factory=frozenset[str])
    has_body_recto: bool = False
    has_body_verso: bool = False
    has_opener: bool = False
    has_blank: bool = False

    @property
    def present_on_body_recto(self) -> bool:
        """Every body-recto page (non-opener) carries a head."""
        return self.has_body_recto and "" not in self.body_recto_heads

    @property
    def present_on_body_verso(self) -> bool:
        """Every body-verso page (non-opener) carries a head."""
        return self.has_body_verso and "" not in self.body_verso_heads

    @property
    def recto_neq_verso(self) -> bool:
        """Recto heads (chapter titles) differ from verso heads (book title)."""
        return bool(self.body_recto_heads) and self.body_recto_heads.isdisjoint(
            self.body_verso_heads
        )

    @property
    def absent_on_openers(self) -> bool:
        """Every chapter opener carries no head."""
        return not self.has_opener or all(h == "" for h in self.opener_heads)

    @property
    def absent_on_blanks(self) -> bool:
        """Every blank page carries no head."""
        return not self.has_blank or all(h == "" for h in self.blank_heads)


def extract_running_headers(
    doc: pymupdf.Document, chapter_titles: tuple[str, ...]
) -> RunningHeaders:
    """Classify pages by role and collect running heads (via classify_pages)."""
    classes = classify_pages(doc, chapter_titles)
    body_recto: set[str] = set()
    body_verso: set[str] = set()
    opener_heads: set[str] = set()
    blank_heads: set[str] = set()
    has_body_recto = has_body_verso = has_opener = has_blank = False

    for c in classes:
        if c.role in ("title", "frontmatter"):
            continue  # running-head probe covers body pages only
        parity = "recto" if c.physical_page % 2 == 1 else "verso"
        if c.role == "blank":
            has_blank = True
            blank_heads.add(c.head)
        elif c.role == "opener":
            has_opener = True
            opener_heads.add(c.head)
        elif parity == "recto":
            has_body_recto = True
            body_recto.add(c.head)
        else:
            has_body_verso = True
            body_verso.add(c.head)

    return RunningHeaders(
        body_recto_heads=frozenset(body_recto),
        body_verso_heads=frozenset(body_verso),
        opener_heads=frozenset(opener_heads),
        blank_heads=frozenset(blank_heads),
        has_body_recto=has_body_recto,
        has_body_verso=has_body_verso,
        has_opener=has_opener,
        has_blank=has_blank,
    )


# ── (5) recto_start ────────────────────────────────────────────────────────


def find_chapter_opener_pages(doc: pymupdf.Document, chapter_titles: tuple[str, ...]) -> list[int]:
    """Physical page numbers (1-based) where each chapter opener lands.

    The recto_start probe asserts every such page is odd (recto).
    """
    return [c.physical_page for c in classify_pages(doc, chapter_titles) if c.role == "opener"]


# ── (6) right_edge_max_error (drift metric) ────────────────────────────────


def right_edge_max_error_mm(doc: pymupdf.Document) -> float:
    """Worst right-edge shortfall of JUSTIFIED lines from the right margin (mm).

    Per page, the reference right edge is that page's fullest line (≈ the
    justified right margin). A line counts as "justified" when its shortfall
    from the reference is below
    :data:`_JUSTIFIED_LINE_MAX_SHORTFALL_MM` — this EXCLUDES
    paragraph-ending last lines (which always end far short) so the metric
    measures justification quality, not paragraph raggedness. The metric is
    the max shortfall among the justified lines across all pages.

    Typst has no glyph expansion: justified lines can end a few mm short of
    the margin (the gap the line-breaker could not fill by stretching spaces
    alone). That residual is the drift signal — a narrare-roman / Typst
    change to justification or hyphenation shifts it. **Per-page** measurement
    is robust to the mirrored Satzspiegel (recto/verso have different right
    margins). Baseline it and assert ``actual <= baseline``.

    Flagged as a hard-to-assert metric (see test docstring): the 15 mm
    justified-line cut is an empirically calibrated threshold, not a derived
    constant. If a future font/paper change narrows the justified/last-line
    gap, recalibrate :data:`_JUSTIFIED_LINE_MAX_SHORTFALL_MM`.
    """
    cut_pt = _JUSTIFIED_LINE_MAX_SHORTFALL_MM * MM_TO_PT
    max_error_pt = 0.0
    for i in range(doc_page_count(doc)):
        lines = list(group_lines(body_words(doc[i])))
        if not lines:
            continue
        line_rights = [max(w.x1 for w in ws) for _, ws in lines]
        page_fullest = max(line_rights)
        for right_edge in line_rights:
            shortfall = page_fullest - right_edge
            # Only measure justified lines (shortfall below the cut). Last
            # lines (shortfall above the cut) are excluded.
            if shortfall <= cut_pt:
                max_error_pt = max(max_error_pt, shortfall)
    return max_error_pt / MM_TO_PT


# ── (7) word_gap_stdev (drift metric) ──────────────────────────────────────


def word_gap_stdev_pt(doc: pymupdf.Document) -> float:
    """Population stdev of inter-word horizontal gaps in justified body lines.

    For each justified line (≥ :data:`_MIN_JUSTIFIED_LINE_WORDS` words), gaps
    between consecutive words are collected; the population stdev measures
    grey-value (whitespace) uniformity. Short lines are excluded (not
    justified). Like :func:`right_edge_max_error_mm` the absolute value is a
    fingerprint of the current font + justification engine; drift shifts it.
    """
    gaps: list[float] = []
    for i in range(doc_page_count(doc)):
        for _, ws in group_lines(body_words(doc[i])):
            if len(ws) < _MIN_JUSTIFIED_LINE_WORDS:
                continue
            ordered = sorted(ws, key=lambda w: w.x0)
            for a, b in pairwise(ordered):
                gaps.append(b.x0 - a.x1)
    if len(gaps) < 2:
        return 0.0
    return statistics.pstdev(gaps)


# ── (8) scene_break_present ────────────────────────────────────────────────


@dataclass(frozen=True)
class SceneBreakInfo:
    """Scene-break ornament result. ``found`` is the pass/fail flag."""

    found: bool
    page_index: int
    n_stars: int
    centered: bool
    clears_margin: bool


def find_scene_break(doc: pymupdf.Document) -> SceneBreakInfo | None:
    """Locate the asterism and verify its spatial signature.

    ``None`` when no page carries ``*`` glyphs. Otherwise the verification:
    exactly three glyphs, one visual line, centred on the page, and clearing
    the body left margin (an ornament, not a literal ``* * *`` paragraph).
    """
    for i in range(doc_page_count(doc)):
        page = doc[i]
        stars = [w for w in page_words(page) if w.text == "*"]
        if not stars:
            continue
        n_stars = len(stars)
        same_line = max(w.y0 for w in stars) - min(w.y0 for w in stars) <= LINE_Y_TOL_PT
        orn_left = min(w.x0 for w in stars)
        orn_right = max(w.x1 for w in stars)
        orn_center = (orn_left + orn_right) / 2.0
        centered = abs(orn_center - page.rect.width / 2.0) <= _CENTER_TOL_PT
        non_star_words = [w for w in body_words(page) if w.text != "*"]
        body_left = min((w.x0 for w in non_star_words), default=orn_left)
        clears_margin = orn_left - body_left >= _MIN_ORNAMENT_MARGIN_GAP_PT
        return SceneBreakInfo(
            found=(n_stars == 3 and same_line and centered and clears_margin),
            page_index=i,
            n_stars=n_stars,
            centered=centered and same_line,
            clears_margin=clears_margin,
        )
    return None
