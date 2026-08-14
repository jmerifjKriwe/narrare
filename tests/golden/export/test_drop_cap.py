"""Golden-Pages probe for Slice 5g — the optional chapter drop cap.

Renders manuscripts with the bundled ``narrare-roman`` Typst package and
asserts the drop-cap invariants of ADR-081 / IO-001 Slice 5g (optional,
default OFF, gated on ``config.drop-caps`` ← ``NarrareRomanConfig.drop_caps``
← ``PdfOptions.drop_caps``):

1. **Default-OFF neutrality** — a render WITHOUT the ``drop-caps`` key
   shows NO drop cap (first paragraphs render as plain body text), and an
   explicit ``drop-caps: false`` is byte-identical to the omitted key
   (deterministic compile via ``--creation-timestamp 0``). The pipeline-
   level neutrality is separately pinned by the Golden-Pages baselines
   (``test_golden_pages.py`` asserts the committed sha256s — 5g must not
   drift them).

2. **ON-presence + no-overlap** — a render with ``drop-caps: true`` caps
   the FIRST paragraph of EACH chapter: exactly one enlarged glyph per
   chapter opener, sized ≥ 2x the body font, with at least two body-size
   text lines beside it (the "spans multiple text lines" property of a
   dropped capital) and no glyph collision (the bake-off saw collisions
   in community templates; droplet's grid + the 0.25 em gap must prevent
   them). Shared geometry assertions live in
   ``_drop_cap_helpers.assert_single_clean_cap``.

3. **Renderer round-trip** — the REAL :class:`TypstPdfRenderer` with
   ``PdfOptions(drop_caps=True)`` produces the enabled output (pandoc
   HTML→Typst + wrapper config + ``typst compile`` — the whole production
   pipeline), asserting the ``drop-caps`` config emission end-to-end.

The chapter-first-paragraph targeting on the Typst side is a pure content
transform (``src/drop_cap.typ``) over the vendored ``droplet`` package
(``vendor/droplet/`` — see its README for provenance); the two show-rule
alternatives were prototyped and rejected on Typst 0.15.1 (non-convergent
state / introspection risk) — see the module header of ``drop_cap.typ``.
Probe infrastructure (span geometry, deterministic compile, the shared
fixture) lives in ``_drop_cap_helpers.py`` (RULE-04 split).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid5

import pymupdf
import pytest

from narrare.export.options import ExportFormat, ExportOptions, PdfOptions
from narrare.export.renderers.typst import TypstPdfRenderer
from narrare_core.export.contracts import ChapterMeta, Language, NormalizedManuscript
from tests.golden.export._drop_cap_helpers import (
    CHAPTER_TITLES,
    assert_single_clean_cap,
    body_font_size,
    compile_deterministic,
    enlarged_spans,
    find_opener_page,
    sha256_of,
    write_probe_doc,
)
from tests.golden.export._typst_probe_helpers import is_typst_available

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


# ── (1) Default OFF ────────────────────────────────────────────────────────


def test_default_off_renders_first_paragraph_without_cap(
    typst_workdir: Path,
) -> None:
    """Omitting ``drop-caps`` (the default) renders NO drop cap.

    Every span on both chapter-opener pages — first paragraphs included
    — stays at body scale: nothing exceeds the enlarged threshold. This
    is the package-level default-OFF contract; the pipeline-level
    byte-neutrality is pinned separately by the Golden-Pages baselines.
    """
    doc_path, pdf_path = write_probe_doc(typst_workdir, "dropcap_default_off", drop_caps_line="")
    compile_deterministic(doc_path, pdf_path)

    with pymupdf.open(pdf_path) as doc:
        for title in CHAPTER_TITLES:
            page = find_opener_page(doc, title)
            assert page is not None, f"chapter opener page for {title!r} not found"
            enlarged = enlarged_spans(page, body_font_size(page))
            assert not enlarged, (
                f"default-OFF render shows enlarged spans on the {title!r} "
                f"opener: {[(s['text'], s['size']) for s in enlarged]!r} — "
                "drop-caps must default to OFF"
            )


def test_explicit_false_is_byte_identical_to_omitted_key(
    typst_workdir: Path,
) -> None:
    """``drop-caps: false`` == omitted key, byte for byte.

    Both docs are identical except the explicit key; deterministic
    compilation (pinned creation timestamp) must yield identical PDFs —
    the byte-level statement of "explicit OFF is the default OFF".
    """
    omitted_doc, omitted_pdf = write_probe_doc(
        typst_workdir, "dropcap_key_omitted", drop_caps_line=""
    )
    false_doc, false_pdf = write_probe_doc(
        typst_workdir, "dropcap_key_false", drop_caps_line="drop-caps: false,"
    )
    compile_deterministic(omitted_doc, omitted_pdf)
    compile_deterministic(false_doc, false_pdf)

    assert sha256_of(omitted_pdf) == sha256_of(false_pdf), (
        "explicit `drop-caps: false` differs byte-wise from the omitted key — "
        "an explicit OFF must be indistinguishable from the default OFF"
    )


# ── (2) ON: presence, multi-line span, no overlap ─────────────────────────


def test_enabled_caps_each_chapter_first_paragraph(typst_workdir: Path) -> None:
    """``drop-caps: true`` caps exactly the first paragraph of each chapter.

    Per chapter opener: exactly ONE enlarged span (the cap — the second
    paragraph stays plain), sized ≥ 2 x body, with ≥ 2 body-size lines
    beside it, and NOTHING in the paragraph band colliding with it (the
    full contract: ``_drop_cap_helpers.assert_single_clean_cap``).
    """
    doc_path, pdf_path = write_probe_doc(
        typst_workdir, "dropcap_enabled", drop_caps_line="drop-caps: true,"
    )
    compile_deterministic(doc_path, pdf_path)

    with pymupdf.open(pdf_path) as doc:
        for title in CHAPTER_TITLES:
            page = find_opener_page(doc, title)
            assert page is not None, f"chapter opener page for {title!r} not found"
            assert_single_clean_cap(page, title, context="package-level")


# ── (3) Renderer round-trip ───────────────────────────────────────────────

#: Deterministic namespace for the round-trip chapter ids (stable output).
_ROUND_TRIP_NAMESPACE = uuid5(UUID(int=0), "narrare-drop-cap-probe")

#: The two-chapter HTML the round-trip manuscript carries (same prose as
#: the package-level fixture — the helpers' paragraph constants are
#: module-private there, so this mirrors the shape rather than sharing).
_ROUND_TRIP_HTML_BODY = (
    "<h2>Chapter One</h2>"
    "<p>Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do "
    "eiusmod tempor incididunt ut labore et dolore magna aliqua as the "
    "opening prose of the first chapter, running long enough to wrap "
    "several lines beside the dropped capital and below it.</p>"
    "<p>Second paragraph of chapter one must stay plain body text.</p>"
    "<h2>Chapter Two</h2>"
    "<p>Duis aute irure dolor in reprehenderit in voluptate velit esse "
    "cillum dolore eu fugiat nulla pariatur on the opening paragraph of "
    "the second chapter, again wrapping multiple lines beside the cap.</p>"
    "<p>Second paragraph of chapter two must also remain plain.</p>"
)


def _round_trip_manuscript() -> NormalizedManuscript:
    """A two-chapter manuscript in the exact shape the service hands over.

    ``<h2>`` chapters + paragraphs — pandoc's ``--shift-heading-level-by=-1``
    promotes them to level-1 Typst openers (F-1), so the drop-cap
    targeting runs against real production body markup.
    """
    chapters = [
        ChapterMeta(
            chapter_id=uuid5(_ROUND_TRIP_NAMESPACE, title),
            title=title,
            position=position,
            volume_id=None,
        )
        for position, title in enumerate(CHAPTER_TITLES)
    ]
    return NormalizedManuscript(
        semantic_html=_ROUND_TRIP_HTML_BODY,
        title="Drop Cap Round Trip",
        author="Slice 5g",
        language=Language.EN,
        chapters=chapters,
    )


@pytest.mark.asyncio
async def test_renderer_round_trip_drop_caps_enabled() -> None:
    """``PdfOptions(drop_caps=True)`` produces capped output end-to-end.

    Round-trips the REAL renderer (pandoc HTML→Typst + wrapper config +
    ``typst compile``): both chapter openers carry exactly one enlarged
    cap with no glyph collision — proving the ``drop-caps`` config key
    is emitted and honoured through the whole production pipeline.
    """
    renderer = TypstPdfRenderer()
    assert renderer.is_available(), "typst binary vanished mid-session"

    artifact = await renderer.render(
        _round_trip_manuscript(),
        ExportOptions(format=ExportFormat.PDF, pdf_options=PdfOptions(drop_caps=True)),
    )
    try:
        with pymupdf.open(artifact.path) as doc:
            for title in CHAPTER_TITLES:
                page = find_opener_page(doc, title)
                assert page is not None, (
                    f"round-trip opener page for {title!r} not found — "
                    "pandoc did not promote the chapter as expected (F-1)"
                )
                assert_single_clean_cap(page, title, context="renderer round-trip")
    finally:
        artifact.path.unlink(missing_ok=True)
