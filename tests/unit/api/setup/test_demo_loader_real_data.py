"""Extended tests for setup/demo_loader.py — real demo data loading.

Split from test_demo_loader.py to comply with RULE-04 (400-line file limit).
"""

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
)

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


class TestLoadChaptersFantasy:
    """Load Fantasy (Echoes of the Thornwall) chapters from real demo data."""

    FANTASY_CHAPTERS = _DEMO_DATA_ROOT / "en" / "echoes-of-the-thornwall" / "chapters"

    @pytest.mark.skipif(
        not FANTASY_CHAPTERS.exists(),
        reason="Fantasy demo data not available",
    )
    async def test_load_chapters_fantasy_creates_4_chapters(self, loader: DemoLoader) -> None:
        novel_id = uuid.uuid4()
        await loader._load_chapters(self.FANTASY_CHAPTERS, novel_id)

        assert loader._session.add.call_count == 4  # pyright: ignore[reportAttributeAccessIssue]

    @pytest.mark.skipif(
        not FANTASY_CHAPTERS.exists(),
        reason="Fantasy demo data not available",
    )
    async def test_load_chapters_fantasy_titles_non_empty(self, loader: DemoLoader) -> None:
        novel_id = uuid.uuid4()
        await loader._load_chapters(self.FANTASY_CHAPTERS, novel_id)

        chapters = [
            call[0][0]
            for call in loader._session.add.call_args_list  # pyright: ignore[reportAttributeAccessIssue]
        ]
        for chapter in chapters:
            assert chapter.title, "Chapter title should not be empty"
            assert chapter.content, f"Chapter '{chapter.title}' should have non-empty content"
            assert chapter.word_count > 0, f"Chapter '{chapter.title}' should have word_count > 0"

    @pytest.mark.skipif(
        not FANTASY_CHAPTERS.exists(),
        reason="Fantasy demo data not available",
    )
    async def test_load_chapters_fantasy_positions_are_sequential(self, loader: DemoLoader) -> None:
        novel_id = uuid.uuid4()
        await loader._load_chapters(self.FANTASY_CHAPTERS, novel_id)

        chapters = [
            call[0][0]
            for call in loader._session.add.call_args_list  # pyright: ignore[reportAttributeAccessIssue]
        ]
        positions = [ch.position for ch in chapters]
        assert positions == sorted(positions), "Positions should be in order"


class TestLoadChaptersSciFi:
    """Load SciFi (Dead Signal) chapters from real demo data."""

    SCIFI_CHAPTERS = _DEMO_DATA_ROOT / "en" / "dead-signal" / "chapters"

    @pytest.mark.skipif(
        not SCIFI_CHAPTERS.exists(),
        reason="SciFi demo data not available",
    )
    async def test_load_chapters_scifi_creates_3_chapters(self, loader: DemoLoader) -> None:
        novel_id = uuid.uuid4()
        await loader._load_chapters(self.SCIFI_CHAPTERS, novel_id)

        assert loader._session.add.call_count == 3  # pyright: ignore[reportAttributeAccessIssue]

    @pytest.mark.skipif(
        not SCIFI_CHAPTERS.exists(),
        reason="SciFi demo data not available",
    )
    async def test_load_chapters_scifi_titles_and_content_non_empty(
        self, loader: DemoLoader
    ) -> None:
        novel_id = uuid.uuid4()
        await loader._load_chapters(self.SCIFI_CHAPTERS, novel_id)

        chapters = [
            call[0][0]
            for call in loader._session.add.call_args_list  # pyright: ignore[reportAttributeAccessIssue]
        ]
        for chapter in chapters:
            assert chapter.title, "Chapter title should not be empty"
            assert chapter.content, f"Chapter '{chapter.title}' should have non-empty content"


class TestLoadChaptersGerman:
    """Load German (Im Stillen Wald) chapters from real demo data."""

    GERMAN_CHAPTERS = _DEMO_DATA_ROOT / "de" / "im-stillen-wald" / "chapters"

    @pytest.mark.skipif(
        not GERMAN_CHAPTERS.exists(),
        reason="German demo data not available",
    )
    async def test_load_chapters_german_creates_2_chapters(self, loader: DemoLoader) -> None:
        novel_id = uuid.uuid4()
        await loader._load_chapters(self.GERMAN_CHAPTERS, novel_id)

        assert loader._session.add.call_count == 2  # pyright: ignore[reportAttributeAccessIssue]

    @pytest.mark.skipif(
        not GERMAN_CHAPTERS.exists(),
        reason="German demo data not available",
    )
    async def test_load_chapters_german_titles_and_content_non_empty(
        self, loader: DemoLoader
    ) -> None:
        novel_id = uuid.uuid4()
        await loader._load_chapters(self.GERMAN_CHAPTERS, novel_id)

        chapters = [
            call[0][0]
            for call in loader._session.add.call_args_list  # pyright: ignore[reportAttributeAccessIssue]
        ]
        for chapter in chapters:
            assert chapter.title, "Chapter title should not be empty"
            assert chapter.content, f"Chapter '{chapter.title}' should have non-empty content"


