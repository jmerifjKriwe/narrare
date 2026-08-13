"""Infrastructure for the narrare-roman Typst probe tests.

Shared by the Slice 5 inline probes (``test_geometric_spine.py`` and the
later sub-slice probes 5b through 5f) and a precursor to the Slice 7 Golden-Pages
harness (``tests/golden/export/harness/``), which will promote + harden
these helpers. Extracted from ``test_geometric_spine.py`` for RULE-04
compliance (the geometric-spine probe reached the 400-line default limit
once its pymupdf boundary types + helpers were added).

Contents:

- Compile helper — wraps ``typst compile`` with the ``--root`` / ``--font-path``
  flags every probe needs (the in-repo package + bundled Libertinus Serif).
- pymupdf boundary types + accessors — the bundled pymupdf stub leaves
  ``Page.get_text`` untyped, so the dict-of-dicts extraction shape is pinned
  with TypedDicts + boundary casts (documented runtime contract, not an
  assumption).
- Shared path / conversion constants.

RULE-08 note (resolved)
-----------------------
``compile_typst`` invokes the ``typst`` binary via ``subprocess.run``. Per
ADR-081 this is a sanctioned test-harness invocation (mirrors the Slice-4
EPUBCheck pattern) and is **deliberately outside RULE-08 confinement scope** —
only the two *production* render binaries are confined, and a test probe is
not production. The RULE-08 AST checker
(``scripts/architecture/_checkers/export_binary_confinement.py``) exempts any
file under a ``tests/`` root via its ``_TEST_ROOTS`` early-return — test /
validation harnesses that spawn the binary to verify rendered output are
legitimate consumers, not drift away from the adapter seam. See commit
``refactor(arch): exempt test paths from RULE-08 render-binary confinement``
for the rationale; this file is therefore not flagged.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict, cast

if TYPE_CHECKING:
    # pymupdf is referenced only in annotations (under future annotations
    # those are stringized), so it lives in the TYPE_CHECKING block.
    import pymupdf

#: Project root (this file lives at tests/golden/export/_typst_probe_helpers.py).
REPO_ROOT = Path(__file__).resolve().parents[3]

#: The vendored narrare-roman package directory.
PACKAGE_DIR = REPO_ROOT / "apps" / "api" / "narrare" / "export" / "typst"

#: Bundled Libertinus Serif fonts — passed via ``--font-path`` so the OFL
#: files under D3 are the ones Typst uses, never an embedded or system
#: fallback (no silent font fallback, ADR-081 / D3).
FONT_PATH = PACKAGE_DIR / "fonts"

#: Millimetres -> PDF points (1 in = 25.4 mm = 72 pt).
MM_TO_PT = 72.0 / 25.4

#: Tolerance for paper-size comparison (Typst rounds to ~0.01 pt).
SIZE_TOL_PT = 0.5

#: Root-relative import path of the package's entry point. Written into
#: every probe doc verbatim (leading ``/`` -> resolved against ``--root``).
PACKAGE_IMPORT = "/apps/api/narrare/export/typst/lib.typ"


# ── pymupdf text-extraction shape ─────────────────────────────────────────
# pymupdf's bundled stub does not express the nested dict-of-dicts returned
# by ``Page.get_text("dict")``; under pyright each level descends to
# Unknown / ``str`` (the stub picks the ``str`` return overload). These
# TypedDicts pin the documented structure the probes rely on, and the
# boundary casts below assert that runtime contract. The shape is a stable
# pymupdf API (text extraction "dict" mode), not an assumption.


class Span(TypedDict, total=False):
    """One text span as returned by ``Page.get_text("dict")``."""

    text: str
    font: str
    bbox: tuple[float, float, float, float]


class _Line(TypedDict, total=False):
    """One line of spans inside a block."""

    spans: list[Span]


class _Block(TypedDict, total=False):
    """One text/image block on a page (image blocks carry no ``lines``)."""

    lines: list[_Line]


class _PageText(TypedDict, total=False):
    """Top-level dict returned by ``Page.get_text("dict")``."""

    blocks: list[_Block]


# ── Compile ───────────────────────────────────────────────────────────────


def is_typst_available() -> bool:
    """True when the ``typst`` binary is on PATH (probe skip-guard)."""
    return shutil.which("typst") is not None


def compile_typst(doc_path: Path, pdf_path: Path) -> subprocess.CompletedProcess[str]:
    """Compile a Typst document to PDF.

    ``--root`` is the repo root (so the package import path resolves);
    ``--font-path`` points at the bundled Libertinus Serif so Typst uses the
    OFL files rather than any embedded or system fallback.
    """
    # typst binary on PATH, fixed argv — no shell, no untrusted input.
    return subprocess.run(
        [
            "typst",
            "compile",
            "--root",
            str(REPO_ROOT),
            "--font-path",
            str(FONT_PATH),
            str(doc_path),
            str(pdf_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


# ── pymupdf accessors (typed boundary over the untyped stub) ──────────────


def page_text(page: pymupdf.Page) -> str:
    """The page's text as a single string (pymupdf "text" extraction mode).

    Cast asserts the documented return shape — ``Page.get_text`` is left
    untyped in the bundled stub (``*args, **kwargs``, no annotation), so
    without the cast the call widens to a ``str | list | dict`` union.
    """
    return cast("str", page.get_text("text"))


def page_spans(page: pymupdf.Page) -> list[Span]:
    """Flat list of non-empty text spans on ``page`` (across all blocks/lines).

    The boundary ``cast`` asserts pymupdf's documented "dict" extraction
    shape (see the TypedDicts above) — the bundled stub does not express it,
    so without the cast each nesting level collapses to ``str``/Unknown.
    """
    raw = cast("_PageText", page.get_text("dict"))
    spans: list[Span] = []
    for block in raw.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                if span.get("text", "").strip():
                    spans.append(span)
    return spans


def page_fonts(page: pymupdf.Page) -> set[str]:
    """Set of font PostScript names used by non-empty text spans on ``page``."""
    return {span["font"] for span in page_spans(page) if "font" in span}


def header_text(page: pymupdf.Page, top_margin_mm: float = 22.0) -> str:
    """Text rendered in the running-head band at the top of ``page``.

    The running head lives inside the top margin; body text starts at the
    top margin. Spans whose top edge sits clearly below the body origin
    (``y0 < 0.85 * top_margin``) are the head — a band with a comfortable
    gap to the first body line (measured head bottom ≈ 46 pt vs. body
    start ≈ 62 pt at the 22 mm B-format default). Returns the joined,
    whitespace-normalised head text (``""`` when the head is suppressed —
    openers and blank versos).

    ``top_margin_mm`` defaults to the B-format Satzspiegel (22 mm); pass
    the effective top margin when a fixture overrides it.
    """
    threshold_pt = 0.85 * top_margin_mm * MM_TO_PT
    parts: list[str] = []
    for span in page_spans(page):
        bbox = span.get("bbox")
        if bbox is not None and bbox[1] < threshold_pt:
            parts.append(span.get("text", ""))
    return " ".join(p for p in (s.strip() for s in parts) if p)


def body_text(page: pymupdf.Page, top_margin_mm: float = 22.0) -> str:
    """Text rendered below the running-head band (the page body).

    Symmetric counterpart to :func:`header_text`: spans at or beyond the
    top-margin origin (``y0 >= 0.85 * top_margin``). Use this — not
    :func:`page_text` — when classifying a page by its *body* content
    (opener heading vs. flowing prose), so a head that repeats the
    chapter title on a body recto is not mistaken for an opener heading.
    """
    threshold_pt = 0.85 * top_margin_mm * MM_TO_PT
    lines: list[str] = []
    for span in page_spans(page):
        bbox = span.get("bbox")
        if bbox is not None and bbox[1] >= threshold_pt:
            text = span.get("text", "").strip()
            if text:
                lines.append(text)
    return "\n".join(lines)


def footer_text(page: pymupdf.Page, bottom_margin_mm: float = 22.0) -> str:
    """Text rendered in the folio band at the bottom of ``page``.

    The folio (page number, Slice 5c) lives inside the bottom margin;
    body text ends at the bottom-margin origin. Spans whose top edge
    sits at or beyond that origin (``y0 >= page_height - bottom_margin``)
    are the footer. Returns the joined, whitespace-normalised footer
    text (``""`` when the folio is suppressed — title page, blank
    pages, or any page before the first phase marker).

    ``bottom_margin_mm`` defaults to the B-format Satzspiegel (22 mm);
    pass the effective bottom margin when a fixture overrides it.
    """
    bottom_start_pt = page.rect.height - bottom_margin_mm * MM_TO_PT
    parts: list[str] = []
    for span in page_spans(page):
        bbox = span.get("bbox")
        if bbox is not None and bbox[1] >= bottom_start_pt:
            parts.append(span.get("text", ""))
    return " ".join(p for p in (s.strip() for s in parts) if p)


def text_bbox_mm(page: pymupdf.Page) -> tuple[float, float] | None:
    """Return ``(left_gap_mm, right_gap_mm)`` of the text block on ``page``.

    ``None`` when the page has no extractable text (a blank verso).
    """
    bboxes = [span["bbox"] for span in page_spans(page) if "bbox" in span]
    if not bboxes:
        return None
    x0 = min(b[0] for b in bboxes)
    x1 = max(b[2] for b in bboxes)
    return x0 / MM_TO_PT, (page.rect.width - x1) / MM_TO_PT
