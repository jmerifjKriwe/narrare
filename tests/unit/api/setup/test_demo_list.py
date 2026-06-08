"""Unit tests for GET /setup/demos endpoint and DemoListResponse schema."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from narrare.setup.base_schemas import DemoListResponse, DemoProjectInfo, StarterContent
from narrare.setup.demo_loader import DemoLoader, _clear_demo_info_cache

if TYPE_CHECKING:
    from collections.abc import Generator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_cache() -> Generator[None]:  # pyright: ignore[reportUnusedFunction]
    """Clear the demo info cache before and after each test."""
    _clear_demo_info_cache()
    yield
    _clear_demo_info_cache()


@pytest.fixture
def mock_session() -> MagicMock:
    return MagicMock(spec=AsyncSession)


@pytest.fixture
def demo_loader(mock_session: MagicMock) -> DemoLoader:
    return DemoLoader(mock_session)


# ---------------------------------------------------------------------------
# DemoListResponse schema validation
# ---------------------------------------------------------------------------


class TestDemoListResponseSchema:
    """Validate DemoListResponse Pydantic model."""

    def test_accepts_list_of_demo_project_info(self) -> None:
        info = DemoProjectInfo(
            id=StarterContent.DEMO_FANTASY,
            title="Test",
            writing_language="en",
            genre="Fantasy",
            chapter_count=1,
            character_count=2,
            word_count=100,
            description="A test demo",
        )
        response = DemoListResponse(demos=[info])
        assert len(response.demos) == 1
        assert response.demos[0].title == "Test"

    def test_accepts_empty_list(self) -> None:
        response = DemoListResponse(demos=[])
        assert response.demos == []

    def test_serialization_round_trip(self) -> None:
        info = DemoProjectInfo(
            id=StarterContent.DEMO_SCIFI,
            title="Dead Signal",
            writing_language="en",
            genre="Sci-Fi",
            chapter_count=3,
            character_count=3,
            word_count=3450,
            description="A signal from a dead world.",
            author="Narrare Demo",
            logline="A test logline.",
            pov="First Person",
            tags=["sci-fi", "space"],
        )
        response = DemoListResponse(demos=[info])
        data = response.model_dump()
        reconstructed = DemoListResponse.model_validate(data)
        assert reconstructed.demos[0].writing_language == "en"
        assert reconstructed.demos[0].tags == ["sci-fi", "space"]


# ---------------------------------------------------------------------------
# DemoProjectInfo.writing_language field
# ---------------------------------------------------------------------------


class TestDemoProjectInfoWritingLanguage:
    """Verify the renamed writing_language field works correctly."""

    def test_writing_language_field_present(self) -> None:
        info = DemoProjectInfo(
            id=StarterContent.DEMO_FANTASY,
            title="Test",
            writing_language="de",
            genre="Fantasy",
            chapter_count=1,
            character_count=1,
            word_count=100,
            description="Test",
        )
        assert info.writing_language == "de"

    def test_model_dump_uses_writing_language_key(self) -> None:
        info = DemoProjectInfo(
            id=StarterContent.DEMO_GERMAN,
            title="Test",
            writing_language="de",
            genre="Literary",
            chapter_count=2,
            character_count=3,
            word_count=2660,
            description="Test",
        )
        data = info.model_dump()
        assert "writing_language" in data
        assert "language" not in data


# ---------------------------------------------------------------------------
# DemoLoader.all_demo_info with real data
# ---------------------------------------------------------------------------


class TestAllDemoInfo:
    """Test DemoLoader.all_demo_info returns real metadata."""

    def test_returns_all_three_demos(self, demo_loader: DemoLoader) -> None:
        demos = demo_loader.all_demo_info()
        assert len(demos) == 3
        ids = {d.id for d in demos}
        assert StarterContent.DEMO_FANTASY in ids
        assert StarterContent.DEMO_SCIFI in ids
        assert StarterContent.DEMO_GERMAN in ids

    def test_each_demo_has_writing_language(self, demo_loader: DemoLoader) -> None:
        demos = demo_loader.all_demo_info()
        for demo in demos:
            assert hasattr(demo, "writing_language")
            assert demo.writing_language in ("en", "de")

    def test_fantasy_demo_has_correct_metadata(self, demo_loader: DemoLoader) -> None:
        demos = demo_loader.all_demo_info()
        fantasy = next(d for d in demos if d.id == StarterContent.DEMO_FANTASY)
        assert fantasy.title == "Echoes of the Thornwall"
        assert fantasy.writing_language == "en"
        assert fantasy.genre == "Fantasy"
        assert fantasy.chapter_count == 4
        assert fantasy.character_count == 5
        assert fantasy.word_count == 3130

    def test_german_demo_has_de_language(self, demo_loader: DemoLoader) -> None:
        demos = demo_loader.all_demo_info()
        german = next(d for d in demos if d.id == StarterContent.DEMO_GERMAN)
        assert german.writing_language == "de"


# ---------------------------------------------------------------------------
# Backward compatibility: metadata.json with "language" key
# ---------------------------------------------------------------------------


class TestBackwardCompatLanguageKey:
    """Verify that metadata.json files using 'language' still work."""

    def test_loads_from_language_key_in_json(
        self, tmp_path: object, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When metadata.json has 'language' but not 'writing_language', it still loads."""
        import json
        from pathlib import Path

        import narrare.setup.demo_loader as mod

        tmp = Path(str(tmp_path))
        demo_dir = tmp / "en" / "test-demo"
        demo_dir.mkdir(parents=True)

        metadata = {
            "title": "Compat Test",
            "genre": "Test",
            "language": "fr",
            "description": "Backward compat test",
            "stats": {"chapters": 1, "characters": 2, "wordcount": 500},
        }
        (demo_dir / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")

        monkeypatch.setattr(mod, "_DEMO_ROOT", tmp)
        monkeypatch.setitem(mod._DEMO_DIRS, StarterContent.DEMO_FANTASY, "en/test-demo")

        info = mod._load_demo_info(StarterContent.DEMO_FANTASY)
        assert info.writing_language == "fr"

    def test_prefers_writing_language_key_over_language(
        self, tmp_path: object, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When metadata.json has both keys, writing_language takes precedence."""
        import json
        from pathlib import Path

        import narrare.setup.demo_loader as mod

        tmp = Path(str(tmp_path))
        demo_dir = tmp / "en" / "priority-demo"
        demo_dir.mkdir(parents=True)

        metadata = {
            "title": "Priority Test",
            "genre": "Test",
            "language": "en",
            "writing_language": "de",
            "description": "Priority test",
            "stats": {"chapters": 1, "characters": 1, "wordcount": 100},
        }
        (demo_dir / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")

        monkeypatch.setattr(mod, "_DEMO_ROOT", tmp)
        monkeypatch.setitem(mod._DEMO_DIRS, StarterContent.DEMO_SCIFI, "en/priority-demo")

        info = mod._load_demo_info(StarterContent.DEMO_SCIFI)
        assert info.writing_language == "de"
