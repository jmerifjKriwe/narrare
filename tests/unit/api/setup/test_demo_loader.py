"""Unit tests for setup/demo_loader.py"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from narrare.setup.demo_loader import (
    DemoLoader,
    _clear_demo_info_cache,
    _load_demo_info,
)
from narrare.setup.schemas import StarterContent

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture(autouse=True)
def _reset_cache() -> Generator[None]:  # pyright: ignore[reportUnusedFunction]
    """Clear the demo info cache before and after each test."""
    _clear_demo_info_cache()
    yield
    _clear_demo_info_cache()


@pytest.fixture
def mock_session() -> MagicMock:
    session = MagicMock(spec=AsyncSession)
    session.flush = AsyncMock()
    return session


@pytest.fixture
def loader(mock_session: MagicMock) -> DemoLoader:
    return DemoLoader(mock_session)


# Root path to real demo data in the repository
_REPO_ROOT = Path(__file__).parent.parent.parent.parent.parent
_DEMO_DATA_ROOT = _REPO_ROOT / "apps" / "api" / "narrare" / "setup" / "demo_data"


class TestLoadDemoInfo:
    """Test the _load_demo_info helper that reads metadata.json files."""

    def test_load_fantasy_metadata_from_file(self) -> None:
        info = _load_demo_info(StarterContent.DEMO_FANTASY)
        assert info.id == StarterContent.DEMO_FANTASY
        assert info.title == "Echoes of the Thornwall"
        assert info.writing_language == "en"
        assert info.genre == "Fantasy"
        assert info.chapter_count == 4
        assert info.character_count == 5
        assert info.word_count == 3130
        assert "mage" in info.description.lower() or "thornwall" in info.description.lower()

    def test_load_scifi_metadata_from_file(self) -> None:
        info = _load_demo_info(StarterContent.DEMO_SCIFI)
        assert info.id == StarterContent.DEMO_SCIFI
        assert info.title == "Dead Signal"
        assert info.writing_language == "en"
        assert info.genre == "Science Fiction"
        assert info.chapter_count == 3

    def test_load_german_metadata_from_file(self) -> None:
        info = _load_demo_info(StarterContent.DEMO_GERMAN)
        assert info.id == StarterContent.DEMO_GERMAN
        assert info.title == "Im Stillen Wald"
        assert info.writing_language == "de"

    def test_load_demo_info_populates_project_md_fields(self) -> None:
        """New fields (author, logline, pov, tags) come from project_md."""
        info = _load_demo_info(StarterContent.DEMO_FANTASY)
        assert info.author == "Narrare Demo"
        assert info.logline != ""
        assert info.pov != ""
        assert len(info.tags) > 0
        assert "fantasy" in info.tags

    def test_load_demo_info_scifi_project_md_fields(self) -> None:
        info = _load_demo_info(StarterContent.DEMO_SCIFI)
        assert info.author == "Narrare Demo"
        assert info.logline != ""
        assert info.pov == "First Person"
        assert "sci-fi" in info.tags

    def test_load_demo_info_german_project_md_fields(self) -> None:
        info = _load_demo_info(StarterContent.DEMO_GERMAN)
        assert info.author == "Narrare Demo"
        assert info.logline != ""
        assert info.pov == "Third Person Limited"
        assert "german" in info.tags

    def test_load_demo_info_missing_starter_raises_key_error(self) -> None:
        with pytest.raises(KeyError, match="No demo directory"):
            _load_demo_info(StarterContent.BLANK)

    def test_load_demo_info_missing_file_raises_file_not_found(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When metadata.json is missing, FileNotFoundError is raised."""
        import narrare.setup.demo_loader as mod

        empty_dir = tmp_path / "demo_data" / "en" / "missing-demo"
        empty_dir.mkdir(parents=True)
        monkeypatch.setattr(mod, "_DEMO_ROOT", tmp_path / "demo_data")
        # Add a mapping that points to the directory without metadata.json
        monkeypatch.setitem(mod._DEMO_DIRS, StarterContent.DEMO_FANTASY, "en/missing-demo")

        with pytest.raises(FileNotFoundError, match="metadata not found"):
            _load_demo_info(StarterContent.DEMO_FANTASY)


