"""Integration tests for SpacyNLPProvider — real spaCy models required.

Module-level skip (spaCy + all models) lives in ``conftest.py``.

No mocking, no faking — every test exercises real model loading,
tokenization, POS tagging, NER, sentence splitting, and syllable counting.
"""

from __future__ import annotations

import pytest

from narrare_core.nlp.contracts_types import Entity, POSTag, TokenResult
from narrare_core.nlp.provider_spacy import SpacyNLPProvider  # noqa: TC001
from narrare_core.shared.errors import NLPProviderError

# ===================================================================
# 1. supported_languages
# ===================================================================


class TestSupportedLanguages:
    """supported_languages property with real models available."""

    def test_returns_exactly_en_de_fr(self, provider: SpacyNLPProvider) -> None:
        langs = provider.supported_languages
        assert sorted(langs) == ["de", "en", "fr"]

    def test_returns_list(self, provider: SpacyNLPProvider) -> None:
        assert isinstance(provider.supported_languages, list)

    def test_returns_three_languages(self, provider: SpacyNLPProvider) -> None:
        assert len(provider.supported_languages) == 3


# ===================================================================
# 2. is_available
# ===================================================================


class TestIsAvailable:
    """is_available() with real spaCy models."""

    def test_english_available(self, provider: SpacyNLPProvider) -> None:
        assert provider.is_available(language="en") is True

    def test_german_available(self, provider: SpacyNLPProvider) -> None:
        assert provider.is_available(language="de") is True

    def test_french_available(self, provider: SpacyNLPProvider) -> None:
        assert provider.is_available(language="fr") is True

    def test_unsupported_language_returns_false(self, provider: SpacyNLPProvider) -> None:
        assert provider.is_available(language="es") is False

    def test_made_up_language_returns_false(self, provider: SpacyNLPProvider) -> None:
        assert provider.is_available(language="xx") is False

    def test_previous_load_error_returns_false(self, provider: SpacyNLPProvider) -> None:
        """Simulate a previous load failure — should return False."""
        provider._load_errors.add("en")
        assert provider.is_available(language="en") is False

    def test_cached_model_returns_true(self, provider: SpacyNLPProvider) -> None:
        """After loading, subsequent is_available returns True."""
        assert provider.is_available(language="en") is True  # loads model
        assert provider.is_available(language="en") is True  # uses cache


# ===================================================================
# 3. tokenize
# ===================================================================


class TestTokenize:
    """tokenize() with real spaCy models."""

    @pytest.mark.asyncio
    async def test_plain_english(self, provider: SpacyNLPProvider) -> None:
        result = await provider.tokenize("Hello, world!", language="en")
        assert isinstance(result, TokenResult)
        assert result.language == "en"
        assert len(result.tokens) >= 4

        texts = [t.text for t in result.tokens]
        assert "Hello" in texts
        assert "world" in texts
        assert "," in texts
        assert "!" in texts

        hello_tok = next(t for t in result.tokens if t.text == "Hello")
        assert hello_tok.is_sent_start is True
        assert hello_tok.pos is not None
        assert hello_tok.lemma == "hello"

        world_tok = next(t for t in result.tokens if t.text == "world")
        assert world_tok.pos == "NOUN"
        # Lemma is None when lemma == text (provider filtering rule)
        assert world_tok.lemma is None

    @pytest.mark.asyncio
    async def test_german_tokenization(self, provider: SpacyNLPProvider) -> None:
        result = await provider.tokenize("Guten Morgen, Berlin!", language="de")
        texts = [t.text for t in result.tokens]
        assert "Guten" in texts
        assert "Morgen" in texts
        assert "Berlin" in texts

        guten = next(t for t in result.tokens if t.text == "Guten")
        assert guten.lemma == "gut"
        assert guten.pos == "ADJ"

        berlin = next(t for t in result.tokens if t.text == "Berlin")
        assert berlin.pos == "PROPN"

    @pytest.mark.asyncio
    async def test_french_tokenization(self, provider: SpacyNLPProvider) -> None:
        result = await provider.tokenize("Bonjour, comment allez-vous?", language="fr")
        texts = [t.text for t in result.tokens]
        assert "Bonjour" in texts
        assert "comment" in texts

    @pytest.mark.asyncio
    async def test_empty_text(self, provider: SpacyNLPProvider) -> None:
        result = await provider.tokenize("", language="en")
        assert result.tokens == []
        assert result.language == "en"

    @pytest.mark.asyncio
    async def test_is_sent_start_flags(self, provider: SpacyNLPProvider) -> None:
        result = await provider.tokenize("She walks.", language="en")
        tokens = result.tokens

        she = tokens[0]
        assert she.text == "She"
        assert she.is_sent_start is True

        # Subsequent tokens should not be sentence starts
        for tok in tokens[1:]:
            assert tok.is_sent_start is False


