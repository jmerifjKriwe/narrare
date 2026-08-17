"""Golden acceptance test for the pandoc DOCX renderer (C3 — design §6.2).

Design §6.2 (binding): verification is a golden test on the UNZIPPED
``word/document.xml`` — a docx is a zip whose container timestamps make
byte-diffing the FILE impossible.

Normalization ruling (evidence-based, locked in the plan)
---------------------------------------------------------
Empirically verified against pandoc 3.10.1 (the pinned version): rendering
the same input twice with the same ``--reference-doc`` yields BYTE-IDENTICAL
``word/document.xml`` (and styles.xml, numbering.xml, …). The ONLY entry
that varies is ``docProps/core.xml`` (``dcterms:created``/``modified``
wall-clock stamps). Pandoc emits no ``w:rsid`` attributes and no dates in
``document.xml`` itself. Normalization is therefore EXTRACT-ONLY: read the
``word/document.xml`` zip entry and compare its sha256 — strip nothing.
Zip-entry metadata (timestamps) lives in the zip directory, never in the
entry bytes.

Tiers (mirrors test_golden_pages.py / test_epubcheck.py):
1. Determinism probe — two consecutive renders produce identical
   document.xml bytes (the premise the golden rests on).
2. THE golden — sha256(document.xml) == the committed baseline. Intentional
   drift (pandoc pin bump, reference.docx regeneration) is blessed via
   ``--golden-update`` (the conftest option) — review + commit the diff.
3. Manuscript-format styles — the OUTPUT word/styles.xml carries the four
   binding properties (document.xml only REFERENCES styles; without this
   class the headline feature would be unverified).
4. Content — title/chapters/bookmarks/prose reach document.xml.
5. Reference-asset reproducibility — the committed reference.docx equals
   generator(pandoc's default) for the INSTALLED pandoc (RULE-08: tests/
   spawns are exempt — the checker's documented test-harness carve-out).

Pandoc-version coupling (honest note): tiers 2 + 5 are pinned to the
installed pandoc. CI installs 3.10.1 (install_export_toolchain.sh); a
local dev machine with a different pandoc may fail these — the documented
response is the regeneration procedure in
apps/api/narrare/export/pandoc/README.md, NOT a skip.

Non-LLM (deterministic render pipeline; no agent, no prompt).
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from uuid import UUID

import pytest
from scripts.generate_reference_docx import build_reference_docx

from narrare.export.options import ExportFormat, ExportOptions
from narrare.export.renderers.pandoc_docx import PandocDocxRenderer
from narrare_core.export.contracts import ChapterMeta, Language, NormalizedManuscript

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

#: The committed baseline for the document.xml golden (this dir/../baselines).
_BASELINE_FILE = Path(__file__).resolve().parent / "baselines" / "docx-manuscript.json"
_BASELINE_SCHEMA_VERSION = 1

#: The committed reference asset (tests/golden/export → repo root → vendor).
_COMMITTED_REFERENCE = (
    Path(__file__).resolve().parents[3]
    / "apps"
    / "api"
    / "narrare"
    / "export"
    / "pandoc"
    / "reference.docx"
)

pytestmark = [
    pytest.mark.golden_pages,
    pytest.mark.skipif(
        shutil.which("pandoc") is None,
        reason="pandoc not installed (install via scripts/install_export_toolchain.sh)",
    ),
]

#: Deterministic chapter ids (uuid4 entropy must never enter asserted output).
_CHAPTER_IDS = (
    UUID("00000000-0000-0000-0000-0000000000e1"),
    UUID("00000000-0000-0000-0000-0000000000e2"),
)

#: The committed corpus content (inline — the test_epubcheck.py pattern for
#: non-PDF golden tests; the PDF CORPUS registry stays untouched). Covers:
#: two chapters (Heading2), multi-paragraph bodies (FirstParagraph AND
#: BodyText styles), one canonical scene break (<hr class="scene-break"/>),
#: one German prose paragraph (UTF-8 round-trip into document.xml).
_SEMANTIC_HTML = (
    "<h2>Chapter One</h2>\n"
    "<p>The lighthouse keeper counted the steps again — forty-two, "
    "always forty-two.</p>\n"
    "<p>Elsewhere in the tower, dust settled over the ledgers no one "
    "read.</p>\n"
    '<hr class="scene-break"/>\n'
    "<p>Morning arrived with gulls.</p>\n"
    "<h2>Chapter Two</h2>\n"
    "<p>Die Wirtin stellte zwei Tassen auf den Tisch und schwieg.</p>\n"
    "<p>Neither of them mentioned the lighthouse.</p>\n"
)


def _manuscript() -> NormalizedManuscript:
    return NormalizedManuscript(
        semantic_html=_SEMANTIC_HTML,
        title="The Lighthouse Years",
        author="Ada Quill",
        language=Language.EN,
        chapters=[
            ChapterMeta(
                chapter_id=_CHAPTER_IDS[0], title="Chapter One", position=0, volume_id=None
            ),
            ChapterMeta(
                chapter_id=_CHAPTER_IDS[1], title="Chapter Two", position=1, volume_id=None
            ),
        ],
    )


async def _render_entries() -> dict[str, bytes]:
    """Render through the REAL adapter; return the docx zip entries."""
    artifact = await PandocDocxRenderer().render(
        _manuscript(), ExportOptions(format=ExportFormat.DOCX)
    )
    try:
        with zipfile.ZipFile(artifact.path) as z:
            return {name: z.read(name) for name in z.namelist()}
    finally:
        artifact.path.unlink(missing_ok=True)


def _write_baseline(sha_hex: str) -> None:
    """--golden-update path: write the baseline (pretty, sorted — the
    tests/golden/export/harness/baselines.py save convention)."""
    payload = {
        "schema_version": _BASELINE_SCHEMA_VERSION,
        "document_xml_sha256": sha_hex,
    }
    _BASELINE_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _style(styles_root: ET.Element, style_id: str) -> ET.Element:
    for style in styles_root.findall(f"{_W}style"):
        if style.get(f"{_W}styleId") == style_id:
            return style
    raise AssertionError(f"style {style_id!r} missing from output styles.xml")


@pytest.fixture(scope="module")
def golden_update(request: pytest.FixtureRequest) -> bool:
    """True when ``--golden-update`` was passed (baseline regeneration mode)."""
    return bool(request.config.getoption("--golden-update"))


class TestDocumentXmlDeterminism:
    @pytest.mark.asyncio
    async def test_two_consecutive_renders_are_byte_identical(self) -> None:
        first, second = await _render_entries(), await _render_entries()
        assert first["word/document.xml"] == second["word/document.xml"]


class TestGoldenDocumentXml:
    """THE design-§12 gate: sha256 of the extracted document.xml."""

    @pytest.mark.asyncio
    async def test_document_xml_matches_committed_baseline(self, golden_update: bool) -> None:
        entries = await _render_entries()
        sha = hashlib.sha256(entries["word/document.xml"]).hexdigest()
        if golden_update:
            _write_baseline(sha)
            return
        assert _BASELINE_FILE.is_file(), (
            "baseline missing — regenerate via: uv run pytest "
            "tests/golden/export/test_docx_golden.py -v -m golden_pages "
            "--golden-update -p no:xdist"
        )
        baseline = json.loads(_BASELINE_FILE.read_text(encoding="utf-8"))
        assert baseline["schema_version"] == _BASELINE_SCHEMA_VERSION
        assert sha == baseline["document_xml_sha256"], (
            f"document.xml drift: sha256 {sha[:16]}… != baseline "
            f"{str(baseline['document_xml_sha256'])[:16]}… — intentional drift "
            f"(pandoc pin bump, reference.docx regeneration) is blessed via "
            f"--golden-update; review + commit the diff."
        )


class TestManuscriptFormatStyles:
    """The four binding §6.1 properties in the OUTPUT word/styles.xml."""

    @pytest.mark.asyncio
    async def test_manuscript_format_reaches_output_styles(self) -> None:
        entries = await _render_entries()
        styles = ET.fromstring(entries["word/styles.xml"])

        # Times 12 pt + 1.5 line spacing on the document base.
        normal = _style(styles, "Normal")
        normal_fonts = normal.find(f"{_W}rPr/{_W}rFonts")
        assert normal_fonts is not None
        assert normal_fonts.get(f"{_W}ascii") == "Times New Roman"
        normal_sz = normal.find(f"{_W}rPr/{_W}sz")
        assert normal_sz is not None
        assert normal_sz.get(f"{_W}val") == "24"
        normal_spacing = normal.find(f"{_W}pPr/{_W}spacing")
        assert normal_spacing is not None
        assert normal_spacing.get(f"{_W}line") == "360"
        assert normal_spacing.get(f"{_W}lineRule") == "auto"

        # 0.5" first-line indent on body paragraphs.
        body_ind = _style(styles, "BodyText").find(f"{_W}pPr/{_W}ind")
        assert body_ind is not None
        assert body_ind.get(f"{_W}firstLine") == "720"

        # Centred, Times, 12 pt chapter headings.
        heading = _style(styles, "Heading2")
        jc = heading.find(f"{_W}pPr/{_W}jc")
        assert jc is not None
        assert jc.get(f"{_W}val") == "center"
        heading_fonts = heading.find(f"{_W}rPr/{_W}rFonts")
        assert heading_fonts is not None
        assert heading_fonts.get(f"{_W}ascii") == "Times New Roman"
        heading_sz = heading.find(f"{_W}rPr/{_W}sz")
        assert heading_sz is not None
        assert heading_sz.get(f"{_W}val") == "24"


class TestContentReachesDocumentXml:
    @pytest.mark.asyncio
    async def test_title_chapters_bookmarks_prose(self) -> None:
        entries = await _render_entries()
        document = ET.fromstring(entries["word/document.xml"])
        texts = [t.text or "" for t in document.iter(f"{_W}t")]
        joined = "\n".join(texts)

        assert "The Lighthouse Years" in joined  # title (metadata → Title style)
        heading_styles = [
            pstyle.get(f"{_W}val")
            for p in document.iter(f"{_W}p")
            if (pstyle := p.find(f"{_W}pPr/{_W}pStyle")) is not None
        ]
        assert heading_styles.count("Heading2") == 2
        assert "Chapter One" in joined
        assert "Chapter Two" in joined
        bookmarks = {b.get(f"{_W}name") for b in document.iter(f"{_W}bookmarkStart")}
        assert "chapter-one" in bookmarks
        assert "chapter-two" in bookmarks
        # Prose survives verbatim (incl. the German UTF-8 paragraph).
        assert "forty-two, always forty-two" in joined
        assert "Die Wirtin stellte zwei Tassen auf den Tisch und schwieg." in joined
        # Both paragraph styles are used (first-after-heading vs body).
        assert heading_styles.count("FirstParagraph") >= 2
        assert heading_styles.count("BodyText") >= 2


class TestReferenceAssetReproducible:
    def test_committed_reference_equals_generator_output(self) -> None:
        """Committed asset == build_reference_docx(pandoc default).

        Pins the vendor-README regeneration contract: the asset in-tree is
        exactly what the documented procedure produces for the installed
        pandoc. A mismatch after a pandoc bump is the signal to regenerate
        the asset + golden baseline together.
        """
        base = subprocess.run(
            ["pandoc", "--print-default-data-file", "reference.docx"],
            check=True,
            capture_output=True,
        ).stdout
        assert build_reference_docx(base) == _COMMITTED_REFERENCE.read_bytes()
