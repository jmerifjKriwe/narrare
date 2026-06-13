"""Tests for RewriteRequest model validators (lines 91-95).

Covers:
1. Voice mode with missing character_id (line 91-92)
2. Custom mode with missing custom_instructions (line 93-94)
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from narrare.writing.schemas_rewrite import RewriteMode, RewriteRequest


class TestRewriteRequestModeValidator:
    """RewriteRequest.validate_mode_requirements coverage."""

    def test_voice_mode_without_character_id_raises_value_error(self) -> None:
        """Voice mode requires character_id (lines 91-92)."""
        with pytest.raises(ValidationError, match="character_id is required"):
            RewriteRequest.model_validate(
                {
                    "selection_text": "x" * 50,
                    "mode": RewriteMode.VOICE,
                }
            )

    def test_custom_mode_without_custom_instructions_raises_value_error(self) -> None:
        """Custom mode requires custom_instructions (lines 93-94)."""
        with pytest.raises(ValidationError, match="custom_instructions is required"):
            RewriteRequest.model_validate(
                {
                    "selection_text": "x" * 50,
                    "mode": RewriteMode.CUSTOM,
                }
            )

    def test_voice_mode_with_character_id_valid(self) -> None:
        """Voice mode with character_id passes validation."""
        import uuid

        request = RewriteRequest.model_validate(
            {
                "selection_text": "x" * 50,
                "mode": RewriteMode.VOICE,
                "character_id": uuid.uuid4(),
            }
        )
        assert request.mode == RewriteMode.VOICE
