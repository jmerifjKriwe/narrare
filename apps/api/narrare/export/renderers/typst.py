"""Typst PDF renderer adapter — the SOLE site the ``typst`` binary is invoked.

RULE-08 (mechanically enforced by
``scripts/architecture/_checkers/export_binary_confinement.py``): no other module
in the codebase may spawn a Typst subprocess. This adapter implements the
:class:`narrare.export.contracts.ManuscriptRenderer` Protocol and is the only
producer of :class:`~narrare.export.contracts.ExportFormat.PDF` artifacts.

Render pipeline (ADR-081 / IO-001 Slice 6)
------------------------------------------
1. **Config** — :class:`NarrareRomanConfig` built from :class:`PdfOptions` +
   manuscript metadata. ``title`` / ``author`` are scalar strings (F-7).
2. **pandoc HTML → Typst body** — via :func:`pandoc_base.run_pandoc` with
   ``--shift-heading-level-by=-1`` (F-1: ``<h2>`` → ``= Heading``, making each
   chapter a level-1 opener that drives recto pagebreaks + ToC entries).
3. **Wrapper** — a Typst source string assembled in-process and piped to
   ``typst compile`` via **stdin** (``-``). It imports the bundled
   ``narrare-roman`` package, applies the config as a document-level show rule,
   emits the title page + frontmatter (ToC) + body, and embeds the pandoc body
   with literal ``@`` defensively escaped (F-6).
4. **Compile** — ``typst compile --root <pkg> --font-path <pkg>/fonts - <out>``
   reads the wrapper from stdin and writes the PDF to a temp file. The
   ``--font-path`` points at the bundled Libertinus Serif (D3); missing fonts
   are a hard :class:`ExportRenderError` (no silent fallback — the bake-off's
   headline fire&forget failure).
5. **Error** — non-zero exit / timeout / missing binary → typed
   :class:`ExportRenderError` carrying a stderr tail (RULE-11).

narrare-roman import resolution
-------------------------------
The wrapper is piped via stdin (``-``) so there is no input *file* and thus no
"source must be under root" constraint. ``--root`` is set to the package
directory (``apps/api/narrare/export/typst/``), and the wrapper imports the
entry point via the root-relative absolute path ``/lib.typ``. This requires **no
source-tree mutation** — no temp files are written into the committed package or
any source directory; the only temp file is the output PDF.

Non-LLM (no ``narrare_core.agents`` / ``narrare_core.prompts`` imports).
"""

from __future__ import annotations

import asyncio
import contextlib
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
    NarrareRomanConfig,
)
from narrare.export.errors import ExportRenderError
from narrare.export.options import MirroredMargins, PdfOptions
from narrare.export.renderers.pandoc_base import run_pandoc

if TYPE_CHECKING:
    from narrare_core.export.contracts import NormalizedManuscript

logger = structlog.get_logger(__name__)

#: The production render binary this adapter owns (RULE-08 SSOT — the literal
#: ``"typst"`` lives here; the AST checker matches string literals in argv).
TYPST_BINARY = "typst"

#: Package directory (``lib.typ`` + ``src/`` + ``fonts/``), resolved
#: PACKAGE-RELATIVELY via ``Path(__file__)`` — never via cwd. ``renderers/`` →
#: ``../typst/``. Used as ``--root`` so the wrapper's ``/lib.typ`` import
#: resolves, and as the parent of :data:`_FONTS_DIR`.
_PACKAGE_DIR: Path = Path(__file__).resolve().parent.parent / "typst"

#: Bundled Libertinus Serif (D3 / OFL). Passed via ``--font-path`` so the OFL
#: files are the ones Typst uses — never a silent fallback. Missing font files
#: are a hard :class:`ExportRenderError` (checked by :func:`_resolve_font_paths`).
_FONTS_DIR: Path = _PACKAGE_DIR / "fonts"

