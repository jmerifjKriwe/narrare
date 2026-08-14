"""Golden-Pages probe for Slice 5c — the narrare-roman 4-phase numbering.

Renders a manuscript with the bundled ``narrare-roman`` Typst package using
the phase markers (``title-page``, ``frontmatter``, ``body``) and asserts the
four folio-numbering invariants of ADR-081 / IO-001 Slice 5c (the
``tieffiction`` 4-phase model re-implemented, not forked):

1. **Frontmatter folios are roman** — frontmatter pages carry lowercase
   roman numerals (i, ii, iii, …).
2. **Body folios are arabic** — body (chapter) pages carry arabic numerals.
3. **Body counter resets** — the first body page is ``1`` (not continued from
   the frontmatter count).
4. **Title page folio suppressed** — the title page carries no folio.

Plus a composition invariant that spans Slice 5b + 5c:

5. **Blank-page folio suppressed** — a blank verso inserted by the recto-
   opener (5a) has its folio suppressed via the shared ``is-page-empty``
   pattern (5b), even though it still *uses up* its number (the next body
   page jumps by 2, not 1).

The folio lives in the page FOOTER (bottom centre), separate from the
running head (header / top — Slice 5b). The two never collide.

The probe invokes ``typst compile`` via subprocess
(``_typst_probe_helpers.compile_typst``); per ADR-081 this is a sanctioned
test-harness invocation, deliberately outside RULE-08 confinement scope
(only the two production render binaries are confined — see
``_typst_probe_helpers.py`` for the full rationale).
"""

from __future__ import annotations

import re
import textwrap
from typing import TYPE_CHECKING

import pymupdf
import pytest

from tests.golden.export._typst_probe_helpers import (
    PACKAGE_IMPORT,
    compile_typst,
    footer_text,
    is_typst_available,
    page_text,
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

#: Regex for lowercase roman numerals (the frontmatter folio format).
_ROMAN_RE = re.compile(r"^[ivxlcdm]+$")

#: Regex for arabic numerals (the body folio format).
_ARABIC_RE = re.compile(r"^\d+$")

#: The book title fed to ``config.title`` — expected on the verso running
#: head of frontmatter pages (the recto head has no chapter to show yet).
BOOK_TITLE = "Numbering Probe"


def test_four_phase_numbering_title_frontmatter_body(
    typst_workdir: Path,
) -> None:
    """Slice 5c invariant: title suppressed → frontmatter roman → body arabic.

    Renders a title page + 2-page frontmatter + 2-chapter body and asserts:
    the title page has no folio, frontmatter folios are roman (i, ii), body
    folios are arabic (1, 3 — the blank verso between chapters "uses" 2),
    and the body counter restarts at 1.
    """
    doc_path = typst_workdir / "numbering.typ"
    pdf_path = typst_workdir / "numbering.pdf"
    doc_path.write_text(
        textwrap.dedent(
            f"""\
            #import "{PACKAGE_IMPORT}": narrare-roman, title-page, frontmatter, body

            #show: narrare-roman.with(
              config: (
                paper-size: "b-format-129x198",
                title: "{BOOK_TITLE}",
                author: "Slice 5c",
                language: "en",
              ),
            )

            #title-page[Title Page]

            #frontmatter[
              Frontmatter copyright page.

              #pagebreak()
              Frontmatter dedication page.
            ]

            #body[
              = Chapter One

              Chapter one content.

              = Chapter Two

              Chapter two content.
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
        # ── Collect (physical_page, whole_text, folio) per page.
        pages: list[tuple[int, str, str]] = []
        for i in range(doc.page_count):
            folio_num = i + 1
            whole = page_text(doc[i])
            folio = footer_text(doc[i])
            pages.append((folio_num, whole, folio))

        assert len(pages) >= 5, (
            f"expected ≥5 pages (title + 2 frontmatter + ≥2 body), got {len(pages)}"
        )

        # ── (4) Title page folio suppressed.
        title_folio = pages[0][2]
        assert title_folio == "", f"title page (page 1) must carry no folio; got {title_folio!r}"

        # ── Identify frontmatter + body pages (skip blank transitional pages).
        # A page is "blank" when it has no extractable text at all.
        non_blank = [(n, w, f) for (n, w, f) in pages if w.strip()]

        # The title page is the first non-blank page. Frontmatter starts
        # at page 2; body chapters start at the first "Chapter" heading.
        frontmatter_pages = [(n, f) for (n, w, f) in non_blank if n > 1 and "Chapter" not in w]
        body_pages = [(n, f) for (n, w, f) in non_blank if "Chapter" in w]

        # ── (1) Frontmatter folios are roman.
        assert frontmatter_pages, "fixture produced no frontmatter pages"
        for _page_num, folio in frontmatter_pages:
            assert _ROMAN_RE.match(folio), (
                f"frontmatter folio {folio!r} is not a lowercase roman numeral"
            )

        # ── (2) Body folios are arabic.
        assert body_pages, "fixture produced no body pages"
        for _page_num, folio in body_pages:
            assert _ARABIC_RE.match(folio), f"body folio {folio!r} is not an arabic numeral"

        # ── (3) Body counter resets — first body page is "1".
        first_body_folio = body_pages[0][1]
        assert first_body_folio == "1", (
            f"first body page folio is {first_body_folio!r}, expected '1' (body counter must reset)"
        )

        # ── (5) Blank-page folio suppressed (composes with 5b is-page-empty).
        blanks = [(n, f) for (n, w, f) in pages if not w.strip()]
        assert blanks, (
            "fixture produced no blank pages — a chapter ending on a recto "
            "should leave a counted blank verso whose folio is suppressed"
        )
        for _page_num, folio in blanks:
            assert folio == "", (
                f"blank page {_page_num} carries folio {folio!r} — is-page-empty suppression failed"
            )

        # ── Cross-check: the body folio sequence skips the blank's number.
        # Chapter One is on a recto with a short body; Chapter Two's
        # recto-opener leaves a blank verso between them. The blank
        # "uses" its number, so Chapter Two's folio = Chapter One's + 2.
        if len(body_pages) >= 2:
            ch1 = int(body_pages[0][1])
            ch2 = int(body_pages[1][1])
            assert ch2 == ch1 + 2, (
                f"body folio jumped from {ch1} to {ch2} — expected +2 "
                "(one blank verso between the two chapters)"
            )


def test_numbering_without_phase_markers_produces_no_folio(
    typst_workdir: Path,
) -> None:
    """Without phase markers, ``folio-footer`` renders nothing.

    This is the back-compat guard: the folio-footer is inert when no
    ``frontmatter`` / ``body`` markers are present, so documents that
    predate Slice 5c (the 5a / 5b probe documents) are unaffected.
    """
    doc_path = typst_workdir / "no_markers.typ"
    pdf_path = typst_workdir / "no_markers.pdf"
    doc_path.write_text(
        textwrap.dedent(
            f"""\
            #import "{PACKAGE_IMPORT}": narrare-roman

            #show: narrare-roman.with(config: (paper-size: "b-format-129x198",))

            = Single Chapter

            #lorem(50)
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
            folio = footer_text(doc[i])
            assert folio == "", (
                f"page {i + 1} carries folio {folio!r} — folio-footer must be "
                "inert without phase markers"
            )
