"""Contracts for the NLP subsystem — NLPProvider Protocol (RULE-08).

Result types are in ``contracts_types.py``, re-exported here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from narrare_core.nlp.contracts_types import (
        Entity,
        LanguageCode,
        POSTag,
        Token,
        TokenResult,
    )


@runtime_checkable
class NLPProvider(Protocol):
    """Protocol for NLP pipeline providers.

    All NLP operations (tokenization, POS tagging, NER, syllable counting,
    dialogue extraction) go through an object that satisfies this protocol.
    The primary implementation uses spaCy; graceful degradation to regex-based
    analysis is available when spaCy is not installed.

    This is a ``@runtime_checkable`` protocol — use
    ``isinstance(provider, NLPProvider)`` for runtime type checks.

    See Also
    --------
    ADR-021 — Deterministic Analysis Strategy (spaCy as NLP backbone).
    CONSTRAINTS.md RULE-08 — External integrations are abstracted.
    CONSTRAINTS.md RULE-03 — Contracts before implementation.
    """

    @property
    def supported_languages(self) -> list[str]:
        """Language codes that this provider can process.

        Returns:
            List of language codes this provider handles
            (e.g. ``["en", "de", "fr"]``).
        """
        ...

    async def tokenize(
        self,
        text: str,
        *,
        language: LanguageCode = "en",
    ) -> TokenResult:
        """Tokenize text into individual tokens.

        Args:
            text: The input text to tokenize.
            language: The language code.  Defaults to ``"en"``.

        Returns:
            A ``TokenResult`` containing all tokens and the resolved language.

        Raises:
            ValueError: If *language* is not in ``supported_languages``.
        """
        ...

    async def sentence_split(
        self,
        text: str,
        *,
        language: LanguageCode = "en",
    ) -> list[str]:
        """Split text into individual sentences.

        Args:
            text: The input text to split.
            language: The language code.  Defaults to ``"en"``.

        Returns:
            List of sentence strings, preserving original whitespace.

        Raises:
            ValueError: If *language* is not in ``supported_languages``.
        """
        ...

    async def pos_tag(
        self,
        text: str,
        *,
        language: LanguageCode = "en",
    ) -> list[POSTag]:
        """Perform part-of-speech tagging on the input text.

        Returns Universal Dependencies POS tags for each token.

        Args:
            text: The input text to tag.
            language: The language code.  Defaults to ``"en"``.

        Returns:
            List of ``POSTag`` results, one per token.

        Raises:
            ValueError: If *language* is not in ``supported_languages``.
        """
        ...

    async def extract_entities(
        self,
        text: str,
        *,
        language: LanguageCode = "en",
    ) -> list[Entity]:
        """Extract named entities from text.

        Args:
            text: The input text to analyse.
            language: The language code.  Defaults to ``"en"``.

        Returns:
            List of ``Entity`` objects found in the text.

        Raises:
            ValueError: If *language* is not in ``supported_languages``.
        """
        ...

    async def count_syllables(
        self,
        word: str,
        *,
        language: LanguageCode = "en",
    ) -> int:
        """Count syllables in a single word.

        Uses language-specific heuristics when a dictionary lookup fails.

        Args:
            word: A single word without whitespace.
            language: The language code.  Defaults to ``"en"``.

        Returns:
            Number of syllables in *word* (``0`` for empty strings).

        Raises:
            ValueError: If *language* is not in ``supported_languages``.
        """
        ...

    async def tokenize_for_sentiment(
        self,
        text: str,
        *,
        language: LanguageCode = "en",
    ) -> tuple[list[Token], list[str]]:
        """Tokenize and sentence-split in a single call.

        Optimised for the sentiment analysis pipeline — returns both tokens
        and sentences from a single processing pass.  This avoids the overhead
        of two separate calls to :meth:`tokenize` and :meth:`sentence_split`.

        The default implementation calls both methods individually.  Providers
        (particularly the spaCy adapter) should override this to perform a
        single ``Doc`` pass.

        Args:
            text: The input text to process.
            language: The language code.  Defaults to ``"en"``.

        Returns:
            A tuple of ``(tokens, sentences)`` where ``tokens`` is the full
            :class:`Token` list and ``sentences`` is a list of sentence strings.

        Raises:
            ValueError: If *language* is not in ``supported_languages``.
        """
        ...

    def is_available(
        self,
        *,
        language: LanguageCode = "en",
    ) -> bool:
        """Check whether this provider is functional for a given language.

        For the spaCy-based provider, this checks that the language model
        is installed and loadable.  For degraded (regex) mode, this always
        returns ``True``.

        Args:
            language: The language code.  Defaults to ``"en"``.

        Returns:
            ``True`` if this provider can process the requested *language*.
        """
        ...
