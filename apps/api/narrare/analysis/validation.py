"""Validation logic for beta reader analysis.

Extracted from beta_reader_service.py to keep file sizes under limit (RULE-04).
Contains word count validation and related constants.
"""

from __future__ import annotations

from narrare.analysis.errors import ExcessiveWordCountError, InsufficientWordCountError

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MIN_WORDS = 1000  # Too short for meaningful feedback
MAX_WORDS = 10000  # Token limit safety


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_word_count(word_count: int) -> None:
    """Validate word count is within acceptable range.

    Args:
        word_count: Total words across all chapters.

    Raises:
        InsufficientWordCountError: If word_count < MIN_WORDS.
        ExcessiveWordCountError: If word_count > MAX_WORDS.
    """
    if word_count < MIN_WORDS:
        raise InsufficientWordCountError(
            f"Chapter is too short for meaningful analysis "
            f"({word_count} words, minimum {MIN_WORDS})."
        )
    if word_count > MAX_WORDS:
        raise ExcessiveWordCountError(
            f"Selected chapters exceed the analysis limit "
            f"({word_count} words, maximum {MAX_WORDS}). "
            f"Try fewer chapters."
        )
