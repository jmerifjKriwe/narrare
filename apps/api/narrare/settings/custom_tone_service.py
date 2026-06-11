"""Custom tone CRUD service — business logic for user-defined writing tones.

Manages custom tones stored as a JSONB array on the user_settings table.
Validates name uniqueness, count limits, and field constraints.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import structlog

from narrare_core.shared.errors import NotFoundError, ValidationError

if TYPE_CHECKING:
    import uuid

    from narrare.settings.contracts import UserSettingsRepositoryProtocol

from narrare.settings.schemas_tones import CustomTone, CustomToneCreate, CustomToneUpdate

logger = structlog.get_logger(__name__)


class CustomToneService:
    """CRUD operations for user-defined writing tones.

    Tones are stored as a JSON array in user_settings.custom_tones.

    Args:
        repo: User settings repository for persistence.
        max_custom_tones: Maximum number of custom tones per user.
    """

    def __init__(
        self,
        repo: UserSettingsRepositoryProtocol,
        *,
        max_custom_tones: int = 20,
    ) -> None:
        self._repo = repo
        self._max_custom_tones = max_custom_tones

    async def list_tones(self, user_id: uuid.UUID) -> list[CustomTone]:
        """List all custom tones for a user.

        Args:
            user_id: The user whose tones to list.

        Returns:
            List of CustomTone objects.
        """
        settings = await self._repo.get(user_id)
        return self._parse_tones(settings.custom_tones)

    async def create_tone(self, user_id: uuid.UUID, request: CustomToneCreate) -> CustomTone:
        """Create a new custom tone for a user.

        Args:
            user_id: The user who owns the tone.
            request: Tone creation data.

        Returns:
            The newly created CustomTone.

        Raises:
            ValidationError: If max tones exceeded or name is not unique.
        """
        settings = await self._repo.get(user_id)
        existing = self._parse_tones(settings.custom_tones)

        if len(existing) >= self._max_custom_tones:
            raise ValidationError(f"Maximum of {self._max_custom_tones} custom tones reached")

        if any(t.name == request.name for t in existing):
            raise ValidationError(f"Custom tone with name '{request.name}' already exists")

        import uuid as uuid_mod

        new_tone = CustomTone(
            id=str(uuid_mod.uuid4()),
            name=request.name,
            instructions=request.instructions,
        )

        updated_tones = [t.model_dump() for t in existing] + [new_tone.model_dump()]

        from narrare.settings.schemas import UpdateUserSettingsRequest

        await self._repo.update(
            user_id,
            UpdateUserSettingsRequest(custom_tones=cast("list[dict[str, object]]", updated_tones)),
        )

        logger.info(
            "custom_tone_created",
            user_id=str(user_id),
            tone_name=request.name,
        )
        return new_tone

    async def update_tone(
        self, user_id: uuid.UUID, tone_id: str, request: CustomToneUpdate
    ) -> CustomTone:
        """Update an existing custom tone.

        Args:
            user_id: The user who owns the tone.
            tone_id: The ID of the tone to update.
            request: Partial update data.

        Returns:
            The updated CustomTone.

        Raises:
            NotFoundError: If tone_id not found for this user.
            ValidationError: If new name conflicts with existing tone.
        """
        settings = await self._repo.get(user_id)
        existing = self._parse_tones(settings.custom_tones)

        target_idx = None
        for i, t in enumerate(existing):
            if t.id == tone_id:
                target_idx = i
                break

        if target_idx is None:
            raise NotFoundError("CustomTone", identifier=tone_id)

        # Check name uniqueness if name is being changed
        new_name = request.name if request.name is not None else existing[target_idx].name
        for i, t in enumerate(existing):
            if i != target_idx and t.name == new_name:
                raise ValidationError(f"Custom tone with name '{new_name}' already exists")

        updated_tone = CustomTone(
            id=existing[target_idx].id,
            name=request.name if request.name is not None else existing[target_idx].name,
            instructions=request.instructions
            if request.instructions is not None
            else existing[target_idx].instructions,
        )

        existing[target_idx] = updated_tone
        updated_tones = [t.model_dump() for t in existing]

        from narrare.settings.schemas import UpdateUserSettingsRequest

        await self._repo.update(
            user_id,
            UpdateUserSettingsRequest(custom_tones=cast("list[dict[str, object]]", updated_tones)),
        )

        logger.info(
            "custom_tone_updated",
            user_id=str(user_id),
            tone_id=tone_id,
        )
        return updated_tone

    async def delete_tone(self, user_id: uuid.UUID, tone_id: str) -> None:
        """Delete a custom tone.

        Args:
            user_id: The user who owns the tone.
            tone_id: The ID of the tone to delete.

        Raises:
            NotFoundError: If tone_id not found for this user.
        """
        settings = await self._repo.get(user_id)
        existing = self._parse_tones(settings.custom_tones)

        filtered = [t for t in existing if t.id != tone_id]
        if len(filtered) == len(existing):
            raise NotFoundError("CustomTone", identifier=tone_id)

        updated_tones = [t.model_dump() for t in filtered]

        from narrare.settings.schemas import UpdateUserSettingsRequest

        await self._repo.update(
            user_id,
            UpdateUserSettingsRequest(custom_tones=cast("list[dict[str, object]]", updated_tones)),
        )

        logger.info(
            "custom_tone_deleted",
            user_id=str(user_id),
            tone_id=tone_id,
        )

    def _parse_tones(self, raw: list[object]) -> list[CustomTone]:
        """Parse JSONB tone data into CustomTone models.

        Args:
            raw: Raw JSONB data from the database.

        Returns:
            Validated list of CustomTone objects.
        """
        tones: list[CustomTone] = []
        for item in raw:
            if isinstance(item, dict):
                try:
                    tones.append(CustomTone.model_validate(item))
                except Exception:
                    logger.warning("invalid_custom_tone_skipped", data=item)
        return tones
