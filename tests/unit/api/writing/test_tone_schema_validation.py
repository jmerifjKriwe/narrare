"""Unit tests for tone schema validation in GenerateRequest.

Tests verify that the GenerateRequest schema accepts valid tones
and rejects invalid ones.
"""

from __future__ import annotations

from typing import Any

import pytest

from narrare.writing.schemas import (
    GenerateRequest,
    GenerationModeEnum,
)

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
# Schema validation — tone acceptance
# ---------------------------------------------------------------------------


class TestToneSchemaValidation:
    """Tests that the GenerateRequest schema accepts valid tones."""

    def test_default_tone_is_balanced(self) -> None:
        """Default tone is 'balanced'."""
        request = _make_request()
        assert request.tone == "balanced"

    def test_all_nine_bundled_tones_accepted(self) -> None:
        """All 9 bundled tones pass schema validation."""
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
            request = _make_request(tone=tone)
            assert request.tone == tone

    def test_custom_tone_string_accepted(self) -> None:
        """Custom tone string (e.g. German) passes schema validation."""
        request = _make_request(tone="düster-melancholisch")
        assert request.tone == "düster-melancholisch"

    def test_custom_tone_with_spaces_accepted(self) -> None:
        """Custom tone with spaces passes validation."""
        request = _make_request(tone="Gothic Horror Style")
        assert request.tone == "Gothic Horror Style"

    def test_empty_tone_rejected(self) -> None:
        """Empty tone string is rejected by min_length=1."""
        from pydantic import ValidationError as PydanticValidationError

        with pytest.raises(PydanticValidationError):
            _make_request(tone="")

    def test_tone_max_length_enforced(self) -> None:
        """Tone exceeding 100 chars is rejected."""
        from pydantic import ValidationError as PydanticValidationError

        with pytest.raises(PydanticValidationError):
            _make_request(tone="x" * 101)
