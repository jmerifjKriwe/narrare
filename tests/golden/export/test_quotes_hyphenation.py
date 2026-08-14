"""Golden-Pages probe for Slice 5e — per-language smart quotes + hyphenation.

Renders short snippets with the bundled ``narrare-roman`` Typst package and
asserts the two typographic invariants of ADR-081 / IO-001 Slice 5e:

1. **Per-language smart quotes** — Typst's smartquote engine converts
   straight ``"`` to language-appropriate typographic glyphs once
   ``#set text(lang: ...)`` is active. The probe renders the same quoted
   snippet in de / en / fr and asserts the correct opening + closing
   glyphs appear:

   =====  ============  ============
   lang   open          close
   =====  ============  ============
   en     U+201C ( “ )   U+201D ( ” )
   de     U+201E ( „ )   U+201C ( “ )
   fr     U+00AB ( « )   U+00BB ( » )
   =====  ============  ============

2. **Hyphenation** — a long compound word in justified body text is broken
   across lines with a hyphen (``set text(hyphenate: true)`` is forced on
   by the entry point). The probe renders a paragraph with a 40+ character
   German compound and asserts:

   - The word is **not** found intact in any single text line (it was
     split by the hyphenator — the load-bearing structural assertion).
   - A soft hyphen (U+00AD) is present in the extracted text (Typst's
     hyphenation break glyph; confirmed by PyMuPDF text extraction).

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
    compile_typst,
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
        reason="typst not installed (install via scripts/install_toolchain.sh)",
    ),
]

# ── Expected smart-quote glyphs per language (mirrors src/quotes.typ) ─────
#: Each value is ``(open_glyph, close_glyph)`` for a straight double-quote
#: pair in that language. Typst's smartquote defaults, probe-verified.
_EXPECTED_DOUBLE_QUOTES: dict[str, tuple[str, str]] = {
    "en": ("\u201c", "\u201d"),  # " … "
    "de": ("\u201e", "\u201c"),  # „ … "
    "fr": ("\u00ab", "\u00bb"),  # « … »
}

#: Soft hyphen (U+00AD) — the glyph Typst inserts at a hyphenation break.
#: Invisible except at line ends; PyMuPDF extracts it into the text layer.
_SOFT_HYPHEN = "\u00ad"

#: A long compound word (41 chars) used to exercise hyphenation. Preceded
#: by filler text in the fixture so it starts mid-line and cannot fit to the
#: end — forcing the hyphenator to break it. Probe-verified to break in en.
_HYPH_WORD = "Geschwindigkeitsueberschreitungskontrolle"


def _compile_snippet(
    typst_workdir: Path,
    name: str,
    language: str,
    body: str,
) -> pymupdf.Document:
    """Compile a one-paragraph Typst snippet for ``language`` and open the PDF.

    Returns an open :class:`pymupdf.Document`; the caller is responsible for
    closing it (use a ``with`` block).
    """
    doc_path = typst_workdir / f"{name}.typ"
    pdf_path = typst_workdir / f"{name}.pdf"
    doc_path.write_text(
        textwrap.dedent(
            f"""\
            #import "{PACKAGE_IMPORT}": narrare-roman

            #show: narrare-roman.with(
              config: (
                paper-size: "b-format-129x198",
                language: "{language}",
              ),
            )

            {body}
            """,
        ),
        encoding="utf-8",
    )
    result = compile_typst(doc_path, pdf_path)
    assert result.returncode == 0, (
        f"typst compile failed for language={language!r}:\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    return pymupdf.open(pdf_path)


def test_smart_quotes_per_language(typst_workdir: Path) -> None:
    """Slice 5e invariant: straight quotes become the correct per-language glyphs.

    Renders the same quoted snippet in de / en / fr and asserts the opening
    and closing double-quote glyphs match the ``quote-glyphs`` contract in
    ``src/quotes.typ``. Typst's smartquote engine is driven by
    ``#set text(lang: ...)`` (set by the entry point from
    ``config.language``); ``#set smartquote(enabled: true)`` is explicit.
    """
    snippets: dict[str, str] = {
        "en": 'She said "hello" to him.',
        "de": 'Sie sagte "hallo" zu ihm.',
        "fr": 'Elle a dit "bonjour" a lui.',
    }
    for language, snippet in snippets.items():
        with _compile_snippet(typst_workdir, f"quotes_{language}", language, snippet) as doc:
            text = page_text(doc[0])
            open_glyph, close_glyph = _EXPECTED_DOUBLE_QUOTES[language]
            assert open_glyph in text, (
                f"[{language}] expected opening quote {open_glyph!r} "
                f"(U+{ord(open_glyph):04X}) in rendered text {text!r}"
            )
            assert close_glyph in text, (
                f"[{language}] expected closing quote {close_glyph!r} "
                f"(U+{ord(close_glyph):04X}) in rendered text {text!r}"
            )


def test_hyphenation_breaks_long_compound(typst_workdir: Path) -> None:
    """Slice 5e invariant: a long compound word is hyphenated across lines.

    Renders a justified English paragraph where the 41-char compound
    ``Geschwindigkeitsueberschreitungskontrolle`` starts mid-line (preceded
    by filler text) and cannot fit to the end — forcing the hyphenator to
    break it. Asserts:

    1. **Structural** (load-bearing): the compound is not found intact in
       any single text line — it was split by the hyphenator. Without
       hyphenation the word would be pushed whole to the next line.
    2. **Glyph** (secondary): a soft hyphen (U+00AD) appears at the break
       point — Typst's hyphenation marker, confirmed by PyMuPDF extraction.
    """
    body = (
        "A long compound word: "
        + _HYPH_WORD
        + " appears here with some more text to fill the line so the "
        "compound must break across lines if hyphenation is active."
    )
    with _compile_snippet(typst_workdir, "hyphenation_en", "en", body) as doc:
        text = page_text(doc[0])
        lines = text.splitlines()

        # ── (1) Structural: the compound is broken (not intact in one line).
        word_intact_in_line = any(_HYPH_WORD in ln for ln in lines)
        assert not word_intact_in_line, (
            f"compound {_HYPH_WORD!r} found intact on a single line — "
            "hyphenation did not break it. Lines:\n" + "\n".join(lines)
        )

        # ── (2) Glyph: a soft hyphen (U+00AD) marks the break.
        assert _SOFT_HYPHEN in text, (
            "no soft hyphen (U+00AD) in the page text — expected Typst's "
            "hyphenation break glyph where the compound was split. "
            f"Text:\n{text!r}"
        )
