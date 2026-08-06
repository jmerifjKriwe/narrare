"""Series voice-drift request schema (Spec 4 Task 3).

The series-scope voice-drift endpoint needs the band (novel) id in the request
body (the URL carries only the series id, mirroring the consistency endpoint).
The novel-level :class:`AuthorVoiceDriftRequest` carries only the optional
``chapter_ids`` filter (its novel id is in the URL path), so it cannot be reused
directly. This request schema carries the ``novel_id`` + the same optional
``chapter_ids`` filter.

The RESPONSE schema is REUSED verbatim from the novel-level module
(:class:`AuthorVoiceDriftResponse`, RULE-22 — no duplication); only the request
shape is series-specific.

See:
    :mod:`narrare.series.series_voice_drift_service` — the service.
    :mod:`narrare.analysis.schemas_author_voice_drift` — the reused response.
"""

from __future__ import annotations

import uuid  # noqa: TC003 - needed at runtime for Pydantic model resolution

from pydantic import BaseModel, Field


class SeriesVoiceDriftCheckRequest(BaseModel):
    """Request body for ``POST /api/v1/series/{series_id}/voice-drift/check``.

    Attributes:
        novel_id: The novel (band) whose chapters are analysed. MUST belong to
            ``series_id`` (the service verifies membership, anti-enumeration).
        chapter_ids: Specific chapter ids to analyse (UUID strings). ``None``
            or an empty list means "analyse every chapter in the novel"
            (mirrors :class:`AuthorVoiceDriftRequest.chapter_ids`).
    """

    novel_id: uuid.UUID
    chapter_ids: list[str] | None = Field(
        default=None,
        description="Specific chapter IDs to analyse, or null/empty for all chapters.",
    )
