"""Tests for SpacyNLPProvider processing methods with Fake spaCy objects.

Injects a fake ``spacy`` module into ``sys.modules`` so that the provider's
lazy-load and processing methods can be exercised without spaCy installed.

Follows the Fake-class pattern (ADR-030): real implementations of the spaCy
Token/Span/Doc/Pipeline interface — not MagicMock stubs.

Covers:
- _get_model: successful load, caching, OSError → NLPProviderError, ValueError
- tokenize: TokenResult construction, lemma/pos edge cases
- sentence_split: sentence extraction and stripping
- pos_tag: POSTag construction
- extract_entities: Entity extraction
- tokenize_for_sentiment: combined tokens + sentences
- is_available: on-demand load try/except (lines 335, 337)
"""

from __future__ import annotations

import sys
import types

import pytest

from narrare_core.nlp.contracts_types import Entity, POSTag, Token, TokenResult
from narrare_core.nlp.provider_spacy import SpacyNLPProvider
from narrare_core.shared.errors import NLPProviderError
from tests.unit.core.nlp._fakes_spacy import (
    _ENTS_ANNA,
    _SENTS_ANNA,
    _TOKENS_ANNA,
    FakeSpacyPipeline,
    FakeSpacySpan,
    FakeSpacyToken,
)

# ---------------------------------------------------------------------------
# Fixtures — inject fake spacy module into sys.modules
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_pipeline() -> FakeSpacyPipeline:
    """A FakeSpacyPipeline pre-loaded with standard test data."""
    pipeline = FakeSpacyPipeline()
    pipeline.set_output(
        tokens=list(_TOKENS_ANNA),
        sents=list(_SENTS_ANNA),
        ents=list(_ENTS_ANNA),
    )
    return pipeline


@pytest.fixture
def inject_spacy(
    monkeypatch: pytest.MonkeyPatch,
    fake_pipeline: FakeSpacyPipeline,
) -> FakeSpacyPipeline:
    """Inject a fake ``spacy`` module whose ``load`` returns *fake_pipeline*.

    After the test, ``monkeypatch`` restores the original ``sys.modules``
    so other tests see the real (uninstalled) state.
    """
    module = types.ModuleType("spacy")
    module.load = lambda model_name: fake_pipeline  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "spacy", module)
    return fake_pipeline


