"""Shared fakes for dialogue-coach SSE integration tests.

Kept in a separate module so the test file stays focused on assertions
(RULE-04). The fakes are NOT reusable production code — they exist only
to drive the service deterministically without a real LLM call.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

from narrare_core.ai_invocation.adaptive_context import (
    AdaptiveContext,
    AdaptiveSettings,
)

if TYPE_CHECKING:
    from pydantic_ai.models.test import TestModel


class FakeChapterRepo:
    """Returns a chapter-like object regardless of id."""

    class _Chapter:
        def __init__(self) -> None:
            self.id = uuid4()
            self.novel_id = uuid4()
            self.content = '"Hello," Alice said.'
            self.title = "Test Chapter"

    async def get(self, chapter_id: Any) -> Any:
        return self._Chapter()

    async def get_by_id(self, chapter_id: Any, novel_id: Any = None) -> Any:
        return self._Chapter()


class FakeNovelRepo:
    """Returns a novel-like object regardless of id."""

    class _Novel:
        def __init__(self) -> None:
            self.id = uuid4()
            self.title = "Test Novel"
            self.genre = "Fantasy"
            self.writing_language = "en"

    async def get_by_id(self, novel_id: Any, user_id: Any | None = None) -> Any:
        return self._Novel()


class FakeComposer:
    async def build(self, *args: Any, **kwargs: Any) -> Any:
        from narrare_core.prompts.composer import ComposedPrompt

        return ComposedPrompt(system="You are a dialogue coach.", user="")


class FakeModelRegistry:
    def __init__(self, model: TestModel) -> None:
        self._model = model

    async def get_model(self, config: Any) -> TestModel:
        return self._model


class FakeAdaptiveProvider:
    def __init__(self) -> None:
        self._context = AdaptiveContext(
            user_id=uuid4(),
            project_id=uuid4(),
            preference_text="prefers terse prose",
            source_summary="preferences",
        )

    async def get_context(self, user_id: Any, project_id: Any) -> AdaptiveContext:
        return self._context

    async def get_settings(self, user_id: Any, project_id: Any) -> AdaptiveSettings:
        return AdaptiveSettings()

    async def record_snapshot(
        self, invocation_id: Any, adaptive_context: Any, evidence_repo: Any
    ) -> None:
        # Best-effort no-op for tests.
        return None
