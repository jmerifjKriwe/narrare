"""pandoc Markdown renderer adapter — co-owner (with ``pandoc_epub.py``) of the
``pandoc`` binary invocation (RULE-08).

Implements :class:`narrare.export.contracts.ManuscriptRenderer` for
:class:`~narrare.export.contracts.ExportFormat.MARKDOWN`. Spawns pandoc via the
shared helper in :mod:`narrare.export.renderers.pandoc_base` — never calls
``asyncio.create_subprocess_exec`` directly.

**Slice 0 scope:** boundary skeleton only. ``render()`` raises
``NotImplementedError``; real Markdown rendering lands in Slice 3.
"""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

from narrare.export.contracts import (
    Artifact,
    ExportFormat,
    ExportOptions,
)

if TYPE_CHECKING:
    from narrare_core.export.contracts import NormalizedManuscript


class PandocMarkdownRenderer:
    """RULE-08 renderer adapter for pandoc Markdown output.

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
        """Render ``manuscript`` to a Markdown artifact. Slice 3."""
        raise NotImplementedError("pandoc Markdown rendering lands in Slice 3")
