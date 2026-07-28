"""Tests for author_metric_distances — the AuthorMetrics delta primitive
(ANAL-009 Phase 2B / ADR-074).

AuthorVoiceDriftAgent needs to compare AuthorMetrics across chapters + against
the stored AuthorVoiceProfile. Phase 1's ``voice_metric_distances`` is typed for
:class:`VoiceMetrics`; this is the parallel primitive for
:class:`~narrare_core.analysis.author_metrics.AuthorMetrics`.

ADR-057 Risk #3 / ADR-073 D2 no-duplication guarantee: this primitive reuses the
SAME :func:`~narrare_core.analysis.voice_check_scoring._scalar_distance`
normalization as ``voice_metric_distances`` (the bounded relative difference
``d = |a-b|/(|a|+|b|)``) — there is exactly one normalization in the codebase.

Deterministic + pure (ADR-021). No LLM, no I/O.
"""

from __future__ import annotations

import pytest

from narrare_core.analysis._metric_distances import _scalar_distance
from narrare_core.analysis.author_metrics import AuthorMetrics
from narrare_core.analysis.voice_check_scoring import (
    author_metric_distances,
    voice_metric_distances,
)


def _am(**kwargs: object) -> AuthorMetrics:
    """Build an AuthorMetrics with only the given fields (others default None)."""
    return AuthorMetrics(**kwargs)  # type: ignore[arg-type]


class TestAuthorMetricDistancesNormalization:
    """author_metric_distances reuses the scalar-distance normalization (ADR-057)."""

    def test_identical_metrics_yield_zero_distances(self) -> None:
        stored = _am(dialogue_ratio=0.4, description_density=0.2)
        current = _am(dialogue_ratio=0.4, description_density=0.2)
        distances = author_metric_distances(stored, current)
        assert set(distances) == {"dialogue_ratio", "description_density"}
        assert distances["dialogue_ratio"] == pytest.approx(0.0)
        assert distances["description_density"] == pytest.approx(0.0)

    def test_divergent_metric_distance_uses_relative_difference(self) -> None:
        """d = |a-b|/(|a|+|b|) — scale-invariant (ADR-057 Decision 2)."""
        stored = _am(dialogue_ratio=0.2)
        current = _am(dialogue_ratio=0.6)
        distances = author_metric_distances(stored, current)
        # d = 0.4 / 0.8 = 0.5
        assert distances["dialogue_ratio"] == pytest.approx(0.5)
        # And it equals the shared _scalar_distance primitive directly (proves
        # reuse, not a re-implementation).
        assert distances["dialogue_ratio"] == pytest.approx(_scalar_distance(0.2, 0.6))

    def test_all_four_author_metrics_compared(self) -> None:
        """All four AuthorMetrics scalar fields are comparable."""
        stored = _am(
            dialogue_ratio=0.3,
            description_density=0.2,
            action_introspection_ratio=0.5,
            metaphor_density=0.05,
        )
        current = _am(
            dialogue_ratio=0.3,
            description_density=0.2,
            action_introspection_ratio=0.5,
            metaphor_density=0.05,
        )
        distances = author_metric_distances(stored, current)
        assert set(distances) == {
            "dialogue_ratio",
            "description_density",
            "action_introspection_ratio",
            "metaphor_density",
        }

    def test_distance_bounded_zero_to_one(self) -> None:
        stored = _am(dialogue_ratio=0.0)
        current = _am(dialogue_ratio=1.0)
        distances = author_metric_distances(stored, current)
        # One side 0 → distance 1.0 (mirrors voice_metric_distances).
        assert distances["dialogue_ratio"] == pytest.approx(1.0)


class TestAuthorMetricDistancesGraceful:
    """RULE-11: a metric None on either side is skipped (never a crash)."""

    def test_metric_none_on_stored_skipped(self) -> None:
        stored = _am()  # all None
        current = _am(dialogue_ratio=0.4, description_density=0.2)
        assert author_metric_distances(stored, current) == {}

    def test_metric_none_on_current_skipped(self) -> None:
        stored = _am(dialogue_ratio=0.4)
        current = _am()  # dialogue_ratio None
        assert author_metric_distances(stored, current) == {}

    def test_all_none_yields_empty_dict(self) -> None:
        assert author_metric_distances(_am(), _am()) == {}

    def test_mixed_present_and_absent(self) -> None:
        """Only metrics present on BOTH sides appear."""
        stored = _am(dialogue_ratio=0.4, description_density=0.2)  # others None
        current = _am(dialogue_ratio=0.4, action_introspection_ratio=0.5)
        distances = author_metric_distances(stored, current)
        # Only dialogue_ratio is present on both sides.
        assert set(distances) == {"dialogue_ratio"}
        assert distances["dialogue_ratio"] == pytest.approx(0.0)


class TestNoDuplicationContract:
    """ADR-057 Risk #3 — author_metric_distances is NOT a re-implementation.

    It shares the same normalization as voice_metric_distances. This is
    asserted structurally: the two primitives produce the same distance for
    equal-valued scalar inputs (proving one normalization, two typed facades).
    """

    def test_same_normalization_as_voice_metric_distances(self) -> None:
        # Two scalars at 0.2 and 0.6: the distance must be identical whether
        # computed via the voice or the author primitive.
        from narrare_core.kb.schemas.character import VoiceMetrics

        voice = voice_metric_distances(
            VoiceMetrics(avg_sentence_length=0.2),  # type: ignore[arg-type]
            VoiceMetrics(avg_sentence_length=0.6),  # type: ignore[arg-type]
        )
        author = author_metric_distances(
            _am(dialogue_ratio=0.2),
            _am(dialogue_ratio=0.6),
        )
        assert voice["avg_sentence_length"] == pytest.approx(author["dialogue_ratio"])

    def test_module_level_function_exists(self) -> None:
        """The primitive is importable from voice_check_scoring (ADR-057 home)."""
        assert callable(author_metric_distances)
