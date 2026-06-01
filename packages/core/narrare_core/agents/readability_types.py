"""Output types for ReadabilityAgent.

See ADR-015 Phase 2.1 — Output Types.
ADR-021 — Deterministic metrics are separate (``analysis/readability.py``);
these types are for the AI-powered sentence-level analysis only.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class SentenceIssue(BaseModel):
    """An issue detected in a sentence.

    Attributes:
        type: Category of the issue (``"too_long"``,
            ``"complex_vocabulary"``, ``"passive_voice"``,
            ``"ambiguous"``).
        description: Human-readable description of the problem.
    """

    type: str = ""
    description: str = ""


class SentenceSuggestion(BaseModel):
    """A rewrite suggestion for a problematic sentence.

    Attributes:
        alternative: The rewritten version of the sentence.
        improvement: What this alternative improves (e.g.
            ``"Breaks a 35-word sentence into two shorter ones"``).
    """

    alternative: str = ""
    improvement: str = ""


class ReadabilityAgentOutput(BaseModel):
    """Structured output from the ReadabilityAgent.

    Contains per-sentence analysis with issues and rewrite suggestions,
    plus an overall readability assessment.

    Attributes:
        problematic_sentences: Sentences identified as hard to read,
            each with position, issues, and suggestions.
        overall_assessment: Free-text summary of the passage's
            readability (1-2 sentences).
    """

    problematic_sentences: list[dict[str, Any]] = []
    overall_assessment: str = ""
