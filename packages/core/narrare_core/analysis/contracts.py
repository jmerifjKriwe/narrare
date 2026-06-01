"""Analysis service contracts — Protocol definitions (RULE-03).

Analysis services in ``core/analysis/`` implement these protocols.
The API layer (``apps/api/analysis/``) consumes them via dependency injection.

See Also
--------
ADR-021 — Deterministic Analysis Strategy.
ADR-025 Decision 3 — ContextAssembler Centralization (Phase 5).
CONSTRAINTS.md RULE-03 — Contracts before implementation.
"""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING, Protocol, runtime_checkable

# Re-export from split contract modules for backward compatibility.
# Consumers importing from ``contracts`` continue to work unchanged.
from narrare_core.analysis.contracts_pov import POVDetector as POVDetector
from narrare_core.analysis.contracts_readability import (
    ReadabilityAgentProtocol as ReadabilityAgentProtocol,
)
from narrare_core.analysis.contracts_readability import (
    ReadabilityAnalyzer as ReadabilityAnalyzer,
)

__all__ = [
    "POVDetector",
    "ReadabilityAgentProtocol",
    "ReadabilityAnalyzer",
]

if TYPE_CHECKING:
    from narrare_core.analysis.types import (
        SentenceSentiment,
        SentimentOverview,
    )
    from narrare_core.context.types import TierBudget
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

    This is a deterministic computation -- identical input always produces
    identical output (per ADR-021).

    This is a ``@runtime_checkable`` protocol -- use
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


# ---------------------------------------------------------------------------
# ADR-025 Phase 5: Analysis Context Assembly Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class AnalysisAssemblerProtocol(Protocol):
    """Protocol for 3-tier analysis context assembly with token budgets.

    Simpler than writing's 5-tier system -- analysis features need
    content + KB context + preferences, but no outline/frontmatter.

    Tier allocation (default 6000-token budget):
        content:      50% -- chapter text / content to analyze
        kb_context:   30% -- KB entities (characters, locations, factions, relationships)
        preferences:  20% -- user preferences, avoidance patterns

    Per ADR-025 Decision 3: ``core/analysis/`` owns the concrete
    implementation; ``core/context/`` owns the abstract base.
    """

    async def assemble(
        self,
        *,
        content: str = "",
        kb_characters: str = "",
        kb_locations: str = "",
        kb_factions: str = "",
        kb_relationships: str = "",
        user_preferences: str = "",
        avoidance_patterns: str = "",
    ) -> dict[str, str]:
        """Assemble analysis context with budget enforcement.

        Returns:
            Flat dictionary of prompt variable names to their
            budget-enforced text values.
        """
        ...

    @property
    def total_budget(self) -> int:
        """Total token budget for context assembly."""
        ...

    def get_tier_allocation(self) -> dict[str, TierBudget]:
        """Return current tier allocation.

        Returns:
            Mapping of tier name to its budget allocation.
        """
        ...
