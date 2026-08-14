"""Golden-Pages probe for Slice 5f — scene-break ornament + widow/orphan.

Renders manuscripts with the bundled ``narrare-roman`` Typst package and
asserts the two body-feature invariants of ADR-081 / IO-001 Slice 5f:

1. **Scene-break-presence** — a scene break renders as a centred, spaced
   typographic ornament, NOT as a literal left-aligned ``* * *`` paragraph.
   The normaliser (Slice 1) canonicalises scene breaks to ``<hr>``; pandoc
   maps ``<hr>`` to ``#divider()`` (a Typst 0.15 built-in element —
   empirically confirmed with pandoc 3.10.1). narrare-roman restyles that
   construct via ``#show divider`` (``src/scene_break.typ``) into the
   centred spaced ``* * *`` asterism (the ``folklore`` ``major-break``
   pattern). The probe reconstructs the ornament from the word-level
   spatial layout (PyMuPDF "words") and asserts the three ``*`` glyphs are
   grouped on one line, centred on the page, and set well clear of the
   left text margin — the spatial signature that distinguishes an ornament
   from a literal asterisk paragraph.

2. **Widow / orphan protection** — Typst 0.15 prevents widows and orphans
   automatically through its optimised line breaker; the on/off switch is
   ``text(costs: ...)`` (the pre-0.15 ``par(orphan-limit/widow-limit)``
   API no longer exists — see ``src/body.typ``). The probe renders the
   SAME body with ``widow-orphan-protection`` on and off and asserts the
   two layouts DIFFER: with protection on, the engine pulls an extra line
   forward onto the overflow page to avoid stranding a widow (the overflow
   page gains a line). This is the load-bearing, drift-robust signal — it
   passes while protection engages and fails (on == off) the moment it
   stops, which is exactly the regression signal the probe exists to
   catch. The body content is calibrated (B-format, 11pt Libertinus Serif,
   leading ratio 1.2) so the target paragraph spans the page-3 → page-4
   boundary; see ``_WIDOW_FILLER`` for the calibration note.

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
    compile_typst,
    doc_page_count,
    is_typst_available,
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

#: Vertical tolerance for grouping words into one visual line (PDF points).
#: Typst places same-line words at identical y0; a small tolerance absorbs
#: sub-pixel rounding in PyMuPDF's coordinate extraction.
_LINE_Y_TOL_PT = 2.0

#: Horizontal tolerance for "centred on the page". The ornament's group
#: centre sits within ~5 pt of the page centre (probe-verified); 20 pt is
#: generous against font-metric drift while still rejecting a left-aligned
#: literal ``* * *`` paragraph (whose centre would be ~70 pt off-centre).
_CENTER_TOL_PT = 20.0

#: Minimum gap (PDF points) between the ornament's left edge and the body
#: text's left margin. A centred ornament sits ~120 pt clear of the margin;
#: a literal left-aligned ``* * *`` paragraph sits AT the margin (gap ≈ 0).
#: 30 pt is comfortably above zero yet far below the real ornament's gap.
_MIN_ORNAMENT_MARGIN_GAP_PT = 30.0

#: Y-band exclusion for the running-head (top) and folio-footer (bottom)
#: when counting body lines — words above ``_BODY_TOP_PT`` or below
#: ``page_height - _BODY_BOTTOM_PT`` are furniture, not body text.
_BODY_TOP_PT = 50.0
_BODY_BOTTOM_PT = 40.0


def _group_lines(
    words: list[TextWord],
) -> Iterator[tuple[float, list[TextWord]]]:
    """Yield ``(y, words)`` pairs — words grouped into visual lines by y0.

    Words whose ``y0`` is within :data:`_LINE_Y_TOL_PT` of an existing
    line's y are appended to that line; otherwise a new line starts. Lines
    are yielded sorted top-to-bottom, words sorted left-to-right within
    each. (Shared shape with ``test_toc._group_lines``; duplicated rather
    than imported to keep each sub-slice probe self-contained per RULE-06.)
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


