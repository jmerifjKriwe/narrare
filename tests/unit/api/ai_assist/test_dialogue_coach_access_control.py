"""Regression tests for Plan-Bug #23 — access-control path.

The previous ``chapter_repo.get_by_id(chapter_id, user_id)`` call
mismatched the production ``get_by_id(chapter_id, novel_id)`` signature.
In production it queried ``Chapter.novel_id = user_id`` → always None
→ 404 on every request. The fix follows voice_check_service precedent:
unscoped ``chapter_repo.get(chapter_id)`` + ``novel_repo.get_by_id(
chapter.novel_id, user_id)`` for ownership enforcement.

Extracted from ``test_dialogue_coach_service.py`` for RULE-04 compliance.
Fakes are imported from the sibling test module (established pattern).
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from pydantic_ai.models.test import TestModel

from narrare.ai_assist.schemas import DialogueCoachRequest
from narrare.ai_assist.service import DialogueCoachService
from tests.unit.api.ai_assist.test_dialogue_coach_service import (
    FakeAdaptiveProvider,
    FakeChapterRepo,
    FakeComposer,
    FakeModelRegistry,
    FakeNovelRepo,
    _coach_output_args,
)


class TestPlanBug23AccessControl:
    """Regression tests for Plan-Bug #23 — access-control path."""

    @pytest.mark.asyncio
    async def test_raises_not_found_when_chapter_missing(self) -> None:
        """chapter_repo.get() returns None → NotFoundError("Chapter")."""

        class EmptyChapterRepo:
            async def get(self, chapter_id: Any) -> Any:
                return None

            async def get_by_id(self, *args: Any) -> Any:
                return None

        service = DialogueCoachService(
            chapter_repo=EmptyChapterRepo(),  # type: ignore[arg-type]
            novel_repo=FakeNovelRepo(),  # type: ignore[arg-type]
            model_registry=FakeModelRegistry(TestModel()),  # type: ignore[arg-type]
            model_config=None,  # type: ignore[arg-type]
            composer=FakeComposer(),  # type: ignore[arg-type]
            invocation_pipeline=None,
            adaptive_provider=FakeAdaptiveProvider(),  # type: ignore[arg-type]
        )
        from narrare_core.shared.errors import NotFoundError

        with pytest.raises(NotFoundError, match="Chapter"):
            await service.run(
                chapter_id=uuid4(),
                user_id=uuid4(),
                request=DialogueCoachRequest(selection_text='"Hi."', mode="analyze"),
            )

    @pytest.mark.asyncio
    async def test_raises_not_found_when_novel_access_denied(self) -> None:
        """novel_repo.get_by_id returns None → NotFoundError("Novel").

        Proves the access-control gate fires: a user who doesn't own the
        novel gets a 404, not the analysis.
        """

        class EmptyNovelRepo:
            async def get_by_id(self, novel_id: Any, user_id: Any | None = None) -> Any:
                return None

        service = DialogueCoachService(
            chapter_repo=FakeChapterRepo(),  # type: ignore[arg-type]
            novel_repo=EmptyNovelRepo(),  # type: ignore[arg-type]
            model_registry=FakeModelRegistry(TestModel()),  # type: ignore[arg-type]
            model_config=None,  # type: ignore[arg-type]
            composer=FakeComposer(),  # type: ignore[arg-type]
            invocation_pipeline=None,
            adaptive_provider=FakeAdaptiveProvider(),  # type: ignore[arg-type]
        )
        from narrare_core.shared.errors import NotFoundError

        with pytest.raises(NotFoundError, match="Novel"):
            await service.run(
                chapter_id=uuid4(),
                user_id=uuid4(),
                request=DialogueCoachRequest(selection_text='"Hi."', mode="analyze"),
            )

    @pytest.mark.asyncio
    async def test_uses_unscoped_chapter_get_not_scoped_get_by_id(self) -> None:
        """The service calls ``chapter_repo.get(chapter_id)``, not the
        scoped ``get_by_id(chapter_id, novel_id)`` — the latter would
        re-introduce Plan-Bug #23.
        """

        class CallTrackingChapterRepo:
            def __init__(self) -> None:
                self.get_calls: list[Any] = []
                self.get_by_id_calls: list[tuple[Any, ...]] = []

            async def get(self, chapter_id: Any) -> Any:
                self.get_calls.append(chapter_id)
                return FakeChapterRepo._Chapter(novel_id=uuid4(), content='"Hi."')

            async def get_by_id(self, *args: Any) -> Any:
                self.get_by_id_calls.append(args)
                return None

        tracker = CallTrackingChapterRepo()
        service = DialogueCoachService(
            chapter_repo=tracker,  # type: ignore[arg-type]
            novel_repo=FakeNovelRepo(),  # type: ignore[arg-type]
            model_registry=FakeModelRegistry(TestModel(custom_output_args=_coach_output_args())),  # type: ignore[arg-type]
            model_config=None,  # type: ignore[arg-type]
            composer=FakeComposer(),  # type: ignore[arg-type]
            invocation_pipeline=None,
            adaptive_provider=FakeAdaptiveProvider(),  # type: ignore[arg-type]
        )
        await service.run(
            chapter_id=uuid4(),
            user_id=uuid4(),
            request=DialogueCoachRequest(selection_text='"Hi."', mode="analyze"),
        )
        assert len(tracker.get_calls) == 1
        assert len(tracker.get_by_id_calls) == 0
