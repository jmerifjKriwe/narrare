"""Analysis error types.

Extracted from contracts.py to keep file sizes under limit (RULE-04).
All analysis-specific exceptions live here.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Error Types
# ---------------------------------------------------------------------------


class AnalysisError(Exception):
    """Base exception for analysis operations."""


class ChapterNotFoundError(AnalysisError):
    """Chapter not found or not accessible."""


class InsufficientWordCountError(AnalysisError):
    """Chapter is too short for meaningful analysis (< 1000 words)."""


class ExcessiveWordCountError(AnalysisError):
    """Chapter(s) exceed token limit for analysis (> 10000 words)."""


class CacheRetrievalError(AnalysisError):
    """Phase 1 cache missing for deep-dive request."""
