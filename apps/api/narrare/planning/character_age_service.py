"""Character age service — reads KB metadata for age tracking (PLAN-004 Phase 3).

Separate service to keep ``timeline_consistency_service.py`` under the
300-line limit (RULE-04). Responsible for reading character birth dates
from KB entity ``metadata_`` and producing age reports.

Follows Integration Contract: Planning reads KB entities, never writes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.planning.timeline_schemas import CharacterAgeInfo, CharacterAgeReport
from narrare_core.shared.errors import NotFoundError

if TYPE_CHECKING:
    import uuid

    from narrare.kb.models import KBEntry
    from narrare.kb.repository import KBRepository
    from narrare.novels.repository import NovelRepository

logger = structlog.get_logger(__name__)


class CharacterAgeService:
    """Service for character age tracking via KB metadata.

    Reads ``metadata_.birth_date`` and ``metadata_.birth_date_narrative``
    from KB character entities to produce age reports.

    Args:
        novel_repo: For novel existence and ownership verification.
        kb_repo: For reading character entity metadata.
    """

    def __init__(
        self,
        novel_repo: NovelRepository,
        kb_repo: KBRepository | None = None,
    ) -> None:
        self._novel_repo = novel_repo
        self._kb_repo = kb_repo

    async def get_character_ages(
        self,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> CharacterAgeReport:
        """Get character age report based on KB metadata.

        Args:
            novel_id: UUID of the novel.
            user_id: UUID of the requesting user.

        Returns:
            Report listing all characters with their age availability.

        Raises:
            NotFoundError: If the novel does not exist.
        """
        novel = await self._novel_repo.get_by_id(novel_id, user_id)
        if novel is None:
            raise NotFoundError("Novel", identifier=str(novel_id))

        characters = await self._load_character_entries(novel_id)
        character_infos: list[CharacterAgeInfo] = []

        for entry in characters:
            metadata = entry.metadata_ or {}
            birth_date = metadata.get("birth_date")
            birth_date_narrative = metadata.get("birth_date_narrative")

            character_infos.append(
                CharacterAgeInfo(
                    character_name=entry.name,
                    character_id=str(entry.id),
                    birth_date=str(birth_date) if birth_date is not None else None,
                    birth_date_narrative=(
                        str(birth_date_narrative) if birth_date_narrative is not None else None
                    ),
                    age_available=birth_date is not None,
                )
            )

        with_age = sum(1 for c in character_infos if c.age_available)
        without_age = len(character_infos) - with_age

        return CharacterAgeReport(
            characters=character_infos,
            characters_with_age=with_age,
            characters_without_age=without_age,
        )

    async def load_birth_date_map(
        self,
        novel_id: uuid.UUID,
    ) -> dict[str, str | None]:
        """Load character birth dates as a name-to-date mapping.

        Used by the consistency service to pass character ages to
        deterministic checks in ``core/analysis/temporal.py``.

        Args:
            novel_id: UUID of the novel.

        Returns:
            Dict mapping character name to birth_date string or None.
        """
        characters = await self._load_character_entries(novel_id)
        ages: dict[str, str | None] = {}
        for entry in characters:
            metadata = entry.metadata_ or {}
            birth_date = metadata.get("birth_date")
            ages[entry.name] = str(birth_date) if birth_date is not None else None
        return ages

    async def _load_character_entries(self, novel_id: uuid.UUID) -> list[KBEntry]:
        """Load all character KB entries for a novel.

        Returns an empty list when KB repository is not available.
        """
        if self._kb_repo is None:
            return []
        try:
            entries, _total = await self._kb_repo.list_entries(
                novel_id, entity_type="character", page_size=200
            )
            return entries
        except Exception:
            logger.warning("failed_to_load_character_entries", exc_info=True)
            return []
