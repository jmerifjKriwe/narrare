"""
spaCy adapter for the NLPProvider Protocol.

This module is the ONLY place where ``import spacy`` is permitted
(RULE-08 in CONSTRAINTS.md). All NLP operations in the analysis layer
go through the :class:`NLPProvider` Protocol, never directly through spaCy.

Graceful degradation
---------------------
- If a spaCy language model is not installed, :meth:`is_available`
  returns ``False`` for that language.
- Callers are expected to check ``is_available()`` before calling
  any processing method.
- Model loading failures are caught, logged with structlog, and
  re-raised as :class:`NLPProviderError`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from narrare_core.nlp.contracts_types import LanguageCode

from narrare_core.nlp.contracts_types import (
    Entity,
    POSTag,
    Token,
    TokenResult,
)
from narrare_core.shared.errors import NLPProviderError

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Language → spaCy model mapping
# ---------------------------------------------------------------------------

_MODEL_MAP: dict[LanguageCode, str] = {
    "de": "de_core_news_md",
    "en": "en_core_web_md",
    "fr": "fr_core_news_md",
}

# ---------------------------------------------------------------------------
# Provider implementation
# ---------------------------------------------------------------------------


class SpacyNLPProvider:
    """NLP provider backed by spaCy language models.

    Models are loaded **lazily** — the first call to any processing method
    for a given language triggers ``spacy.load()``.  Once loaded, the
    pipeline object is cached in-memory for the lifetime of this provider
    instance.

    If loading fails (model not installed, file corruption), the error is
    logged via structlog and :class:`NLPProviderError` is raised.
    Subsequent calls to :meth:`is_available` will return ``False`` for that
    language until a new provider instance is created.

    Usage::

        provider = SpacyNLPProvider()
        if provider.is_available(language="en"):
            result = await provider.tokenize("Hello, world!", language="en")

    See Also
    --------
    NLPProvider : Protocol this class implements.
    """

    def __init__(self) -> None:
        # language code -> loaded spaCy pipeline (cached after first load)
        self._models: dict[str, Any] = {}
        # set of language codes whose model failed to load
        self._load_errors: set[str] = set()

    # ------------------------------------------------------------------
    # Protocol: supported_languages
    # ------------------------------------------------------------------

    @property
    def supported_languages(self) -> list[str]:
        return list(_MODEL_MAP.keys())

    # ------------------------------------------------------------------
    # Internal: lazy model loading
    # ------------------------------------------------------------------

    def _get_model(self, language: LanguageCode) -> Any:
        """Load (or retrieve cached) spaCy pipeline for *language*.

        Args:
            language: One of ``"en"``, ``"de"``, ``"fr"``.

        Returns:
            A loaded ``spacy.Language`` pipeline.

        Raises:
            ValueError: If *language* is not in ``supported_languages``.
            NLPProviderError: If the model could not be loaded.
        """
        import spacy  # pyright: ignore[reportMissingImports] -- optional dependency

        if language not in _MODEL_MAP:
            raise ValueError(
                f"Unsupported language '{language}'. Supported: {list(_MODEL_MAP.keys())}."
            )

        # Previously failed — fast path
        if language in self._load_errors:
            raise NLPProviderError(
                f"spaCy model for language '{language}' was not available "
                f"on a previous attempt and has not been retried."
            )

        # Already cached — fast path
        if language in self._models:
            return self._models[language]

        # Lazy load
        model_name = _MODEL_MAP[language]
        try:
            nlp: Any = spacy.load(model_name)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            self._models[language] = nlp
            logger.info(
                "spacy_model_loaded",
                language=language,
                model=model_name,
            )
            return nlp  # pyright: ignore[reportUnknownVariableType]
        except OSError as exc:
            self._load_errors.add(language)
            logger.error(
                "spacy_model_load_failed",
                language=language,
                model=model_name,
                error=str(exc),
            )
            raise NLPProviderError(
                f"spaCy model '{model_name}' for language '{language}' "
                f"is not installed. "
                f"Install with: python -m spacy download {model_name}"
            ) from exc

    # ------------------------------------------------------------------
    # Protocol: tokenize
    # ------------------------------------------------------------------

    async def tokenize(
        self,
        text: str,
        *,
        language: LanguageCode = "en",
    ) -> TokenResult:
        """Tokenize text using spaCy's tokenizer.

        Returns a :class:`TokenResult` with one :class:`Token` per
        spaCy token (including punctuation and whitespace tokens).
        """
        nlp = self._get_model(language)
        doc = nlp(text)

        tokens = [
            Token(
                text=token.text,
                start=token.idx,
                end=token.idx + len(token.text),
                pos=token.pos_ if token.pos_ else None,
                lemma=(token.lemma_ if token.lemma_ and token.lemma_ != token.text else None),
                is_sent_start=token.is_sent_start,
            )
            for token in doc
        ]

        return TokenResult(tokens=tokens, language=language)

    # ------------------------------------------------------------------
    # Protocol: sentence_split
    # ------------------------------------------------------------------

    async def sentence_split(
        self,
        text: str,
        *,
        language: LanguageCode = "en",
    ) -> list[str]:
        """Split text into sentences using spaCy's sentence boundary detection."""
        nlp = self._get_model(language)
        doc = nlp(text)
        return [sent.text.strip() for sent in doc.sents]

    # ------------------------------------------------------------------
    # Protocol: pos_tag
    # ------------------------------------------------------------------

    async def pos_tag(
        self,
        text: str,
        *,
        language: LanguageCode = "en",
    ) -> list[POSTag]:
        """Part-of-speech tagging using spaCy's tagger component.

        Returns one :class:`POSTag` per token with Universal Dependencies POS tags.
        """
        nlp = self._get_model(language)
        doc = nlp(text)

        return [
            POSTag(
                token=token.text,
                pos=token.pos_,
                lemma=(token.lemma_ if token.lemma_ and token.lemma_ != token.text else None),
                start=token.idx,
                end=token.idx + len(token.text),
            )
            for token in doc
        ]

    # ------------------------------------------------------------------
    # Protocol: extract_entities
    # ------------------------------------------------------------------

    async def extract_entities(
        self,
        text: str,
        *,
        language: LanguageCode = "en",
    ) -> list[Entity]:
        """Extract named entities using spaCy's NER component."""
        nlp = self._get_model(language)
        doc = nlp(text)

        return [
            Entity(
                text=ent.text,
                label=ent.label_,
                start=ent.start_char,
                end=ent.end_char,
            )
            for ent in doc.ents
        ]

    # ------------------------------------------------------------------
    # Protocol: count_syllables
    # ------------------------------------------------------------------

    async def count_syllables(
        self,
        word: str,
        *,
        language: LanguageCode = "en",
    ) -> int:
        """Count syllables by delegating to the syllables module.

        See ``narrare_core.nlp.syllables`` for the implementation
        (pyphen-based with heuristic fallback).
        """
        from narrare_core.nlp.syllables import (
            count_syllables as _count,
        )

        return _count(word, language=language)

    # ------------------------------------------------------------------
    # Protocol: tokenize_for_sentiment
    # ------------------------------------------------------------------

    async def tokenize_for_sentiment(
        self,
        text: str,
        *,
        language: LanguageCode = "en",
    ) -> tuple[list[Token], list[str]]:
        """Tokenize and sentence-split in a single spaCy pass.

        This is an optimisation over calling :meth:`tokenize` and
        :meth:`sentence_split` separately — both use the same internal
        ``Doc`` object, avoiding redundant parsing.

        Returns:
            A tuple of ``(tokens, sentences)`` derived from the same parse.
        """
        nlp = self._get_model(language)
        doc = nlp(text)

        tokens = [
            Token(
                text=token.text,
                start=token.idx,
                end=token.idx + len(token.text),
                pos=token.pos_ if token.pos_ else None,
                lemma=(token.lemma_ if token.lemma_ and token.lemma_ != token.text else None),
                is_sent_start=token.is_sent_start,
            )
            for token in doc
        ]

        sentences = [sent.text.strip() for sent in doc.sents]

        return tokens, sentences

    # ------------------------------------------------------------------
    # Protocol: is_available
    # ------------------------------------------------------------------

    def is_available(
        self,
        *,
        language: LanguageCode = "en",
    ) -> bool:
        """Check whether the spaCy model for *language* is usable.

        ``False`` is returned when:
        - The language is not in ``supported_languages``.
        - The model was previously attempted and failed to load.
        - The model cannot be loaded on demand (spaCy not installed,
          model not downloaded, file corruption).
        """
        if language not in _MODEL_MAP:
            return False
        if language in self._load_errors:
            return False
        if language in self._models:
            return True

        # Try loading on demand
        try:
            self._get_model(language)
            return True
        except NLPProviderError, ValueError:
            return False
