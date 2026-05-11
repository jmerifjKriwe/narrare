"""Unit tests for setup/demo_loader.py"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare.setup.demo_loader import DemoLoader
from narrare.setup.schemas import StarterContent

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def mock_session() -> MagicMock:
    # narrare: allow  reason="Mocking SQLAlchemy AsyncSession infrastructure for DemoLoader"
    session = MagicMock()
    # narrare: allow  reason="Mocking SQLAlchemy AsyncSession infrastructure for DemoLoader"
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


@pytest.fixture
def loader(mock_session: MagicMock) -> DemoLoader:
    return DemoLoader(mock_session)


class TestGetInfo:
    def test_returns_info_for_german_demo(self, loader: DemoLoader) -> None:
        info = loader.get_info(StarterContent.DEMO_GERMAN)
        assert info.title == "Im stillen Wald"
        assert info.language == "de"
        assert info.chapter_count == 2
        assert info.character_count == 3

    def test_returns_info_for_fantasy_demo(self, loader: DemoLoader) -> None:
        info = loader.get_info(StarterContent.DEMO_FANTASY)
        assert info.title == "Echoes of the Thornwall"
        assert info.language == "en"

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
        assert "Im stillen Wald" in titles
        assert "Echoes of the Thornwall" in titles
        assert "Dead Signal" in titles


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

        import uuid

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
        import uuid

        await loader._load_chapters(tmp_path / "nonexistent", uuid.uuid4())
        loader._session.add.assert_not_called()  # pyright: ignore[reportAttributeAccessIssue]

    async def test_raises_for_non_demo_starter(self, loader: DemoLoader) -> None:
        import uuid

        with pytest.raises(ValueError, match="Not a demo starter"):
            await loader.load(StarterContent.BLANK, uuid.uuid4(), uuid.uuid4())