# ===================================================================
# 4. sentence_split
# ===================================================================


class TestSentenceSplit:
    """sentence_split() with real spaCy models."""

    @pytest.mark.asyncio
    async def test_multi_sentence_english(self, provider: SpacyNLPProvider) -> None:
        sentences = await provider.sentence_split("Hello world. How are you?", language="en")
        assert len(sentences) == 2

    @pytest.mark.asyncio
    async def test_single_sentence(self, provider: SpacyNLPProvider) -> None:
        sentences = await provider.sentence_split("This is one sentence.", language="en")
        assert len(sentences) == 1

    @pytest.mark.asyncio
    async def test_german_sentences(self, provider: SpacyNLPProvider) -> None:
        sentences = await provider.sentence_split(
            "Das ist ein Satz. Und noch einer.", language="de"
        )
        assert len(sentences) == 2
        assert "Das ist ein Satz." in sentences[0]

    @pytest.mark.asyncio
    async def test_french_sentences(self, provider: SpacyNLPProvider) -> None:
        sentences = await provider.sentence_split("Bonjour le monde. Comment ça va?", language="fr")
        assert len(sentences) == 2

    @pytest.mark.asyncio
    async def test_empty_text(self, provider: SpacyNLPProvider) -> None:
        sentences = await provider.sentence_split("", language="en")
        assert sentences == []


# ===================================================================
# 5. pos_tag
# ===================================================================


class TestPOSTag:
    """pos_tag() with real spaCy models."""

    @pytest.mark.asyncio
    async def test_english_pos_tags(self, provider: SpacyNLPProvider) -> None:
        tags = await provider.pos_tag("She walks.", language="en")
        assert len(tags) >= 3

        she = next(t for t in tags if t.token == "She")
        assert she.pos == "PRON"
        assert she.lemma == "she"

        walks = next(t for t in tags if t.token == "walks")
        assert walks.pos == "VERB"
        assert walks.lemma == "walk"

    @pytest.mark.asyncio
    async def test_german_pos_tags(self, provider: SpacyNLPProvider) -> None:
        tags = await provider.pos_tag("Der Hund läuft.", language="de")
        # Find tokens by text
        pos_map = {t.token: t.pos for t in tags}
        assert pos_map.get("Der") == "DET"
        assert pos_map.get("Hund") == "NOUN"
        assert pos_map.get("läuft") == "VERB"

    @pytest.mark.asyncio
    async def test_french_pos_tags(self, provider: SpacyNLPProvider) -> None:
        tags = await provider.pos_tag("Le chat dort.", language="fr")
        pos_map = {t.token: t.pos for t in tags}
        assert pos_map.get("Le") == "DET"
        assert pos_map.get("chat") == "NOUN"

    @pytest.mark.asyncio
    async def test_returns_postag_type(self, provider: SpacyNLPProvider) -> None:
        tags = await provider.pos_tag("Hello world.", language="en")
        assert all(isinstance(t, POSTag) for t in tags)


# ===================================================================
# 6. extract_entities
# ===================================================================


class TestExtractEntities:
    """extract_entities() with real spaCy models."""

    @pytest.mark.asyncio
    async def test_english_entities(self, provider: SpacyNLPProvider) -> None:
        text = "Apple is looking at buying U.K. startup for $1 billion"
        entities = await provider.extract_entities(text, language="en")
        entity_map = {e.text: e.label for e in entities}

        assert "Apple" in entity_map
        assert entity_map["Apple"] == "ORG"

        assert "U.K." in entity_map
        assert entity_map["U.K."] == "GPE"

        # Money entity: spaCy may return "$1 billion" or "1 billion"
        money_entities = [e for e in entities if e.label == "MONEY"]
        assert len(money_entities) >= 1

    @pytest.mark.asyncio
    async def test_german_entities(self, provider: SpacyNLPProvider) -> None:
        text = "Angela Merkel besuchte Berlin."
        entities = await provider.extract_entities(text, language="de")
        entity_map = {e.text: e.label for e in entities}

        assert "Angela Merkel" in entity_map
        assert entity_map["Angela Merkel"] == "PER"

        assert "Berlin" in entity_map
        assert entity_map["Berlin"] == "LOC" or entity_map["Berlin"] == "GPE"

    @pytest.mark.asyncio
    async def test_no_entities(self, provider: SpacyNLPProvider) -> None:
        entities = await provider.extract_entities("hello world this has no names", language="en")
        assert entities == []

    @pytest.mark.asyncio
    async def test_returns_entity_type(self, provider: SpacyNLPProvider) -> None:
        entities = await provider.extract_entities("Apple is based in Cupertino.", language="en")
        if entities:  # may or may not find entities in minimal text
            assert all(isinstance(e, Entity) for e in entities)


