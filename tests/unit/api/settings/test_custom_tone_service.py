"""Unit tests for CustomToneService — validation, limits, CRUD logic."""

from __future__ import annotations

import uuid

import pytest

from narrare.settings.custom_tone_service import CustomToneService
from narrare.settings.schemas_tones import CustomToneCreate, CustomToneUpdate
from narrare_core.shared.errors import NotFoundError, ValidationError
from tests.fakes.fake_user_settings_repo import FakeUserSettingsRepository


@pytest.fixture
def repo() -> FakeUserSettingsRepository:
    return FakeUserSettingsRepository()


@pytest.fixture
def service(repo: FakeUserSettingsRepository) -> CustomToneService:
    return CustomToneService(repo)


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


def _make_tone_data(
    name: str = "Dark Humor", instructions: str = "Write with dark humor."
) -> dict[str, object]:
    return {"id": str(uuid.uuid4()), "name": name, "instructions": instructions}


# ---------------------------------------------------------------------------
# list_tones
# ---------------------------------------------------------------------------


class TestListTones:
    async def test_returns_empty_list_for_new_user(
        self, service: CustomToneService, user_id: uuid.UUID
    ) -> None:
        result = await service.list_tones(user_id)
        assert result == []

    async def test_returns_existing_tones(
        self, service: CustomToneService, user_id: uuid.UUID, repo: FakeUserSettingsRepository
    ) -> None:
        tone_data = _make_tone_data()
        repo.seed(user_id, custom_tones=[tone_data])

        result = await service.list_tones(user_id)
        assert len(result) == 1
        assert result[0].name == "Dark Humor"

    async def test_skips_invalid_tone_entries(
        self, service: CustomToneService, user_id: uuid.UUID, repo: FakeUserSettingsRepository
    ) -> None:
        repo.seed(
            user_id,
            custom_tones=[
                _make_tone_data(),
                {"invalid": "no name or instructions"},  # type: ignore[dict-item]
            ],
        )

        result = await service.list_tones(user_id)
        assert len(result) == 1  # Invalid entry skipped


# ---------------------------------------------------------------------------
# create_tone
# ---------------------------------------------------------------------------


class TestCreateTone:
    async def test_creates_tone_successfully(
        self, service: CustomToneService, user_id: uuid.UUID
    ) -> None:
        request = CustomToneCreate(name="Epic", instructions="Write in an epic style.")
        result = await service.create_tone(user_id, request)

        assert result.name == "Epic"
        assert result.instructions == "Write in an epic style."
        assert result.id  # UUID string assigned

    async def test_created_tone_appears_in_list(
        self, service: CustomToneService, user_id: uuid.UUID
    ) -> None:
        await service.create_tone(
            user_id, CustomToneCreate(name="Gothic", instructions="Dark and moody.")
        )

        tones = await service.list_tones(user_id)
        assert len(tones) == 1
        assert tones[0].name == "Gothic"

    async def test_duplicate_name_rejected(
        self, service: CustomToneService, user_id: uuid.UUID
    ) -> None:
        await service.create_tone(
            user_id, CustomToneCreate(name="Noir", instructions="Hard-boiled.")
        )

        with pytest.raises(ValidationError, match="already exists"):
            await service.create_tone(
                user_id, CustomToneCreate(name="Noir", instructions="Different.")
            )

    async def test_max_tones_enforced(self, service: CustomToneService, user_id: uuid.UUID) -> None:
        for i in range(20):
            await service.create_tone(
                user_id,
                CustomToneCreate(name=f"Tone {i}", instructions=f"Instructions {i}"),
            )

        with pytest.raises(ValidationError, match="Maximum"):
            await service.create_tone(
                user_id,
                CustomToneCreate(name="Overflow", instructions="One too many."),
            )


# ---------------------------------------------------------------------------
# update_tone
# ---------------------------------------------------------------------------


class TestUpdateTone:
    async def test_update_name(self, service: CustomToneService, user_id: uuid.UUID) -> None:
        created = await service.create_tone(
            user_id, CustomToneCreate(name="Original", instructions="Original instructions.")
        )

        updated = await service.update_tone(user_id, created.id, CustomToneUpdate(name="Renamed"))
        assert updated.name == "Renamed"
        assert updated.instructions == "Original instructions."

    async def test_update_instructions(
        self, service: CustomToneService, user_id: uuid.UUID
    ) -> None:
        created = await service.create_tone(
            user_id, CustomToneCreate(name="Tone", instructions="Old instructions.")
        )

        updated = await service.update_tone(
            user_id, created.id, CustomToneUpdate(instructions="New instructions.")
        )
        assert updated.instructions == "New instructions."
        assert updated.name == "Tone"

    async def test_update_nonexistent_tone_raises_not_found(
        self, service: CustomToneService, user_id: uuid.UUID
    ) -> None:
        with pytest.raises(NotFoundError):
            await service.update_tone(user_id, str(uuid.uuid4()), CustomToneUpdate(name="Ghost"))

    async def test_update_name_to_existing_name_rejected(
        self, service: CustomToneService, user_id: uuid.UUID
    ) -> None:
        tone_a = await service.create_tone(
            user_id, CustomToneCreate(name="Tone A", instructions="A")
        )
        await service.create_tone(user_id, CustomToneCreate(name="Tone B", instructions="B"))

        with pytest.raises(ValidationError, match="already exists"):
            await service.update_tone(user_id, tone_a.id, CustomToneUpdate(name="Tone B"))


# ---------------------------------------------------------------------------
# delete_tone
# ---------------------------------------------------------------------------


class TestDeleteTone:
    async def test_delete_removes_tone(
        self, service: CustomToneService, user_id: uuid.UUID
    ) -> None:
        created = await service.create_tone(
            user_id, CustomToneCreate(name="ToDelete", instructions="Bye.")
        )

        await service.delete_tone(user_id, created.id)

        tones = await service.list_tones(user_id)
        assert len(tones) == 0

    async def test_delete_nonexistent_tone_raises_not_found(
        self, service: CustomToneService, user_id: uuid.UUID
    ) -> None:
        with pytest.raises(NotFoundError):
            await service.delete_tone(user_id, str(uuid.uuid4()))

    async def test_delete_one_of_many_preserves_others(
        self, service: CustomToneService, user_id: uuid.UUID
    ) -> None:
        t1 = await service.create_tone(user_id, CustomToneCreate(name="Keep", instructions="Stay."))
        t2 = await service.create_tone(
            user_id, CustomToneCreate(name="Remove", instructions="Go away.")
        )

        await service.delete_tone(user_id, t2.id)

        tones = await service.list_tones(user_id)
        assert len(tones) == 1
        assert tones[0].id == t1.id
