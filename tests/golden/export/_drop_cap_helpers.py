"""Probe infrastructure for the Slice 5g drop-cap probe.

Extracted from ``test_drop_cap.py`` for RULE-04 (the probe exceeded the
400-line hard limit once doc-writing, span extraction, and the shared
cap assertions were complete — the limit means split, not compress).

Owns three concerns (one module, cohesive: everything the drop-cap probe
needs beyond the shared Typst helpers):

- **Span geometry** — pymupdf ``dict``-mode extraction WITH font size
  (the shared :class:`~tests.golden.export._typst_probe_helpers.Span`
  TypedDict pins text/font/bbox but not ``size``), body-band filtering,
  chapter-opener page location, and the enlarged-span finder.
- **Deterministic compile** — ``typst compile`` with a pinned
  ``--creation-timestamp 0`` (the production renderer's reproducibility
  flag) so two renders are byte-comparable. Same argv as
  ``_typst_probe_helpers.compile_typ`` otherwise; local so the shared
  helper stays untouched (RULE-06).
- **The shared two-chapter probe fixture + cap assertions** — the body
  prose both probe tests render, and the "exactly one clean cap per
  chapter opener" contract (presence, ≥2x body scale, multi-line span,
  no glyph collision) asserted identically by the package-level and the
  renderer-round-trip tests.

RULE-08: the compile helper spawns the ``typst`` binary from a test
harness — sanctioned per ADR-081 (see
``_typst_probe_helpers.py`` for the rationale).
"""

from __future__ import annotations

import hashlib
import subprocess
import textwrap
from typing import TYPE_CHECKING, TypedDict, cast

from tests.golden.export._typst_probe_helpers import (
    FONT_PATH,
    PACKAGE_IMPORT,
    REPO_ROOT,
    body_text,
    doc_page_count,
)

if TYPE_CHECKING:
    from pathlib import Path

    import pymupdf

#: Body-band y-limits are fixed by the B-format Satzspiegel (the head
#: sits above ~50 pt, the folio below height - 40 pt — same bands as the
#: scene-break probe). The body FONT size is NOT a constant here: it is
#: MEASURED from each rendered page (:func:`body_font_size`) — the
#: probe holds no assumption about narrare-roman's default body size.

#: A span is "enlarged" above 1.8 x the measured body size. The measured
#: drop cap is ≈ 2.34 x and the chapter-heading span ≈ 1.4 x — the
#: threshold separates both with a wide margin on either side.
ENLARGED_FACTOR = 1.8

#: The cap must be at least 2 x the body font (the "2-line drop cap"
#: sizing target; measured ≈ 2.3 x because droplet scales the glyph so
#: its bounds span exactly two body lines INCLUDING leading).
MIN_CAP_FACTOR = 2.0

#: Tolerances (PDF points): bbox comparison slop for PyMuPDF rounding.
X_TOL_PT = 0.5
Y_TOL_PT = 2.0

#: Font-size comparison slop (PDF points) for "is body size".
SIZE_TOL_PT = 0.2

#: The two chapters every drop-cap probe renders. First paragraphs are
#: long enough for the aside column to wrap ≥ 2 lines at the B-format
#: measure (the multi-line-beside-the-cap geometry the ON assertions
#: check); second paragraphs prove the cap applies ONLY to the
#: chapter's first paragraph.
CHAPTER_TITLES = ("Chapter One", "Chapter Two")

_CH1_PAR_1 = (
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod "
    "tempor incididunt ut labore et dolore magna aliqua as the opening prose "
    "of the first chapter, running long enough to wrap several lines beside "
    "the dropped capital and below it in the measured paragraph band."
)
_CH1_PAR_2 = (
    "Second paragraph of chapter one must stay plain body text with every "
    "glyph at the regular body size, starting flush at the left margin."
)
_CH2_PAR_1 = (
    "Duis aute irure dolor in reprehenderit in voluptate velit esse cillum "
    "dolore eu fugiat nulla pariatur on the opening paragraph of the second "
    "chapter, again wrapping multiple lines so the cap geometry is visible "
    "and measurable next to the enlarged first letter of the paragraph."
)
_CH2_PAR_2 = (
    "Second paragraph of chapter two must also remain plain body text and "
    "carry no enlarged glyph anywhere in its lines."
)


