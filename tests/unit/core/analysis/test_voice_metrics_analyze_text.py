"""VoiceMetricsAnalyzer.analyze_text — prose-level entry point (ANAL-007 / ADR-074).

Verifies the new public ``analyze_text`` method on
:class:`~narrare_core.analysis.voice_metrics.VoiceMetricsAnalyzer`. It runs the
SAME ``_compute_metrics`` pipeline as :meth:`analyze` but over the author's
full chapter prose (narrator + dialogue together) rather than per-speaker
attributed utterances. Deterministic (ADR-021). The result is a single
:class:`~narrare_core.schemas.voice.VoiceMetrics` block, not a per-speaker dict.

Binding differences (ANAL-007 spec):
    - :meth:`analyze` is for **character voice** — per-utterance dialogue
      grouped by speaker (returns ``dict[str, VoiceMetrics]``).
    - :meth:`analyze_text` is for **author voice** — prose-level, single
      narrator voice over full chapter text (returns ``VoiceMetrics``).

Both call the same ``_compute_metrics`` (zero measurement-logic duplication).
``verbal_tic_frequency`` is ``None`` for author voice (verbal tics are a
per-character concept, not a narrator concept).

See:
    - ``docs/features/analysis/ANAL-007-voice-author.md``
      "Architecture: prose-level measurement" subsection.
    - ``docs/architecture/decisions/ADR-074-author-voice-storage.md``.
    - ADR-021 (determinism), RULE-11 (graceful degradation).
"""

from __future__ import annotations

from narrare_core.analysis.voice_metrics import VoiceMetricsAnalyzer
from narrare_core.schemas.voice import VoiceMetrics

# Sample prose with narrator + quoted dialogue together (the author-voice input
# shape). Includes distinctive punctuation (em-dash, ellipsis), varied sentence
# lengths, and contractions so every VoiceMetrics field gets exercised.
_CHAPTER_PROSE = [
    (
        "The wind shook the shutters. Elena crossed the room—her hands were "
        'steady, her breath was not. "I don\'t know what you mean," she said, '
        "watching the door. Outside, the dogs were howling... someone was coming."
    ),
    (
        'Marc laughed. "You\'re impossible." He turned away from her, '
        'studying the darkened window. "But I won\'t leave." The firelight '
        "flickered across his face; he did not blink."
    ),
]


class TestAnalyzeTextExists:
    """analyze_text is a new public entry point on VoiceMetricsAnalyzer."""

    def test_analyze_text_is_callable_public_method(self) -> None:
        analyzer = VoiceMetricsAnalyzer()
        assert callable(getattr(analyzer, "analyze_text", None)), (
            "VoiceMetricsAnalyzer must expose a public analyze_text method "
            "(ANAL-007 / ADR-074 prose-level entry point)."
        )


class TestAnalyzeTextReturnsSingleVoiceMetrics:
    """Author voice is ONE narrator voice → a single block, not a per-speaker dict."""

    def test_returns_voice_metrics_not_dict(self) -> None:
        analyzer = VoiceMetricsAnalyzer()
        result = analyzer.analyze_text(_CHAPTER_PROSE)
        assert isinstance(result, VoiceMetrics), (
            "analyze_text must return a single VoiceMetrics (author voice = one "
            f"narrator), got {type(result).__name__}."
        )


class TestAnalyzeTextReusesComputeMetrics:
    """The same _compute_metrics pipeline feeds both entry points (zero duplication).

    A prose-level run over a single chapter's text must produce metrics identical
    to a per-speaker run that has grouped just that chapter under one speaker.
    """

    def test_prose_level_matches_single_speaker_group(self) -> None:
        from narrare_core.analysis.voice_types import AttributedUtterance

        analyzer = VoiceMetricsAnalyzer()
        prose_result = analyzer.analyze_text(_CHAPTER_PROSE)

        # Treat the same chapter strings as a single speaker's "utterances" so
        # analyze() runs _compute_metrics on the exact same input list.
        utterances = [AttributedUtterance(text=t, speaker="narrator") for t in _CHAPTER_PROSE]
        grouped = analyzer.analyze(utterances)
        narrator_result = grouped["narrator"]

        # Every metric computed by _compute_metrics must match exactly.
        assert prose_result.avg_sentence_length == narrator_result.avg_sentence_length
        assert prose_result.sentence_length_std == narrator_result.sentence_length_std
        assert prose_result.type_token_ratio == narrator_result.type_token_ratio
        assert prose_result.avg_syllables_per_word == narrator_result.avg_syllables_per_word
        assert prose_result.contraction_rate == narrator_result.contraction_rate
        assert prose_result.punctuation_profile == narrator_result.punctuation_profile
        # verbal_tic_frequency differs by design (see TestVerbalTicFrequencyIsNone).


