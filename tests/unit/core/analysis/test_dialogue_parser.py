"""Tests for DialogueParser — deterministic dialogue attribution (ANAL-008).

Covers:
- Tagged attribution after a quote (``"Hi," said Elena``) → speaker, high conf.
- Tagged attribution before a quote (``Elena replied, "Hi."``) → high conf.
- Action-beat attribution (``Elena turned. "No."``) → medium conf.
- Em-dash attribution (``"Go—" Elena said.``) → medium conf.
- Untagged quotes → speaker ``None``, low confidence.
- Edge cases: no dialogue, empty/malformed prose, nested quotes, ordering.
- Determinism + purity (same input → identical output, no I/O).

RULE-11: the parser never raises on malformed prose. No real LLM (RULE-01b).
"""

from __future__ import annotations

import pytest

from narrare_core.analysis.dialogue_parser import DialogueParser
from narrare_core.analysis.voice_types import AttributedUtterance

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def parser() -> DialogueParser:
    return DialogueParser()


# ---------------------------------------------------------------------------
# A. Tagged attribution
# ---------------------------------------------------------------------------


class TestTagAttribution:
    """Speech-verb tags produce high-confidence attribution."""

    def test_tag_after_quote_attributes_speaker(self, parser: DialogueParser) -> None:
        text = '"Hello there," said Elena.'
        utterances = parser.parse(text)
        assert len(utterances) == 1
        u = utterances[0]
        assert u.speaker == "Elena"
        assert u.text == "Hello there,"
        assert u.confidence >= 0.8

    def test_tag_before_quote_attributes_speaker(self, parser: DialogueParser) -> None:
        text = 'Elena replied, "I am here."'
        utterances = parser.parse(text)
        assert len(utterances) == 1
        assert utterances[0].speaker == "Elena"
        assert utterances[0].confidence >= 0.8

    def test_multi_word_speaker_name(self, parser: DialogueParser) -> None:
        text = '"Indeed," said Mary Jane.'
        utterances = parser.parse(text)
        assert utterances[0].speaker == "Mary Jane"

    def test_various_speech_verbs(self, parser: DialogueParser) -> None:
        for verb in ("asked", "whispered", "shouted", "answered"):
            text = f'"No," {verb} Tom.'
            utterances = parser.parse(text)
            assert utterances[0].speaker == "Tom", f"failed for verb {verb!r}"


# ---------------------------------------------------------------------------
# B. Action-beat + em-dash attribution (medium confidence)
# ---------------------------------------------------------------------------


class TestActionBeatAttribution:
    """Action beats / em-dashes attribute at medium confidence."""

    def test_action_beat_before_quote(self, parser: DialogueParser) -> None:
        text = 'Elena turned away. "I told you so."'
        utterances = parser.parse(text)
        assert len(utterances) == 1
        assert utterances[0].speaker == "Elena"
        medium = utterances[0].confidence
        assert 0.4 <= medium < 0.8

    def test_emdash_after_quote(self, parser: DialogueParser) -> None:
        # Em-dash + name with NO speech verb → medium confidence.
        text = '"No." — Elena turned away.'
        utterances = parser.parse(text)
        assert len(utterances) == 1
        assert utterances[0].speaker == "Elena"
        assert 0.4 <= utterances[0].confidence < 0.8

    def test_tagged_confidence_above_untagged(self, parser: DialogueParser) -> None:
        tagged = parser.parse('"Hi," said Elena.')
        untagged = parser.parse('"Hi."')
        assert tagged[0].confidence > untagged[0].confidence


# ---------------------------------------------------------------------------
# C. Untagged quotes → speaker None, low confidence
# ---------------------------------------------------------------------------


class TestUntaggedQuotes:
    """Quotes without attribution resolve to speaker None (left for the agent)."""

    def test_untagged_quote_speaker_none(self, parser: DialogueParser) -> None:
        utterances = parser.parse('"Where are we going?"')
        assert len(utterances) == 1
        assert utterances[0].speaker is None
        assert utterances[0].confidence < 0.5

    def test_untagged_quote_low_confidence(self, parser: DialogueParser) -> None:
        utterances = parser.parse('"Hmm."')
        assert utterances[0].confidence <= 0.3


# ---------------------------------------------------------------------------
# D. Edge cases + determinism (RULE-11)
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """No dialogue / empty / malformed prose never raise (RULE-11)."""

    def test_no_dialogue_returns_empty(self, parser: DialogueParser) -> None:
        assert parser.parse("Just narration. No quotes here.") == []

    def test_empty_string_returns_empty(self, parser: DialogueParser) -> None:
        assert parser.parse("") == []

    def test_malformed_prose_does_not_raise(self, parser: DialogueParser) -> None:
        # Unbalanced quote + stray punctuation must not crash.
        result = parser.parse('"""...,,,   ')
        assert isinstance(result, list)

    def test_nested_single_quotes_inside_double(self, parser: DialogueParser) -> None:
        # The outer double quote is one utterance; inner single quotes do not
        # produce a separate (overlapping) utterance.
        utterances = parser.parse("He wrote, \"She said 'no' and left.\"")
        assert len(utterances) == 1
        assert utterances[0].text == "She said 'no' and left."


class TestOrderingAndOffsets:
    """Utterances preserve source order and carry valid offsets."""

    def test_multiple_quotes_preserve_order(self, parser: DialogueParser) -> None:
        text = '"First," said Anna. "Second," said Bob.'
        utterances = parser.parse(text)
        assert [u.speaker for u in utterances] == ["Anna", "Bob"]

    def test_offsets_are_valid(self, parser: DialogueParser) -> None:
        text = '"Hi," said Elena.'
        utterances = parser.parse(text)
        u = utterances[0]
        assert u.start < u.end
        assert text[u.start : u.end].startswith('"')

    def test_deterministic_same_input_same_output(self, parser: DialogueParser) -> None:
        text = '"One," said Anna. "Two," said Bob.'
        first = parser.parse(text)
        second = parser.parse(text)
        assert first == second


class TestReturnType:
    """parse returns AttributedUtterance instances with bounded confidence."""

    def test_returns_attributed_utterances(self, parser: DialogueParser) -> None:
        for u in parser.parse('"Hi," said Elena.'):
            assert isinstance(u, AttributedUtterance)

    def test_confidence_within_bounds(self, parser: DialogueParser) -> None:
        text = '"Hi," said Elena. "Bye." "Later," said Bob.'
        for u in parser.parse(text):
            assert 0.0 <= u.confidence <= 1.0