# ── Span geometry (dict mode with font size) ───────────────────────────────


class SizedSpan(TypedDict):
    """One non-empty text span from ``Page.get_text("dict")`` (with size).

    All three keys are required: pymupdf populates them for every span,
    and the boundary ``cast`` in :func:`page_spans` asserts that
    documented runtime contract (same philosophy as the shared helpers'
    Span casts).
    """

    text: str
    size: float
    bbox: tuple[float, float, float, float]


def page_spans(page: pymupdf.Page) -> list[SizedSpan]:
    """Non-empty spans on ``page`` across all blocks/lines (with size)."""
    raw = cast("dict[str, list[dict[str, object]]]", page.get_text("dict"))
    spans: list[SizedSpan] = []
    for block in raw.get("blocks", []):
        lines = cast("list[dict[str, object]]", block.get("lines", []))
        for line in lines:
            for span in cast("list[dict[str, object]]", line.get("spans", [])):
                text = str(span.get("text", ""))
                if text.strip():
                    spans.append(cast("SizedSpan", span))
    return spans


def body_band_spans(page: pymupdf.Page) -> list[SizedSpan]:
    """Spans inside the body band (excludes running head + folio footer).

    The B-format Satzspiegel leaves the head above ~50 pt and the footer
    below height - 40 pt (same bands as the scene-break probe).
    """
    top, bottom = 50.0, page.rect.height - 40.0
    return [s for s in page_spans(page) if top < s["bbox"][1] < bottom]


def body_font_size(page: pymupdf.Page) -> float:
    """The page's body font size, MEASURED as the modal span size.

    Body prose dominates every body band, so the most common span size
    IS the body size — no assumption about narrare-roman's default
    (11 pt today) is baked into the probe. Raises if the band has no
    spans (a fixture bug, not a render variance).
    """
    sizes: dict[float, int] = {}
    for span in body_band_spans(page):
        key = round(span["size"], 1)
        sizes[key] = sizes.get(key, 0) + 1
    assert sizes, "body band has no spans — cannot measure body font size"
    return max(sizes, key=lambda size: sizes[size])


def enlarged_spans(page: pymupdf.Page, body_size: float) -> list[SizedSpan]:
    """Body-band spans clearly larger than the body font (the cap(s))."""
    threshold = body_size * ENLARGED_FACTOR
    return [s for s in body_band_spans(page) if s["size"] > threshold]


def find_opener_page(doc: pymupdf.Document, title: str) -> pymupdf.Page | None:
    """The page whose BODY band starts with the chapter ``title``.

    On a chapter opener the running head is suppressed, so the body band
    begins with the heading itself — unambiguous even though body rectos
    repeat the chapter title in the header on later pages.
    """
    for i in range(doc_page_count(doc)):
        page = doc[i]
        if body_text(page).lstrip().startswith(title):
            return page
    return None


# ── Deterministic compile (byte-comparable renders) ────────────────────────


