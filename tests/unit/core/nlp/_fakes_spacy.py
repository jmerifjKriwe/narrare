"""Shared Fake spaCy classes and standard test data for NLP tests.

Follows the Fake-class pattern (ADR-030): real implementations of the spaCy
Token/Span/Doc/Pipeline interface — not MagicMock stubs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator


# --- Fake spaCy objects ---


@dataclass
class FakeSpacyToken:
    """Mimics a spaCy Token — only the attributes the provider reads."""

    text: str
    idx: int
    pos_: str = ""
    lemma_: str = ""
    is_sent_start: bool = False


@dataclass
class FakeSpacySpan:
    """Mimics a spaCy Span (sentence boundary)."""

    text: str


@dataclass
class FakeSpacyEntity:
    """Mimics a spaCy named entity."""

    text: str
    label_: str
    start_char: int
    end_char: int


@dataclass
class FakeSpacyDoc:
    """Mimics a spaCy Doc — iterable of tokens with ``.sents`` and ``.ents``."""

    tokens: list[FakeSpacyToken]
    sents: list[FakeSpacySpan]
    ents: list[FakeSpacyEntity] = field(default_factory=list)

    def __iter__(self) -> Iterator[FakeSpacyToken]:
        return iter(self.tokens)


class FakeSpacyPipeline:
    """Mimics a loaded spaCy pipeline — callable, returns a FakeSpacyDoc."""

    def __init__(self) -> None:
        self._tokens: list[FakeSpacyToken] = []
        self._sents: list[FakeSpacySpan] = []
        self._ents: list[FakeSpacyEntity] = []

    def set_output(
        self,
        tokens: list[FakeSpacyToken],
        sents: list[FakeSpacySpan],
        ents: list[FakeSpacyEntity] | None = None,
    ) -> None:
        self._tokens = tokens
        self._sents = sents
        self._ents = ents or []

    def __call__(self, text: str) -> FakeSpacyDoc:
        return FakeSpacyDoc(tokens=self._tokens, sents=self._sents, ents=self._ents)


# ---------------------------------------------------------------------------
# Standard test data — "Anna runs fast."
# ---------------------------------------------------------------------------

_TOKENS_ANNA: list[FakeSpacyToken] = [
    FakeSpacyToken(text="Anna", idx=0, pos_="PROPN", lemma_="Anna", is_sent_start=True),
    FakeSpacyToken(text="runs", idx=5, pos_="VERB", lemma_="run", is_sent_start=False),
    FakeSpacyToken(text="fast", idx=10, pos_="ADV", lemma_="", is_sent_start=False),
    FakeSpacyToken(text=".", idx=14, pos_="PUNCT", lemma_=".", is_sent_start=False),
]

_SENTS_ANNA: list[FakeSpacySpan] = [FakeSpacySpan(text="Anna runs fast.")]
_ENTS_ANNA: list[FakeSpacyEntity] = [
    FakeSpacyEntity(text="Anna", label_="PER", start_char=0, end_char=4),
]