class TestCaching:
    """Test that _get_demo_info caches results."""

    def test_second_call_returns_cached_object(self) -> None:
        from narrare.setup.demo_loader import _get_demo_info

        info1 = _get_demo_info(StarterContent.DEMO_FANTASY)
        info2 = _get_demo_info(StarterContent.DEMO_FANTASY)
        assert info1 is info2

    def test_cache_is_per_starter(self) -> None:
        from narrare.setup.demo_loader import _get_demo_info

        fantasy = _get_demo_info(StarterContent.DEMO_FANTASY)
        scifi = _get_demo_info(StarterContent.DEMO_SCIFI)
        assert fantasy is not scifi
        assert fantasy.title != scifi.title


class TestGetInfo:
    def test_returns_info_for_german_demo(self, loader: DemoLoader) -> None:
        info = loader.get_info(StarterContent.DEMO_GERMAN)
        assert info.title == "Im Stillen Wald"
        assert info.writing_language == "de"
        assert info.chapter_count == 2
        assert info.character_count == 3

    def test_returns_info_for_fantasy_demo(self, loader: DemoLoader) -> None:
        info = loader.get_info(StarterContent.DEMO_FANTASY)
        assert info.title == "Echoes of the Thornwall"
        assert info.writing_language == "en"

    def test_returns_info_for_scifi_demo(self, loader: DemoLoader) -> None:
        info = loader.get_info(StarterContent.DEMO_SCIFI)
        assert info.title == "Dead Signal"

    def test_raises_for_blank_starter(self, loader: DemoLoader) -> None:
        with pytest.raises(KeyError):
            loader.get_info(StarterContent.BLANK)

    def test_all_demo_info_returns_all_three(self, loader: DemoLoader) -> None:
        all_info = loader.all_demo_info()
        assert len(all_info) == 3
        titles = {i.title for i in all_info}
        assert "Im Stillen Wald" in titles
        assert "Echoes of the Thornwall" in titles
        assert "Dead Signal" in titles

    def test_get_info_populates_new_fields(self, loader: DemoLoader) -> None:
        """DemoProjectInfo from get_info has author, logline, pov, tags."""
        info = loader.get_info(StarterContent.DEMO_FANTASY)
        assert info.author == "Narrare Demo"
        assert info.logline != ""
        assert info.pov != ""
        assert len(info.tags) > 0


class TestLoadChapters:
    async def test_loads_chapters_from_files(self, loader: DemoLoader, tmp_path: Path) -> None:
        """Test that chapters are created from Markdown files."""
        chapters_dir = tmp_path / "chapters"
        chapters_dir.mkdir()

        # Write a test chapter file
        (chapters_dir / "ch-001-test.md").write_text(
            "---\ntitle: Test Chapter\nstatus: draft\n---\n\nOnce upon a time.",
            encoding="utf-8",
        )

        novel_id = uuid.uuid4()
        await loader._load_chapters(chapters_dir, novel_id)

        # One chapter should have been added to the session
        loader._session.add.assert_called_once()  # pyright: ignore[reportAttributeAccessIssue]
        chapter = loader._session.add.call_args[0][0]  # pyright: ignore[reportAttributeAccessIssue]
        assert chapter.title == "Test Chapter"
        assert chapter.content == "Once upon a time."
        assert chapter.word_count == 4

    async def test_skips_missing_chapters_dir(self, loader: DemoLoader, tmp_path: Path) -> None:
        """Missing chapters directory is handled gracefully."""
        await loader._load_chapters(tmp_path / "nonexistent", uuid.uuid4())
        loader._session.add.assert_not_called()  # pyright: ignore[reportAttributeAccessIssue]

    async def test_raises_for_non_demo_starter(self, loader: DemoLoader) -> None:
        with pytest.raises(ValueError, match="Not a demo starter"):
            await loader.load(StarterContent.BLANK, uuid.uuid4(), uuid.uuid4())
