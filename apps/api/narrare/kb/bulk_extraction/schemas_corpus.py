"""Corpus pass wire schemas (F3, spec §4.3/§6.3).

The corpus-specific additions to the bulk extraction surface, split from
``schemas.py`` (RULE-04: that file sat exactly at its 200-line hard limit —
the prescribed response is modularization, mirroring the kb domain's
``schemas_extraction.py`` / ``entity_resolution/schemas_resolution.py``
naming precedent). Field names are the RULE-17 mirror targets: the FE
(``CorpusEstimate`` in T4, the dedup card in T5) must match them EXACTLY.
Every model forbids extra fields so FE/BE drift fails loudly at the seam.
"""

from __future__ import annotations

from typing import Self
from uuid import UUID  # noqa: TC003 — needed at runtime for Pydantic model resolution

from pydantic import BaseModel, ConfigDict, Field, model_validator

from narrare.kb.bulk_extraction.corpus import (
    CapReason,  # noqa: TC001 — runtime Pydantic resolution (Literal alias)
)


class BulkDedupInfo(BaseModel):
    """Post-pass duplicate-analysis block (F3 §6.3).

    ``None`` on explicit jobs (the trigger is corpus-only — invariant 3);
    on corpus jobs ``{analyzed: false, suggestion_count: null}`` until the
    runner's post-pass lands or gives up (RULE-11: visible, never silent).
    """

    model_config = ConfigDict(extra="forbid")

    analyzed: bool
    """Whether the automatic ADR-085 analysis ran after the pass completed."""

    suggestion_count: int | None = None
    """Detected duplicate suggestions — set (≥ 0) iff ``analyzed`` is true."""

    @model_validator(mode="after")
    def _count_iff_analyzed(self) -> Self:
        """Self-defending invariant: a count exists ⟺ the analysis ran."""
        if self.analyzed != (self.suggestion_count is not None):
            raise ValueError("suggestion_count must be set if and only if analyzed is true")
        return self


class CorpusEstimateView(BaseModel):
    """Honest pre-run estimate (spec §4.3) — mirrors ``CorpusEstimateData`` 1:1.

    The estimate NEVER understates: ``ai_calls == chapter_count`` (D14a —
    cost transparency is a count of calls), totals cover ALL enumerated
    chapters, and truncation is explicit via ``capped``/``cap_reason``.
    """

    model_config = ConfigDict(extra="forbid")

    total_chapters: int = Field(ge=0)
    """All chapters enumerated for the novel (not just the selected prefix)."""

    total_word_count: int = Field(ge=0)
    """Word sum over ALL enumerated chapters."""

    selected_chapter_ids: list[UUID]
    """The selected prefix's ids, in position order (what the run will cover)."""

    chapter_count: int = Field(ge=0)
    """Length of the selected prefix."""

    word_count: int = Field(ge=0)
    """Word sum of the selected prefix (what the run will actually cost)."""

    ai_calls: int = Field(ge=0)
    """Extraction calls the run will make — exactly ``chapter_count`` (D14a)."""

    capped: bool
    """Whether a D20a cap truncated the selection (never silent)."""

    cap_reason: CapReason | None = None
    """Which cap truncated the selection — ``"chapters"`` | ``"words"`` | ``None``."""

    @model_validator(mode="after")
    def _ai_calls_iff_chapters(self) -> Self:
        """Self-defending invariant: one AI call per chapter (D14a)."""
        if self.ai_calls != self.chapter_count:
            raise ValueError("ai_calls must equal chapter_count (one call per chapter, D14a)")
        return self


__all__ = [
    "BulkDedupInfo",
    "CorpusEstimateView",
]