#: The four Libertinus Serif variants bundled under :data:`_FONTS_DIR` (same
#: set as the EPUB renderer, D7). Verified present before every compile so a
#: missing bundle fails loud, never as a wrong-font fallback.
_FONT_FILES: tuple[str, ...] = (
    "libertinus-serif-regular.otf",
    "libertinus-serif-italic.otf",
    "libertinus-serif-bold.otf",
    "libertinus-serif-bolditalic.otf",
)

#: Root-relative import of the package entry point, resolved against
#: ``--root _PACKAGE_DIR``. Leading ``/`` makes it absolute w.r.t. the root.
_LIB_IMPORT = "/lib.typ"

#: Generous default render timeout (seconds). Typst compilation of a large
#: manuscript is fast but a stuck process must surface as a typed
#: :class:`ExportRenderError` (RULE-11), not hang an export job.
_DEFAULT_TIMEOUT_SECONDS: float = 120.0

#: Trailing stderr characters retained in the typed error (actionable tail).
_STDERR_TAIL_CHARS: int = 1024

#: Fallback filename stem when a manuscript title has no slug-able characters.
_EMPTY_TITLE_SLUG = "manuscript"

#: Matches a literal ``@`` NOT already preceded by ``\`` (F-6 defensive escape;
#: pandoc's Typst writer escapes ``@`` → ``\@`` already — this catches any
#: bare ``@`` that slips through, without double-escaping pandoc's output).
_AT_SIGN_UNESCAPED: re.Pattern[str] = re.compile(r"(?<!\\)@")


# ── Helpers ─────────────────────────────────────────────────────────────────


def _slugify(title: str) -> str:
    """Reduce a manuscript title to a safe filename stem.

    Mirrors :func:`narrare.export.renderers.pandoc_epub._slugify` (and
    ``pandoc_md._slugify``) so all three adapters derive identical stems.
    """
    stem = re.sub(r"[^\w]+", "-", title, flags=re.UNICODE).strip("-").lower()
    return stem or _EMPTY_TITLE_SLUG


def _typst_string(value: str) -> str:
    """Escape a Python string for embedding in a Typst string literal.

    Typst string literals use ``\\`` and ``"`` as the only escapes that matter
    here; everything else (including ``@``) is literal inside a string.
    """
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _resolve_font_paths() -> list[Path]:
    """Resolve the four bundled Libertinus ``.otf`` paths (D3).

    Raises :class:`ExportRenderError` if any variant is missing — there is
    never a silent fallback to a system font (RULE-11 / ADR-081). Reads
    :data:`_FONTS_DIR` at call time so tests can redirect it.
    """
    paths: list[Path] = []
    for name in _FONT_FILES:
        path = _FONTS_DIR / name
        if not path.is_file():
            raise ExportRenderError(
                f"Bundled Libertinus font missing (D3 no-silent-fallback): "
                f"{path}. Restore the file or reinstall the package."
            )
        paths.append(path)
    return paths


def _margins_to_typst(margins: MirroredMargins | None) -> str:
    """Serialize a :class:`MirroredMargins` to a Typst dict, or ``none``.

    ``none`` lets narrare-roman pick the paper-specific default Satzspiegel;
    a dict carries the four ``*_mm`` keys the Typst side translates (see
    ``src/margins.typ``).
    """
    if margins is None:
        return "none"
    return (
        f"(inside_mm: {margins.inside_mm}, outside_mm: {margins.outside_mm}, "
        f"top_mm: {margins.top_mm}, bottom_mm: {margins.bottom_mm})"
    )


def _escape_at_signs(body: str) -> str:
    """Defensively escape bare ``@`` signs in the pandoc Typst body (F-6).

    Typst parses a bare ``@word`` as a label/citation reference and errors if
    the label is absent (``error: label '<word>' does not exist``). Pandoc's
    Typst writer already escapes ``@`` → ``\\@``, but this belt-and-suspenders
    pass catches any ``@`` that is NOT already backslash-escaped, turning it
    into ``\\@`` (a literal ``@`` in Typst markup). It never double-escapes
    pandoc's existing ``\\@`` output.
    """
    return _AT_SIGN_UNESCAPED.sub(r"\\@", body)


