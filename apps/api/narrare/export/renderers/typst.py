"""Typst PDF renderer adapter — the SOLE site the ``typst`` binary is invoked.

RULE-08 (mechanically enforced by
``scripts/architecture/_checkers/export_binary_confinement.py``): no other module
in the codebase may spawn a Typst subprocess. This adapter implements the
:class:`narrare.export.contracts.ManuscriptRenderer` Protocol and is the only
producer of :class:`~narrare.export.contracts.ExportFormat.PDF` artifacts.

**Slice 0 scope:** boundary skeleton only. ``render()`` raises
``NotImplementedError``; real PDF rendering (HTML → pandoc Typst AST →
``narrare-roman`` wrapper → ``typst compile``) lands in Slice 6.
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


class TypstPdfRenderer:
    """RULE-08 renderer adapter for Typst PDF output.

    Structurally satisfies :class:`~narrare.export.contracts.ManuscriptRenderer`
    (no explicit inheritance — matches the repo's adapter convention). The Typst
    binary is invoked ONLY inside this class's ``render()`` (Slice 6).
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
        """Render ``manuscript`` to a PDF artifact. Slice 6."""
        raise NotImplementedError("Typst PDF rendering lands in Slice 6")