class TestVerbalTicFrequencyIsNone:
    """Verbal tics are a per-character concept; not computed for the narrator."""

    def test_verbal_tic_frequency_none_without_candidates(self) -> None:
        analyzer = VoiceMetricsAnalyzer()
        result = analyzer.analyze_text(_CHAPTER_PROSE)
        assert result.verbal_tic_frequency is None, (
            "analyze_text must NOT compute verbal_tic_frequency — verbal tics are "
            "a per-character concept, not a narrator concept (ANAL-007 spec)."
        )


class TestAnalyzeTextPopulatesMetrics:
    """Prose with contractions + em-dashes + ellipsis + varied sentences yields
    populated metrics (the pipeline is not silently returning defaults)."""

    def test_metrics_populated_for_realistic_prose(self) -> None:
        analyzer = VoiceMetricsAnalyzer()
        result = analyzer.analyze_text(_CHAPTER_PROSE)
        assert result.avg_sentence_length is not None and result.avg_sentence_length > 0
        assert result.type_token_ratio is not None and 0.0 < result.type_token_ratio <= 1.0
        assert result.contraction_rate is not None and result.contraction_rate > 0.0, (
            "Prose contains 'don't' / 'You're' / 'won't' → contraction_rate > 0."
        )
        assert result.punctuation_profile is not None
        # Em-dash + ellipsis are present in the sample → their rates must be > 0.
        assert result.punctuation_profile.get("em_dash", 0.0) > 0.0
        assert result.punctuation_profile.get("ellipsis", 0.0) > 0.0


class TestAnalyzeTextGracefulEmpty:
    """RULE-11: empty / all-blank input → all-None VoiceMetrics (never raises)."""

    def test_empty_list_returns_all_none_metrics(self) -> None:
        analyzer = VoiceMetricsAnalyzer()
        result = analyzer.analyze_text([])
        assert isinstance(result, VoiceMetrics)
        assert result.avg_sentence_length is None
        assert result.type_token_ratio is None

    def test_all_blank_strings_returns_all_none_metrics(self) -> None:
        analyzer = VoiceMetricsAnalyzer()
        result = analyzer.analyze_text(["", "   ", "\n\t"])
        assert result.avg_sentence_length is None

    def test_does_not_raise_on_empty_input(self) -> None:
        analyzer = VoiceMetricsAnalyzer()
        # Must not raise.
        analyzer.analyze_text([])


class TestAnalyzeTextDeterministic:
    """ADR-021: identical input → identical output (across runs)."""

    def test_repeated_calls_produce_identical_result(self) -> None:
        analyzer = VoiceMetricsAnalyzer()
        first = analyzer.analyze_text(_CHAPTER_PROSE)
        second = analyzer.analyze_text(_CHAPTER_PROSE)
        assert first.model_dump() == second.model_dump()


class TestAnalyzeTextDoesNotChangeAnalyzeBehaviour:
    """The new prose-level entry point is ADDITIVE — analyze() must be unchanged."""

    def test_analyze_still_returns_dict_keyed_by_speaker(self) -> None:
        from narrare_core.analysis.voice_types import AttributedUtterance

        analyzer = VoiceMetricsAnalyzer()
        utterances = [
            AttributedUtterance(text='"Hello," she said.', speaker="Elena"),
            AttributedUtterance(text='"Hi," he said.', speaker="Marc"),
        ]
        result = analyzer.analyze(utterances)
        # analyze() STILL returns a per-speaker dict (regression guard).
        assert isinstance(result, dict)
        assert set(result.keys()) == {"Elena", "Marc"}
        assert all(isinstance(v, VoiceMetrics) for v in result.values())
