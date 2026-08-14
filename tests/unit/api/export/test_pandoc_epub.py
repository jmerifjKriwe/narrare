"""Unit tests for the pandoc EPUB renderer (Slice 4 / ADR-081).

Two layers (mirrors ``test_pandoc_md.py``):

1. **Pure unit tests** (always run, no binary): availability probe, slug,
   font-path resolution (including the D7 missing-font failure), the generated
   ``@font-face`` stylesheet, and argv construction (the four unconditional
   ``--epub-embed-font`` entries + the generated ``--css`` + metadata).
2. **Real-pandoc tests** (``_REQUIRES_PANDOC`` skip guard): the renderer
   against the actual ``pandoc`` binary — produces a valid EPUB zip with the
   four Libertinus variants embedded.

The EPUBCheck validation gate lives in ``tests/golden/export/`` (it needs the
CI-only ``epubcheck`` binary + the ``golden_pages`` marker).
"""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path
from uuid import uuid4

import pytest

from narrare.export.errors import ExportRenderError
from narrare.export.options import EpubOptions, ExportFormat, ExportOptions
from narrare.export.renderers import pandoc_epub
from narrare.export.renderers.pandoc_epub import (
    PandocEpubRenderer,
    _build_argv,
    _build_font_face_css,
    _resolve_font_paths,
    _slugify,
)
from narrare_core.export.contracts import ChapterMeta, Language, NormalizedManuscript

_REQUIRES_PANDOC = pytest.mark.skipif(
    shutil.which("pandoc") is None,
    reason="pandoc not installed (install via scripts/install_export_toolchain.sh)",
)

#: The four Libertinus Serif variants the renderer must embed (D7). Mirrors the
#: renderer's font policy as observed from the bundled ``typst/fonts/`` tree —
#: kept test-local so the unit test does not reach into a private module const.
_EXPECTED_FONT_FILES: frozenset[str] = frozenset(
    {
        "libertinus-serif-regular.otf",
        "libertinus-serif-italic.otf",
        "libertinus-serif-bold.otf",
        "libertinus-serif-bolditalic.otf",
    }
)


def _normalized(
    semantic_html: str = "<h2>Chapter One</h2>\n<p>Body text.</p>",
    *,
    title: str = "Test Novel",
    author: str = "Test Author",
    language: Language = Language.EN,
    isbn: str | None = None,
    description: str | None = None,
) -> NormalizedManuscript:
    """Build a NormalizedManuscript with a single placeholder chapter."""
    return NormalizedManuscript(
        semantic_html=semantic_html,
        title=title,
        author=author,
        language=language,
        chapters=[ChapterMeta(chapter_id=uuid4(), title="C1", position=0, volume_id=None)],
        isbn=isbn,
        description=description,
    )


# ── Pure unit tests (always run) ────────────────────────────────────────────