def compile_deterministic(doc_path: Path, pdf_path: Path) -> None:
    """Compile with a pinned ``--creation-timestamp`` (byte-comparable).

    Without the epoch pin Typst embeds the wall clock and two renders
    are never byte-equal; with it, identical sources yield identical
    PDFs (the production renderer's reproducibility flag).
    """
    result = subprocess.run(
        [
            "typst",
            "compile",
            "--root",
            str(REPO_ROOT),
            "--font-path",
            str(FONT_PATH),
            "--creation-timestamp",
            "0",
            str(doc_path),
            str(pdf_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"typst compile failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def sha256_of(path: Path) -> str:
    """File sha256 hex digest."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ── Shared two-chapter probe document ──────────────────────────────────────


def write_probe_doc(
    typst_workdir: Path,
    name: str,
    *,
    drop_caps_line: str,
) -> tuple[Path, Path]:
    """Write the two-chapter probe doc; returns ``(doc_path, pdf_path)``.

    ``drop_caps_line`` is injected verbatim into the config dict (``""``
    omits the key entirely — the default-OFF case).
    """
    doc_path = typst_workdir / f"{name}.typ"
    pdf_path = typst_workdir / f"{name}.pdf"
    doc_path.write_text(
        textwrap.dedent(
            f"""\
            #import "{PACKAGE_IMPORT}": narrare-roman, title-page, body

            #show: narrare-roman.with(
              config: (
                paper-size: "b-format-129x198",
                title: "Drop Cap Probe",
                author: "Slice 5g",
                language: "en",
                include-toc: false,
                {drop_caps_line}
              ),
            )

            #title-page[Title Page]

            #body[
              = {CHAPTER_TITLES[0]}

              {_CH1_PAR_1}

              {_CH1_PAR_2}

              = {CHAPTER_TITLES[1]}

              {_CH2_PAR_1}

              {_CH2_PAR_2}
            ]
            """,
        ),
        encoding="utf-8",
    )
    return doc_path, pdf_path


# ── The "one clean cap per chapter opener" contract ────────────────────────


def assert_single_clean_cap(page: pymupdf.Page, title: str, *, context: str) -> None:
    """Assert ``page`` (a chapter opener) carries exactly one clean cap.

    The shared ON-mode contract, asserted identically by the
    package-level probe and the renderer round-trip:

    - exactly ONE enlarged span (the cap — a second paragraph or heading
      scale-up would fail this),
    - cap scale ≥ 2 x body font (a dropped capital, not an inline tweak),
    - ≥ 2 body-size lines run BESIDE the cap (it spans multiple text
      lines — the defining shape),
    - no glyph collision: nothing starts strictly inside the cap's
      horizontal range and vertically intersects it. (Beside lines start
      at/after the cap's right edge and the below-cap continuation
      starts AT the left margin — both structurally clear per droplet's
      two-column grid; spans at cap scale are the cap itself, compared
      by size because each extraction builds fresh span objects.)
    """
    body_size = body_font_size(page)
    enlarged = enlarged_spans(page, body_size)
    assert len(enlarged) == 1, (
        f"{context}: {title!r} opener shows {len(enlarged)} enlarged spans "
        f"({[(s['text'], s['size']) for s in enlarged]!r}) — expected exactly "
        "one (the chapter-first-paragraph cap; later paragraphs must stay plain)"
    )
    cap = enlarged[0]
    assert cap["size"] >= body_size * MIN_CAP_FACTOR, (
        f"{context}: cap {cap['text']!r} is {cap['size']:.1f} pt — below the "
        f"{MIN_CAP_FACTOR}x body floor ({body_size * MIN_CAP_FACTOR:.1f} pt); "
        "not a drop cap"
    )
    cap_x0, cap_y0, cap_x1, cap_y1 = cap["bbox"]

    beside = [
        s
        for s in body_band_spans(page)
        if abs(s["size"] - body_size) < SIZE_TOL_PT
        and s["bbox"][0] >= cap_x1 - X_TOL_PT
        and s["bbox"][1] >= cap_y0 - Y_TOL_PT
        and s["bbox"][3] <= cap_y1 + Y_TOL_PT
    ]
    beside_lines = {round(s["bbox"][1]) for s in beside}
    assert len(beside_lines) >= 2, (
        f"{context}: cap {cap['text']!r} has {len(beside_lines)} body-size "
        f"lines beside it (need ≥ 2) — it does not span multiple text lines"
    )

    threshold = body_size * ENLARGED_FACTOR
    colliding = [
        s
        for s in body_band_spans(page)
        if s["size"] <= threshold
        and s["bbox"][0] > cap_x0 + X_TOL_PT
        and s["bbox"][0] < cap_x1 - X_TOL_PT
        and min(s["bbox"][3], cap_y1) - max(s["bbox"][1], cap_y0) > Y_TOL_PT
    ]
    assert not colliding, (
        f"{context}: cap {cap['text']!r} collides with neighbouring spans "
        f"{[(s['text'], tuple(round(v, 1) for v in s['bbox'])) for s in colliding]!r} "
        "— the bake-off collision failure mode"
    )
