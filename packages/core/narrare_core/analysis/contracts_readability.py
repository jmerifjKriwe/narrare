"""Readability analysis contracts — Protocol definitions (RULE-03).

Protocols for deterministic readability computation and AI-powered
sentence-level analysis.

See Also
--------
ADR-021 — Deterministic Analysis Strategy.
CONSTRAINTS.md RULE-03 — Contracts before implementation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from narrare_core.analysis.types import ReadabilityResult, SentenceAnalysis
    from narrare_core.nlp.contracts_types import LanguageCode


# ---------------------------------------------------------------------------
# ANAL-003: Readability — Protocols
# ---------------------------------------------------------------------------


@runtime_checkable
class ReadabilityAnalyzer(Protocol):
    """Protocol for the deterministic readability computation.

    Computes formula-based metrics only: Flesch Reading Ease,
    Flesch-Kincaid Grade Level, Gunning Fog Index.
    Purely mathematical -- no LLM calls (ADR-021).

    This is a ``@runtime_checkable`` protocol -- use
    ``isinstance(analyzer, ReadabilityAnalyzer)`` for runtime checks.
    """

    async def analyze(
        self,
        text: str,
        *,
        language: LanguageCode = "en",
    ) -> ReadabilityResult:
        """Compute formula-based readability metrics for the given text.

        Args:
            text: The text to analyse (chapter content, passage, etc.).
            language: Language code (``"en"``, ``"de"``, ``"fr"``).
                Defaults to ``"en"``.

        Returns:
            A :class:`ReadabilityResult` containing metrics plus genre
            benchmarks.  The ``sentence_analyses`` field will be empty
            when called directly -- use a ``ReadabilityAgentProtocol``
            for sentence-level AI analysis.
        """
        ...


@runtime_checkable
class ReadabilityAgentProtocol(Protocol):
    """Protocol for AI-powered sentence-level readability analysis.

    Uses a pydantic-ai agent (``ReadabilityAgent``) to identify
    problematic sentences and generate rewrite suggestions that
    preserve the author's voice.

    This is a ``@runtime_checkable`` protocol -- use
    ``isinstance(agent, ReadabilityAgentProtocol)`` for runtime checks.
    """

    async def analyze_sentences(
        self,
        text: str,
        *,
        language: LanguageCode = "en",
    ) -> list[SentenceAnalysis]:
        """Analyse sentence-level readability with AI.

        Args:
            text: The text to analyse.
            language: Language code (``"en"``, ``"de"``, ``"fr"``).
                Defaults to ``"en"``.

        Returns:
            A list of :class:`SentenceAnalysis` objects, one per
            sentence, with identified issues and rewrite suggestions.
        """
        ...
