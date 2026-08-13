"""Golden-Pages acceptance test (IO-001 / ADR-081 Slice 7).

The fire&forget robustness gate. Renders every committed corpus fixture
through the REAL :class:`TypstPdfRenderer.render()` (pandoc HTML→Typst +
wrapper assembly + ``typst compile`` — the whole production pipeline, not a
hand-rolled compile) and asserts the 8 probes against fixed invariants or
committed baseline values. This is the acceptance test that catches a
narrare-roman / Typst / pandoc regression before it reaches a user's export.

Probes (see ``harness/probes.py`` for the full rationale of each):

    byte_reproducibility   — two consecutive renders are byte-identical (the
                             decisive Typst property) + the absolute sha256
                             matches the committed golden (drift signal).
    text_layer_tounicode   — every fixture's probe-words extract verbatim
                             (ToUnicode CMap correct — the SILE disqualifier).
    folio_numbering        — frontmatter roman, body arabic restarting at 1.
    running_header         — present on body recto+verso, absent on
                             openers+blanks, recto≠verso.
    recto_start            — every chapter opener on an odd (recto) page.
    right_edge_max_error   — ≤ committed baseline (drift; justified raggedness).
    word_gap_stdev         — ≤ committed baseline (drift; grey uniformity).
    scene_break_present    — the asterism renders as a centred ornament.

Baseline regeneration: ``just golden-update`` (or pass ``--golden-update``),
which renders the corpus + writes the new expected values. Review the diff,
then commit — the documented human-review path for intentional drift.

CI: collected by the ``test-integration`` job step
``uv run pytest tests/golden/ -v -m golden_pages`` (the toolchain is installed
in that job). CI-green itself is confirmed at push/PR time — same as EPUBCheck
— because the branch is not pushed from this session.

Non-LLM (the golden test renders deterministic prose; no agent, no prompt).
"""

from __future__ import annotations

import shutil

import pymupdf
import pytest

from narrare.export.renderers.typst import TypstPdfRenderer
from tests.golden.export._typst_probe_helpers import doc_page_count
from tests.golden.export.harness import baselines, probes
from tests.golden.export.harness.corpus import (
    CORPUS,
    CorpusFixture,
    build_manuscript,
    build_options,
)

# ── Skip guard: the real pipeline needs both render binaries ───────────────
#: The test renders via TypstPdfRenderer.render(), which shells out to BOTH
#: typst AND pandoc. Skip the whole module when either is missing (local
#: portability) — the test-integration CI job installs both.
_SKIP_NO_BINARY = pytest.mark.skipif(
    shutil.which("typst") is None or shutil.which("pandoc") is None,
    reason="typst and/or pandoc not installed (install via scripts/install_export_toolchain.sh)",
)

pytestmark = [pytest.mark.golden_pages, _SKIP_NO_BINARY]

#: Drift tolerances for the floating-point metrics. Typst + PyMuPDF are
#: deterministic, so the SAME versions produce identical measurements (no
#: epsilon needed). The epsilon absorbs CROSS-VERSION float noise (a PyMuPDF
#: coordinate-extraction tweak) without masking a real regression — a
#: justification/leading change shifts the metric by orders of magnitude more.
_DRIFT_EPSILON_MM = 0.05  # ~0.4% of a 129 mm B-format sheet
_DRIFT_EPSILON_PT = 0.01  # well below any visible spacing change


# ── Parametrisation: one test case per corpus fixture ──────────────────────


def _fixture_ids() -> list[str]:
    return [f.name for f in CORPUS]


@pytest.fixture(scope="module")
def golden_update(request: pytest.FixtureRequest) -> bool:
    """True when ``--golden-update`` was passed (baseline regeneration mode)."""
    return bool(request.config.getoption("--golden-update"))


# ── The acceptance test ────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("fixture", CORPUS, ids=_fixture_ids())
async def test_golden_pages(
    fixture: CorpusFixture,
    golden_update: bool,
) -> None:
    """Render ``fixture`` through the real pipeline and assert every probe.

    In ``--golden-update`` mode this captures + writes the baselines instead of
    asserting (the human-review regeneration path).
    """
    manuscript = build_manuscript(fixture)
    options = build_options(fixture)
    renderer = TypstPdfRenderer()

    # ── (1) byte_reproducibility — two consecutive renders, identical sha256.
    artifact_a = await renderer.render(manuscript, options)
    artifact_b = await renderer.render(manuscript, options)
    try:
        sha_a = probes.sha256_of_path(artifact_a.path)
        sha_b = probes.sha256_of_path(artifact_b.path)
        assert sha_a == sha_b, (
            f"byte reproducibility violated: sha256 of two consecutive renders "
            f"differs ({sha_a[:16]}… ≠ {sha_b[:16]}…)"
        )

        with pymupdf.open(artifact_a.path) as doc:
            if golden_update:
                _regenerate(fixture, doc, sha_a)
                return
            _assert_all_probes(fixture, doc, sha_a)
    finally:
        artifact_a.path.unlink(missing_ok=True)
        artifact_b.path.unlink(missing_ok=True)


# ── Assertion path (normal CI mode) ────────────────────────────────────────


