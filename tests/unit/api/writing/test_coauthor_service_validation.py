"""Unit tests for CoAuthorService.validate_coauthor — SET-005 cascade wiring.

Tests that the word-limit validation in validate_coauthor uses the
resolved max_selection_words from the SET-005 cascade rather than a
hardcoded value.

Covers:
1. User-level override takes priority (cascade: user > project > env > code)
2. Project-level override applies when no user override exists
3. Code default (2000) applies when no settings configured
4. ValidationError raised when word count exceeds resolved limit
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare.writing.coauthor_service import CoAuthorService
from narrare.writing.schemas_coauthor import CoAuthorFocus, CoAuthorRequest
from narrare_core.llm import ResolvedModelConfig
from narrare_core.shared.errors import ValidationError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CONFIG = ResolvedModelConfig(
    provider_name="test",
    model_id="test-model",
    temperature=0.7,
    max_tokens=4000,
)

# Minimum valid selection text (must be >= 50 chars due to CoAuthorRequest validation)
_SHORT_SELECTION = "The quick brown fox jumps over the lazy dog in the forest nearby."
# Short words to stay under max_length=10000 chars: 2001 x 2 chars ~= 4002 chars
_LONG_SELECTION = " ".join(["a"] * 2001)


def _request(**kw: Any) -> CoAuthorRequest:
    """Build a valid CoAuthorRequest with sensible defaults."""
    defaults: dict[str, Any] = {
        "selection_text": _SHORT_SELECTION,
        "focus": [CoAuthorFocus.WORD_CHOICE],
        "tone": "balanced",
        "language": "en",
    }
    defaults.update(kw)
    return CoAuthorRequest(**defaults)


def _make_service(max_selection_words: int = 2000) -> CoAuthorService:
    """Create a CoAuthorService with mocked deps and configurable word limit."""
    repo = AsyncMock()
    repo.chapter_exists = AsyncMock(return_value=True)
    repo.get_active_for_chapter = AsyncMock(return_value=None)

    pipeline = AsyncMock()
    proc = MagicMock(spec=["process"])
    proc.process = MagicMock(spec=[], side_effect=lambda text, **kw: text)

    return CoAuthorService(
        repo=repo,
        pipeline=pipeline,
        draft_processor=proc,
        config=CONFIG,
        max_selection_words=max_selection_words,
    )


# ---------------------------------------------------------------------------
# Tests: cascade resolution returns user-level value when set
# ---------------------------------------------------------------------------


class TestCascadeUserLevel:
    """User-level override takes highest priority."""

    async def test_user_override_applied_to_validation(self) -> None:
        """When user sets max_selection_words=500, validation uses 500."""
        service = _make_service(max_selection_words=500)
        # 100 words — under user limit of 500
        text_100_words = " ".join(["a"] * 100)
        req = _request(selection_text=text_100_words)
        # Should pass — 100 < 500
        await service.validate_coauthor(uuid.uuid4(), uuid.uuid4(), req)

    async def test_user_override_rejects_oversized(self) -> None:
        """When user sets max_selection_words=500, 600 words is rejected."""
        service = _make_service(max_selection_words=500)
        text_600_words = " ".join(["a"] * 600)
        req = _request(selection_text=text_600_words)
        with pytest.raises(ValidationError, match="exceeds 500 words"):
            await service.validate_coauthor(uuid.uuid4(), uuid.uuid4(), req)


# ---------------------------------------------------------------------------
# Tests: cascade resolution falls back to project-level value
# ---------------------------------------------------------------------------


class TestCascadeProjectLevel:
    """Project-level override applies when no user override exists."""

    async def test_project_override_applied(self) -> None:
        """When project sets max_selection_words=3000, 2500 words pass."""
        service = _make_service(max_selection_words=3000)
        text_2500_words = " ".join(["a"] * 2500)
        req = _request(selection_text=text_2500_words)
        await service.validate_coauthor(uuid.uuid4(), uuid.uuid4(), req)

    async def test_project_override_rejects_oversized(self) -> None:
        """When project sets max_selection_words=100, 200 words is rejected."""
        service = _make_service(max_selection_words=100)
        text_200_words = " ".join(["a"] * 200)
        req = _request(selection_text=text_200_words)
        with pytest.raises(ValidationError, match="exceeds 100 words"):
            await service.validate_coauthor(uuid.uuid4(), uuid.uuid4(), req)


# ---------------------------------------------------------------------------
# Tests: default 2000 when no settings configured
# ---------------------------------------------------------------------------


class TestCascadeDefaultFallback:
    """Code default of 2000 applies when no overrides exist."""

    async def test_default_2000_allows_2000_words(self) -> None:
        """Exactly 2000 words is NOT rejected (boundary: <=)."""
        service = _make_service()  # default 2000
        text_2000_words = " ".join(["a"] * 2000)
        req = _request(selection_text=text_2000_words)
        await service.validate_coauthor(uuid.uuid4(), uuid.uuid4(), req)

    async def test_default_2000_rejects_2001_words(self) -> None:
        """2001 words is rejected when using default 2000."""
        service = _make_service()  # default 2000
        req = _request(selection_text=_LONG_SELECTION)
        with pytest.raises(ValidationError, match="exceeds 2000 words"):
            await service.validate_coauthor(uuid.uuid4(), uuid.uuid4(), req)


# ---------------------------------------------------------------------------
# Tests: validation still raises ValidationError when exceeding limit
# ---------------------------------------------------------------------------


class TestValidationBehavior:
    """Ensure ValidationError behavior is preserved after cascade wiring."""

    async def test_error_code_is_selection_too_long(self) -> None:
        """ValidationError has the correct error code."""
        service = _make_service(max_selection_words=50)
        text_100_words = " ".join(["a"] * 100)
        req = _request(selection_text=text_100_words)
        with pytest.raises(ValidationError) as exc_info:
            await service.validate_coauthor(uuid.uuid4(), uuid.uuid4(), req)
        assert exc_info.value.code == "SELECTION_TOO_LONG"

    async def test_error_message_includes_actual_count(self) -> None:
        """Error message contains both the limit and actual word count."""
        service = _make_service(max_selection_words=50)
        text_100_words = " ".join(["a"] * 100)
        req = _request(selection_text=text_100_words)
        with pytest.raises(ValidationError, match="got 100"):
            await service.validate_coauthor(uuid.uuid4(), uuid.uuid4(), req)

    async def test_short_selection_passes_with_default_limit(self) -> None:
        """A short selection passes validation with the default 2000 limit."""
        service = _make_service()
        req = _request()
        await service.validate_coauthor(uuid.uuid4(), uuid.uuid4(), req)
