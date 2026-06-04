"""Shared fakes and helpers for sentiment analysis tests (RULE-TEST-01).

This module provides test-only fakes and utilities that are shared across
the split test files. Unlike conftest.py, this is a regular module that
test files can import from directly.
"""

from __future__ import annotations

from typing import Any

from narrare_core.nlp.contracts_types import Token, TokenResult


class FakeNLPProvider:
    """Deterministic fake NLP provider for sentiment analysis tests.

    Provides controllable tokenization and sentence splitting without
    requiring spaCy.
    """

    def __init__(
        self,
        *,
        available: bool = True,
        tokenize_result: TokenResult | None = None,
        sentences: list[str] | None = None,
    ) -> None:
        self._available = available
        self._tokenize_result = tokenize_result
        self._sentences = sentences

    @property
    def supported_languages(self) -> list[str]:
        return ["en", "de", "fr"]

    def is_available(self, *, language: str = "en") -> bool:
        return self._available

    async def tokenize(self, text: str, *, language: str = "en") -> TokenResult:
        if self._tokenize_result is not None:
            return self._tokenize_result
        # Default: simple whitespace tokenization
        tokens = [
            Token(
                text=word,
                start=i,
                end=i + len(word),
                pos=None,
                lemma=None,
                is_sent_start=(i == 0),
            )
            for i, word in enumerate(text.split())
        ]
        return TokenResult(tokens=tokens, language=language)

    async def sentence_split(self, text: str, *, language: str = "en") -> list[str]:
        if self._sentences is not None:
            return self._sentences
        # Default: split on period
        return [s.strip() for s in text.split(".") if s.strip()]

    async def pos_tag(self, text: str, *, language: str = "en") -> list[Any]:
        return []

    async def extract_entities(self, text: str, *, language: str = "en") -> list[Any]:
        return []

    async def count_syllables(self, word: str, *, language: str = "en") -> int:
        return 1

    async def tokenize_for_sentiment(
        self,
        text: str,
        *,
        language: str = "en",
    ) -> tuple[list[Token], list[str]]:
        result = await self.tokenize(text, language=language)
        sentences = await self.sentence_split(text, language=language)
        return result.tokens, sentences


class FailingNLPProvider(FakeNLPProvider):
    """NLP provider that raises on tokenize/tokenize_for_sentiment."""

    async def tokenize(self, text: str, *, language: str = "en") -> TokenResult:
        raise RuntimeError("Tokenization engine crashed")

    async def tokenize_for_sentiment(
        self,
        text: str,
        *,
        language: str = "en",
    ) -> tuple[list[Token], list[str]]:
        raise RuntimeError("Tokenization engine crashed")


def _make_tokens(words: list[str]) -> list[Token]:  # pyright: ignore[reportUnusedFunction]
    """Create Token objects from a list of word strings."""
    offset = 0
    tokens: list[Token] = []
    for i, word in enumerate(words):
        tokens.append(
            Token(
                text=word,
                start=offset,
                end=offset + len(word),
                pos=None,
                lemma=None,
                is_sent_start=(i == 0),
            )
        )
        offset += len(word) + 1  # +1 for space
    return tokens
