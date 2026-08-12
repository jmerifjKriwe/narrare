"""Golden-Pages probe for Slice 5a — the narrare-roman geometric spine.

Renders a tiny 3-chapter manuscript with the bundled ``narrare-roman`` Typst
package and asserts the four geometric-spine invariants of ADR-081 / IO-001
Slice 5a (paper + mirrored Satzspiegel + recto chapter starts + blank verso):

1. **Paper size** — the rendered PDF is B-format (129 x 198 mm).
2. **Folio count** — at least 5 pages for 3 recto-starting chapters
   (each chapter on an odd page → minimum pages 1, 3, 5 + blank versos
   2 and 4 = 5).
3. **Recto-start** — every chapter heading lands on a recto (odd) page.
4. **Blank verso** — at least one verso page exists with no extractable
   text (the deliberate blank behind a chapter that ended on a recto).

Plus two quality invariants that span the whole slice series:

5. **No silent font fallback** (D3 / the bake-off's headline fire&forget
   failure): the body text is rendered with the bundled Libertinus Serif,
   not a fallback. Verified by extracting per-span font names via PyMuPDF.
6. **Mirrored Satzspiegel** — the inside margin (toward the binding) is
   on the LEFT of recto pages and the RIGHT of verso pages (Typst's
   ``inside``/``outside`` binding-aware margin).

The probe invokes ``typst compile`` via subprocess (in
``_typst_probe_helpers.compile_typst``). Per ADR-081 this is a sanctioned
test-harness invocation (mirrors the Slice-4 EPUBCheck pattern) and is
**deliberately outside RULE-08 confinement scope** — only the two
production render binaries are confined, and a test probe is not
production. The RULE-08 AST checker
(see ``scripts/architecture/_checkers/export_binary_confinement.py``)
exempts any file under a ``tests/`` root via its ``_TEST_ROOTS``
early-return, so ``_typst_probe_helpers.py`` is not flagged (same rationale
as the EPUBCheck exemption — test/validation harnesses that spawn the binary
to verify output are legitimate consumers).

PyMuPDF (``pymupdf>=1.28``) is the Slice-7 Golden-Pages probe library,
pulled forward here for the inline 5a probe.
"""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

import pymupdf
import pytest

from tests.golden.export._typst_probe_helpers import (
    MM_TO_PT,
    PACKAGE_IMPORT,
    SIZE_TOL_PT,
    compile_typst,
    is_typst_available,
    page_fonts,
    page_text,
    text_bbox_mm,
)

if TYPE_CHECKING:
    from pathlib import Path

# ── Skip guard: nothing in this module runs without the typst binary ──────
pytestmark = [
    pytest.mark.golden_pages,
    pytest.mark.skipif(
        not is_typst_available(),
        reason="typst not installed (install via scripts/install_export_toolchain.sh)",
    ),
]


