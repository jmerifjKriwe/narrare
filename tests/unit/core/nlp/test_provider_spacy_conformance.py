"""Protocol conformance tests for SpacyNLPProvider — FakeNLPProvider + runtime_checkable.

Since spaCy may not be installed in test environments, these tests use
FakeNLPProvider for deterministic protocol conformance checking.

Covers:
- FakeNLPProvider implements NLPProvider protocol
- SpacyNLPProvider implements NLPProvider protocol
- FakeNLPProvider method correctness (is_available, tokenize, etc.)
- SpacyNLPProvider.tokenize_for_sentiment graceful degradation
"""

from __future__ import annotations

from typing import Any

import pytest

from narrare_core.nlp.contracts import NLPProvider
from narrare_core.nlp.contracts_types import Token, TokenResult
from narrare_core.nlp.provider_spacy import SpacyNLPProvider
from narrare_core.shared.errors import NLPProviderError

# ---------------------------------------------------------------------------
# Fake for protocol conformance (independent of helpers.FakeNLPProvider)
# ---------------------------------------------------------------------------


class FakeNLPProvider:
    """Minimal fake implementing NLPProvider protocol for conformance tests.

    This fake does not require spaCy. It provides deterministic stub
    responses for all protocol methods.
    """

    def __init__(self, available: bool = True) -> None:
        self._available = available

    @property
    def supported_languages(self) -> list[str]:
        return ["en", "de", "fr"]

    def is_available(self, *, language: str = "en") -> bool:
        return self._available

    async def tokenize(self, text: str, *, language: str = "en") -> TokenResult:
        tokens = [
            Token(
                text=text,
                start=0,
                end=len(text),
                pos=None,
                lemma=None,
                is_sent_start=True,
            )
        ]
        return TokenResult(tokens=tokens, language=language)

    async def sentence_split(self, text: str, *, language: str = "en") -> list[str]:
        return [text]

    async def pos_tag(self, text: str, *, language: str = "en") -> list[Any]:
        return []

    async def extract_entities(self, text: str, *, language: str = "en") -> list[Any]:
        return []

    async def count_syllables(self, word: str, *, language: str = "en") -> int:
        return 1  # Stub — exact counting is tested in test_syllables.py

    async def tokenize_for_sentiment(
        self,
        text: str,
        *,
        language: str = "en",
    ) -> tuple[list[Token], list[str]]:
        tokens = await self.tokenize(text, language=language)
        sentences = await self.sentence_split(text, language=language)
        return tokens.tokens, sentences


class TestProtocolConformance:
    """Verify that providers satisfy the NLPProvider Protocol (RULE-03)."""

    def test_fake_nlp_provider_conforms_to_protocol(self) -> None:
        """FakeNLPProvider satisfies NLPProvider protocol."""
        provider: NLPProvider = FakeNLPProvider()
        assert isinstance(provider, NLPProvider)

    def test_spacy_provider_conforms_to_protocol(self) -> None:
        """SpacyNLPProvider satisfies NLPProvider protocol."""
        provider: NLPProvider = SpacyNLPProvider()
        assert isinstance(provider, NLPProvider)

    def test_fake_is_available(self) -> None:
        """FakeNLPProvider.is_available returns configured value."""
        available = FakeNLPProvider(available=True)
        unavailable = FakeNLPProvider(available=False)
        assert available.is_available() is True
        assert unavailable.is_available() is False

    def test_fake_supported_languages(self) -> None:
        """FakeNLPProvider.supported_languages returns en, de, fr."""
        provider = FakeNLPProvider()
        assert "en" in provider.supported_languages
        assert "de" in provider.supported_languages
        assert "fr" in provider.supported_languages

    @pytest.mark.asyncio
    async def test_fake_tokenize_returns_token_result(self) -> None:
        """FakeNLPProvider.tokenize returns a valid TokenResult."""
        provider = FakeNLPProvider()
        result = await provider.tokenize("Hello, world!")
        assert isinstance(result, TokenResult)
        assert len(result.tokens) == 1
        assert result.language == "en"

    @pytest.mark.asyncio
    async def test_fake_sentence_split_returns_list(self) -> None:
        """FakeNLPProvider.sentence_split returns a list of sentences."""
        provider = FakeNLPProvider()
        sentences = await provider.sentence_split("Hello. World.")
        assert isinstance(sentences, list)
        assert len(sentences) >= 1

    @pytest.mark.asyncio
    async def test_fake_tokenize_for_sentiment_returns_tuple(self) -> None:
        """FakeNLPProvider.tokenize_for_sentiment returns (tokens, sentences)."""
        provider = FakeNLPProvider()
        tokens, sentences = await provider.tokenize_for_sentiment("Hello!")
        assert isinstance(tokens, list)
        assert isinstance(sentences, list)

    @pytest.mark.asyncio
    async def test_fake_count_syllables_returns_int(self) -> None:
        """FakeNLPProvider.count_syllables returns an int."""
        provider = FakeNLPProvider()
        result = await provider.count_syllables("test")
        assert isinstance(result, int)


class TestTokenizeForSentiment:
    """SpacyNLPProvider.tokenize_for_sentiment — delegates to _get_model."""

    @pytest.mark.asyncio
    async def test_tokenize_for_sentiment_raises_without_spacy(self) -> None:
        """Without spaCy, tokenize_for_sentiment raises ImportError."""
        try:
            __import__("spacy")
            pytest.skip("spaCy is installed — test only valid without spaCy")
        except ImportError:
            pass
        provider = SpacyNLPProvider()
        with pytest.raises((ImportError, NLPProviderError, ValueError)):
            await provider.tokenize_for_sentiment("Hello, world!")
