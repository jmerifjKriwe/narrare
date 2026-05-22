"""Unit tests for WritingService — mocked dependencies.

Tests verify service business logic without touching the database,
LLM gateway, or prompt composer.  All dependencies are mocked.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare.writing.schemas import (
    GenerateRequest,
    GenerationModeEnum,
)
from narrare_core.shared.errors import ConflictError, NotFoundError, ValidationError

if TYPE_CHECKING:
    from narrare.writing.service import WritingService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request(**overrides: Any) -> GenerateRequest:
    """Create a GenerateRequest with sensible defaults."""
    defaults: dict[str, Any] = {
        "mode": GenerationModeEnum.FULL_DRAFT,
        "prompt": "Write a dramatic scene",
        "outline": None,
        "auto_continue": False,
    }
    defaults.update(overrides)
    return GenerateRequest(**defaults)


# ---------------------------------------------------------------------------
# start_generation
# ---------------------------------------------------------------------------


class TestStartGeneration:
    async def test_start_generation_with_valid_input(
        self,
        service: WritingService,
        mock_repo: AsyncMock,
    ) -> None:
        """start_generation() creates a request and returns GenerateResponse."""
        chapter_id = uuid.uuid4()
        novel_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        request = _make_request()

        response = await service.start_generation(
            chapter_id,
            novel_id,
            user_id,
            request,
        )

        assert response.status == "pending"
        assert response.mode == "full_draft"
        assert isinstance(response.request_id, uuid.UUID)
        mock_repo.create.assert_called_once()

    async def test_start_generation_passes_tone_to_repo(
        self,
        service: WritingService,
        mock_repo: AsyncMock,
    ) -> None:
        """start_generation() stores the tone from the request."""
        chapter_id = uuid.uuid4()
        novel_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        request = _make_request(tone="humorous")

        await service.start_generation(chapter_id, novel_id, user_id, request)

        mock_repo.create.assert_called_once()
        call_kwargs = mock_repo.create.call_args.kwargs
        assert call_kwargs["tone"] == "humorous"

    async def test_start_generation_default_tone_is_balanced(
        self,
        service: WritingService,
        mock_repo: AsyncMock,
    ) -> None:
        """start_generation() defaults tone to 'balanced' when not specified."""
        chapter_id = uuid.uuid4()
        novel_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        request = _make_request()

        await service.start_generation(chapter_id, novel_id, user_id, request)

        call_kwargs = mock_repo.create.call_args.kwargs
        assert call_kwargs.get("tone", "balanced") == "balanced"

    async def test_start_generation_with_concurrent_request_raises_conflict(
        self,
        service: WritingService,
        mock_repo: AsyncMock,
    ) -> None:
        """start_generation() raises ConflictError when a request is active."""
        mock_repo.get_active_for_chapter.return_value = MagicMock(spec=["id"])

        with pytest.raises(ConflictError):
            await service.start_generation(
                uuid.uuid4(),
                uuid.uuid4(),
                str(uuid.uuid4()),
                _make_request(),
            )

    async def test_start_generation_without_input_raises_validation(
        self,
        service: WritingService,
        mock_repo: AsyncMock,
    ) -> None:
        """start_generation() raises ValidationError without prompt/outline/auto."""
        request = GenerateRequest(
            mode=GenerationModeEnum.FULL_DRAFT,
            prompt=None,
            outline=None,
            auto_continue=False,
            word_target=None,
            tone="balanced",
            language="en",
        )

        with pytest.raises(ValidationError):
            await service.start_generation(
                uuid.uuid4(),
                uuid.uuid4(),
                str(uuid.uuid4()),
                request,
            )

    async def test_start_generation_with_outline_only(
        self,
        service: WritingService,
        mock_repo: AsyncMock,
    ) -> None:
        """start_generation() accepts outline as sole input."""
        request = _make_request(prompt=None, outline="Chapter outline here")
        response = await service.start_generation(
            uuid.uuid4(),
            uuid.uuid4(),
            str(uuid.uuid4()),
            request,
        )
        assert response.status == "pending"

    async def test_start_generation_with_auto_continue(
        self,
        service: WritingService,
        mock_repo: AsyncMock,
    ) -> None:
        """start_generation() accepts auto_continue as sole input."""
        request = _make_request(prompt=None, auto_continue=True)
        response = await service.start_generation(
            uuid.uuid4(),
            uuid.uuid4(),
            str(uuid.uuid4()),
            request,
        )
        assert response.status == "pending"

    async def test_start_generation_with_invalid_fk_raises_not_found(
        self,
        service: WritingService,
        mock_repo: AsyncMock,
    ) -> None:
        """start_generation() converts IntegrityError to NotFoundError.

        Regression test: when chapter_id or novel_id don't exist in the DB,
        the FK constraint raises IntegrityError.  The service must convert
        this to NotFoundError (HTTP 404) instead of letting it bubble up as
        an unhandled 500.
        """
        from sqlalchemy.exc import IntegrityError

        mock_repo.create = AsyncMock(side_effect=IntegrityError("", {}, Exception()))
        mock_repo.get_active_for_chapter.return_value = None

        with pytest.raises(NotFoundError):
            await service.start_generation(
                uuid.uuid4(),
                uuid.uuid4(),
                str(uuid.uuid4()),
                _make_request(),
            )
