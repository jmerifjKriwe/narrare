"""Validation logic for beta reader analysis.

Extracted from beta_reader_service.py to keep file sizes under limit (RULE-04).
Contains word count validation and related constants.
"""

from __future__ import annotations

from narrare.analysis.errors import ExcessiveWordCountError, InsufficientWordCountError


def validate_word_count(
    word_count: int,
    *,
    min_words: int = 1000,
    max_words: int = 10000,
) -> None:
    """Validate word count is within acceptable range.

    Args:
        word_count: Total words across all chapters.
        min_words: Minimum words for meaningful feedback.
        max_words: Maximum words for token limit safety.

    Raises:
        InsufficientWordCountError: If word_count < min_words.
        ExcessiveWordCountError: If word_count > max_words.
    """
    if word_count < min_words:
        raise InsufficientWordCountError(
            f"Chapter is too short for meaningful analysis "
            f"({word_count} words, minimum {min_words})."
        )
    if word_count > max_words:
        raise ExcessiveWordCountError(
            f"Selected chapters exceed the analysis limit "
            f"({word_count} words, maximum {max_words}). "
            f"Try fewer chapters."
        )
