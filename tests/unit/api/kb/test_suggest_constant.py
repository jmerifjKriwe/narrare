"""Unit tests for DEFAULT_KB_SUGGEST_MAX_RESULTS constant.

Extracted from test_suggest_service.py to keep file under RULE-04 limit.
FIND-005: constant is the single source of truth for max suggestion count.
"""

from __future__ import annotations

import uuid
from typing import Any

from narrare.kb.suggest_service import DEFAULT_KB_SUGGEST_MAX_RESULTS, KBSuggestService


class FakeProactiveContext:
    """Minimal fake for ProactiveContextService."""

    def __init__(self, suggestions: list[Any] | None = None, **_kwargs: object) -> None:
        self.suggestions = suggestions or []
        self.last_max_results: int | None = None

    async def get_suggestions(
        self,
        *,
        chapter_id: uuid.UUID,
        novel_id: uuid.UUID,
        max_results: int,
    ) -> list[Any]:
        self.last_max_results = max_results
        return self.suggestions


class FakeChapter:
    """Minimal fake for ChapterRepository."""

    async def get_by_id(self, chapter_id: uuid.UUID, novel_id: uuid.UUID) -> None:
        return None


def _make_service(**overrides: object) -> KBSuggestService:
    defaults = {
        "proactive": FakeProactiveContext(),
        "chapter": FakeChapter(),
        "kb_repo": None,
    }
    defaults.update(overrides)  # type: ignore[typeddict-item]
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

        service = _make_service(proactive=fake_proactive, chapter=FakeChapter())

        await service.get_suggestions(
            chapter_id=uuid.uuid4(),
            novel_id=uuid.uuid4(),
        )

        assert fake_proactive.last_max_results == DEFAULT_KB_SUGGEST_MAX_RESULTS
