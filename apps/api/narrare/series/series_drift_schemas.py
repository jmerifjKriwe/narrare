"""Snapshot schema for C2 drift persistence (SERIES-004 Slice 6).

One response backs ``GET /api/v1/series/{series_id}/consistency/{novel_id}``.
The sections REUSE the existing run-result models verbatim (RULE-22 — the
stored JSON serializes THOSE models; no re-shaping): ``consistency`` is a
``SeriesConsistencyCheckResponse``, ``voice_drift`` an
``AuthorVoiceDriftResponse``.

RULE-04: separate file because ``series/schemas.py`` is at its 200-line
limit (``series_voice_schemas.py`` precedent).
"""

from __future__ import annotations

import uuid  # noqa: TC003 - needed at runtime for Pydantic model resolution
from datetime import datetime  # noqa: TC003 - needed at runtime for Pydantic model resolution

from pydantic import BaseModel

# Runtime imports (not TYPE_CHECKING): these are Pydantic field types —
# Pydantic resolves field annotations at class-definition time. noqa: TC001
# (mirrors series_consistency_schemas importing CanonConflict).
from narrare.analysis.schemas_author_voice_drift import (  # noqa: TC001
    AuthorVoiceDriftResponse,
)
from narrare.series.series_consistency_schemas import (  # noqa: TC001
    SeriesConsistencyCheckResponse,
)


class SeriesDriftSnapshotResponse(BaseModel):
    """GET /api/v1/series/{series_id}/consistency/{novel_id} response.

    The persisted latest-wins snapshot for one band, fetched as ONE document
    with the staleness verdict.

    Attributes:
        series_id: The series whose checks produced the snapshot.
        novel_id: The novel (band) the snapshot belongs to.
        generated_at: Record-level timestamp of the LAST completed write of
            either check (refreshed on every section upsert — the design's
            singular ``generated_at``). ``None`` when nothing is persisted.
        stale: ``True`` when the band's current chapter-texts fingerprint
            differs from the fingerprint stored at save time — the results
            predate text edits. Always ``False`` when nothing is persisted.
        consistency: The persisted canon-contradiction result (``None`` when
            that check never completed a run for this band).
        voice_drift: The persisted series-voice-drift result (``None`` when
            that check never completed a run for this band).
    """

    series_id: uuid.UUID
    novel_id: uuid.UUID
    generated_at: datetime | None
    stale: bool
    consistency: SeriesConsistencyCheckResponse | None
    voice_drift: AuthorVoiceDriftResponse | None
