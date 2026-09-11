"""Unit tests for AI-settings repositories (fake session).

Covers ``ProjectAiSettingsRepository``, ``UserAiSettingsRepository`` and
``UserProvidersRepository`` — the auto-create-on-miss ``get()`` path, the
setattr ``update()`` loop, and the provider CRUD including the
``ValueError`` on missing update and the ``count ... or 0`` fallback.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from uuid import uuid4

import pytest

from narrare.settings.models import ProjectSettings, UserAiSettings, UserProvider
from narrare.settings.project_ai_settings_repository import ProjectAiSettingsRepository
from narrare.settings.user_ai_settings_repository import UserAiSettingsRepository
from narrare.settings.user_providers_repository import UserProvidersRepository
from tests.fakes.fake_db_session import FakeDbSession, FakeResult

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# ProjectAiSettingsRepository
# ---------------------------------------------------------------------------


class TestProjectAiSettingsRepository:
    async def test_get_returns_existing_settings(self) -> None:
        settings = ProjectSettings(novel_id=uuid4())
        session = FakeDbSession([FakeResult(value=settings)])
        repo = ProjectAiSettingsRepository(cast("AsyncSession", session))

        result = await repo.get(settings.novel_id)

        assert result is settings
        assert session.added == []

    async def test_get_auto_creates_when_missing(self) -> None:
        """When no row exists, get() upserts (ON CONFLICT DO NOTHING) and
        re-selects the created row — no add()+flush() (race-safe)."""
        novel_id = uuid4()
        created = ProjectSettings(novel_id=novel_id)
        session = FakeDbSession(
            [
                FakeResult(value=None),  # initial select: miss
                FakeResult(value=None),  # INSERT ... ON CONFLICT DO NOTHING
                FakeResult(value=created),  # re-select reads the new row back
            ]
        )
        repo = ProjectAiSettingsRepository(cast("AsyncSession", session))

        result = await repo.get(novel_id)

        assert result is created
        assert session.added == []
        assert session.flush_count == 0

    async def test_update_sets_fields_on_existing_row(self) -> None:
        settings = ProjectSettings(novel_id=uuid4())
        session = FakeDbSession([FakeResult(value=settings)])
        repo = ProjectAiSettingsRepository(cast("AsyncSession", session))

        result = await repo.update(settings.novel_id, category_overrides={"drafting": "x"})

        assert result.category_overrides == {"drafting": "x"}
        assert session.flush_count == 1


# ---------------------------------------------------------------------------
# UserAiSettingsRepository
# ---------------------------------------------------------------------------


class TestUserAiSettingsRepository:
    async def test_get_returns_existing_settings(self) -> None:
        settings = UserAiSettings(user_id=uuid4())
        session = FakeDbSession([FakeResult(value=settings)])
        repo = UserAiSettingsRepository(cast("AsyncSession", session))

        result = await repo.get(settings.user_id)

        assert result is settings

    async def test_get_auto_creates_when_missing(self) -> None:
        """When no row exists, get() upserts (ON CONFLICT DO NOTHING) and
        re-selects the created row — no add()+flush() (race-safe)."""
        user_id = uuid4()
        created = UserAiSettings(user_id=user_id)
        session = FakeDbSession(
            [
                FakeResult(value=None),  # initial select: miss
                FakeResult(value=None),  # INSERT ... ON CONFLICT DO NOTHING
                FakeResult(value=created),  # re-select reads the new row back
            ]
        )
        repo = UserAiSettingsRepository(cast("AsyncSession", session))

        result = await repo.get(user_id)

        assert result is created
        assert session.added == []
        assert session.flush_count == 0

    async def test_update_sets_default_model(self) -> None:
        settings = UserAiSettings(user_id=uuid4())
        session = FakeDbSession([FakeResult(value=settings)])
        repo = UserAiSettingsRepository(cast("AsyncSession", session))

        result = await repo.update(settings.user_id, default_model="claude-sonnet")

        assert result.default_model == "claude-sonnet"


# ---------------------------------------------------------------------------
# UserProvidersRepository
# ---------------------------------------------------------------------------


class TestUserProvidersRepositoryCreate:
    async def test_create_adds_and_flushes(self) -> None:
        session = FakeDbSession()
        repo = UserProvidersRepository(cast("AsyncSession", session))

        result = await repo.create(uuid4(), "anthropic", "enc-key", "https://api.x")

        assert result.provider_name == "anthropic"
        assert result.api_key_encrypted == "enc-key"
        assert result.base_url == "https://api.x"
        assert len(session.added) == 1
        assert session.flush_count == 1


class TestUserProvidersRepositoryReads:
    async def _repo(self, result: FakeResult) -> UserProvidersRepository:
        return UserProvidersRepository(cast("AsyncSession", FakeDbSession([result])))

    async def test_get_returns_provider(self) -> None:
        provider = UserProvider(provider_name="openai")
        repo = await self._repo(FakeResult(value=provider))

        assert await repo.get(uuid4()) is provider

    async def test_get_returns_none_when_missing(self) -> None:
        repo = await self._repo(FakeResult(value=None))
        assert await repo.get(uuid4()) is None

    async def test_get_by_user_returns_list(self) -> None:
        providers = [UserProvider(provider_name="a"), UserProvider(provider_name="b")]
        repo = await self._repo(FakeResult(scalars=providers))

        assert await repo.get_by_user(uuid4()) == providers

    async def test_get_active_returns_list(self) -> None:
        active = [UserProvider(provider_name="a")]
        repo = await self._repo(FakeResult(scalars=active))

        assert await repo.get_active(uuid4()) == active

    async def test_get_by_name_returns_match(self) -> None:
        provider = UserProvider(provider_name="anthropic")
        repo = await self._repo(FakeResult(value=provider))

        assert await repo.get_by_name(uuid4(), "anthropic") is provider

    async def test_count_by_user_returns_count(self) -> None:
        repo = await self._repo(FakeResult(value=3))
        assert await repo.count_by_user(uuid4()) == 3

    async def test_count_by_user_returns_zero_when_none(self) -> None:
        """A None aggregate resolves to 0 via ``or 0``."""
        repo = await self._repo(FakeResult(value=None))
        assert await repo.count_by_user(uuid4()) == 0


class TestUserProvidersRepositoryUpdate:
    async def test_update_sets_fields(self) -> None:
        provider = UserProvider(provider_name="openai")
        session = FakeDbSession([FakeResult(value=provider)])
        repo = UserProvidersRepository(cast("AsyncSession", session))

        result = await repo.update(provider.id, is_active=False)

        assert result.is_active is False
        assert session.flush_count == 1

    async def test_update_raises_when_not_found(self) -> None:
        session = FakeDbSession([FakeResult(value=None)])
        repo = UserProvidersRepository(cast("AsyncSession", session))

        with pytest.raises(ValueError):
            await repo.update(uuid4(), is_active=False)


class TestUserProvidersRepositoryDelete:
    async def test_delete_removes_existing_provider(self) -> None:
        provider = UserProvider(provider_name="openai")
        session = FakeDbSession([FakeResult(value=provider)])
        repo = UserProvidersRepository(cast("AsyncSession", session))

        await repo.delete(provider.id)

        assert session.deleted == [provider]
        assert session.flush_count == 1

    async def test_delete_is_noop_when_missing(self) -> None:
        session = FakeDbSession([FakeResult(value=None)])
        repo = UserProvidersRepository(cast("AsyncSession", session))

        await repo.delete(uuid4())

        assert session.deleted == []
        assert session.flush_count == 0
