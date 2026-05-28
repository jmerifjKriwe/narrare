"""Analysis service contracts — Protocol definitions (RULE-03).

Analysis services in ``core/analysis/`` implement these protocols.
The API layer (``apps/api/analysis/``) consumes them via dependency injection.

See Also
--------
ADR-021 — Deterministic Analysis Strategy.
CONSTRAINTS.md RULE-03 — Contracts before implementation.
"""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from narrare_core.analysis.types import (
        SentenceSentiment,
        SentimentOverview,
    )
    from narrare_core.nlp.contracts_types import LanguageCode


# ---------------------------------------------------------------------------
# Shared Enums
# ---------------------------------------------------------------------------


class NarrativeArcType(enum.StrEnum):
    """Types of narrative arcs that can be detected from sentiment progression."""

    FREYTAG_PYRAMID = "freytag_pyramid"
    HERO_JOURNEY = "hero_journey"
    MAN_IN_HOLE = "man_in_hole"
    COMEDY = "comedy"
    TRAGEDY = "tragedy"
    REVERSAL = "reversal"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# ANAL-002: Sentiment — Service Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class SentimentAnalyzer(Protocol):
    """Protocol for text sentiment analysis.

    Implementations use the NLPProvider (``core/nlp/``) plus emotion lexica
    to produce deterministic VAD and emotion scores for any text.

    This is a deterministic computation — identical input always produces
    identical output (per ADR-021).

    This is a ``@runtime_checkable`` protocol — use
    ``isinstance(analyzer, SentimentAnalyzer)`` for runtime type checks.
    """

    async def analyze(
        self,
        text: str,
        *,
        language: LanguageCode = "en",
        detect_arc: bool = True,
    ) -> SentimentOverview:
        """Analyze sentiment of the given text.

        Args:
            text: The full text (chapter content) to analyze.
            language: Language code (``"en"``, ``"de"``, ``"fr"``).
                Defaults to ``"en"``.
            detect_arc: Whether to attempt narrative arc detection.
                Set to ``False`` for short texts (< 5 sentences).
                Defaults to ``True``.

        Returns:
            A :class:`SentimentOverview` with per-sentence breakdown
            and overall aggregate scores.
        """
        ...

    async def analyze_sentence(
        self,
        sentence: str,
        *,
        language: LanguageCode = "en",
    ) -> SentenceSentiment:
        """Analyze sentiment of a single sentence.

        Args:
            sentence: A single sentence to analyze.
            language: Language code (``"en"``, ``"de"``, ``"fr"``).
                Defaults to ``"en"``.

        Returns:
            Per-sentence :class:`SentenceSentiment` with VAD + emotions.
        """
        ...