def _build_config_block(config: NarrareRomanConfig) -> str:
    """Serialize :class:`NarrareRomanConfig` to the narrare-roman config dict.

    Keys mirror what ``lib.typ`` reads (kebab-case). ``drop_caps`` is omitted —
    the Typst side does not read ``drop-caps`` yet (Slice 5g is optional). The
    ``title``/``author`` reference the ``booktitle``/``bookauthor`` Typst
    variables defined in the wrapper (F-7: always scalar strings).
    """
    return (
        "  config: (\n"
        f'    paper-size: "{config.paper_size.value}",\n'
        '    body-font: "Libertinus Serif",\n'
        f"    body-size-pt: {config.body_size_pt},\n"
        f"    leading-ratio: {config.leading_ratio},\n"
        f"    margins: {_margins_to_typst(config.margins)},\n"
        "    title: booktitle,\n"
        "    author: bookauthor,\n"
        f'    language: "{config.language.value}",\n'
        f"    include-toc: {'true' if config.include_toc else 'false'},\n"
        '    running-head-preset: "default",\n'
        '    scene-break-style: "asterism",\n'
        "    widow-orphan-protection: true,\n"
        "  ),\n"
    )


def _build_wrapper(config: NarrareRomanConfig, body_typst: str) -> str:
    """Assemble the full Typst wrapper source piped to ``typst compile``.

    Structure: import → ``#let`` title/author vars (F-7 scalars) → document
    show rule with config → title page → conditional frontmatter (ToC) → body
    (pandoc output with F-6 defensive ``@`` escape).
    """
    title = _typst_string(config.title)
    author = _typst_string(config.author)
    body = _escape_at_signs(body_typst)
    frontmatter = "  #toc()\n" if config.include_toc else ""
    frontmatter_block = f"#frontmatter[\n{frontmatter}]\n" if config.include_toc else ""
    return (
        f'#import "{_LIB_IMPORT}": '
        "narrare-roman, title-page, frontmatter, body, toc\n"
        f'#let booktitle = "{title}"\n'
        f'#let bookauthor = "{author}"\n'
        "#show: narrare-roman.with(\n"
        f"{_build_config_block(config)}"
        ")\n"
        "#title-page[\n"
        "  #align(center)[\n"
        "    #v(2fr)\n"
        '    #text(size: 28pt, weight: "bold")[#booktitle]\n'
        "    #v(1fr)\n"
        "    #text(size: 14pt)[#bookauthor]\n"
        "    #v(2fr)\n"
        "  ]\n"
        "]\n"
        f"{frontmatter_block}"
        "#body[\n"
        f"{body}\n"
        "]\n"
    )


async def _terminate(proc: asyncio.subprocess.Process) -> None:
    """Kill + reap a typst process so a timeout never leaks a zombie."""
    with contextlib.suppress(ProcessLookupError):
        proc.kill()
    with contextlib.suppress(ProcessLookupError):
        await proc.wait()


# ── Renderer ────────────────────────────────────────────────────────────────


