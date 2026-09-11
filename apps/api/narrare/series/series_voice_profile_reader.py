"""Reader for the persisted series voice profile (RULE-04 extraction).

Extracted from :class:`narrare.series.series_voice_drift_service`
``_load_series_voice`` — that file had no headroom under the 300-line
service limit (RULE-04) for the model-routing credential threading, so the
stored-baseline reading seam moves here. Single responsibility (RULE-06):
load ``SeriesSettings.author_voice`` via the repository (RULE-07: no raw
column access) and validate it into an :class:`AuthorVoiceProfile`.

RULE-11 graceful degradation: no stored voice or a malformed JSONB blob
yields ``None`` — never a crash. NOTE: :meth:`SeriesVoiceService.get`
carries the same read-and-validate shape — a follow-up may reuse this
reader there (left untouched here to keep Task 5 scoped to the routing
migration).

See:
    ADR-078 — Series Voice Hierarchy (Delta model).
    ADR-074 — Author Voice Storage Contract.
    CONSTRAINTS.md RULE-04/06/07/11
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.profiles.author_voice import AuthorVoiceProfile

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.series.contracts import SeriesRepositoryProtocol

logger = structlog.get_logger(__name__)


async def read_series_voice_profile(
    series_repo: SeriesRepositoryProtocol,
    series_id: UUID,
) -> AuthorVoiceProfile | None:
    """Load the stored series voice profile (None when empty or malformed).

    Reads ``SeriesSettings.author_voice`` via
    :meth:`SeriesRepositoryProtocol.get_settings` (RULE-07: no raw column
    access). A malformed JSONB blob degrades gracefully to None (RULE-11).
    """
    settings = await series_repo.get_settings(series_id)
    if settings is None or settings.author_voice is None:
        return None
    try:
        return AuthorVoiceProfile.model_validate(settings.author_voice)
    except Exception as exc:  # malformed JSONB — graceful (RULE-11)
        logger.warning(
            "series_voice_drift_malformed_json",
            series_id=str(series_id),
            error=str(exc),
        )
        return None