def _assert_all_probes(fixture: CorpusFixture, doc: pymupdf.Document, sha256_hex: str) -> None:
    """Assert every applicable probe against its invariant or baseline."""
    baseline = baselines.load_baseline(fixture)
    chapter_titles = fixture.chapter_titles

    # ── byte_reproducibility: the absolute sha256 matches the golden (drift).
    assert sha256_hex == baseline.sha256, (
        f"golden sha256 drift: {sha256_hex[:16]}… ≠ baseline {baseline.sha256[:16]}…. "
        "Run `just golden-update`, review the diff, and commit if the change is "
        "intentional (narrare-roman / Typst / pandoc rendering change)."
    )

    # ── page_count: exact match (drift — a page-count change is a regression).
    actual_pages = doc_page_count(doc)
    assert actual_pages == baseline.page_count, (
        f"page-count drift: rendered {actual_pages} pages, baseline "
        f"{baseline.page_count}. Run `just golden-update` after review."
    )

    # ── text_layer_tounicode: every probe-word extracts verbatim.
    missing = probes.tounicode_missing_words(doc, fixture.tounicode_words)
    assert not missing, (
        f"ToUnicode regression: words {missing!r} not found verbatim in the "
        f"PDF text layer (broken ToUnicode CMap — the SILE failure mode)."
    )

    # ── folio_numbering: 4-phase (title suppressed → frontmatter roman →
    # body arabic restarting at 1).
    folio = probes.extract_folio_numbering(doc, chapter_titles)
    assert folio.has_frontmatter, "fixture produced no frontmatter pages (ToC)"
    assert folio.has_body, "fixture produced no body pages (chapters)"
    assert folio.title_page_suppressed, "title page must carry no folio"
    assert folio.frontmatter_all_roman, "frontmatter folios are not all roman"
    assert folio.body_all_arabic, "body folios are not all arabic"
    assert folio.body_starts_at_one, "body counter did not restart at 1"

    # ── running_header: present on body recto+verso, absent on openers+blanks.
    heads = probes.extract_running_headers(doc, chapter_titles)
    assert heads.absent_on_openers, (
        f"chapter openers must carry no running head; found {set(heads.opener_heads)!r}"
    )
    assert heads.absent_on_blanks, (
        f"blank pages must carry no running head; found {set(heads.blank_heads)!r}"
    )
    if heads.has_body_recto:
        assert heads.present_on_body_recto, (
            f"a body-recto page carries no running head: {set(heads.body_recto_heads)!r}"
        )
    if heads.has_body_verso:
        assert heads.present_on_body_verso, (
            f"a body-verso page carries no running head: {set(heads.body_verso_heads)!r}"
        )
    if heads.has_body_recto and heads.has_body_verso:
        assert heads.recto_neq_verso, (
            "recto and verso running heads are identical — recto≠verso violated"
        )

    # ── recto_start: every chapter opener on an odd (recto) page.
    opener_pages = probes.find_chapter_opener_pages(doc, chapter_titles)
    assert opener_pages, "no chapter-opener pages found (fixture has no chapters?)"
    verso_openers = [p for p in opener_pages if p % 2 == 0]
    assert not verso_openers, (
        f"chapter openers landed on verso (even) pages {verso_openers}; "
        "every chapter must open on a recto (odd) page"
    )

    # ── right_edge_max_error: ≤ baseline (drift; justified raggedness).
    # The epsilon absorbs cross-version PyMuPDF float noise; a real
    # justification regression is orders of magnitude larger.
    if "right_edge_max_error" in fixture.probes:
        actual = probes.right_edge_max_error_mm(doc)
        limit = baseline.right_edge_max_error_mm + _DRIFT_EPSILON_MM  # type: ignore[operator]
        assert actual <= limit, (
            f"right_edge_max_error drift: {actual:.4f} mm > baseline "
            f"{baseline.right_edge_max_error_mm:.4f} mm. The justified-body "
            "raggedness worsened — review the narrare-roman body engine or run "
            "`just golden-update` after review."
        )

    # ── word_gap_stdev: ≤ baseline (drift; grey-value uniformity).
    if "word_gap_stdev" in fixture.probes:
        actual = probes.word_gap_stdev_pt(doc)
        limit = baseline.word_gap_stdev_pt + _DRIFT_EPSILON_PT  # type: ignore[operator]
        assert actual <= limit, (
            f"word_gap_stdev drift: {actual:.4f} pt > baseline "
            f"{baseline.word_gap_stdev_pt:.4f} pt. Inter-word spacing became "
            "less uniform — review the justification engine or run "
            "`just golden-update` after review."
        )

    # ── scene_break_present: the asterism renders as a centred ornament.
    if "scene_break_present" in fixture.probes:
        sb = probes.find_scene_break(doc)
        assert sb is not None, (
            "no scene-break ornament found (no '*' glyphs) — the `show divider` "
            "rule did not render the asterism"
        )
        assert sb.found, (
            f"scene-break ornament malformed: n_stars={sb.n_stars}, "
            f"centered={sb.centered}, clears_margin={sb.clears_margin}"
        )


# ── Regeneration path (--golden-update mode) ───────────────────────────────


def _regenerate(fixture: CorpusFixture, doc: pymupdf.Document, sha256_hex: str) -> None:
    """Capture the current drift metrics and write them as the new baseline."""
    baseline = baselines.capture_baseline(doc, fixture, sha256_hex)
    baselines.save_baseline(fixture, baseline)
    print(
        f"\n  [golden-update] {fixture.name}: sha256={sha256_hex[:16]}…, "
        f"pages={baseline.page_count}, "
        f"right_edge={baseline.right_edge_max_error_mm}, "
        f"word_gap={baseline.word_gap_stdev_pt}"
    )
