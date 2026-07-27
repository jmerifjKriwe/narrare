"""AuthorMetrics + AuthorMetricsAnalyzer — deterministic prose-level metrics
(ANAL-007 / ADR-074).

Author-voice-specific prose-level metrics have no character-voice analogue, so
a new deterministic analyzer computes them. The analyzer is **pure** and
**deterministic** (ADR-021). All metrics are nullable + provisional; the set
is eval-tunable via ADR-032.

The descriptive/metric boundary (ADR-055/057/074) is preserved: AuthorMetrics
NEVER reach generation. They are comparison-only (ANAL-009 Phase 2 drift).

This test suite covers:
    - The :class:`AuthorMetrics` Pydantic model contract.
    - The :class:`AuthorMetricsAnalyzer.analyze` prose-level computation,
      metric-by-metric (dialogue_ratio, description_density,
      action_introspection_ratio, metaphor_density).
    - RULE-11 graceful degradation (empty input → all-None).
    - ADR-021 determinism (identical input → identical output).

See:
    - ``docs/features/analysis/ANAL-007-voice-author.md``
      "Architecture: prose-level measurement" + the metaphor_density decision.
    - ADR-074 (storage contract — AuthorMetrics shape).
    - ADR-021 (determinism).
"""

from __future__ import annotations

import pytest

from narrare_core.analysis.author_metrics import (
    AuthorMetrics,
    AuthorMetricsAnalyzer,
)

# ---------------------------------------------------------------------------
# Sample prose fixtures
# ---------------------------------------------------------------------------

#: Dialogue-heavy prose: ~half the words sit inside quotes.
_DIALOGUE_HEAVY = [
    (
        '"I told you not to come," Elena said. "You never listen to me." '
        'Marc replied, "And I told you I would. We are here now."'
    )
]

#: Narration-only prose (no quotes at all).
_DIALOGUE_FREE = [
    (
        "The wind moved through the long grass. Somewhere a bird was singing. "
        "Elena walked toward the river, her hands deep in her pockets."
    )
]

#: Modifier-heavy prose: many adjective / adverb suffix tokens.
_DESCRIPTION_DENSE = [
    (
        "The beautiful, luminous sky glowed softly above the quiet valley. "
        "Small bright birds sang sweetly; restless leaves whispered endlessly. "
        "A cold mysterious fog drifted slowly across the darkened fields."
    )
]

#: Modifier-sparse prose: mostly nouns and verbs.
_DESCRIPTION_SPARSE = [
    (
        "Sky. Valley. Birds. Fog. Leaves moved. Water ran over rocks. "
        "She walked home. He ate. They waited. The sun set."
    )
]

#: Simile / figurative-cue heavy prose (many "like a", "as a", "as if").
_METAPHOR_DENSE = [
    (
        "Her voice was like a knife, cold as a winter river. "
        "He moved as if wounded, his gaze like iron. "
        "The town lay silent, as still as a photograph."
    )
]

#: Simile-free prose (no figurative cues).
_METAPHOR_FREE = [
    ("Her voice was sharp. He moved carefully. The town lay silent. Birds sang in the trees.")
]

#: Introspection-heavy prose: many thought / reflection markers.
_INTROSPECTION_HEAVY = [
    (
        "She wondered why he had left. Perhaps he had never loved her, she "
        "thought. She felt alone. She remembered the summer, reflecting on "
        "what might have been. Inside, she knew the truth."
    )
]

#: Action-heavy prose: many motion / verb cues, no introspection markers.
_ACTION_HEAVY = [
    (
        "She ran across the field, leapt the fence, and grabbed the rope. "
        "He dodged, struck, and pivoted. They charged, climbed, and jumped. "
        "Footsteps pounded; doors slammed; glass shattered."
    )
]


# ---------------------------------------------------------------------------
# AuthorMetrics Pydantic model
# ---------------------------------------------------------------------------


