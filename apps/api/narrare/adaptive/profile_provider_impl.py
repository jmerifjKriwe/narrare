"""Backend ProfileProvider — loads ProjectWritingProfile from KB (ADR-069).

Closes the Phase 2 boundary gap: ``AdaptiveContextProviderImpl`` was wired
with ``profile_provider=None`` because no Backend ProfileProvider existed.
This module ships the consolidated adapter the invocation pipeline (and the
REST dashboard path) consume.

Pattern mirrors ``apps/api/narrare/kb/kb_suggested_provider.py`` (the
singleton-compatible session-factory provider shipped under ADR-048 Q3) and
composes the same
:func:`build_character_voice_profile` + :class:`ProfileAssembler` path over
KB character entities that ``apps/api/narrare/writing/voice_profile_adapter.py``
uses on the writing-API side. Task 15 does NOT duplicate extraction logic.

ADR-055/057 boundary: this provider surfaces ONLY the descriptive
``speech_summary`` via :attr:`ProjectWritingProfile.formatted_voice_profiles`.
Numeric ``voice_metrics`` (when present on ``CharacterVoiceProfile``) are
never read by the adaptive enricher and never enter ``AdaptiveContext``.

RULE-11 graceful degradation: returns ``None`` when the KB query fails,
returns no characters, or no character has ``speech.voice_analysis``. The
caller (``AdaptiveContextProviderImpl``) handles ``None`` correctly — empty
``voice_profiles_text``, dashboard shows "no voice signals".

See:
    ADR-069 Decision 4 (ProfileProvider boundary),
    ADR-050 P1-C (writing-side VoiceProfileConsumer precedent),
    ADR-055/057 (voice_metrics stay checking-path only),
    CONSTRAINTS.md RULE-08 (external integrations abstracted), RULE-11.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.profiles._voice_extraction import build_character_voice_profile
from narrare_core.profiles.assembly import ProfileAssembler

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from narrare.kb.models import KBEntry
    from narrare_core.profiles.models import CharacterVoiceProfile, ProjectWritingProfile

logger = structlog.get_logger(__name__)

#: Freshness window (days) passed to extraction + assembly. Matches the
#: ProfileAssembler default and the writing-side adapter.
_DEFAULT_MAX_AGE_DAYS: int = 30


def _to_uuid(value: object) -> UUID | None:
    """Resolve a ``project_id: object`` to a UUID, or None if unresolvable.

    Mirrors the resolution strategy of
    :func:`narrare.kb.kb_suggested_provider._resolve_novel_id` without
    importing that module-private helper (avoids cross-module private
    coupling). Localised here so the query + ``assemble()`` calls stay
    type-clean (UUID, not object) and unresolvable ids short-circuit
    before hitting the database.
    """
    import uuid

    if isinstance(value, uuid.UUID):
        return value
    if isinstance(value, str):
        try:
            return uuid.UUID(value)
        except ValueError:
            return None
    return None


class _CharacterVoiceProfileProvider:
    """Single-snapshot provider over character KB entities.

    Adapter around :func:`build_character_voice_profile` so the
    :class:`ProfileAssembler` consumes the same extraction path as the
    writing-side adapter. Filters to characters with populated
    ``speech.voice_analysis`` — the adaptive context surfaces
    machine-derived voice signals (ANAL-008), not every hand-written
    speech note.
    """

    def __init__(self, entities: Sequence[KBEntry]) -> None:
        self._entities = entities

    async def get_character_voices(
        self,
        project_id: UUID,
        *,
        max_age_days: int = _DEFAULT_MAX_AGE_DAYS,
    ) -> list[CharacterVoiceProfile]:
        """Return voice profiles for characters with voice_analysis.

        Args:
            project_id: Project identifier (contract compatibility — the
                snapshot is already scoped by the caller's query).
            max_age_days: Freshness window for stale-profile labelling.

        Returns:
            Character voice profiles for characters whose
            ``speech.voice_analysis`` block is populated.
        """
        del project_id  # snapshot already scoped by the caller
        profiles: list[CharacterVoiceProfile] = []
        for entity in self._entities:
            if entity.entity_type != "character":
                continue
            metadata = entity.metadata_
            if not isinstance(metadata, dict):
                continue
            speech = metadata.get("speech")
            if not isinstance(speech, dict) or "voice_analysis" not in speech:
                continue
            updated_at = _to_iso(entity.updated_at)
            profile = build_character_voice_profile(
                entity_id=str(entity.id),
                name=entity.name,
                metadata=entity.metadata_,
                updated_at=updated_at,
                max_age_days=max_age_days,
            )
            if profile is not None:
                profiles.append(profile)
        return profiles


def _to_iso(updated_at: datetime | None) -> str | None:
    """Convert a KBEntry ``updated_at`` datetime to the ISO-8601 str the
    extraction function expects, or None."""
    if updated_at is None:
        return None
    return updated_at.isoformat()


class BackendProfileProvider:
    """Production :class:`ProfileProvider` for the invocation pipeline.

    Bound to a session factory (NOT a request-scoped session) so it can be
    wired into the ``@lru_cache``-decorated ``get_invocation_pipeline()``
    singleton and the request-scoped REST dashboard path alike. Each
    ``get_profile()`` call opens a short-lived session, loads character KB
    entities, filters to those with voice_analysis, and assembles the
    :class:`ProjectWritingProfile`.

    Args:
        session_factory: Callable returning a fresh ``AsyncSession``
            (production: ``get_session_factory()``).
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_profile(
        self,
        project_id: object,
    ) -> ProjectWritingProfile | None:
        """Load the project writing profile from KB character entities.

        Args:
            project_id: The project identifier (resolved to UUID).

        Returns:
            The assembled :class:`ProjectWritingProfile`, or ``None`` when
            the id is unresolvable, the KB query fails, or no character
            entity has populated ``speech.voice_analysis`` (RULE-11
            graceful degradation).
        """
        novel_id = _to_uuid(project_id)
        if novel_id is None:
            logger.debug(
                "backend_profile_provider_unresolvable_project",
                project_id_type=type(project_id).__name__,
            )
            return None

        # Lazy import keeps the module-level dependency graph clean (the KB
        # model is an API-layer class; importing eagerly would couple this
        # adapter's import time to SQLAlchemy model metadata initialisation).
        from sqlalchemy import select

        from narrare.kb.models import KBEntry

        try:
            async with self._session_factory() as session:
                stmt = (
                    select(KBEntry)
                    .where(KBEntry.novel_id == novel_id)
                    .where(KBEntry.entity_type == "character")
                )
                result = await session.execute(stmt)
                entries: list[KBEntry] = list(result.scalars().all())
        except Exception:
            logger.warning(
                "backend_profile_provider_kb_load_failed",
                project_id=str(novel_id),
                exc_info=True,
            )
            return None

        if not entries:
            return None

        provider = _CharacterVoiceProfileProvider(entries)
        assembler = ProfileAssembler(provider=provider)
        try:
            profile = await assembler.assemble(
                project_id=novel_id,
                max_age_days=_DEFAULT_MAX_AGE_DAYS,
            )
        except Exception:
            logger.warning(
                "backend_profile_provider_assemble_failed",
                project_id=str(novel_id),
                exc_info=True,
            )
            return None

        # Drop the profile when no character contributed a voice profile
        # (assembler returns an empty-shell ProjectWritingProfile when the
        # provider yields no voices — e.g. no character had voice_analysis).
        if not profile.formatted_voice_profiles.strip():
            return None
        return profile
