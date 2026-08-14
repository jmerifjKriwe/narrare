"""pandoc Markdown renderer adapter — co-owner (with ``pandoc_epub.py``) of the
``pandoc`` binary invocation (RULE-08).

Implements :class:`narrare.export.contracts.ManuscriptRenderer` for
:class:`~narrare.export.options.ExportFormat.MARKDOWN`. Spawns pandoc via the
shared helper in :mod:`narrare.export.renderers.pandoc_base` — never calls
``asyncio.create_subprocess_exec`` directly (RULE-08 confinement).

Output format: GitHub-Flavored Markdown (``--from=html --to=gfm``).

Heading-shift mapping (seam-fix F-1)
------------------------------------
Chapter titles in the assembled manuscript HTML are ``<h2>`` (see
:func:`narrare.export.tasks.assemble_raw_html` — the book title is metadata,
never a body ``<h1>``, so the body is a pure sequence of chapter sections).
``MarkdownOptions.chapter_heading_level`` (default 1) is the heading level
chapters should appear at in the Markdown output. pandoc's
``--shift-heading-level-by=N`` maps each heading to ``original_level + N``, so
to place the ``<h2>`` chapters at ``chapter_heading_level`` (target)::

    target = 2 + N   →   N = chapter_heading_level - 2

  chapter_heading_level = 1 → N = -1 (``<h2>`` → ``#``, the default)
  chapter_heading_level = 2 → N =  0 (no-op; chapters stay ``##``)
  chapter_heading_level = 3 → N = +1 (``<h2>`` → ``###``)

Front-matter decision
---------------------
When ``MarkdownOptions.include_front_matter`` is True, a YAML front-matter
block (``title`` / ``author`` / ``lang``) is prepended to the pandoc Markdown
output **in Python**, not via pandoc's ``--standalone`` + template. Reason: the
``gfm`` writer has no rich default template, and a deterministic,
template-independent block is preferable to coupling to pandoc's template
internals (and to the version of pandoc shipped). The block is plain YAML so
GitHub renderers / static-site generators consume it natively.

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
from narrare.export.options import MarkdownOptions
from narrare.export.renderers.pandoc_base import (
    DEFAULT_TIMEOUT_SECONDS,
    run_pandoc,
)

if TYPE_CHECKING:
    from narrare_core.export.contracts import NormalizedManuscript

logger = structlog.get_logger(__name__)

#: The HTML heading level chapter titles carry in the assembled manuscript
#: (titles are emitted as ``<h2>`` — see narrare.export.tasks._chapter_chunk).
#: Drives the ``--shift-heading-level-by`` derivation (see module docstring).
_CHAPTER_HTML_HEADING_LEVEL = 2

#: Fallback filename stem when a manuscript title has no slug-able characters.
_EMPTY_TITLE_SLUG = "manuscript"


def _slugify(title: str) -> str:
    """Reduce a manuscript title to a safe filename stem.

    Keeps ASCII alphanumerics (and any Unicode word chars); every other run
    collapses to a single ``-``; trimmed and lower-cased. A title with no
    usable characters falls back to :data:`_EMPTY_TITLE_SLUG` so the suggested
    filename is never empty.
    """
    stem = re.sub(r"[^\w]+", "-", title, flags=re.UNICODE).strip("-").lower()
    return stem or _EMPTY_TITLE_SLUG


def _yaml_quoted(value: str) -> str:
    """Render a scalar as a double-quoted YAML string.

    Backslash and double-quote are escaped; every value is quoted unconditionally
    so the block is deterministic and never mis-parsed by a YAML loader tripping
    on a stray ``:`` or leading special character in a title/author.
    """
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


class PandocMarkdownRenderer:
    """RULE-08 renderer adapter for pandoc Markdown (GFM) output.

    Structurally satisfies :class:`~narrare.export.contracts.ManuscriptRenderer`
    (no explicit inheritance — matches the repo's adapter convention). Markdown
    is plain text and carries no font (D7).
    """

    def __init__(self) -> None:
        # Cached availability probe (RULE-11); refreshable by re-instantiating.
        self._available: bool | None = None

    @property
    def format(self) -> ExportFormat:
        """The format this renderer produces."""
        return ExportFormat.MARKDOWN

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
        """Render ``manuscript`` to a GitHub-Flavored Markdown artifact.

        See the module docstring for the heading-shift formula and the
        front-matter decision.
        """
        md_options = options.markdown_options or MarkdownOptions()
        # N = target_level - 2 (chapter titles are <h2> in the input HTML).
        shift = md_options.chapter_heading_level - _CHAPTER_HTML_HEADING_LEVEL

        argv: list[str] = ["--from=html", "--to=gfm"]
        if shift != 0:
            argv.append(f"--shift-heading-level-by={shift}")

        stdout = await run_pandoc(
            argv,
            manuscript.semantic_html.encode("utf-8"),
            format_label=self.format.value,
            timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
        )
        body = stdout.decode("utf-8", errors="replace")
        content = (
            self._with_front_matter(body, manuscript) if md_options.include_front_matter else body
        )

        path = self._write_temp(content)
        logger.info(
            "export_markdown_rendered",
            bytes=len(content),
            shift_heading_level_by=shift,
            front_matter=md_options.include_front_matter,
        )
        return Artifact(
            format=self.format,
            path=path,
            media_type="text/markdown",
            suggested_filename=f"{_slugify(manuscript.title)}.md",
        )

    @staticmethod
    def _with_front_matter(body: str, manuscript: NormalizedManuscript) -> str:
        """Prepend a YAML front-matter block (title / author / lang) to ``body``.

        Emitted in Python rather than via pandoc ``--standalone`` (see the
        module docstring's front-matter decision). A blank line separates the
        closing ``---`` from the body so Markdown parsers treat the body
        correctly.
        """
        lines = [
            "---",
            f"title: {_yaml_quoted(manuscript.title)}",
            f"author: {_yaml_quoted(manuscript.author)}",
            f"lang: {manuscript.language.value}",
            "---",
            "",
        ]
        return "\n".join(lines) + body

    @staticmethod
    def _write_temp(content: str) -> Path:
        """Write ``content`` to a uniquely-named temp ``.md`` file; return it.

        The temp file is created ONLY after pandoc succeeded, so a render
        failure (which raises before this point) never leaves an orphan file.
        If the write itself fails after the file is opened, it is unlinked
        before re-raising — no leak on partial writes (RULE-11 belt-and-braces).
        The registry + router own cleanup once the :class:`Artifact` is
        registered (single-use token download + sweep).
        """
        fd, raw_path = tempfile.mkstemp(suffix="-export.md", prefix="narrare-")
        path = Path(raw_path)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(content)
        except OSError:
            path.unlink(missing_ok=True)
            raise
        return path