class TypstPdfRenderer:
    """RULE-08 renderer adapter for Typst PDF output.

    Structurally satisfies :class:`~narrare.export.contracts.ManuscriptRenderer`
    (no explicit inheritance — matches the repo's adapter convention). The Typst
    binary is invoked ONLY inside this class's ``render()``.
    """

    def __init__(self) -> None:
        # Cached availability probe (RULE-11); refreshable by re-instantiating.
        self._available: bool | None = None

    @property
    def format(self) -> ExportFormat:
        """The format this renderer produces."""
        return ExportFormat.PDF

    def is_available(self) -> bool:
        """True iff the ``typst`` binary is on ``$PATH`` (RULE-11).

        Cached on the instance after the first call; a missing binary degrades
        gracefully (the service reports the format unavailable rather than
        producing a wrong-font / missing-font fallback).
        """
        if self._available is None:
            self._available = shutil.which("typst") is not None
        return self._available

    async def render(
        self,
        manuscript: NormalizedManuscript,
        options: ExportOptions,
    ) -> Artifact:
        """Render ``manuscript`` to a PDF artifact via narrare-roman.

        See the module docstring for the full pipeline (config → pandoc →
        wrapper → ``typst compile``). Temp PDF is cleaned up on failure
        (RULE-11); on success the registry owns cleanup.
        """
        pdf_options = options.pdf_options or PdfOptions()
        config = NarrareRomanConfig(
            paper_size=pdf_options.paper_size,
            margins=pdf_options.margins,
            body_size_pt=pdf_options.body_size_pt,
            leading_ratio=pdf_options.leading_ratio,
            language=manuscript.language,
            title=manuscript.title,
            author=manuscript.author,
            drop_caps=pdf_options.drop_caps,
            include_toc=pdf_options.include_toc,
        )

        # F-1: pandoc HTML → Typst, --shift-heading-level-by=-1 makes <h2>
        # chapters level-1 openers (recto pagebreak + ToC entry).
        body_bytes = await run_pandoc(
            ["--from=html", "--to=typst", "--shift-heading-level-by=-1"],
            manuscript.semantic_html.encode("utf-8"),
            format_label=self.format.value,
        )

        # D3: verify bundled fonts exist BEFORE compiling (no silent fallback).
        _resolve_font_paths()

        wrapper = _build_wrapper(config, body_bytes.decode("utf-8"))

        fd, raw_path = tempfile.mkstemp(suffix="-export.pdf", prefix="narrare-")
        os.close(fd)  # typst overwrites it via the output positional arg
        output_path = Path(raw_path)
        try:
            await self._compile(wrapper, output_path)
            logger.info(
                "export_pdf_rendered",
                bytes=output_path.stat().st_size,
            )
        except Exception:
            # RULE-11: never leave a partial/corrupt PDF on disk.
            output_path.unlink(missing_ok=True)
            raise

        return Artifact(
            format=self.format,
            path=output_path,
            media_type="application/pdf",
            suggested_filename=f"{_slugify(manuscript.title)}.pdf",
        )

    async def _compile(self, wrapper_source: str, output_path: Path) -> None:
        """The SOLE ``typst`` subprocess spawn site (RULE-08).

        Pipes ``wrapper_source`` via stdin (``-``) and writes the PDF to
        ``output_path``. ``--root`` is the package dir so ``/lib.typ`` resolves;
        ``--font-path`` is the bundled Libertinus dir (D3). Non-zero exit,
        timeout, or a missing binary → typed :class:`ExportRenderError`.
        """
        argv: list[str] = [
            TYPST_BINARY,
            "compile",
            "--root",
            str(_PACKAGE_DIR),
            "--font-path",
            str(_FONTS_DIR),
            "-",  # read source from stdin
            str(output_path),
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            # TOCTOU: binary vanished between is_available() and the spawn.
            raise ExportRenderError(
                f"typst for format '{self.format.value}' is not installed: {exc}"
            ) from exc

        try:
            _, stderr = await asyncio.wait_for(
                proc.communicate(wrapper_source.encode("utf-8")),
                timeout=_DEFAULT_TIMEOUT_SECONDS,
            )
        except TimeoutError as exc:
            await _terminate(proc)
            raise ExportRenderError(
                f"typst for format '{self.format.value}' timed out after "
                f"{_DEFAULT_TIMEOUT_SECONDS}s and was killed."
            ) from exc

        if proc.returncode != 0:
            tail = stderr.decode("utf-8", errors="replace").strip()[-_STDERR_TAIL_CHARS:]
            raise ExportRenderError(
                f"typst for format '{self.format.value}' exited {proc.returncode}: {tail}"
            )
