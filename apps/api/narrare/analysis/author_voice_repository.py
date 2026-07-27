"""AuthorVoiceRepository — load/save/clear author_voice JSONB (ADR-074).

Persistence layer for ``ProjectSettings.author_voice``. Maps between the Core
:class:`~narrare_core.profiles.author_voice.AuthorVoiceProfile` Pydantic model
and the JSONB column added by migration 0036. All SQLAlchemy queries live here
— services never write SQL directly (RULE-07).

Mirrors :class:`narrare.adaptive.repository.AdaptiveSettingsRepository` (the
proven per-novel structured-JSONB-column pattern, ADR-069 D2) — the structural
parallel ADR-074 binds this repository to.

RULE-11 graceful degradation:
    - NULL column / missing row → ``load()`` returns ``None`` (callers fall
      back to "no profile"; generation renders empty ``{{author_voice}}``).
    - Malformed JSONB → ``load()`` returns ``None`` (Pydantic validation).

See:
    ADR-074 — Author Voice Storage Contract (the storage contract).
    ADR-069 Decision 2 — AdaptiveSettings (the persistence pattern mirrored).
    CONSTRAINTS.md RULE-07 / RULE-11 / RULE-14.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from sqlalchemy import delete, select, update

from narrare.settings.models import ProjectSettings
from narrare_core.profiles.author_voice import AuthorVoiceProfile

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


def _profile_to_json(profile: AuthorVoiceProfile) -> dict[str, object]:
    """Serialise ``AuthorVoiceProfile`` to a JSONB-compatible dict.

    Uses Pydantic's ``model_dump(mode="json")`` so nested models
    (``VoiceAnalysis``, ``AuthorMetrics``) serialise recursively to JSON-safe
    primitives. Round-trip: ``_json_to_profile(_profile_to_json(p)) == p``.
    """
    dumped = profile.model_dump(mode="json")
    # model_dump returns dict[str, object] for a BaseModel; cast for mypy/pyright.
    return dict(dumped)


def _json_to_profile(data: object) -> AuthorVoiceProfile | None:
    """Deserialise ``AuthorVoiceProfile`` from a JSONB-loaded dict.

    Returns ``None`` when the input is ``None`` or malformed (graceful
    degradation per RULE-11 — Pydantic validation rejects malformed JSON).
    """
    if not isinstance(data, dict):
        return None
    try:
        return AuthorVoiceProfile.model_validate(data)
    except Exception as exc:  # Pydantic ValidationError + friends — see below
        # RULE-11: malformed JSONB never crashes the reader. Log + return None
        # so consumers degrade gracefully ("no profile"); never a silent
        # prompt regression because None is an explicit "no profile" signal.
        logger.warning(
            "author_voice_malformed_json",
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return None


class AuthorVoiceRepository:
    """Repository for the ``ProjectSettings.author_voice`` JSONB column.

    Mirrors :class:`AdaptiveSettingsRepository` (ADR-069 D2). The repository
    owns the (de)serialisation between the JSONB column and the Core
    :class:`AuthorVoiceProfile` Pydantic model — services never touch the
    column directly (RULE-07 / ADR-074 binding).

    Args:
        session: SQLAlchemy async session.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def load(self, novel_id: UUID) -> AuthorVoiceProfile | None:
        """Load the stored author-voice profile for a novel.

        Returns:
            The stored :class:`AuthorVoiceProfile`, or ``None`` when no row
            exists yet, the column is NULL, or the JSONB is malformed
            (RULE-11 graceful degradation). Callers treat ``None`` as
            "no profile" (generation renders empty ``{{author_voice}}``).
        """
        stmt = select(ProjectSettings.author_voice).where(ProjectSettings.novel_id == novel_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _json_to_profile(row)

    async def save(self, novel_id: UUID, profile: AuthorVoiceProfile) -> None:
        """Upsert the author-voice profile for a novel.

        If no ``ProjectSettings`` row exists for this novel, one is created
        with the supplied profile. If a row exists, only ``author_voice`` is
        updated (``updated_at`` bumps via ``onupdate=func.now()`` so freshness
        signals keep working, mirroring character-voice KB bumps).
        """
        json_payload = _profile_to_json(profile)
        stmt = (
            update(ProjectSettings)
            .where(ProjectSettings.novel_id == novel_id)
            .values(author_voice=json_payload)
        )
        result = await self._session.execute(stmt)
        if result.rowcount == 0:  # type: ignore[union-attr]
            model = ProjectSettings(novel_id=novel_id, author_voice=json_payload)
            self._session.add(model)
        await self._session.flush()

    async def clear(self, novel_id: UUID) -> None:
        """Clear the stored author-voice profile for a novel.

        Sets the column to NULL (the user returns to the default AI style).
        No-op when no row exists. Mirrors the spec's "Delete it anytime to
        return to the default AI style" UX.
        """
        stmt = (
            update(ProjectSettings)
            .where(ProjectSettings.novel_id == novel_id)
            .values(author_voice=None)
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def delete_row(self, novel_id: UUID) -> None:
        """Delete the ``ProjectSettings`` row for a novel.

        Test-helper / cascade-cleanup helper. Production callers use
        :meth:`clear` (the user-facing "delete profile" action sets the column
        to NULL, preserving the rest of the project settings row).
        """
        stmt = delete(ProjectSettings).where(ProjectSettings.novel_id == novel_id)
        await self._session.execute(stmt)
        await self._session.flush()
