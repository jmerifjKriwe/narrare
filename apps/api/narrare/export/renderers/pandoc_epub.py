"""pandoc EPUB renderer adapter — co-owner (with ``pandoc_md.py``) of the
``pandoc`` binary invocation (RULE-08).

Implements :class:`narrare.export.contracts.ManuscriptRenderer` for
:class:`~narrare.export.contracts.ExportFormat.EPUB`. Spawns pandoc via the
shared helper in :mod:`narrare.export.renderers.pandoc_base` — never calls
``asyncio.create_subprocess_exec`` directly.

D7 (font policy): in Slice 4 this renderer embeds the **bundled Libertinus
Serif** (regular/italic/bold/bolditalic from
``apps/api/narrare/export/typst/fonts/``) via pandoc ``--epub-embed-font``
**unconditionally** — there is no ``embed_fonts`` toggle (see
:class:`~narrare.export.contracts.EpubOptions`). This extends ADR-081's
no-silent-font-fallback principle to EPUB.

**Slice 0 scope:** boundary skeleton only. ``render()`` raises
``NotImplementedError``; real EPUB rendering lands in Slice 4.
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


class PandocEpubRenderer:
    """RULE-08 renderer adapter for pandoc EPUB output.

    Structurally satisfies :class:`~narrare.export.contracts.ManuscriptRenderer`
    (no explicit inheritance — matches the repo's adapter convention). Embeds
    bundled Libertinus via ``--epub-embed-font`` in Slice 4 (D7).
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
        """Render ``manuscript`` to an EPUB artifact. Slice 4."""
        raise NotImplementedError("pandoc EPUB rendering lands in Slice 4")
