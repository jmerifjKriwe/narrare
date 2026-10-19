"""Analysis error types.

Extracted from contracts.py to keep file sizes under limit (RULE-04).
All analysis-specific exceptions live here.
"""

from __future__ import annotations

from narrare_core.shared.errors import ValidationError

# ---------------------------------------------------------------------------
# Error Types
# ---------------------------------------------------------------------------


class AnalysisError(Exception):
    """Base exception for analysis operations."""


class ChapterNotFoundError(AnalysisError):
    """Chapter not found or not accessible."""


class InsufficientWordCountError(ValidationError):
    """Chapter is too short for meaningful analysis (< 1000 words).

    N13: re-based on the core ``ValidationError`` so the app-level domain
    handler answers 422 machine-readable instead of a generic 500 (the
    beta-reader min-words business rule; M06 ``EMPTY_DRAFT`` precedent).
    """

    def __init__(self, message: str) -> None:
        super().__init__(message, code="WORD_COUNT_BELOW_MINIMUM")


class ExcessiveWordCountError(ValidationError):
    """Chapter(s) exceed token limit for analysis (> 10000 words)."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="WORD_COUNT_ABOVE_MAXIMUM")


class CacheRetrievalError(AnalysisError):
    """Phase 1 cache missing for deep-dive request."""
