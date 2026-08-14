"""pandoc EPUB renderer adapter — co-owner (with ``pandoc_md.py``) of the
``pandoc`` binary invocation (RULE-08).

Implements :class:`narrare.export.contracts.ManuscriptRenderer` for
:class:`~narrare.export.contracts.ExportFormat.EPUB`. Spawns pandoc via the
shared helper in :mod:`narrare.export.renderers.pandoc_base` — never calls
``asyncio.create_subprocess_exec`` directly (RULE-08 confinement).

D7 (font policy): the **bundled Libertinus Serif** (regular/italic/bold/
bolditalic from ``apps/api/narrare/export/typst/fonts/`` — the same files the
PDF renderer compiles in, D3) is embedded **unconditionally**. There is no
``embed_fonts`` toggle (see :class:`~narrare.export.contracts.EpubOptions`):
this extends ADR-081's no-silent-font-fallback principle to EPUB.

How the embedding is wired (two pandoc mechanisms, one font policy)
------------------------------------------------------------------
Empirically, pandoc's ``--epub-embed-font`` copies each ``.otf`` into
``EPUB/fonts/`` AND registers it in the OPF manifest (``media-type=font/otf``),
but it does **not** emit the ``@font-face`` CSS that actually binds the body
to the font — pandoc's own default stylesheet still sets
``font-family: Georgia, serif``. Embedding alone therefore leaves the body
silently falling back to a reader/system font, which would violate D7.

The renderer closes that gap by generating a small ``@font-face`` stylesheet
(one rule per variant + a ``body`` font-family) and passing it via ``--css``
alongside the four ``--epub-embed-font`` entries. pandoc merges the supplied
CSS into its generated ``EPUB/styles/stylesheetN.css`` and preserves the
``src: url(../fonts/<basename>)`` relative paths (CSS at ``EPUB/styles/``,
fonts at ``EPUB/fonts/``). The Slice-4 golden test asserts the OPF manifest
declarations, the ``EPUB/fonts/`` entries, AND the ``@font-face`` rules, then
runs EPUBCheck over the rendered EPUB (the full no-silent-fallback guarantee).

EPUBCheck is invoked ONLY from the ``tests/golden/export/`` harness (CI-only),
never from production — so it is deliberately outside RULE-08 scope (only the
two production render binaries ``typst`` / ``pandoc`` are confined).

Non-LLM (no ``narrare_core.agents`` / ``narrare_core.prompts`` imports) — export
is a deterministic render pipeline.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from narrare.export.contracts import (
    Artifact,
    ExportFormat,
    ExportOptions,
)
from narrare.export.errors import ExportRenderError
from narrare.export.options import EpubOptions
from narrare.export.renderers.pandoc_base import (
    DEFAULT_TIMEOUT_SECONDS,
    run_pandoc,
)

if TYPE_CHECKING:
    from narrare_core.export.contracts import NormalizedManuscript

logger = structlog.get_logger(__name__)

#: Bundled-font directory resolved PACKAGE-RELATIVELY (``Path(__file__)``),
#: never via cwd — the background runner may execute with any working
#: directory. ``renderers/`` → ``../typst/fonts/`` (the same files the Typst
#: PDF renderer uses — D3, one bundled font).
_FONTS_DIR: Path = Path(__file__).resolve().parent.parent / "typst" / "fonts"

#: The four Libertinus Serif variants embedded unconditionally (D7). Keys are
#: the bundled basenames; values map each file to its (font-style, font-weight)
#: pair for the generated ``@font-face`` rule. Kept in lock-step with the
#: files actually shipped under ``_FONTS_DIR`` (verified at render time).
_FONT_VARIANTS: dict[str, tuple[str, str]] = {
    "libertinus-serif-regular.otf": ("normal", "normal"),
    "libertinus-serif-italic.otf": ("italic", "normal"),
    "libertinus-serif-bold.otf": ("normal", "bold"),
    "libertinus-serif-bolditalic.otf": ("italic", "bold"),
}

#: Fallback filename stem when a manuscript title has no slug-able characters.
_EMPTY_TITLE_SLUG = "manuscript"


def _slugify(title: str) -> str:
    """Reduce a manuscript title to a safe filename stem.

    Mirrors :func:`narrare.export.renderers.pandoc_md._slugify` so both pandoc
    adapters derive identical stems for the same title (consistency across the
    two formats a user might export back-to-back).
    """
    stem = re.sub(r"[^\w]+", "-", title, flags=re.UNICODE).strip("-").lower()
    return stem or _EMPTY_TITLE_SLUG


def _resolve_font_paths() -> list[Path]:
    """Resolve the four bundled Libertinus ``.otf`` paths (D7).

    Raises :class:`ExportRenderError` if any variant is missing — there is
    never a silent fallback to a system font (RULE-11 / ADR-081). Reads
    :data:`_FONTS_DIR` at call time so tests can redirect it.
    """
    paths: list[Path] = []
    for name in _FONT_VARIANTS:
        path = _FONTS_DIR / name
        if not path.is_file():
            raise ExportRenderError(
                f"Bundled Libertinus font missing (D7 no-silent-fallback): "
                f"{path}. Restore the file or reinstall the package."
            )
        paths.append(path)
    return paths


def _build_font_face_css(font_paths: list[Path]) -> str:
    """Build the ``@font-face`` stylesheet that binds the body to Libertinus.

    One ``@font-face`` rule per variant + a ``body`` rule. The ``src`` paths
    are relative to the CSS pandoc emits (``EPUB/styles/``) →
    ``../fonts/<basename>`` (the ``EPUB/fonts/`` location pandoc places the
    embedded files at — verified by the Slice-4 golden harness).
    """
    blocks: list[str] = []
    for path in font_paths:
        style, weight = _FONT_VARIANTS.get(path.name, ("normal", "normal"))
        blocks.append(
            f'@font-face {{ font-family: "Libertinus Serif"; '
            f"font-style: {style}; font-weight: {weight}; "
            f"src: url(../fonts/{path.name}); }}"
        )
    blocks.append('body { font-family: "Libertinus Serif", serif; }')
    return "\n".join(blocks)


def _write_font_face_css(font_paths: list[Path]) -> Path:
    """Write the generated font-face stylesheet to a temp ``.css`` file."""
    css = _build_font_face_css(font_paths)
    fd, raw_path = tempfile.mkstemp(suffix="-fonts.css", prefix="narrare-")
    path = Path(raw_path)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(css)
    except OSError:
        path.unlink(missing_ok=True)
        raise
    return path


def _build_argv(
    manuscript: NormalizedManuscript,
    epub_options: EpubOptions,
    font_paths: list[Path],
    css_path: Path,
    output_path: Path,
) -> list[str]:
    """Assemble the pandoc argv (without the binary name — run_pandoc adds it).

    Metadata uses pandoc's YAML-style ``--metadata=KEY:VALUE`` colon form:
    only the FIRST colon separates key from value, so titles/authors containing
    colons or ``=`` survive intact (verified empirically).
    """
    argv: list[str] = [
        "--from=html",
        "--to=epub3",
        "--toc",
        f"--metadata=title:{manuscript.title}",
        f"--metadata=author:{manuscript.author}",
        f"--metadata=lang:{manuscript.language.value}",
    ]
    # D7: four unconditional --epub-embed-font entries (no flag).
    for font_path in font_paths:
        argv.append(f"--epub-embed-font={font_path}")
    # The generated @font-face stylesheet (unconditional) + the optional user
    # CSS. pandoc accepts multiple --css flags and merges them.
    argv.append(f"--css={css_path}")
    if epub_options.css:
        argv.append(f"--css={epub_options.css}")
    if epub_options.cover_image_path:
        argv.append(f"--epub-cover-image={epub_options.cover_image_path}")
    argv.append(f"--output={output_path}")
    return argv


class PandocEpubRenderer:
    """RULE-08 renderer adapter for pandoc EPUB3 output.

    Structurally satisfies :class:`~narrare.export.contracts.ManuscriptRenderer`
    (no explicit inheritance — matches the repo's adapter convention). Embeds
    the bundled Libertinus Serif unconditionally (D7) via ``--epub-embed-font``
    + a generated ``@font-face`` stylesheet (see the module docstring for why
    both are needed).
    """

    def __init__(self) -> None:
        # Cached availability probe (RULE-11); refreshable by re-instantiating.
        self._available: bool | None = None

    @property
    def format(self) -> ExportFormat:
        """The format this renderer produces."""
        return ExportFormat.EPUB

    def is_available(self) -> bool:
        """True iff the ``pandoc`` binary is on ``$PATH`` (RULE-11).

        Cached on the instance after the first call; a missing binary degrades
        gracefully (the service reports the format unavailable).
        """
        if self._available is None:
            self._available = shutil.which("pandoc") is not None
        return self._available

    async def render(
        self,
        manuscript: NormalizedManuscript,
        options: ExportOptions,
    ) -> Artifact:
        """Render ``manuscript`` to an EPUB3 artifact with embedded Libertinus.

        Pandoc writes the EPUB (a zip) to a temp ``--output`` file rather than
        stdout; the body is piped on stdin. The generated ``@font-face``
        stylesheet lives in a second temp file that is unlinked as soon as
        pandoc has consumed it (always — ``finally``); the output EPUB is the
        returned :class:`Artifact` and is unlinked only on render failure
        (the registry owns cleanup on success).
        """
        epub_options = options.epub_options or EpubOptions()
        font_paths = _resolve_font_paths()
        css_path = _write_font_face_css(font_paths)

        fd, raw_path = tempfile.mkstemp(suffix="-export.epub", prefix="narrare-")
        os.close(fd)  # pandoc overwrites it via --output
        output_path = Path(raw_path)
        try:
            argv = _build_argv(manuscript, epub_options, font_paths, css_path, output_path)
            await run_pandoc(
                argv,
                manuscript.semantic_html.encode("utf-8"),
                format_label=self.format.value,
                timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
            )
            logger.info(
                "export_epub_rendered",
                bytes=output_path.stat().st_size,
                embedded_fonts=len(font_paths),
                cover_image=epub_options.cover_image_path is not None,
                user_css=epub_options.css is not None,
            )
        except Exception:
            # RULE-11: never leave a partial/corrupt EPUB on disk; the typed
            # error (from run_pandoc or _resolve_font_paths) propagates.
            output_path.unlink(missing_ok=True)
            raise
        finally:
            # The font-face stylesheet is consumed during the run; drop it
            # regardless of outcome so no orphan CSS leaks on disk.
            css_path.unlink(missing_ok=True)

        return Artifact(
            format=self.format,
            path=output_path,
            media_type="application/epub+zip",
            suggested_filename=f"{_slugify(manuscript.title)}.epub",
        )