class TestAuthorMetricsModel:
    """The AuthorMetrics data contract (ADR-074 data shape)."""

    def test_default_construction_has_all_none_fields(self) -> None:
        metrics = AuthorMetrics()
        assert metrics.dialogue_ratio is None
        assert metrics.description_density is None
        assert metrics.action_introspection_ratio is None
        assert metrics.metaphor_density is None

    def test_accepts_float_values(self) -> None:
        metrics = AuthorMetrics(
            dialogue_ratio=0.42,
            description_density=0.17,
            action_introspection_ratio=0.55,
            metaphor_density=0.03,
        )
        assert metrics.dialogue_ratio == pytest.approx(0.42)

    def test_extra_allow(self) -> None:
        """extra='allow' so the metric block can grow without a migration (ADR-074)."""
        metrics = AuthorMetrics(dialogue_ratio=0.1, future_metric=0.5)  # type: ignore[call-arg]
        assert metrics.model_dump()["future_metric"] == 0.5  # type: ignore[operator]

    def test_field_set_is_exactly_the_spec_contract(self) -> None:
        """The four author-specific prose-level metrics per the spec."""
        expected = {
            "dialogue_ratio",
            "description_density",
            "action_introspection_ratio",
            "metaphor_density",
        }
        assert set(AuthorMetrics.model_fields.keys()) >= expected


# ---------------------------------------------------------------------------
# AuthorMetricsAnalyzer — public surface + graceful degradation
# ---------------------------------------------------------------------------


class TestAnalyzePublicSurface:
    def test_analyze_returns_author_metrics(self) -> None:
        analyzer = AuthorMetricsAnalyzer()
        result = analyzer.analyze(_DIALOGUE_FREE)
        assert isinstance(result, AuthorMetrics)

    def test_analyze_empty_list_returns_all_none(self) -> None:
        """RULE-11: empty input → all-None metrics, never raises."""
        analyzer = AuthorMetricsAnalyzer()
        result = analyzer.analyze([])
        assert isinstance(result, AuthorMetrics)
        assert result.dialogue_ratio is None
        assert result.description_density is None
        assert result.action_introspection_ratio is None
        assert result.metaphor_density is None

    def test_analyze_all_blank_returns_all_none(self) -> None:
        analyzer = AuthorMetricsAnalyzer()
        result = analyzer.analyze(["", "   ", "\n\t"])
        assert result.dialogue_ratio is None


# ---------------------------------------------------------------------------
# dialogue_ratio — quoted-dialogue word count / total word count
# ---------------------------------------------------------------------------


class TestDialogueRatio:
    """Quoted-dialogue word count / total word count (DialogueParser quote spans)."""

    def test_dialogue_heavy_prose_has_nonzero_ratio(self) -> None:
        analyzer = AuthorMetricsAnalyzer()
        result = analyzer.analyze(_DIALOGUE_HEAVY)
        assert result.dialogue_ratio is not None
        assert 0.0 < result.dialogue_ratio <= 1.0

    def test_dialogue_free_prose_has_zero_ratio(self) -> None:
        analyzer = AuthorMetricsAnalyzer()
        result = analyzer.analyze(_DIALOGUE_FREE)
        assert result.dialogue_ratio is not None
        assert result.dialogue_ratio == 0.0

    def test_dialogue_ratio_is_bounded_in_unit_interval(self) -> None:
        analyzer = AuthorMetricsAnalyzer()
        result = analyzer.analyze(_DIALOGUE_HEAVY + _DIALOGUE_FREE)
        assert result.dialogue_ratio is not None
        assert 0.0 <= result.dialogue_ratio <= 1.0


# ---------------------------------------------------------------------------
# description_density — modifier (adj/adv) density proxy
# ---------------------------------------------------------------------------


