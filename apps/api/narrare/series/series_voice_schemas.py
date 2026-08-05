"""Series Voice request/response schemas (Spec 3 Task 3).

Extracted into a dedicated module (not appended to ``series/schemas.py``)
because ``schemas.py`` is at 196/200 lines (RULE-04 file-size limit). Mirrors
the ``band_summary`` precedent of grouping series-sub-feature DTOs, but in its
own file once the parent hit its limit. Shares the ``/api/v1/series`` prefix.

The persisted :class:`AuthorVoiceProfile` (Core type — descriptive + metric
groups, ADR-074) is mirrored read-only on ``SeriesVoiceResponse``: the wire
schema carries the FULL profile so the UI can display composition metrics, and
the GENERATION consumer (Task 4) renders descriptive-only via the Core
:func:`render_author_voice_for_generation` (the boundary is enforced at the
consumer contract, not the wire schema — same as ``AuthorVoiceResult``).

See:
    :mod:`narrare.series.router_voice` — the router that uses these.
    :mod:`narrare.series.series_voice_service` — the service.
    ADR-078 — Series Voice Hierarchy (Delta model).
    ADR-074 — Author Voice Storage Contract (data shape reused).
"""

from __future__ import annotations

import uuid  # noqa: TC003 - needed at runtime for Pydantic model resolution

from pydantic import BaseModel, ConfigDict, Field

# Runtime import (not TYPE_CHECKING): AuthorVoiceProfile is a Pydantic field
# type on SeriesVoiceResponse and must resolve at class-definition time
# (mirrors schemas_author_voice.py — the inline noqa silences TC001 on a
# Pydantic field type that cannot move into a TYPE_CHECKING block).
from narrare_core.profiles.author_voice import AuthorVoiceProfile  # noqa: TC001


class SeriesVoiceProfileRequest(BaseModel):
    """POST /api/v1/series/{id}/voice/profile body — the band (novel) to profile.

    The novel MUST belong to the series (the service verifies membership and
    raises ``ForbiddenError`` otherwise — anti-enumeration).
    """

    novel_id: uuid.UUID = Field(description="The novel (band) whose voice is profiled.")


class SeriesVoiceResponse(BaseModel):
    """Response for GET / PATCH /api/v1/series/{id}/voice.

    Carries the stored series-voice profile (the Delta-model foundation,
    ADR-078). ``None`` means "no series voice profiled yet" (RULE-11 graceful
    degradation — generation renders empty ``{{author_voice}}``).
    """

    series_id: uuid.UUID
    author_voice: AuthorVoiceProfile | None


class SeriesVoiceOverrideRequest(BaseModel):
    """PATCH /api/v1/series/{id}/voice body — manual voice-profile override.

    The dict is validated as :class:`AuthorVoiceProfile` by the service for
    type safety before persisting (a malformed override → ``ValidationError``).
    Carried as a raw dict on the wire so the UI can edit the full profile shape
    without the schema enumerating every nested field here.
    """

    author_voice: dict[str, object] = Field(
        description="A full author-voice profile dict (validated server-side)."
    )


class SeriesVoiceStateResponse(BaseModel):
    """Response for POST /api/v1/series/{id}/voice/profile (profiling result).

    Mirrors :class:`SeriesVoiceResponse` but is the explicit return type of the
    profiling trigger (HTTP 200 — upsert semantics, like band-summary POST).
    """

    model_config = ConfigDict(from_attributes=True)

    series_id: uuid.UUID
    novel_id: uuid.UUID
    author_voice: AuthorVoiceProfile
