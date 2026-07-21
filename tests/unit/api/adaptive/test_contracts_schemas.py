"""Tests for adaptive domain Protocol + Pydantic schemas (RULE-03).

Phase 3 Task 3: contracts and schemas land BEFORE the service (Task 4) and
router (Task 5). The Protocol is runtime-checkable; schemas validate input
clamping and graceful defaults.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from narrare.adaptive.contracts import AdaptiveContextServiceProtocol
from narrare.adaptive.schemas import (
    AdaptiveContextResponse,
    AdaptiveSettingsResponse,
    AdaptiveSourceSummary,
    AdaptiveToggleInput,
    AdaptiveWeightsInput,
    AdaptiveWeightsResponse,
)


class FakeAdaptiveService:
    """Complete AdaptiveContextServiceProtocol implementation for tests."""

    async def get_context(
        self,
        project_id: object,
        user_id: object,
    ) -> AdaptiveContextResponse:
        return AdaptiveContextResponse(
            project_id=str(project_id),
            enabled=True,
            weights=AdaptiveWeightsResponse(),
            sources=AdaptiveSourceSummary(),
            has_any_signal=False,
        )

    async def set_enabled(
        self,
        project_id: object,
        user_id: object,
        enabled: bool,
    ) -> AdaptiveSettingsResponse:
        return AdaptiveSettingsResponse(enabled=enabled)

    async def set_weights(
        self,
        project_id: object,
        user_id: object,
        weights: AdaptiveWeightsInput,
    ) -> AdaptiveSettingsResponse:
        clamped = weights.validated()
        return AdaptiveSettingsResponse(
            enabled=True,
            weights=AdaptiveWeightsResponse(
                preference=clamped.preference,
                voice_fidelity=clamped.voice_fidelity,
                style_constraints=clamped.style_constraints,
                avoidance=clamped.avoidance,
            ),
        )


class TestAdaptiveContextServiceProtocol:
    """Protocol conformance."""

    def test_fake_satisfies_protocol(self) -> None:
        fake = FakeAdaptiveService()
        assert isinstance(fake, AdaptiveContextServiceProtocol)

    def test_incomplete_does_not_satisfy(self) -> None:
        class OnlyGetContext:
            async def get_context(
                self, project_id: object, user_id: object
            ) -> AdaptiveContextResponse: ...

        assert not isinstance(OnlyGetContext(), AdaptiveContextServiceProtocol)


class TestAdaptiveWeightsInput:
    """AdaptiveWeightsInput validates + clamps."""

    def test_defaults(self) -> None:
        w = AdaptiveWeightsInput()
        assert w.preference == 0.7
        assert w.voice_fidelity == 0.9
        assert w.style_constraints == 1.0
        assert w.avoidance == 1.0

    def test_validated_clamps_out_of_range(self) -> None:
        w = AdaptiveWeightsInput(preference=-0.5, voice_fidelity=2.0)
        clamped = w.validated()
        assert clamped.preference == 0.0
        assert clamped.voice_fidelity == 1.0

    def test_validated_preserves_in_range(self) -> None:
        w = AdaptiveWeightsInput(preference=0.42)
        clamped = w.validated()
        assert clamped.preference == 0.42


class TestAdaptiveContextResponse:
    """AdaptiveContextResponse schema."""

    def test_minimal_construction(self) -> None:
        r = AdaptiveContextResponse(
            project_id=str(uuid4()),
            enabled=True,
            weights=AdaptiveWeightsResponse(),
            sources=AdaptiveSourceSummary(),
            has_any_signal=False,
        )
        assert r.has_any_signal is False
        assert r.sources.preference_text == ""

    def test_with_signals(self) -> None:
        r = AdaptiveContextResponse(
            project_id=str(uuid4()),
            enabled=True,
            weights=AdaptiveWeightsResponse(),
            sources=AdaptiveSourceSummary(
                preference_text="prefers dark prose",
                voice_profiles_text="**Alice**: terse",
            ),
            has_any_signal=True,
        )
        assert r.has_any_signal is True
        assert "dark prose" in r.sources.preference_text


class TestAdaptiveToggleInput:
    """AdaptiveToggleInput body schema."""

    def test_enabled_true(self) -> None:
        body = AdaptiveToggleInput(enabled=True)
        assert body.enabled is True

    def test_enabled_false(self) -> None:
        body = AdaptiveToggleInput(enabled=False)
        assert body.enabled is False

    def test_field_is_required(self) -> None:
        with pytest.raises(ValueError):
            AdaptiveToggleInput()  # type: ignore[call-arg]
