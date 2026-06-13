"""Unit tests for InlineSuggestService.validate_suggest — mocked dependencies.

Tests verify ghost-text suggestion validation logic without touching the
LLM gateway or prompt composer.  Streaming tests live in
``test_suggest_inline.py`` (split for RULE-04 compliance).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare.writing.suggest_service import InlineSuggestService
from tests.unit.api.writing._suggest_factories import (
    make_mock_chapter_repo,
    make_mock_composer,
    make_mock_registry,
    make_suggest_config,
)

if TYPE_CHECKING:
    from narrare_core.llm import ResolvedModelConfig

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_composer() -> MagicMock:
    return make_mock_composer()


@pytest.fixture
def mock_registry() -> MagicMock:
    return make_mock_registry()


@pytest.fixture
def suggest_config() -> ResolvedModelConfig:
    return make_suggest_config()


@pytest.fixture
def mock_chapter_repo() -> MagicMock:
    return make_mock_chapter_repo()


@pytest.fixture
def suggest_service(
    mock_composer: MagicMock,
    mock_registry: MagicMock,
    mock_chapter_repo: MagicMock,
    suggest_config: ResolvedModelConfig,
) -> InlineSuggestService:
    """InlineSuggestService with mocked dependencies."""
    return InlineSuggestService(
        registry=mock_registry,
        composer=mock_composer,
        config=suggest_config,
        chapter_repo=mock_chapter_repo,
    )


# ---------------------------------------------------------------------------
# validate_suggest
# ---------------------------------------------------------------------------


class TestValidateSuggest:
    """Tests for InlineSuggestService.validate_suggest()."""

    async def test_validate_suggest_with_empty_text_before_raises_validation_error(
        self,
        suggest_service: InlineSuggestService,
    ) -> None:
        """Empty text_before triggers ValidationError (lines 97-101)."""
        import uuid

        from narrare.writing.schemas import InlineSuggestRequest
        from narrare_core.shared.errors import ValidationError

        chapter_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        request = InlineSuggestRequest(text_before="   ")

        with pytest.raises(ValidationError, match="text_before must not be empty"):
            await suggest_service.validate_suggest(chapter_id, user_id, request)

    async def test_validate_suggest_with_nonexistent_chapter_raises_not_found(
        self,
        suggest_service: InlineSuggestService,
        mock_chapter_repo: MagicMock,
    ) -> None:
        """Non-existent chapter triggers NotFoundError (lines 103-105)."""
        import uuid

        from narrare.writing.schemas import InlineSuggestRequest
        from narrare_core.shared.errors import NotFoundError

        mock_chapter_repo.get = AsyncMock(return_value=None)

        chapter_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        request = InlineSuggestRequest(text_before="Valid text here")

        with pytest.raises(NotFoundError, match="Chapter"):
            await suggest_service.validate_suggest(chapter_id, user_id, request)

    async def test_validate_suggest_with_valid_input_passes(
        self,
        suggest_service: InlineSuggestService,
    ) -> None:
        """Valid input passes without error."""
        import uuid

        from narrare.writing.schemas import InlineSuggestRequest

        chapter_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        request = InlineSuggestRequest(text_before="Valid text here")

        # Should not raise any exception
        result = await suggest_service.validate_suggest(chapter_id, user_id, request)
        assert result is None