# ===================================================================
# 7. tokenize_for_sentiment
# ===================================================================


class TestTokenizeForSentiment:
    """tokenize_for_sentiment() — single-pass tokenization + sentence split."""

    @pytest.mark.asyncio
    async def test_returns_tokens_and_sentences(self, provider: SpacyNLPProvider) -> None:
        tokens, sentences = await provider.tokenize_for_sentiment(
            "Hello world. How are you?", language="en"
        )
        assert isinstance(tokens, list)
        assert isinstance(sentences, list)
        assert len(tokens) >= 5
        assert len(sentences) == 2

    @pytest.mark.asyncio
    async def test_equivalent_to_separate_calls(self, provider: SpacyNLPProvider) -> None:
        text = "This is a test. It has two sentences."
        tokens_combined, sentences_combined = await provider.tokenize_for_sentiment(
            text, language="en"
        )
        token_result = await provider.tokenize(text, language="en")
        sentences_separate = await provider.sentence_split(text, language="en")

        assert token_result.tokens == tokens_combined
        assert sentences_separate == sentences_combined

    @pytest.mark.asyncio
    async def test_single_sentence(self, provider: SpacyNLPProvider) -> None:
        tokens, sentences = await provider.tokenize_for_sentiment(
            "Just one sentence.", language="en"
        )
        assert len(sentences) == 1
        assert len(tokens) >= 3

    @pytest.mark.asyncio
    async def test_multi_sentence_german(self, provider: SpacyNLPProvider) -> None:
        tokens, sentences = await provider.tokenize_for_sentiment(
            "Hallo Welt. Wie geht es dir?", language="de"
        )
        assert len(sentences) >= 2
        assert len(tokens) >= 6


# ===================================================================
# 8. count_syllables
# ===================================================================


class TestCountSyllables:
    """count_syllables() — delegates to syllables module."""

    @pytest.mark.asyncio
    async def test_hello_has_two_syllables(self, provider: SpacyNLPProvider) -> None:
        result = await provider.count_syllables("hello", language="en")
        assert result == 2

    @pytest.mark.asyncio
    async def test_cat_has_one_syllable(self, provider: SpacyNLPProvider) -> None:
        result = await provider.count_syllables("cat", language="en")
        assert result == 1

    @pytest.mark.asyncio
    async def test_german_word(self, provider: SpacyNLPProvider) -> None:
        result = await provider.count_syllables("Haus", language="de")
        assert result >= 1

    @pytest.mark.asyncio
    async def test_french_word(self, provider: SpacyNLPProvider) -> None:
        result = await provider.count_syllables("bonjour", language="fr")
        assert result >= 2

    @pytest.mark.asyncio
    async def test_empty_string(self, provider: SpacyNLPProvider) -> None:
        result = await provider.count_syllables("", language="en")
        assert result == 0


# ===================================================================
# 9. _get_model — lazy loading & caching (tested through public API)
# ===================================================================


class TestGetModel:
    """Internal model loading — verified through observable behavior."""

    def test_lazy_loading_populates_cache(self, provider: SpacyNLPProvider) -> None:
        """is_available triggers lazy loading; cache populated afterwards."""
        assert "en" not in provider._models
        available = provider.is_available(language="en")
        assert available is True
        assert "en" in provider._models

    def test_unsupported_language_raises_value_error(self, provider: SpacyNLPProvider) -> None:
        with pytest.raises(ValueError, match="Unsupported language"):
            provider._get_model("xx")

    def test_previous_load_error_raises_nlp_provider_error(
        self, provider: SpacyNLPProvider
    ) -> None:
        provider._load_errors.add("en")
        with pytest.raises(NLPProviderError, match="was not available"):
            provider._get_model("en")

    def test_get_model_caches_on_success(self, provider: SpacyNLPProvider) -> None:
        """First call caches the model; second call returns same object."""
        model1 = provider._get_model("en")  # loads and caches
        model2 = provider._get_model("en")  # returns from cache
        assert model1 is model2  # same cached pipeline object

    def test_get_model_for_german(self, provider: SpacyNLPProvider) -> None:
        """German model can be loaded."""
        model = provider._get_model("de")
        assert model is not None

    def test_get_model_for_french(self, provider: SpacyNLPProvider) -> None:
        """French model can be loaded."""
        model = provider._get_model("fr")
        assert model is not None
