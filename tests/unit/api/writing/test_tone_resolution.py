"""Unit tests for tone resolution — bundled vs custom tones.

Tests verify that resolve_tone_instructions correctly distinguishes
bundled tones from custom tones, with graceful fallbacks.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from narrare.writing.tone_resolver import resolve_tone_instructions

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_tone_service() -> AsyncMock:
    """Mock CustomToneService."""
    service = AsyncMock()
    service.list_tones = AsyncMock(return_value=[])
    return service


# ---------------------------------------------------------------------------
# Tone resolution
# ---------------------------------------------------------------------------


class TestToneResolution:
    """Tests for resolve_tone_instructions — bundled vs custom tones."""

    async def test_bundled_tone_returns_none(self) -> None:
        """Bundled tones return None so pipeline uses built-in lookup."""
        result = await resolve_tone_instructions(
            tone="dramatic",
            user_id=uuid.uuid4(),
            tone_service=None,
        )
        assert result is None

    async def test_all_nine_bundled_tones_return_none(self) -> None:
        """All 9 bundled tones are recognized and return None."""
        bundled = [
            "dramatic",
            "quiet",
            "suspenseful",
            "balanced",
            "humorous",
            "contemplative",
            "romantic",
            "dark",
            "adventurous",
        ]
        for tone in bundled:
            result = await resolve_tone_instructions(
                tone=tone,
                user_id=uuid.uuid4(),
                tone_service=None,
            )
            assert result is None, f"Tone '{tone}' should be bundled"

    async def test_custom_tone_with_service_returns_instructions(
        self,
        mock_tone_service: AsyncMock,
    ) -> None:
        """Custom tone resolves to instructions from CustomToneService."""
        from narrare.settings.schemas_tones import CustomTone

        custom = CustomTone(
            id="tone-123",
            name="düster-melancholisch",
            instructions="Use dark, melancholic imagery with introspective passages.",
        )
        mock_tone_service.list_tones = AsyncMock(return_value=[custom])

        result = await resolve_tone_instructions(
            tone="düster-melancholisch",
            user_id=uuid.uuid4(),
            tone_service=mock_tone_service,
        )
        assert result == "Use dark, melancholic imagery with introspective passages."

    async def test_custom_tone_by_id_returns_instructions(
        self,
        mock_tone_service: AsyncMock,
    ) -> None:
        """Custom tone resolved by ID (not name) returns instructions."""
        from narrare.settings.schemas_tones import CustomTone

        custom = CustomTone(
            id="abc-123",
            name="Gothic Horror",
            instructions="Write with gothic atmosphere and dread.",
        )
        mock_tone_service.list_tones = AsyncMock(return_value=[custom])

        result = await resolve_tone_instructions(
            tone="abc-123",
            user_id=uuid.uuid4(),
            tone_service=mock_tone_service,
        )
        assert result == "Write with gothic atmosphere and dread."

    async def test_custom_tone_without_service_returns_empty(self) -> None:
        """Custom tone with no tone service returns empty string."""
        result = await resolve_tone_instructions(
            tone="nonexistent-custom",
            user_id=uuid.uuid4(),
            tone_service=None,
        )
        assert result == ""

    async def test_custom_tone_not_found_returns_empty(
        self,
        mock_tone_service: AsyncMock,
    ) -> None:
        """Custom tone not matching any stored tone returns empty string."""
        mock_tone_service.list_tones = AsyncMock(return_value=[])

        result = await resolve_tone_instructions(
            tone="unknown-tone",
            user_id=uuid.uuid4(),
            tone_service=mock_tone_service,
        )
        assert result == ""

    async def test_custom_tone_service_error_returns_empty(
        self,
        mock_tone_service: AsyncMock,
    ) -> None:
        """When tone service throws, graceful fallback to empty string."""
        mock_tone_service.list_tones = AsyncMock(side_effect=RuntimeError("DB error"))

        result = await resolve_tone_instructions(
            tone="my-custom-tone",
            user_id=uuid.uuid4(),
            tone_service=mock_tone_service,
        )
        assert result == ""
