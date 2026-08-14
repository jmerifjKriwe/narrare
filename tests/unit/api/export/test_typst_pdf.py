"""Pure unit tests for the Typst PDF renderer (Slice 6 / ADR-081).

Always run (no binary required): availability probe, slug, Typst string
escaping, ``@``-sign escaping (F-6), margins serialization, font-path
resolution (including the D3 missing-font failure), config + wrapper
generation.

The real-binary integration + seam-fix regression tests (F-1/F-6/F-7, font
embedding, byte reproducibility, failure path) live in
:mod:`test_typst_pdf_render`.
"""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

import pytest

from narrare.export.contracts import NarrareRomanConfig
from narrare.export.errors import ExportRenderError
from narrare.export.options import (
    ExportFormat,
    MirroredMargins,
    PaperSize,
)
from narrare.export.renderers import typst as typst_mod
from narrare.export.renderers.typst import (
    TypstPdfRenderer,
    _build_config_block,
    _build_wrapper,
    _escape_at_signs,
    _margins_to_typst,
    _resolve_font_paths,
    _slugify,
    _typst_string,
)
from narrare_core.export.contracts import Language

if TYPE_CHECKING:
    from pathlib import Path


# ── Pure unit tests ─────────────────────────────────────────────────────────


class TestFormatAndAvailability:
    def test_format_is_pdf(self) -> None:
        assert TypstPdfRenderer().format is ExportFormat.PDF

    def test_is_available_true_when_typst_on_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(shutil, "which", lambda _cmd: "/usr/bin/typst")
        assert TypstPdfRenderer().is_available() is True

    def test_is_available_false_when_typst_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(shutil, "which", lambda _cmd: None)
        assert TypstPdfRenderer().is_available() is False

    def test_availability_is_cached(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = 0

        def which(_cmd: str) -> str | None:
            nonlocal calls
            calls += 1
            return "/usr/bin/typst"

        monkeypatch.setattr(shutil, "which", which)
        renderer = TypstPdfRenderer()
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


class TestTypstString:
    def test_escapes_backslash_and_quote(self) -> None:
        assert _typst_string('He said "hi"') == 'He said \\"hi\\"'
        assert _typst_string(r"path\to\file") == r"path\\to\\file"

    def test_leaves_at_sign_intact(self) -> None:
        """@ is NOT special inside a Typst string literal (only in markup)."""
        assert _typst_string("user@host") == "user@host"


class TestEscapeAtSigns:
    """F-6: defensive @ escaping on the pandoc Typst body."""

    def test_escapes_bare_at_sign(self) -> None:
        assert _escape_at_signs("see @preview/foo") == r"see \@preview/foo"

    def test_does_not_double_escape_already_escaped(self) -> None:
        assert _escape_at_signs(r"already \@escaped") == r"already \@escaped"

    def test_no_at_sign_unchanged(self) -> None:
        assert _escape_at_signs("no at sign here") == "no at sign here"

    def test_multiple_bare_at_signs_all_escaped(self) -> None:
        result = _escape_at_signs("@one and @two")
        assert result == r"\@one and \@two"


class TestMarginsToTypst:
    def test_none_yields_typst_none(self) -> None:
        assert _margins_to_typst(None) == "none"

    def test_margins_serialize_to_typst_dict(self) -> None:
        margins = MirroredMargins(inside_mm=18.0, outside_mm=15.0, top_mm=22.0, bottom_mm=22.0)
        result = _margins_to_typst(margins)
        assert "inside_mm: 18.0" in result
        assert "outside_mm: 15.0" in result
        assert "top_mm: 22.0" in result
        assert "bottom_mm: 22.0" in result


class TestResolveFontPaths:
    """D3: the four bundled variants resolve package-relatively; missing → error."""

    def test_returns_four_variants_pointing_at_bundled_fonts(self) -> None:
        paths = _resolve_font_paths()
        names = {p.name for p in paths}
        assert names == {
            "libertinus-serif-regular.otf",
            "libertinus-serif-italic.otf",
            "libertinus-serif-bold.otf",
            "libertinus-serif-bolditalic.otf",
        }
        for path in paths:
            assert path.is_file(), f"bundled font missing: {path}"
            assert path.parent.name == "fonts"

    def test_missing_font_raises_export_render_error_no_silent_fallback(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(typst_mod, "_FONTS_DIR", tmp_path)
        with pytest.raises(ExportRenderError, match="Libertinus font missing"):
            _resolve_font_paths()


class TestBuildConfigBlock:
    """The config dict carries every key narrare-roman reads."""

    def test_config_block_contains_all_typst_keys(self) -> None:
        config = NarrareRomanConfig(language=Language.EN, title="My Novel", author="Jane Doe")
        block = _build_config_block(config)
        for key in (
            "paper-size",
            "body-font",
            "body-size-pt",
            "leading-ratio",
            "margins",
            "title: booktitle",
            "author: bookauthor",
            "language",
            "include-toc",
            "running-head-preset",
            "scene-break-style",
            "widow-orphan-protection",
        ):
            assert key in block, f"missing config key '{key}' in block"

    def test_config_block_uses_kebab_case_paper_size(self) -> None:
        config = NarrareRomanConfig(
            paper_size=PaperSize.A5,
            language=Language.EN,
            title="T",
            author="A",
        )
        assert 'paper-size: "a5"' in _build_config_block(config)


class TestBuildWrapper:
    """The wrapper source carries the import, config, title page, and body."""

    def test_wrapper_imports_lib_typ_absolute(self) -> None:
        config = NarrareRomanConfig(language=Language.EN, title="T", author="A")
        wrapper = _build_wrapper(config, "= Chapter\nBody.")
        assert '#import "/lib.typ"' in wrapper

    def test_wrapper_defines_title_and_author_as_scalar_strings(self) -> None:
        """F-7: title/author are scalar Typst strings, never arrays."""
        config = NarrareRomanConfig(language=Language.EN, title='Quote "test"', author="Jane")
        wrapper = _build_wrapper(config, "Body.")
        # Escaped string literal (F-7 scalar).
        assert '#let booktitle = "Quote \\"test\\""' in wrapper
        assert '#let bookauthor = "Jane"' in wrapper

    def test_wrapper_includes_title_page_with_title_and_author(self) -> None:
        config = NarrareRomanConfig(language=Language.EN, title="My Book", author="My Author")
        wrapper = _build_wrapper(config, "Body.")
        assert "#title-page[" in wrapper
        assert "#booktitle" in wrapper
        assert "#bookauthor" in wrapper

    def test_wrapper_includes_frontmatter_toc_when_include_toc_true(self) -> None:
        config = NarrareRomanConfig(language=Language.EN, title="T", author="A", include_toc=True)
        wrapper = _build_wrapper(config, "Body.")
        assert "#frontmatter[" in wrapper
        assert "#toc()" in wrapper

    def test_wrapper_omits_frontmatter_when_include_toc_false(self) -> None:
        config = NarrareRomanConfig(language=Language.EN, title="T", author="A", include_toc=False)
        wrapper = _build_wrapper(config, "Body.")
        assert "#frontmatter" not in wrapper
        assert "#toc()" not in wrapper

    def test_wrapper_escapes_at_signs_in_body(self) -> None:
        """F-6: bare @ in the pandoc body is defensively escaped."""
        config = NarrareRomanConfig(language=Language.EN, title="T", author="A")
        wrapper = _build_wrapper(config, "See @preview/lib for info.")
        assert r"\@preview/lib" in wrapper

    def test_wrapper_wraps_body_in_body_phase_marker(self) -> None:
        config = NarrareRomanConfig(language=Language.EN, title="T", author="A")
        wrapper = _build_wrapper(config, "= Chapter\nBody text.")
        assert "#body[" in wrapper
        assert "= Chapter" in wrapper
