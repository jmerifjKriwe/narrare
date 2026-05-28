"""
Pydantic result types for NLP operations.

Extracted from ``contracts.py`` to comply with RULE-04 (200-line file limit).
All types are re-exported from ``contracts.py`` — import from there or from
``narrare_core.nlp``.

See Also
--------
CONSTRAINTS.md RULE-04 — File size limits.
"""

from __future__ import annotations

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

type LanguageCode = str  # Accepted values: "en", "de", "fr"

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


class Token(BaseModel):
    """A single token produced by tokenization.

    Attributes:
        text: The token text (e.g. ``"Anna"``, ``"run"``, ``"."``).
        start: Character offset of the start of this token in the source text.
        end: Character offset of the end of this token (exclusive).
        pos: Universal Dependencies POS tag if available, else ``None``.
        lemma: Lemma of the token if available (e.g. ``"run"`` for ``"running"``),
            else ``None``.
        is_sent_start: ``True`` if this token begins a sentence.
    """

    text: str
    start: int
    end: int
    pos: str | None = None
    lemma: str | None = None
    is_sent_start: bool = False


class TokenResult(BaseModel):
    """Result of a full tokenization operation.

    Attributes:
        tokens: All tokens produced from the input text, in order.
        language: The resolved language code after any auto-detection.
    """

    tokens: list[Token]
    language: LanguageCode


class POSTag(BaseModel):
    """Per-token part-of-speech tagging result.

    Attributes:
        token: The token text.
        pos: Universal Dependencies POS tag (e.g. ``"NOUN"``, ``"VERB"``).
        lemma: Lemma of the token if available.
        start: Character offset start in the source text.
        end: Character offset end (exclusive).
    """

    token: str
    pos: str
    lemma: str | None = None
    start: int
    end: int


class Entity(BaseModel):
    """A named entity extracted from text.

    Attributes:
        text: The entity surface form (e.g. ``"Anna"``).
        label: The entity label (e.g. ``"PER"``, ``"LOC"``, ``"ORG"``).
        start: Character offset start in the source text.
        end: Character offset end (exclusive).
    """

    text: str
    label: str
    start: int
    end: int