class TestDescriptionDensity:
    """Modifier-density proxy: (adj + adv token count) / total token count."""

    def test_dense_prose_higher_than_sparse_prose(self) -> None:
        analyzer = AuthorMetricsAnalyzer()
        dense = analyzer.analyze(_DESCRIPTION_DENSE).description_density
        sparse = analyzer.analyze(_DESCRIPTION_SPARSE).description_density
        assert dense is not None and sparse is not None
        assert dense > sparse, (
            "Modifier-heavy prose must yield higher description_density than "
            f"modifier-sparse prose (dense={dense}, sparse={sparse})."
        )

    def test_description_density_bounded_in_unit_interval(self) -> None:
        analyzer = AuthorMetricsAnalyzer()
        result = analyzer.analyze(_DESCRIPTION_DENSE)
        assert result.description_density is not None
        assert 0.0 <= result.description_density <= 1.0


# ---------------------------------------------------------------------------
# action_introspection_ratio — 0.0 action-heavy → 1.0 introspection-heavy
# ---------------------------------------------------------------------------


class TestActionIntrospectionRatio:
    """Verb/action density vs internal-thought-marker density proxy.

    0.0 = action-heavy, 1.0 = introspection-heavy.
    """

    def test_introspection_heavy_scores_higher_than_action_heavy(self) -> None:
        analyzer = AuthorMetricsAnalyzer()
        introspection = analyzer.analyze(_INTROSPECTION_HEAVY).action_introspection_ratio
        action = analyzer.analyze(_ACTION_HEAVY).action_introspection_ratio
        assert introspection is not None and action is not None
        assert introspection > action, (
            "Introspection-heavy prose must score higher on "
            f"action_introspection_ratio than action-heavy prose "
            f"(introspection={introspection}, action={action})."
        )

    def test_ratio_bounded_in_unit_interval(self) -> None:
        analyzer = AuthorMetricsAnalyzer()
        for prose in (_INTROSPECTION_HEAVY, _ACTION_HEAVY):
            ratio = analyzer.analyze(prose).action_introspection_ratio
            assert ratio is not None
            assert 0.0 <= ratio <= 1.0


# ---------------------------------------------------------------------------
# metaphor_density — simile/figurative-cue proxy (PROVISIONAL)
# ---------------------------------------------------------------------------


class TestMetaphorDensity:
    """Simile/figurative-cue density proxy (deliberately crude, ADR-021)."""

    def test_metaphor_dense_prose_higher_than_free_prose(self) -> None:
        analyzer = AuthorMetricsAnalyzer()
        dense = analyzer.analyze(_METAPHOR_DENSE).metaphor_density
        free = analyzer.analyze(_METAPHOR_FREE).metaphor_density
        assert dense is not None and free is not None
        assert dense > free, (
            "Simile-cue-rich prose must score higher on metaphor_density than "
            f"simile-free prose (dense={dense}, free={free})."
        )

    def test_metaphor_density_bounded_in_unit_interval(self) -> None:
        analyzer = AuthorMetricsAnalyzer()
        result = analyzer.analyze(_METAPHOR_DENSE)
        assert result.metaphor_density is not None
        assert 0.0 <= result.metaphor_density <= 1.0


# ---------------------------------------------------------------------------
# Determinism (ADR-021)
# ---------------------------------------------------------------------------


class TestDeterminism:
    """Identical input → identical output (across runs, ADR-021)."""

    def test_repeated_calls_produce_identical_result(self) -> None:
        analyzer = AuthorMetricsAnalyzer()
        prose = _DIALOGUE_HEAVY + _DESCRIPTION_DENSE + _METAPHOR_DENSE
        first = analyzer.analyze(prose).model_dump()
        second = analyzer.analyze(prose).model_dump()
        assert first == second

    def test_two_instances_produce_identical_result(self) -> None:
        prose = _INTROSPECTION_HEAVY + _ACTION_HEAVY
        first = AuthorMetricsAnalyzer().analyze(prose).model_dump()
        second = AuthorMetricsAnalyzer().analyze(prose).model_dump()
        assert first == second