class TestLoadKBEntries:
    """Test _load_kb_entries behavior with real and missing KB module."""

    async def test_load_kb_entries_handles_missing_kb_module(
        self, loader: DemoLoader, tmp_path: Path
    ) -> None:
        """When KB module is not available, _load_kb_entries logs and returns."""
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        (kb_dir / "char-test.md").write_text(
            "---\nname: Test Character\ntype: character\n---\n\nA test character.",
            encoding="utf-8",
        )

        novel_id = uuid.uuid4()
        # Should not raise — the ImportError is caught internally
        await loader._load_kb_entries(kb_dir, novel_id)

        # No KB entries should be added since the module doesn't exist
        loader._session.add.assert_not_called()  # pyright: ignore[reportAttributeAccessIssue]

    async def test_load_kb_entries_skips_missing_dir(
        self, loader: DemoLoader, tmp_path: Path
    ) -> None:
        """Missing KB directory is handled gracefully."""
        novel_id = uuid.uuid4()
        await loader._load_kb_entries(tmp_path / "nonexistent", novel_id)
        loader._session.add.assert_not_called()  # pyright: ignore[reportAttributeAccessIssue]

    async def test_load_kb_entries_skips_empty_dir(
        self, loader: DemoLoader, tmp_path: Path
    ) -> None:
        """Empty KB directory is handled gracefully."""
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()

        novel_id = uuid.uuid4()
        await loader._load_kb_entries(kb_dir, novel_id)
        loader._session.add.assert_not_called()  # pyright: ignore[reportAttributeAccessIssue]

    async def test_load_kb_entries_with_mocked_kb_module(
        self, loader: DemoLoader, tmp_path: Path
    ) -> None:
        """When KB module is mocked, entries are loaded from files."""
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        (kb_dir / "char-anna.md").write_text(
            "---\nname: Anna\ntype: character\n---\n\nA teacher.",
            encoding="utf-8",
        )
        (kb_dir / "loc-village.md").write_text(
            "---\nname: Village\ntype: location\n---\n\nA small village.",
            encoding="utf-8",
        )

        # Create a mock KBEntry class
        mock_kb_entry = (
            MagicMock()
        )  # narrare: allow reason="No real KBEntry class available to spec"

        novel_id = uuid.uuid4()
        import sys

        # Mock the narrare.kb.models module
        kb_module = MagicMock()  # narrare: allow reason="Mocking module for sys.modules injection"
        kb_module.KBEntry = mock_kb_entry
        sys.modules["narrare.kb.models"] = kb_module

        try:
            await loader._load_kb_entries(kb_dir, novel_id)
            # Two KB entries should have been added to the session
            assert loader._session.add.call_count == 2  # pyright: ignore[reportAttributeAccessIssue]
        finally:
            sys.modules.pop("narrare.kb.models", None)


class TestLoadKBEntryCounts:
    """Verify KB file counts in the actual demo data directories."""

    FANTASY_KB = _DEMO_DATA_ROOT / "en" / "echoes-of-the-thornwall" / "kb"
    SCIFI_KB = _DEMO_DATA_ROOT / "en" / "dead-signal" / "kb"
    GERMAN_KB = _DEMO_DATA_ROOT / "de" / "im-stillen-wald" / "kb"

    @pytest.mark.skipif(
        not FANTASY_KB.exists(),
        reason="Fantasy demo data not available",
    )
    def test_fantasy_kb_has_15_entries(self) -> None:
        """Fantasy demo should have 15 KB entry files."""
        kb_files = list(self.FANTASY_KB.glob("*.md"))
        assert len(kb_files) == 15

    @pytest.mark.skipif(
        not SCIFI_KB.exists(),
        reason="SciFi demo data not available",
    )
    def test_scifi_kb_has_8_entries(self) -> None:
        """SciFi demo should have 8 KB entry files."""
        kb_files = list(self.SCIFI_KB.glob("*.md"))
        assert len(kb_files) == 8

    @pytest.mark.skipif(
        not GERMAN_KB.exists(),
        reason="German demo data not available",
    )
    def test_german_kb_has_6_entries(self) -> None:
        """German demo should have 6 KB entry files."""
        kb_files = list(self.GERMAN_KB.glob("*.md"))
        assert len(kb_files) == 6

    @pytest.mark.skipif(
        not FANTASY_KB.exists(),
        reason="Fantasy demo data not available",
    )
    def test_fantasy_kb_names_and_categories_correct(self) -> None:
        """Verify KB entry file names follow the expected pattern."""
        kb_files = list(self.FANTASY_KB.glob("*.md"))
        stems = sorted(f.stem for f in kb_files)

        # Verify character entries exist
        char_files = [s for s in stems if s.startswith("char-")]
        assert len(char_files) == 5, f"Expected 5 characters, got {char_files}"

        # Verify location entries exist
        loc_files = [s for s in stems if s.startswith("loc-")]
        assert len(loc_files) >= 1, "Expected at least 1 location"

    @pytest.mark.skipif(
        not FANTASY_KB.exists(),
        reason="Fantasy demo data not available",
    )
    def test_fantasy_kb_files_have_valid_frontmatter(self) -> None:
        """All KB files should parse with valid frontmatter containing name and type."""
        from narrare_core.shared.frontmatter import parse_frontmatter

        kb_files = list(self.FANTASY_KB.glob("*.md"))
        for kb_file in kb_files:
            raw = kb_file.read_text(encoding="utf-8")
            parsed = parse_frontmatter(raw)
            assert parsed.get("name"), f"KB file {kb_file.name} missing 'name' in frontmatter"
            assert parsed.get("type"), f"KB file {kb_file.name} missing 'type' in frontmatter"
            assert parsed.content, f"KB file {kb_file.name} should have non-empty content"
