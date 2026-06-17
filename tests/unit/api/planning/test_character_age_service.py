"""Tests for character_age_service.py — uncovered branches and error paths.

Covers:
1. get_character_ages happy path (birth dates present and absent)
2. get_character_ages when novel not found (NotFoundError)
3. get_character_ages with no KB repository
4. load_birth_date_map with various date states
5. _load_character_entries fallbacks (None repo, exception)
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare.kb.models import KBEntry
from narrare.kb.repository import KBRepository
from narrare.novels.models import Novel
from narrare.novels.repository import NovelRepository
from narrare.planning.character_age_service import CharacterAgeService
from narrare_core.shared.errors import NotFoundError


@pytest.fixture
def novel_repo() -> MagicMock:
    repo = MagicMock(spec=NovelRepository)
    repo.get_by_id = AsyncMock()
    return repo


@pytest.fixture
def kb_repo() -> MagicMock:
    repo = MagicMock(spec=KBRepository)
    repo.list_entries = AsyncMock()
    return repo


def _make_kb_entry(
    name: str,
    birth_date: str | None = None,
    birth_date_narrative: str | None = None,
) -> MagicMock:
    entry = MagicMock(spec=KBEntry)
    entry.name = name
    entry.id = uuid.uuid4()
    metadata: dict[str, object] = {}
    if birth_date is not None:
        metadata["birth_date"] = birth_date
    if birth_date_narrative is not None:
        metadata["birth_date_narrative"] = birth_date_narrative
    entry.metadata_ = metadata
    return entry


class TestInit:
    def test_stores_repositories(self, novel_repo: MagicMock, kb_repo: MagicMock) -> None:
        service = CharacterAgeService(novel_repo=novel_repo, kb_repo=kb_repo)
        assert service._novel_repo is novel_repo
        assert service._kb_repo is kb_repo

    def test_kb_repo_defaults_to_none(self, novel_repo: MagicMock) -> None:
        service = CharacterAgeService(novel_repo=novel_repo)
        assert service._kb_repo is None


class TestGetCharacterAges:
    async def test_returns_age_report_with_birth_dates(
        self, novel_repo: MagicMock, kb_repo: MagicMock
    ) -> None:
        novel_repo.get_by_id.return_value = MagicMock(spec=Novel)
        entry_with_birth = _make_kb_entry(
            name="Alice", birth_date="1990-01-15", birth_date_narrative="mid-winter"
        )
        entry_without_birth = _make_kb_entry(name="Bob")
        kb_repo.list_entries.return_value = ([entry_with_birth, entry_without_birth], 2)

        service = CharacterAgeService(novel_repo=novel_repo, kb_repo=kb_repo)
        result = await service.get_character_ages(novel_id=uuid.uuid4(), user_id=uuid.uuid4())

        assert result.characters_with_age == 1
        assert result.characters_without_age == 1
        assert len(result.characters) == 2
        alice = next(c for c in result.characters if c.character_name == "Alice")
        assert alice.age_available is True
        assert alice.birth_date == "1990-01-15"
        assert alice.birth_date_narrative == "mid-winter"
        bob = next(c for c in result.characters if c.character_name == "Bob")
        assert bob.age_available is False
        assert bob.birth_date is None

    async def test_raises_not_found_when_novel_missing(
        self, novel_repo: MagicMock, kb_repo: MagicMock
    ) -> None:
        novel_repo.get_by_id.return_value = None
        service = CharacterAgeService(novel_repo=novel_repo, kb_repo=kb_repo)

        with pytest.raises(NotFoundError, match="Novel"):
            await service.get_character_ages(novel_id=uuid.uuid4(), user_id=uuid.uuid4())

    async def test_returns_empty_report_when_no_kb_repo(self, novel_repo: MagicMock) -> None:
        novel_repo.get_by_id.return_value = MagicMock(spec=Novel)
        service = CharacterAgeService(novel_repo=novel_repo, kb_repo=None)

        result = await service.get_character_ages(novel_id=uuid.uuid4(), user_id=uuid.uuid4())

        assert result.characters == []
        assert result.characters_with_age == 0
        assert result.characters_without_age == 0

    async def test_returns_empty_report_when_kb_repo_fails(
        self, novel_repo: MagicMock, kb_repo: MagicMock
    ) -> None:
        novel_repo.get_by_id.return_value = MagicMock(spec=Novel)
        kb_repo.list_entries.side_effect = ValueError("connection error")
        service = CharacterAgeService(novel_repo=novel_repo, kb_repo=kb_repo)

        result = await service.get_character_ages(novel_id=uuid.uuid4(), user_id=uuid.uuid4())

        assert result.characters == []


class TestLoadBirthDateMap:
    async def test_maps_birth_dates_by_name(
        self, novel_repo: MagicMock, kb_repo: MagicMock
    ) -> None:
        kb_repo.list_entries.return_value = (
            [
                _make_kb_entry(name="Alice", birth_date="1990-01-15"),
                _make_kb_entry(name="Bob"),
                _make_kb_entry(name="Carol", birth_date="1985-06-01"),
            ],
            3,
        )
        service = CharacterAgeService(novel_repo=novel_repo, kb_repo=kb_repo)

        result = await service.load_birth_date_map(novel_id=uuid.uuid4())

        assert result == {
            "Alice": "1990-01-15",
            "Bob": None,
            "Carol": "1985-06-01",
        }

    async def test_returns_empty_dict_when_no_entries(
        self, novel_repo: MagicMock, kb_repo: MagicMock
    ) -> None:
        kb_repo.list_entries.return_value = ([], 0)
        service = CharacterAgeService(novel_repo=novel_repo, kb_repo=kb_repo)

        result = await service.load_birth_date_map(novel_id=uuid.uuid4())

        assert result == {}


class TestLoadCharacterEntries:
    async def test_returns_empty_list_when_kb_repo_is_none(self, novel_repo: MagicMock) -> None:
        service = CharacterAgeService(novel_repo=novel_repo, kb_repo=None)

        result = await service._load_character_entries(novel_id=uuid.uuid4())

        assert result == []

    async def test_returns_empty_list_on_exception(
        self, novel_repo: MagicMock, kb_repo: MagicMock
    ) -> None:
        kb_repo.list_entries.side_effect = RuntimeError("db error")
        service = CharacterAgeService(novel_repo=novel_repo, kb_repo=kb_repo)

        result = await service._load_character_entries(novel_id=uuid.uuid4())

        assert result == []
