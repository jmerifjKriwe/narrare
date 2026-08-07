"""Series-consistency request/response schemas (Spec 4 Task 2).

Pydantic DTOs for the ``POST /api/v1/series/{id}/consistency/check`` endpoint.
The conflict shape REUSES the Core
:class:`~narrare_core.agents.series_consistency_types.CanonConflict` verbatim
(RULE-22 — no duplication); the response wraps it with the series/novel
identifiers + the agent summary + transparency counts.

The check is read-only and stateless in this slice: nothing is persisted. The
``conflicts`` / ``summary`` are display-only report artifacts.

See:
    :mod:`narrare.series.series_consistency_service` — the service that yields
        these responses.
    :mod:`narrare_core.agents.series_consistency_types` — the reused
        :class:`CanonConflict` agent output type.
    ADR-075 — Series Foundation (Canon KB scope).
"""

from __future__ import annotations

import uuid  # noqa: TC003 - needed at runtime for Pydantic model resolution

from pydantic import BaseModel, ConfigDict

# Runtime import (not TYPE_CHECKING): CanonConflict is a Pydantic field type —
# Pydantic resolves field annotations at class-definition time, so the symbol
# MUST be importable at runtime (mirrors schemas_author_voice_drift importing
# VoiceDriftResult). noqa: TC001.
from narrare_core.agents.series_consistency_types import (  # noqa: TC001
    CanonConflict,
)


class SeriesConsistencyCheckRequest(BaseModel):
    """Request body for ``POST /api/v1/series/{series_id}/consistency/check``.

    The series id is carried by the URL path parameter; the body carries the
    band (novel) whose chapter prose is checked against the series Canon.

    Attributes:
        novel_id: The novel (band) to check. MUST belong to ``series_id`` (the
            service verifies membership, anti-enumeration).
    """

    novel_id: uuid.UUID


class SeriesConsistencyCheckResponse(BaseModel):
    """Response for the series-consistency check.

    Carries the agent's conflicts (possibly empty — no contradictions found)
    + the overall summary + the identifiers + transparency counts so the UI
    can show "checked N canon entries against M chapters".

    Attributes:
        series_id: The series whose Canon was the reference.
        novel_id: The novel (band) that was checked.
        conflicts: The canon contradictions found, ordered by severity (errors
            before warnings). **Empty means no contradictions were found** — a
            valid and common result.
        summary: The agent's 1-2 sentence overall assessment of the band's
            consistency with the series Canon.
        canon_entry_count: How many Canon entries were supplied to the agent
            (transparency; 0 → the check was a no-op graceful skip).
        chapter_count: How many chapters with prose were supplied to the agent.
    """

    model_config = ConfigDict(from_attributes=True)

    series_id: uuid.UUID
    novel_id: uuid.UUID
    # ``= []`` (not Field(default_factory=list)) keeps pyright strict happy for
    # a custom-element list — mirrors schemas_author_voice_drift.TrendPoint.
    conflicts: list[CanonConflict] = []
    summary: str = ""
    canon_entry_count: int = 0
    chapter_count: int = 0
