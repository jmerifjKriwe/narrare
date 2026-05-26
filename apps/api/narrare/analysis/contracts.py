"""Analysis service contracts — Protocol definitions.

Contracts are written before implementation (RULE-03).
This is the umbrella contract file for the analysis module,
shared across all ANAL features (ANAL-001 through ANAL-011).
"""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.analysis.schemas import (
        BetaReaderDeepDiveRequest,
        BetaReaderDeepDiveResponse,
        BetaReaderRequest,
        BetaReaderResponse,
    )


# ---------------------------------------------------------------------------
# Shared Enums
# ---------------------------------------------------------------------------


class FeedbackSeverity(enum.StrEnum):
    """Severity level for analysis feedback."""

    CRITICAL = "critical"  # Blocks reader engagement — must fix
    MODERATE = "moderate"  # Noticeable issue — should address
    MINOR = "minor"  # Small improvement — nice to fix


class FeedbackCategory(enum.StrEnum):
    """Analysis feedback categories."""

    PLOT = "plot"  # Plot structure, goals, conflicts, resolution
    CHARACTER = "character"  # Character believability, motivation, consistency
    PROSE = "prose"  # Clarity, flow, show/tell, voice
    PACING = "pacing"  # Rhythm, momentum, chapter structure
    EXPERIENCE = "experience"  # Reader engagement, confusion, emotion


# ---------------------------------------------------------------------------
# ANAL-001: Beta Reader — Service Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class BetaReaderProtocol(Protocol):
    """Protocol for beta reader analysis services.

    Provides two analysis phases:
      Phase 1 (full): Comprehensive chapter analysis across all categories.
      Phase 2 (deepdive): Focused deep-dive on a specific category.

    Results are cached with 30min TTL.
    """

    async def analyze(
        self,
        *,
        novel_id: UUID,
        user_id: UUID,
        request: BetaReaderRequest,
    ) -> BetaReaderResponse:
        """Analyze chapter(s) from a beta reader's perspective.

        Phase 1: Comprehensive analysis across all requested categories.
        Produces strengths, feedback items, reader questions, and an overall
        assessment with scores.

        Args:
            novel_id: The project containing the chapters.
            user_id: The user requesting analysis.
            request: Analysis parameters (chapter IDs, categories, options).

        Returns:
            Complete beta reader feedback with overall assessment.
        """
        ...

    async def deep_dive(
        self,
        *,
        novel_id: UUID,
        user_id: UUID,
        request: BetaReaderDeepDiveRequest,
    ) -> BetaReaderDeepDiveResponse:
        """Run Phase 2 deep-dive on a specific category.

        Takes the context from Phase 1 (via cache key) and produces
        more detailed feedback for a specific category, including
        text-level references and revision suggestions.

        Args:
            novel_id: The project containing the chapters.
            user_id: The user requesting the deep-dive.
            request: Deep-dive parameters (chapter IDs, category, cache key).

        Returns:
            Detailed category-specific feedback with revision suggestions.
        """
        ...
