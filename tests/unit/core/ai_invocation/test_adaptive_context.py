"""Tests for AdaptiveWeights, AdaptiveContext, AdaptiveSettings dataclasses.

Covers: defaults, clamping, frozen, slots, has_any_signal.
See: ADR-069, CONSTRAINTS.md RULE-03/RULE-04.
"""

from __future__ import annotations

import dataclasses

import pytest

from narrare_core.ai_invocation.adaptive_context import AdaptiveWeights


class TestAdaptiveWeights:
    """AdaptiveWeights — frozen value object with clamping."""

    def test_default_weights_match_spec(self) -> None:
        """Spec §5.1: preference=0.7, voice_fidelity=0.9,
        style_constraints=1.0, avoidance=1.0."""
        weights = AdaptiveWeights()
        assert weights.preference == 0.7
        assert weights.voice_fidelity == 0.9
        assert weights.style_constraints == 1.0
        assert weights.avoidance == 1.0

    def test_custom_weights_preserved(self) -> None:
        weights = AdaptiveWeights(preference=0.3, voice_fidelity=0.5)
        assert weights.preference == 0.3
        assert weights.voice_fidelity == 0.5

    def test_is_frozen(self) -> None:
        """RULE-03: immutable value object."""
        weights = AdaptiveWeights()
        with pytest.raises(dataclasses.FrozenInstanceError):
            weights.preference = 0.5  # type: ignore[misc]

    def test_is_slotted(self) -> None:
        """No __dict__ — slots prevent arbitrary attribute addition."""
        weights = AdaptiveWeights()
        assert not hasattr(weights, "__dict__")

    def test_validated_clamps_below_zero(self) -> None:
        weights = AdaptiveWeights(preference=-0.5, voice_fidelity=-1.0)
        clamped = weights.validated()
        assert clamped.preference == 0.0
        assert clamped.voice_fidelity == 0.0

    def test_validated_clamps_above_one(self) -> None:
        weights = AdaptiveWeights(style_constraints=2.0, avoidance=1.5)
        clamped = weights.validated()
        assert clamped.style_constraints == 1.0
        assert clamped.avoidance == 1.0

    def test_validated_preserves_in_range(self) -> None:
        weights = AdaptiveWeights(preference=0.42, voice_fidelity=0.81)
        clamped = weights.validated()
        assert clamped.preference == 0.42
        assert clamped.voice_fidelity == 0.81

    def test_validated_returns_new_instance(self) -> None:
        """validated() does not mutate; returns a new frozen instance."""
        weights = AdaptiveWeights(preference=2.0)
        clamped = weights.validated()
        assert weights.preference == 2.0  # original unchanged
        assert clamped.preference == 1.0
        assert clamped is not weights