class TestFormatAndAvailability:
    def test_format_is_epub(self) -> None:
        assert PandocEpubRenderer().format is ExportFormat.EPUB

    def test_is_available_true_when_pandoc_on_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(shutil, "which", lambda _cmd: "/usr/bin/pandoc")
        assert PandocEpubRenderer().is_available() is True

    def test_is_available_false_when_pandoc_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(shutil, "which", lambda _cmd: None)
        assert PandocEpubRenderer().is_available() is False

    def test_availability_is_cached(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = 0

        def which(_cmd: str) -> str | None:
            nonlocal calls
            calls += 1
            return "/usr/bin/pandoc"

        monkeypatch.setattr(shutil, "which", which)
        renderer = PandocEpubRenderer()
        renderer.is_available()
        renderer.is_available()
        assert calls == 1


class TestSlugify:
    @pytest.mark.parametrize(
        ("title", "expected"),
        [
            ("My Novel", "my-novel"),
            ("My Novel!", "my-novel"),
            ("", "manuscript"),
            ("!!!", "manuscript"),
            ("Café Münster", "café-münster"),
        ],
    )
    def test_slugify_sanitizes_title(self, title: str, expected: str) -> None:
        assert _slugify(title) == expected


class TestResolveFontPaths:
    """D7: the four bundled variants resolve package-relatively; missing → typed error."""

    def test_returns_four_variants_pointing_at_bundled_fonts(self) -> None:
        paths = _resolve_font_paths()
        names = {p.name for p in paths}
        assert names == set(_EXPECTED_FONT_FILES)
        # Package-relative resolution: every path exists and lives under a
        # bundled ``fonts/`` directory (the renderer resolves via __file__).
        for path in paths:
            assert path.is_file(), f"bundled font missing: {path}"
            assert path.parent.name == "fonts"

    def test_missing_font_raises_export_render_error_no_silent_fallback(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        # Redirect the font dir to an empty dir → all four variants "missing".
        monkeypatch.setattr(pandoc_epub, "_FONTS_DIR", tmp_path)
        with pytest.raises(ExportRenderError, match="Libertinus font missing"):
            _resolve_font_paths()


class TestFontFaceCss:
    def test_css_has_one_face_rule_per_variant_plus_body_family(self) -> None:
        paths = _resolve_font_paths()
        css = _build_font_face_css(paths)

        assert css.count("@font-face") == len(_EXPECTED_FONT_FILES)
        # Every variant basename is referenced by a relative font url.
        for name in _EXPECTED_FONT_FILES:
            assert f"url(../fonts/{name})" in css
        # Body rule binds the rendered text to Libertinus (D7 no-silent-fallback).
        assert 'font-family: "Libertinus Serif"' in css
        assert "body {" in css

    def test_css_variant_styles_match_the_font_policy(self) -> None:
        paths = _resolve_font_paths()
        css = _build_font_face_css(paths)

        # italic + bold + bolditalic variants carry their style/weight pair.
        assert "font-style: italic;" in css
        assert "font-weight: bold;" in css
        # Regular variant is normal/normal (the default body face).
        assert "font-style: normal;" in css
        assert "font-weight: normal;" in css


class TestBuildArgv:
    """The argv carries the D7 embedding unconditionally — no flag."""

    def test_argv_has_four_epub_embed_font_entries_unconditionally(self) -> None:
        manuscript = _normalized()
        paths = _resolve_font_paths()
        css_path = Path("/tmp/dummy-fonts.css")
        output_path = Path("/tmp/out.epub")

        argv = _build_argv(manuscript, EpubOptions(), paths, css_path, output_path)

        embed_entries = [a for a in argv if a.startswith("--epub-embed-font=")]
        assert len(embed_entries) == 4
        # Each entry points at a bundled .otf (absolute, package-relative path).
        for path, entry in zip(paths, embed_entries, strict=True):
            assert entry == f"--epub-embed-font={path}"
            assert path.is_file()

    def test_argv_includes_generated_font_css_unconditionally(self) -> None:
        manuscript = _normalized()
        paths = _resolve_font_paths()
        css_path = Path("/tmp/dummy-fonts.css")
        output_path = Path("/tmp/out.epub")

        argv = _build_argv(manuscript, EpubOptions(), paths, css_path, output_path)

        assert f"--css={css_path}" in argv

    def test_argv_carries_title_author_language_metadata(self) -> None:
        manuscript = _normalized(title="My Novel", author="Jane Doe", language=Language.DE)
        paths = _resolve_font_paths()
        argv = _build_argv(
            manuscript, EpubOptions(), paths, Path("/tmp/f.css"), Path("/tmp/o.epub")
        )
        assert "--metadata=title:My Novel" in argv
        assert "--metadata=author:Jane Doe" in argv
        assert "--metadata=lang:de" in argv
        assert "--from=html" in argv
        assert "--to=epub3" in argv
        assert "--toc" in argv

    def test_argv_appends_user_css_and_cover_when_provided(self) -> None:
        manuscript = _normalized()
        paths = _resolve_font_paths()
        opts = EpubOptions(css="/tmp/user.css", cover_image_path="/tmp/cover.png")

        argv = _build_argv(manuscript, opts, paths, Path("/tmp/f.css"), Path("/tmp/o.epub"))

        # Generated font CSS first, then the user CSS (both via --css).
        css_entries = [a for a in argv if a.startswith("--css=")]
        assert css_entries == [f"--css={Path('/tmp/f.css')}", "--css=/tmp/user.css"]
        assert "--epub-cover-image=/tmp/cover.png" in argv

    def test_argv_writes_to_output_path(self) -> None:
        manuscript = _normalized()
        paths = _resolve_font_paths()
        output_path = Path("/tmp/out.epub")
        argv = _build_argv(manuscript, EpubOptions(), paths, Path("/tmp/f.css"), output_path)
        assert argv[-1] == "--output=/tmp/out.epub"


class TestIsbnDescriptionArgv:
    """ISBN/description ride the manuscript (post-normalizer) into pandoc
    ``--metadata identifier/description`` flags — only when actually set.

    Empirically verified against pandoc 3.10.1 (see the golden suite for the
    OPF side): ``identifier`` REPLACES pandoc's uuid default as the package
    unique-identifier; a bare ISBN is wrapped into the idiomatic EPUB3
    ``urn:isbn:`` URN (no scheme attribute — the URN prefix carries the type).
    """

    def test_isbn_adds_urn_isbn_identifier_flag(self) -> None:
        manuscript = _normalized(isbn="978-3-16-148410-0")
        argv = _build_argv(
            manuscript,
            EpubOptions(),
            _resolve_font_paths(),
            Path("/tmp/f.css"),
            Path("/tmp/o.epub"),
        )
        assert "--metadata=identifier:urn:isbn:978-3-16-148410-0" in argv

    def test_isbn_already_uri_form_passes_through_undoubled(self) -> None:
        """A caller-supplied URI (urn:… or scheme://…) is never double-wrapped."""
        manuscript = _normalized(isbn="urn:isbn:978-3-16-148410-0")
        argv = _build_argv(
            manuscript,
            EpubOptions(),
            _resolve_font_paths(),
            Path("/tmp/f.css"),
            Path("/tmp/o.epub"),
        )
        identifier_entries = [a for a in argv if a.startswith("--metadata=identifier:")]
        assert identifier_entries == ["--metadata=identifier:urn:isbn:978-3-16-148410-0"]

    def test_isbn_absent_adds_no_identifier_flag(self) -> None:
        """No ISBN → no identifier flag → pandoc keeps its uuid default."""
        manuscript = _normalized()
        argv = _build_argv(
            manuscript,
            EpubOptions(),
            _resolve_font_paths(),
            Path("/tmp/f.css"),
            Path("/tmp/o.epub"),
        )
        assert not any(a.startswith("--metadata=identifier:") for a in argv)

    def test_isbn_empty_string_treated_as_unset(self) -> None:
        manuscript = _normalized(isbn="")
        argv = _build_argv(
            manuscript,
            EpubOptions(),
            _resolve_font_paths(),
            Path("/tmp/f.css"),
            Path("/tmp/o.epub"),
        )
        assert not any(a.startswith("--metadata=identifier:") for a in argv)

    def test_description_adds_description_flag(self) -> None:
        manuscript = _normalized(description="A tale of lighthouses and the sea.")
        argv = _build_argv(
            manuscript,
            EpubOptions(),
            _resolve_font_paths(),
            Path("/tmp/f.css"),
            Path("/tmp/o.epub"),
        )
        assert "--metadata=description:A tale of lighthouses and the sea." in argv

    def test_description_absent_adds_no_flag(self) -> None:
        manuscript = _normalized()
        argv = _build_argv(
            manuscript,
            EpubOptions(),
            _resolve_font_paths(),
            Path("/tmp/f.css"),
            Path("/tmp/o.epub"),
        )
        assert not any(a.startswith("--metadata=description:") for a in argv)

    def test_description_empty_string_treated_as_unset(self) -> None:
        manuscript = _normalized(description="")
        argv = _build_argv(
            manuscript,
            EpubOptions(),
            _resolve_font_paths(),
            Path("/tmp/f.css"),
            Path("/tmp/o.epub"),
        )
        assert not any(a.startswith("--metadata=description:") for a in argv)


# ── Real-pandoc tests (skipif guarded) ──────────────────────────────────────


class TestRenderEpub:
    """``render()`` produces a real EPUB3 zip with embedded Libertinus (D7)."""

    @_REQUIRES_PANDOC
    @pytest.mark.asyncio
    async def test_render_produces_valid_epub_artifact(self) -> None:
        manuscript = _normalized()
        artifact = await PandocEpubRenderer().render(
            manuscript, ExportOptions(format=ExportFormat.EPUB)
        )
        try:
            assert artifact.format is ExportFormat.EPUB
            assert artifact.media_type == "application/epub+zip"
            assert artifact.suggested_filename == "test-novel.epub"
            assert artifact.path.is_file()
            # It is a real zip (EPUB container).
            with zipfile.ZipFile(artifact.path) as z:
                assert "mimetype" in z.namelist()
                assert "META-INF/container.xml" in z.namelist()
        finally:
            artifact.path.unlink(missing_ok=True)

    @_REQUIRES_PANDOC
    @pytest.mark.asyncio
    async def test_render_embeds_four_libertinus_variants(self) -> None:
        manuscript = _normalized()
        artifact = await PandocEpubRenderer().render(
            manuscript, ExportOptions(format=ExportFormat.EPUB)
        )
        try:
            with zipfile.ZipFile(artifact.path) as z:
                names = z.namelist()
            font_entries = {n.split("/")[-1] for n in names if n.endswith(".otf")}
            assert font_entries == set(_EXPECTED_FONT_FILES)
        finally:
            artifact.path.unlink(missing_ok=True)

    @_REQUIRES_PANDOC
    @pytest.mark.asyncio
    async def test_render_cleans_up_on_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A render failure unlinks the partial EPUB + the temp font CSS (RULE-11)."""
        from narrare.export.renderers import pandoc_epub as pe

        async def _boom(*_args: object, **_kwargs: object) -> bytes:
            raise ExportRenderError("simulated pandoc failure")

        monkeypatch.setattr(pe, "run_pandoc", _boom)

        manuscript = _normalized()
        with pytest.raises(ExportRenderError, match="simulated pandoc failure"):
            await PandocEpubRenderer().render(manuscript, ExportOptions(format=ExportFormat.EPUB))
        # No partial .epub leaked in the temp dir (best-effort sweep — the
        # exact path is gone, so nothing named *-export.epub remains new).
        leftover = list(Path("/tmp").glob("narrare-*-export.epub"))
        assert leftover == []