def test_scene_break_renders_centered_ornament(typst_workdir: Path) -> None:
    """Slice 5f invariant: a scene break renders as a centred ornament.

    Renders a body with two scenes separated by ``#divider()`` (the Typst
    construct pandoc emits for ``<hr>``) and asserts the ornament's spatial
    signature: three ``*`` glyphs on ONE visual line, centred on the page,
    and set well clear of the body's left text margin — i.e. an ornament,
    not a literal left-aligned ``* * *`` paragraph.
    """
    doc_path = typst_workdir / "scene_break.typ"
    pdf_path = typst_workdir / "scene_break.pdf"
    doc_path.write_text(
        textwrap.dedent(
            f"""\
            #import "{PACKAGE_IMPORT}": narrare-roman, title-page, body

            #show: narrare-roman.with(
              config: (
                paper-size: "b-format-129x198",
                title: "Scene Break Probe",
                author: "Slice 5f",
                language: "en",
                scene-break-style: "asterism",
              ),
            )

            #title-page[Title Page]

            #body[
              = Chapter One

              First scene content here, a short paragraph before the break.

              #divider()

              Second scene content after the ornament, a short paragraph.
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
        # ── Locate the ornament: the page carrying the three `*` glyphs.
        ornament_page: pymupdf.Page | None = None
        ornament_words: list[TextWord] = []
        for i in range(doc_page_count(doc)):
            page = doc[i]
            stars = [w for w in page_words(page) if w.text == "*"]
            if stars:
                ornament_page = page
                ornament_words = stars
                break
        assert ornament_page is not None, (
            "no page contains the scene-break ornament (no `*` glyphs found) — "
            "the `show divider` rule did not render the asterism"
        )

        page_w = ornament_page.rect.width
        page_center = page_w / 2.0

        # (1) Exactly three asterisks (the asterism `* * *`).
        assert len(ornament_words) == 3, (
            f"expected the 3-glyph asterism, found {len(ornament_words)} `*` words: "
            f"{[w.text for w in ornament_words]!r}"
        )

        # (2) All three glyphs share one visual line (same y0).
        star_ys = [w.y0 for w in ornament_words]
        assert max(star_ys) - min(star_ys) <= _LINE_Y_TOL_PT, (
            f"ornament glyphs are not on one line — y0 values {star_ys!r} span "
            f"{max(star_ys) - min(star_ys):.1f} pt (> {_LINE_Y_TOL_PT} pt tol)"
        )

        # (3) Centred: the ornament group's horizontal midpoint ≈ page centre.
        orn_left = min(w.x0 for w in ornament_words)
        orn_right = max(w.x1 for w in ornament_words)
        orn_center = (orn_left + orn_right) / 2.0
        assert abs(orn_center - page_center) <= _CENTER_TOL_PT, (
            f"ornament centre {orn_center:.1f} pt is > {_CENTER_TOL_PT} pt off the "
            f"page centre {page_center:.1f} pt — the ornament is not centred"
        )

        # (4) NOT a literal paragraph: the ornament starts well right of the
        # body text's left margin. A left-aligned `* * *` paragraph would
        # begin at the margin (gap ≈ 0); the centred ornament clears it by
        # ~120 pt. This is the decisive "ornament, not body text" check.
        body_words = [
            w
            for w in page_words(ornament_page)
            if w.text != "*" and _BODY_TOP_PT < w.y0 < ornament_page.rect.height - _BODY_BOTTOM_PT
        ]
        assert body_words, "no body words found on the ornament page to compare against"
        body_left = min(w.x0 for w in body_words)
        assert orn_left - body_left >= _MIN_ORNAMENT_MARGIN_GAP_PT, (
            f"ornament left edge {orn_left:.1f} pt is only {orn_left - body_left:.1f} pt "
            f"right of the body left margin {body_left:.1f} pt (need ≥ "
            f"{_MIN_ORNAMENT_MARGIN_GAP_PT} pt) — the ornament is left-aligned like a "
            "literal paragraph, not centred"
        )


# ── Widow / orphan protection ─────────────────────────────────────────────
#
# The body is calibrated so the target paragraph spans the page-3 → page-4
# boundary on a B-format sheet at 11 pt Libertinus Serif / leading 1.2. The
# filler is 8 repeats of ``_WIDOW_FILLER_UNIT`` (each ~5 body lines): that
# fills page 3 (≈46 body lines) almost completely, so the target paragraph
# begins near the bottom of page 3 and spills its tail onto page 4. With
# protection OFF, exactly that tail strands; with protection ON, the engine
# pulls one extra line forward onto page 4 to avoid the strand. The exact
# line counts (OFF p4 = 2, ON p4 = 3 at the time of writing) are NOT what
# the assertion pins — it pins the DIRECTIONAL difference (ON > OFF), which
# holds across a comfortable tolerance band and fails the instant protection
# stops engaging (on == off). If a future Typst/font bump pushes the
# construction out of the spanning window (on == off with no spill at all),
# the filler repeat count is the single calibration knob to adjust.
_WIDOW_FILLER_UNIT = (
    "This is repeated filler prose designed to occupy a full body page of the "
    "manuscript so that the target paragraph which follows is forced to begin "
    "near the bottom of the page and then spill across the page boundary onto "
    "the next sheet in a deterministic and reproducible way. "
)

#: Number of filler-unit repeats that place the target paragraph's tail at
#: the page-3 → page-4 boundary (see the calibration note above).
_WIDOW_FILLER_REPEATS = 8

#: The target paragraph — its final line is the would-be widow. Long enough
#: to be unambiguously multi-line and to span the boundary once started.
_WIDOW_TARGET = (
    "Now this is the target paragraph. It carries several lines of running prose "
    "and we want its final line to land alone atop the next page when there is no "
    "widow protection active, with enough additional words to make it clearly "
    "multi-line so that it will spill across the page break without question. "
    "The quick brown fox jumps over the dog today repeatedly without any end."
)


def _render_widow_doc(
    typst_workdir: Path, name: str, widow_orphan_protection: bool
) -> pymupdf.Document:
    """Compile the calibrated widow fixture with the given protection flag.

    Returns an open :class:`pymupdf.Document`; the caller closes it.
    """
    doc_path = typst_workdir / f"{name}.typ"
    pdf_path = typst_workdir / f"{name}.pdf"
    filler = _WIDOW_FILLER_UNIT * _WIDOW_FILLER_REPEATS
    doc_path.write_text(
        textwrap.dedent(
            f"""\
            #import "{PACKAGE_IMPORT}": narrare-roman, title-page, body

            #show: narrare-roman.with(
              config: (
                paper-size: "b-format-129x198",
                title: "Widow Probe",
                author: "Slice 5f",
                language: "en",
                include-toc: false,
                widow-orphan-protection: {str(widow_orphan_protection).lower()},
              ),
            )

            #title-page[Title Page]

            #body[
              = Chapter One

              {filler}

              {_WIDOW_TARGET}
            ]
            """,
        ),
        encoding="utf-8",
    )
    result = compile_typst(doc_path, pdf_path)
    assert result.returncode == 0, (
        f"typst compile failed (widow_orphan_protection="
        f"{widow_orphan_protection}):\nstdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    return pymupdf.open(pdf_path)


def _body_line_count(page: pymupdf.Page) -> int:
    """Count distinct body text lines on ``page`` (excludes head/footer).

    Groups body words (those outside the running-head / folio-footer bands)
    into visual lines by y0 and returns the line count. Used to measure how
    the widow/orphan engine redistributes lines across the page boundary.
    """
    body = [w for w in page_words(page) if _BODY_TOP_PT < w.y0 < page.rect.height - _BODY_BOTTOM_PT]
    return len(list(_group_lines(body)))


def test_widow_orphan_protection_engages(typst_workdir: Path) -> None:
    """Slice 5f invariant: widow/orphan protection measurably changes layout.

    Renders the calibrated body (target paragraph spanning page 3 → 4) with
    protection on and off, and asserts the overflow page carries strictly
    MORE body lines with protection on — the engine pulled an extra line
    forward to avoid stranding a widow. Same total page count for both
    (protection redistributes; it does not add a page). The directional
    difference is the load-bearing, drift-robust signal: it holds while
    protection engages and fails (on == off) the moment it stops.
    """
    with (
        _render_widow_doc(typst_workdir, "widow_off", widow_orphan_protection=False) as doc_off,
        _render_widow_doc(typst_workdir, "widow_on", widow_orphan_protection=True) as doc_on,
    ):
        # ── Same page count (protection redistributes, never adds a page).
        off_pages = doc_page_count(doc_off)
        on_pages = doc_page_count(doc_on)
        assert off_pages == on_pages, (
            f"page count differs (off={off_pages}, on={on_pages}) — "
            "widow/orphan protection should not change the number of pages"
        )
        last = off_pages - 1

        # ── Sanity: the body spans onto the last page in BOTH renders
        # (otherwise the fixture is miscalibrated and proves nothing).
        off_last = _body_line_count(doc_off[last])
        on_last = _body_line_count(doc_on[last])
        assert off_last >= 1, (
            "protection-OFF body does not spill onto the last page — the fixture is "
            "miscalibrated (increase _WIDOW_FILLER_REPEATS)"
        )

        # ── Load-bearing: protection pulled ≥1 extra line onto the overflow
        # page (the widow-prevention move). on_last > off_last while
        # protection engages; equality means it stopped engaging.
        assert on_last > off_last, (
            f"widow/orphan protection did NOT change the overflow page layout "
            f"(on={on_last} body lines == off={off_last} body lines on page {last + 1}). "
            "Expected protection to pull an extra line forward (on > off) — the fixture "
            "may need recalibration, or protection is no longer wired."
        )
