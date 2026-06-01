"""Unit tests for DEFAULT_KB_SUGGEST_MAX_RESULTS constant.

Extracted from test_suggest_service.py to keep file under RULE-04 limit.
FIND-005: constant is the single source of truth for max suggestion count.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from narrare.kb.suggest_service import DEFAULT_KB_SUGGEST_MAX_RESULTS, KBSuggestService


class FakeProactiveContext:
    """Minimal fake for ProactiveContextProtocol.suggest()."""

    def __init__(self, suggestions: list[Any] | None = None, **_kwargs: object) -> None:
        self.suggestions = suggestions or []
        self.last_max_results: int | None = None

    async def suggest(
        self,
        chapter_content: str,
        *,
        novel_id: uuid.UUID,
        chapter_frontmatter: dict[str, object] | None = None,
        entity_names: list[str] | None = None,
        max_results: int = 20,
        entity_metadata: dict[uuid.UUID, Any] | None = None,
    ) -> list[Any]:
        self.last_max_results = max_results
        return self.suggestions


@dataclass
class FakeChapter:
    """Minimal fake for ChapterRepositoryProtocol — returns a valid chapter."""

    content: str = "Some chapter content."

    async def get_by_id(self, chapter_id: uuid.UUID, novel_id: uuid.UUID) -> FakeChapter:
        return self


class FakeKBRepo:
    """Minimal fake for KBRepositoryProtocol — returns empty entries."""

    async def list_entries(
        self,
        novel_id: uuid.UUID,
        entity_type: str | None = None,
        tags: list[str] | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Any], int]:
        return [], 0


def _make_service(**overrides: object) -> KBSuggestService:
    defaults: dict[str, object] = {
        "proactive_context": FakeProactiveContext(),
        "chapter_repo": FakeChapter(),
        "kb_repo": FakeKBRepo(),
    }
    defaults.update(overrides)
    return KBSuggestService(**defaults)  # type: ignore[arg-type]


class TestDefaultMaxResultsConstant:
    """FIND-005: DEFAULT_KB_SUGGEST_MAX_RESULTS is the single source of truth."""

    def test_constant_is_reasonable_default(self) -> None:
        """Constant is a positive integer within the router's 1-100 range."""
        assert isinstance(DEFAULT_KB_SUGGEST_MAX_RESULTS, int)
        assert 1 <= DEFAULT_KB_SUGGEST_MAX_RESULTS <= 100

    async def test_service_uses_constant_as_default(self) -> None:
        """When no max_results is passed, service forwards the constant value."""
        fake_proactive = FakeProactiveContext(suggestions=[])

        service = _make_service(proactive_context=fake_proactive)

        await service.get_suggestions(
            chapter_id=uuid.uuid4(),
            novel_id=uuid.uuid4(),
        )

        assert fake_proactive.last_max_results == DEFAULT_KB_SUGGEST_MAX_RESULTS