def test_geometric_spine_produces_b_format_pdf_with_recto_chapter_starts(
    typst_workdir: Path,
) -> None:
    """Slice 5a invariant: paper + margins + recto starts + blank versos."""
    doc_path = typst_workdir / "manuscript.typ"
    pdf_path = typst_workdir / "manuscript.pdf"
    doc_path.write_text(
        textwrap.dedent(
            f"""\
            #import "{PACKAGE_IMPORT}": narrare-roman

            #show: narrare-roman.with(
              config: (
                paper-size: "b-format-129x198",
                body-font: "Libertinus Serif",
                body-size-pt: 11.0,
                leading-ratio: 1.2,
                title: "Geometric Spine Probe",
                author: "Slice 5a",
                language: "en",
              ),
            )

            = Chapter One

            The first chapter opens on a recto. This short paragraph fits on
            the single opening page, so the next chapter forces a blank verso.

            = Chapter Two

            The second chapter must open on the next recto, leaving a
            deliberately blank verso behind it.

            = Chapter Three

            The third chapter again opens on a recto, another blank verso
            before it. Three recto starts + two blank versos = five pages.
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
        # ── (1) Paper size: B-format 129 x 198 mm.
        page0 = doc[0]
        assert abs(page0.rect.width - 129.0 * MM_TO_PT) <= SIZE_TOL_PT, (
            f"page width {page0.rect.width:.2f}pt ≠ 129 mm ({129.0 * MM_TO_PT:.2f}pt)"
        )
        assert abs(page0.rect.height - 198.0 * MM_TO_PT) <= SIZE_TOL_PT, (
            f"page height {page0.rect.height:.2f}pt ≠ 198 mm ({198.0 * MM_TO_PT:.2f}pt)"
        )

        # ── (2) Folio count: ≥ 5 (3 chapters on rectos + ≥ 2 blank versos).
        page_count = doc.page_count
        assert page_count >= 5, f"expected ≥5 pages for 3 recto-starting chapters, got {page_count}"

        # ── (3) Recto-start: each chapter heading on an odd (recto) page.
        # PyMuPDF page indices are 0-based; PDF folio numbers are 1-based.
        # Iteration is index-based (range + doc[i]) because pymupdf's
        # ``Document`` stub is not typed as ``Iterable``.
        chapter_pages: list[int] = []
        for i in range(doc.page_count):
            text = page_text(doc[i])
            folio = i + 1
            lines = {ln.strip() for ln in text.splitlines() if ln.strip()}
            for label in ("Chapter One", "Chapter Two", "Chapter Three"):
                # Anchor the match to a heading line (heading renders as
                # its own line in the PDF text stream); this avoids false
                # positives from body prose mentioning the phrase.
                if label in lines and folio not in chapter_pages:
                    chapter_pages.append(folio)
        assert len(chapter_pages) == 3, (
            f"expected to locate all 3 chapter headings, found {chapter_pages!r}"
        )
        for folio in chapter_pages:
            assert folio % 2 == 1, (
                f"chapter heading landed on verso (even) page {folio}; "
                "recto-start invariant violated"
            )
        # Stronger: the three rectos are exactly pages 1, 3, 5 (each
        # chapter's body fits on its opening page in this fixture).
        assert chapter_pages == [1, 3, 5], (
            f"expected chapters on rectos [1, 3, 5], got {chapter_pages}"
        )

        # ── (4) Blank verso: ≥ 1 even page with no extractable text.
        blank_versos = [
            i + 1
            for i in range(doc.page_count)
            if (i + 1) % 2 == 0 and not page_text(doc[i]).strip()
        ]
        assert blank_versos, (
            "no blank verso pages found — chapter-ending recto should leave "
            "a counted blank verso behind it (suppressed-head is a 5b concern)"
        )

        # ── (5) No silent font fallback (D3): every body span uses Libertinus.
        for i in range(doc.page_count):
            fonts = page_fonts(doc[i])
            if not fonts:
                continue  # blank verso — nothing to check
            non_libertinus = {f for f in fonts if "libertinus" not in f.lower()}
            assert not non_libertinus, (
                f"page {i + 1} used non-Libertinus font(s) "
                f"{non_libertinus!r} — silent fallback (D3 violation)"
            )

        # ── (6) Mirrored Satzspiegel: recto inside (left) > outside (right).
        # The verso side of the mirror is probed separately in the
        # overflowing-body test below (in this fixture every verso is blank).
        recto_margins = text_bbox_mm(doc[0])
        assert recto_margins is not None, "recto page has no text to probe"
        left_gap, right_gap = recto_margins
        assert left_gap > right_gap, (
            "recto Satzspiegel not honored: left gap "
            f"({left_gap:.2f} mm, expected ~18 inside) ≤ right gap "
            f"({right_gap:.2f} mm, expected ~15 outside)"
        )


def test_geometric_spine_margins_mirror_across_spread_with_overflowing_body(
    typst_workdir: Path,
) -> None:
    """Margin-mirror probe on a verso that actually carries body text.

    The 3-chapter fixture above leaves every verso blank (each chapter's
    body fits on its opening recto), so the verso-side mirroring cannot
    be probed there. This companion doc fills the first chapter past the
    recto so body text flows onto the verso — letting us assert that the
    verso's *right* gap (its inside margin) exceeds its *left* gap.
    """
    doc_path = typst_workdir / "overflow.typ"
    pdf_path = typst_workdir / "overflow.pdf"
    doc_path.write_text(
        textwrap.dedent(
            f"""\
            #import "{PACKAGE_IMPORT}": narrare-roman

            #show: narrare-roman.with(config: (:))

            = Single Chapter

            #lorem(400)
            """,
        ),
        encoding="utf-8",
    )

    result = compile_typst(doc_path, pdf_path)
    assert result.returncode == 0, (
        f"typst compile failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    with pymupdf.open(pdf_path) as doc:
        assert doc.page_count >= 2, f"overflow fixture must span ≥2 pages, got {doc.page_count}"
        recto = text_bbox_mm(doc[0])
        verso = text_bbox_mm(doc[1])
        assert recto is not None and verso is not None, (
            "both recto and verso must carry text in this fixture"
        )
        recto_left, _ = recto
        verso_left, verso_right = verso
        # Recto: inside on LEFT → left gap is the larger margin.
        assert recto_left > 16.0, (
            f"recto inside margin {recto_left:.2f} mm too small "
            "(expected ~18 mm inside on left of recto)"
        )
        # Verso: inside on RIGHT → right gap is the larger margin.
        assert verso_right > verso_left, (
            f"verso not mirrored: right gap {verso_right:.2f} mm "
            f"(inside) ≤ left gap {verso_left:.2f} mm (outside)"
        )


def test_paper_size_a5_compiles_and_sets_a5_dimensions(
    typst_workdir: Path,
) -> None:
    """Paper-size selector: A5 produces A5 dimensions (148 x 210 mm).

    Locks the public Typst-side ``paper-size`` selector surface against
    drift — Slice 6's wrapper writes the PaperSize enum value verbatim.
    """
    doc_path = typst_workdir / "a5.typ"
    pdf_path = typst_workdir / "a5.pdf"
    doc_path.write_text(
        textwrap.dedent(
            f"""\
            #import "{PACKAGE_IMPORT}": narrare-roman

            #show: narrare-roman.with(config: (paper-size: "a5",))

            = A Five

            Body text.
            """,
        ),
        encoding="utf-8",
    )
    result = compile_typst(doc_path, pdf_path)
    assert result.returncode == 0, f"typst compile (a5) failed:\nstderr:\n{result.stderr}"
    with pymupdf.open(pdf_path) as doc:
        page = doc[0]
        assert abs(page.rect.width - 148.0 * MM_TO_PT) <= SIZE_TOL_PT
        assert abs(page.rect.height - 210.0 * MM_TO_PT) <= SIZE_TOL_PT


def test_custom_paper_without_dimensions_panics(typst_workdir: Path) -> None:
    """Custom paper without width/height is a hard error (no silent fallback)."""
    doc_path = typst_workdir / "custom.typ"
    pdf_path = typst_workdir / "custom.pdf"
    doc_path.write_text(
        textwrap.dedent(
            f"""\
            #import "{PACKAGE_IMPORT}": narrare-roman

            #show: narrare-roman.with(config: (paper-size: "custom",))

            = Custom

            Body text.
            """,
        ),
        encoding="utf-8",
    )
    result = compile_typst(doc_path, pdf_path)
    assert result.returncode != 0, (
        "expected typst compile to fail on custom paper without dimensions"
    )
    # The panic message comes from our package; it lands in stderr.
    combined = (result.stdout + "\n" + result.stderr).lower()
    assert "custom" in combined or "paper" in combined, (
        f"expected an error mentioning custom/paper, got:\n{result.stderr}"
    )
