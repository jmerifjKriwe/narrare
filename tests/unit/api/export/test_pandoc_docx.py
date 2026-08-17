"""Unit + real-pandoc tests for the pandoc DOCX renderer (C3 — design §6).

Two layers (mirrors test_pandoc_md.py):

1. **Pure unit tests** (always run, no binary): availability probe, slug
   derivation, missing-reference fast-fail (no silent fallback to pandoc's
   default styles).
2. **Real-pandoc tests** (``_REQUIRES_PANDOC`` skip guard): render → a
   well-formed docx zip whose document.xml carries the chapters as
   Heading2 paragraphs + the title, and whose styles.xml carries the
   manuscript format from the reference doc.

The full golden verification (byte-determinism + committed baseline) lives
in ``tests/golden/export/test_docx_golden.py`` (Task 4).
"""

from __future__ import annotations

import shutil
import zipfile
from uuid import UUID

import pytest

from narrare.export.errors import ExportRenderError
from narrare.export.options import ExportFormat, ExportOptions
from narrare.export.renderers.pandoc_docx import PandocDocxRenderer, _slugify
from narrare_core.export.contracts import ChapterMeta, Language, NormalizedManuscript

_REQUIRES_PANDOC = pytest.mark.skipif(
    shutil.which("pandoc") is None,
    reason="pandoc not installed (install via scripts/install_export_toolchain.sh)",
)

#: Deterministic chapter ids (the golden file shares this practice — uuid4
#: entropy must never leak into anything a test asserts on).
_CHAPTER_ONE_ID = UUID("00000000-0000-0000-0000-0000000000d1")
_CHAPTER_TWO_ID = UUID("00000000-0000-0000-0000-0000000000d2")


def _normalized(
    semantic_html: str = (
        "<h2>Chapter One</h2>\n<p>Body text here.</p>\n"
        "<h2>Chapter Two</h2>\n<p>More prose follows.</p>"
    ),
    *,
    title: str = "Test Novel",
    author: str = "Test Author",
    language: Language = Language.EN,
) -> NormalizedManuscript:
    return NormalizedManuscript(
        semantic_html=semantic_html,
        title=title,
        author=author,
        language=language,
        chapters=[
            ChapterMeta(chapter_id=_CHAPTER_ONE_ID, title="C1", position=0, volume_id=None),
            ChapterMeta(chapter_id=_CHAPTER_TWO_ID, title="C2", position=1, volume_id=None),
        ],
    )


# ── Pure unit tests (always run) ────────────────────────────────────────────


class TestFormatAndAvailability:
    def test_format_is_docx(self) -> None:
        assert PandocDocxRenderer().format is ExportFormat.DOCX

    def test_export_format_enum_has_docx_member(self) -> None:
        assert ExportFormat("docx") is ExportFormat.DOCX
        assert ExportFormat.DOCX.value == "docx"

    def test_is_available_true_when_pandoc_on_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(shutil, "which", lambda _cmd: "/usr/bin/pandoc")
        assert PandocDocxRenderer().is_available() is True

    def test_is_available_false_when_pandoc_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(shutil, "which", lambda _cmd: None)
        # Fresh instance — _available cache must start unset.
        assert PandocDocxRenderer().is_available() is False

    def test_availability_is_cached(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = 0

        def which(_cmd: str) -> str | None:
            nonlocal calls
            calls += 1
            return "/usr/bin/pandoc"

        monkeypatch.setattr(shutil, "which", which)
        renderer = PandocDocxRenderer()
        renderer.is_available()
        renderer.is_available()
        assert calls == 1  # probed once, then cached on the instance


class TestSlugify:
    @pytest.mark.parametrize(
        ("title", "expected"),
        [
            ("My Novel", "my-novel"),
            ("My Novel!", "my-novel"),
            ("A <b> & B", "a-b-b"),
            ("", "manuscript"),
            ("!!!", "manuscript"),
        ],
    )
    def test_slug(self, title: str, expected: str) -> None:
        assert _slugify(title) == expected


class TestMissingReferenceFastFail:
    def test_missing_reference_raises_export_render_error(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        from narrare.export.renderers import pandoc_docx

        monkeypatch.setattr(pandoc_docx, "_REFERENCE_DOC_PATH", tmp_path / "missing.docx")
        with pytest.raises(ExportRenderError, match="reference document missing"):
            import asyncio

            asyncio.run(
                PandocDocxRenderer().render(_normalized(), ExportOptions(format=ExportFormat.DOCX))
            )


# ── Real-pandoc tests ───────────────────────────────────────────────────────


@_REQUIRES_PANDOC
class TestRealPandocRender:
    @pytest.mark.asyncio
    async def test_render_produces_docx_with_chapters_and_title(self) -> None:
        artifact = await PandocDocxRenderer().render(
            _normalized(), ExportOptions(format=ExportFormat.DOCX)
        )
        try:
            assert artifact.format is ExportFormat.DOCX
            assert artifact.media_type == (
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
            assert artifact.suggested_filename == "test-novel.docx"

            with zipfile.ZipFile(artifact.path) as z:
                document_xml = z.read("word/document.xml").decode("utf-8")
                styles_xml = z.read("word/styles.xml").decode("utf-8")

            # Content: title (metadata → Title style) + chapters (h2 → Heading2).
            assert '<w:pStyle w:val="Title" />' in document_xml
            assert "Test Novel" in document_xml
            assert document_xml.count('<w:pStyle w:val="Heading2" />') == 2
            assert "Chapter One" in document_xml
            assert "Chapter Two" in document_xml
            # Manuscript format reached the OUTPUT styles (reference.docx wired).
            assert "Times New Roman" in styles_xml
        finally:
            artifact.path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_metadata_author_lang_reach_core_properties(self) -> None:
        manuscript = _normalized(title="Das Leuchtfeuer", author="Ada Quill")
        artifact = await PandocDocxRenderer().render(
            manuscript, ExportOptions(format=ExportFormat.DOCX)
        )
        try:
            with zipfile.ZipFile(artifact.path) as z:
                core_xml = z.read("docProps/core.xml").decode("utf-8")
            assert "<dc:title>Das Leuchtfeuer</dc:title>" in core_xml
            assert "<dc:creator>Ada Quill</dc:creator>" in core_xml
        finally:
            artifact.path.unlink(missing_ok=True)
