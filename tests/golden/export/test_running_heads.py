"""Golden-Pages probe for Slice 5b — the narrare-roman running heads.

Renders a 3-chapter manuscript with the bundled ``narrare-roman`` Typst
package and asserts the four running-head invariants of ADR-081 / IO-001
Slice 5b (recto ≠ verso, suppressed on chapter openers and blank versos
via the ``is-page-empty`` pattern borrowed from wonderous-book):

1. **Present on body recto + verso** — every non-opener, non-blank page
   carries a running head.
2. **Recto ≠ verso** — the recto (odd) head carries the *current chapter
   title*; the verso (even) head carries the *book title*. The two sides
   show different content (the load-bearing recto/verso distinction).
3. **Absent on chapter openers** — the page where a chapter begins has no
   running head (the opener is its own title).
4. **Absent on blank versos** — the ``is-page-empty`` suppression: a
   blank verso inserted to keep the next chapter on a recto has no head.

The probe classifies each rendered page by role (opener / body / blank)
from the extracted text, then asserts the head behaviour matches the role
— robust to a one-page drift in where the long first chapter's body ends.

Recto/verso choice (documented, per the IO-001 sub-slice-5b row): verso =
book title (``config.title``), recto = chapter title (most recent
level-1 heading). The traditional English-fiction convention.

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
    body_text,
    compile_typst,
    header_text,
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

#: The three chapter headings in the fixture (rendered as their own body
#: line on the opener page). Used to classify pages by role.
CHAPTER_TITLES: tuple[str, ...] = ("Chapter One", "Chapter Two", "Chapter Three")

#: The book title fed to ``config.title`` — expected on verso heads.
BOOK_TITLE = "The Running-Head Probe"


def _classify_page(body_only: str, whole_page: str) -> str:
    """Classify a page by role.

    ``body_only`` is the text *below* the running-head band (excludes the
    head, so a head that repeats the chapter title on a body recto is not
    mistaken for an opener heading); ``whole_page`` is the full page text
    (used to detect a truly blank page, which has no head either).

    Returns ``"blank"`` (no text anywhere), ``"opener"`` (a chapter title
    is the first body line — the heading renders at the body top), or
    ``"body"`` (any other text-bearing page).
    """
    if not whole_page.strip():
        return "blank"
    lines = [ln.strip() for ln in body_only.splitlines() if ln.strip()]
    if lines and lines[0] in CHAPTER_TITLES:
        return "opener"
    return "body"


def test_running_heads_recto_verso_suppressed_on_openers_and_blanks(
    typst_workdir: Path,
) -> None:
    """Slice 5b invariant: recto≠verso heads, suppressed on openers/blanks."""
    doc_path = typst_workdir / "heads.typ"
    pdf_path = typst_workdir / "heads.pdf"
    # Chapter One is long enough to spill a body line onto a verso (p2)
    # AND a recto (p3) — so both parities of body page carry a head and
    # the recto/verso distinction is exercisable. Chapters Two/Three are
    # short (end on their opener recto), each forcing a blank verso.
    doc_path.write_text(
        textwrap.dedent(
            f"""\
            #import "{PACKAGE_IMPORT}": narrare-roman

            #show: narrare-roman.with(
              config: (
                paper-size: "b-format-129x198",
                title: "{BOOK_TITLE}",
                author: "Slice 5b",
                running-head-preset: "default",
              ),
            )

            = Chapter One

            #lorem(900)

            = Chapter Two

            A short chapter that ends on its opener recto, forcing a
            counted blank verso before the next chapter opener.

            = Chapter Three

            Another short opener.
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
        # ── Classify every page and collect its (parity, role, head).
        pages: list[tuple[int, str, str, str]] = []  # (folio, parity, role, head)
        for i in range(doc.page_count):
            folio = i + 1
            parity = "recto" if folio % 2 == 1 else "verso"
            whole = page_text(doc[i])
            role = _classify_page(body_text(doc[i]), whole)
            head = header_text(doc[i])
            pages.append((folio, parity, role, head))

        # Sanity: the fixture must produce the full matrix of roles.
        roles = {p[2] for p in pages}
        assert {"opener", "body", "blank"} <= roles, (
            f"fixture did not produce all three page roles; got {sorted(roles)} (pages: {pages!r})"
        )

        body_recto_heads = {p[3] for p in pages if p[1] == "recto" and p[2] == "body"}
        body_verso_heads = {p[3] for p in pages if p[1] == "verso" and p[2] == "body"}

        # ── (1) Present on body recto + verso.
        assert body_recto_heads, (
            "no body recto page with a head found — fixture must overflow "
            "chapter one onto a recto body page"
        )
        assert body_verso_heads, (
            "no body verso page with a head found — fixture must overflow "
            "chapter one onto a verso body page"
        )
        assert "" not in body_recto_heads, f"a body recto page carries no head: {pages!r}"
        assert "" not in body_verso_heads, f"a body verso page carries no head: {pages!r}"

        # ── (2) Recto ≠ verso: recto = chapter title, verso = book title.
        # Every body recto head is a chapter title; every body verso head
        # is the book title. The two sets are disjoint by construction.
        assert all(h in CHAPTER_TITLES for h in body_recto_heads), (
            f"body recto head(s) {body_recto_heads!r} are not chapter titles; "
            f"expected one of {CHAPTER_TITLES!r}"
        )
        assert body_verso_heads == {BOOK_TITLE}, (
            f"body verso head(s) {body_verso_heads!r} ≠ book title {BOOK_TITLE!r}"
        )
        # Stronger: the recto head actually tracks the *current* chapter —
        # every body recto in this fixture belongs to Chapter One, so its
        # head must read exactly "Chapter One".
        assert body_recto_heads == {"Chapter One"}, (
            f"body recto head {body_recto_heads!r} ≠ current chapter 'Chapter One'"
        )
        assert body_recto_heads.isdisjoint(body_verso_heads), (
            "recto and verso heads are identical — recto≠verso invariant violated"
        )

        # ── (3) Absent on chapter openers.
        opener_heads = [(p[0], p[3]) for p in pages if p[2] == "opener"]
        assert opener_heads, "fixture produced no opener page to probe"
        assert all(h == "" for _, h in opener_heads), (
            f"chapter openers must carry no running head; found: {opener_heads!r}"
        )

        # ── (4) Absent on blank versos (the is-page-empty suppression).
        blank_heads = [(p[0], p[1], p[3]) for p in pages if p[2] == "blank"]
        assert blank_heads, (
            "no blank page found — a chapter ending on a recto should leave "
            "a counted blank verso whose head is suppressed"
        )
        assert all(h == "" for _, _, h in blank_heads), (
            f"blank pages must carry no running head; found: {blank_heads!r}"
        )
        # Blanks only ever occur on versos in this layout (a recto-ending
        # chapter leaves a verso blank for the next recto opener).
        assert all(parity == "verso" for _, parity, _ in blank_heads), (
            f"unexpected recto blank page: {blank_heads!r}"
        )


def test_running_head_preset_is_read_without_error(typst_workdir: Path) -> None:
    """The forward-compat ``running-head-preset`` key is honoured (read).

    Only ``"default"`` is implemented (Slice 5b); the key is exercised
    here so a typo or an unrecognised value degrades cleanly (renders as
    default) rather than erroring — the preset is a reserved knob, not a
    validated enum, until a later slice adds real presets.
    """
    doc_path = typst_workdir / "preset.typ"
    pdf_path = typst_workdir / "preset.pdf"
    doc_path.write_text(
        textwrap.dedent(
            f"""\
            #import "{PACKAGE_IMPORT}": narrare-roman

            #show: narrare-roman.with(
              config: (
                paper-size: "b-format-129x198",
                title: "{BOOK_TITLE}",
                running-head-preset: "future-author-verso",
              ),
            )

            = Single

            #lorem(50)
            """,
        ),
        encoding="utf-8",
    )
    result = compile_typst(doc_path, pdf_path)
    assert result.returncode == 0, (
        f"unrecognised running-head-preset must degrade to default, not error:\n"
        f"stderr:\n{result.stderr}"
    )