@pytest.fixture
def inject_failing_spacy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inject a fake ``spacy`` module whose ``load`` raises OSError."""

    def _fail_load(model_name: str) -> FakeSpacyPipeline:
        msg = f"Can't find model '{model_name}'. It doesn't seem to be a Python package."
        raise OSError(msg)

    module = types.ModuleType("spacy")
    module.load = _fail_load  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "spacy", module)


# ---------------------------------------------------------------------------
# A. _get_model — successful load, caching, error handling (lines 109-144)
# ---------------------------------------------------------------------------


class TestGetModelWithFakeSpacy:
    """_get_model() with an injected fake spaCy module."""

    def test_successful_load_returns_pipeline(self, inject_spacy: FakeSpacyPipeline) -> None:
        """First call loads and returns the pipeline."""
        provider = SpacyNLPProvider()
        result = provider._get_model("en")
        assert result is inject_spacy

    def test_successful_load_caches_in_models(self, inject_spacy: FakeSpacyPipeline) -> None:
        """Loaded model is stored in _models for future calls."""
        provider = SpacyNLPProvider()
        provider._get_model("en")
        assert "en" in provider._models

    def test_second_call_returns_cached_object(self, inject_spacy: FakeSpacyPipeline) -> None:
        """Second call returns the same cached object."""
        provider = SpacyNLPProvider()
        first = provider._get_model("en")
        second = provider._get_model("en")
        assert first is second

    def test_pre_cached_model_returned_directly(self, inject_spacy: FakeSpacyPipeline) -> None:
        """Pre-cached model is returned without calling spacy.load."""
        provider = SpacyNLPProvider()
        provider._models["de"] = inject_spacy
        result = provider._get_model("de")
        assert result is inject_spacy

    def test_unsupported_language_raises_valueerror(self, inject_spacy: FakeSpacyPipeline) -> None:
        provider = SpacyNLPProvider()
        with pytest.raises(ValueError, match="Unsupported language"):
            provider._get_model("zh")

    def test_cached_error_raises_nlp_provider_error(self, inject_spacy: FakeSpacyPipeline) -> None:
        """Previously failed language raises immediately."""
        provider = SpacyNLPProvider()
        provider._load_errors.add("en")
        with pytest.raises(NLPProviderError, match="not been retried"):
            provider._get_model("en")

    def test_oserror_raises_nlp_provider_error(self, inject_failing_spacy: None) -> None:
        """OSError from spacy.load is converted to NLPProviderError."""
        provider = SpacyNLPProvider()
        with pytest.raises(NLPProviderError, match="is not installed"):
            provider._get_model("en")

    def test_oserror_caches_failure_in_load_errors(self, inject_failing_spacy: None) -> None:
        """After OSError, the language is added to _load_errors."""
        provider = SpacyNLPProvider()
        with pytest.raises(NLPProviderError):
            provider._get_model("fr")
        assert "fr" in provider._load_errors


# ---------------------------------------------------------------------------
# B. is_available — on-demand load try/except (lines 335, 337)
# ---------------------------------------------------------------------------


class TestIsAvailableWithFakeSpacy:
    """is_available() on-demand loading path."""

    def test_returns_true_when_model_loads(self, inject_spacy: FakeSpacyPipeline) -> None:
        """Valid language + successful load → True."""
        provider = SpacyNLPProvider()
        assert provider.is_available(language="en") is True
        assert "en" in provider._models

    def test_returns_false_when_load_raises(self, inject_failing_spacy: None) -> None:
        """NLPProviderError from _get_model → False."""
        provider = SpacyNLPProvider()
        assert provider.is_available(language="en") is False
        assert "en" in provider._load_errors


# ---------------------------------------------------------------------------
# C. tokenize — TokenResult construction (lines 165-180)
# ---------------------------------------------------------------------------


class TestTokenizeWithFakeSpacy:
    """tokenize() builds TokenResult from a spaCy Doc."""

    async def test_returns_token_result(self, inject_spacy: FakeSpacyPipeline) -> None:
        provider = SpacyNLPProvider()
        result = await provider.tokenize("Anna runs fast.", language="en")
        assert isinstance(result, TokenResult)
        assert result.language == "en"

    async def test_token_count_matches_doc(self, inject_spacy: FakeSpacyPipeline) -> None:
        provider = SpacyNLPProvider()
        result = await provider.tokenize("Anna runs fast.", language="en")
        assert len(result.tokens) == 4

    async def test_token_text_and_offsets(self, inject_spacy: FakeSpacyPipeline) -> None:
        provider = SpacyNLPProvider()
        result = await provider.tokenize("Anna runs fast.", language="en")
        anna = result.tokens[0]
        assert anna.text == "Anna"
        assert anna.start == 0
        assert anna.end == 4
        assert anna.is_sent_start is True

    async def test_lemma_none_when_equals_text(self, inject_spacy: FakeSpacyPipeline) -> None:
        """Lemma is None when lemma_ equals the token text."""
        provider = SpacyNLPProvider()
        result = await provider.tokenize("Anna runs fast.", language="en")
        assert result.tokens[0].lemma is None  # "Anna" == "Anna"

    async def test_lemma_set_when_different(self, inject_spacy: FakeSpacyPipeline) -> None:
        """Lemma is populated when lemma_ differs from text."""
        provider = SpacyNLPProvider()
        result = await provider.tokenize("Anna runs fast.", language="en")
        assert result.tokens[1].lemma == "run"  # "runs" → "run"

    async def test_lemma_none_when_empty(self, inject_spacy: FakeSpacyPipeline) -> None:
        """Lemma is None when lemma_ is an empty string (falsy)."""
        provider = SpacyNLPProvider()
        result = await provider.tokenize("Anna runs fast.", language="en")
        assert result.tokens[2].lemma is None  # "fast", lemma_=""

    async def test_pos_none_when_empty(self, inject_spacy: FakeSpacyPipeline) -> None:
        """pos is None when pos_ is an empty string (falsy)."""
        inject_spacy.set_output(
            tokens=[FakeSpacyToken(text="hmm", idx=0, pos_="", lemma_="")],
            sents=[FakeSpacySpan(text="hmm")],
        )
        provider = SpacyNLPProvider()
        result = await provider.tokenize("hmm", language="en")
        assert result.tokens[0].pos is None


# ---------------------------------------------------------------------------
# D. sentence_split — sentence extraction (lines 193-195)
# ---------------------------------------------------------------------------


class TestSentenceSplitWithFakeSpacy:
    """sentence_split() extracts and strips sentences from a Doc."""

    async def test_returns_stripped_sentences(self, inject_spacy: FakeSpacyPipeline) -> None:
        provider = SpacyNLPProvider()
        result = await provider.sentence_split("Anna runs fast.", language="en")
        assert result == ["Anna runs fast."]

    async def test_multiple_sentences_stripped(self, inject_spacy: FakeSpacyPipeline) -> None:
        inject_spacy.set_output(
            tokens=list(_TOKENS_ANNA),
            sents=[FakeSpacySpan(text="Hello world. "), FakeSpacySpan(text="Goodbye. ")],
        )
        provider = SpacyNLPProvider()
        result = await provider.sentence_split("Hello world. Goodbye.", language="en")
        assert result == ["Hello world.", "Goodbye."]


# ---------------------------------------------------------------------------
# E. pos_tag — POSTag construction (lines 211-214)
# ---------------------------------------------------------------------------


class TestPosTagWithFakeSpacy:
    """pos_tag() builds POSTag list from a Doc."""

    async def test_returns_postag_list(self, inject_spacy: FakeSpacyPipeline) -> None:
        provider = SpacyNLPProvider()
        result = await provider.pos_tag("Anna runs fast.", language="en")
        assert len(result) == 4
        assert all(isinstance(tag, POSTag) for tag in result)

    async def test_postag_fields_populated(self, inject_spacy: FakeSpacyPipeline) -> None:
        provider = SpacyNLPProvider()
        result = await provider.pos_tag("Anna runs fast.", language="en")
        anna = result[0]
        assert anna.token == "Anna"
        assert anna.pos == "PROPN"
        assert anna.start == 0
        assert anna.end == 4

    async def test_postag_lemma_none_when_equals_text(
        self, inject_spacy: FakeSpacyPipeline
    ) -> None:
        provider = SpacyNLPProvider()
        result = await provider.pos_tag("Anna runs fast.", language="en")
        assert result[0].lemma is None  # "Anna" == "Anna"
        assert result[1].lemma == "run"  # "runs" → "run"


# ---------------------------------------------------------------------------
# F. extract_entities — Entity extraction (lines 236-239)
# ---------------------------------------------------------------------------


class TestExtractEntitiesWithFakeSpacy:
    """extract_entities() builds Entity list from Doc.ents."""

    async def test_returns_entities(self, inject_spacy: FakeSpacyPipeline) -> None:
        provider = SpacyNLPProvider()
        result = await provider.extract_entities("Anna runs fast.", language="en")
        assert len(result) == 1
        assert all(isinstance(ent, Entity) for ent in result)

    async def test_entity_fields(self, inject_spacy: FakeSpacyPipeline) -> None:
        provider = SpacyNLPProvider()
        result = await provider.extract_entities("Anna runs fast.", language="en")
        ent = result[0]
        assert ent.text == "Anna"
        assert ent.label == "PER"
        assert ent.start == 0
        assert ent.end == 4

    async def test_empty_entities_returns_empty_list(self, inject_spacy: FakeSpacyPipeline) -> None:
        inject_spacy.set_output(
            tokens=[FakeSpacyToken(text="sky", idx=0, pos_="NOUN", lemma_="sky")],
            sents=[FakeSpacySpan(text="sky")],
            ents=[],
        )
        provider = SpacyNLPProvider()
        result = await provider.extract_entities("sky", language="en")
        assert result == []


# ---------------------------------------------------------------------------
# G. tokenize_for_sentiment — combined pass (lines 290-306)
# ---------------------------------------------------------------------------


class TestTokenizeForSentimentWithFakeSpacy:
    """tokenize_for_sentiment() returns tokens + sentences from one Doc pass."""

    async def test_returns_tokens_and_sentences(self, inject_spacy: FakeSpacyPipeline) -> None:
        provider = SpacyNLPProvider()
        tokens, sentences = await provider.tokenize_for_sentiment("Anna runs fast.", language="en")
        assert len(tokens) == 4
        assert sentences == ["Anna runs fast."]

    async def test_tokens_are_token_instances(self, inject_spacy: FakeSpacyPipeline) -> None:
        provider = SpacyNLPProvider()
        tokens, _ = await provider.tokenize_for_sentiment("Anna.", language="en")
        assert all(isinstance(t, Token) for t in tokens)

    async def test_token_pos_and_lemma_branches(self, inject_spacy: FakeSpacyPipeline) -> None:
        """Exercise pos/lemma conditionals within a single-pass call."""
        provider = SpacyNLPProvider()
        tokens, _ = await provider.tokenize_for_sentiment("Anna runs.", language="en")
        # "runs" has different lemma → lemma set
        assert tokens[1].pos == "VERB"
        assert tokens[1].lemma == "run"
        # "fast" has empty lemma_ → lemma None, but pos is ADV
        assert tokens[2].lemma is None
        assert tokens[2].pos == "ADV"
