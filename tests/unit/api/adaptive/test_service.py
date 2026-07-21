"""Tests for AdaptiveContextService (RULE-03 contract conformance).

The service delegates to AdaptiveContextProvider (read path) +
AdaptiveSettingsRepository (persistence). Fakes isolate the service from
all I/O.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from narrare.adaptive.schemas import (
    AdaptiveWeightsInput,
)
from narrare.adaptive.service import AdaptiveContextService
from narrare_core.ai_invocation.adaptive_context import (
    AdaptiveContext,
    AdaptiveSettings,
)


class FakeAdaptiveProvider:
    """Async fake AdaptiveContextProvider (Phase 1 Protocol shape)."""

    def __init__(
        self,
        context: AdaptiveContext | None = None,
        settings: AdaptiveSettings | None = None,
    ) -> None:
        self._context = context
        self._settings = settings
        self.context_calls: list[tuple[object, object]] = []
        self.settings_calls: list[tuple[object, object]] = []

    async def get_context(self, user_id: object, project_id: object) -> AdaptiveContext:
        self.context_calls.append((user_id, project_id))
        return self._context or AdaptiveContext(
            user_id=user_id,  # type: ignore[arg-type]
            project_id=project_id,  # type: ignore[arg-type]
        )

    async def get_settings(self, user_id: object, project_id: object) -> AdaptiveSettings:
        self.settings_calls.append((user_id, project_id))
        return self._settings or AdaptiveSettings()


class FakeAdaptiveRepo:
    """Async fake AdaptiveSettingsRepository."""

    def __init__(self, loaded: AdaptiveSettings | None = None) -> None:
        self._loaded = loaded
        self.saved: list[tuple[object, AdaptiveSettings]] = []

    async def load(self, project_id: object) -> AdaptiveSettings | None:
        del project_id
        return self._loaded

    async def save(self, project_id: object, settings: AdaptiveSettings) -> None:
        self.saved.append((project_id, settings))


def _full_context(user_id: object, project_id: object) -> AdaptiveContext:
    return AdaptiveContext(
        user_id=user_id,  # type: ignore[arg-type]
        project_id=project_id,  # type: ignore[arg-type]
        preference_text="prefers dark prose",
        voice_profiles_text="**Alice**: terse",
        style_constraints_text="- Short sentences",
        avoidance_patterns_text="- No passive voice",
        source_summary="preferences, voice profiles",
    )


class TestGetContext:
    """get_context() delegates to provider + maps to response schema."""

    @pytest.mark.asyncio
    async def test_returns_response_with_signals(self) -> None:
        user_id = uuid4()
        project_id = uuid4()
        provider = FakeAdaptiveProvider(
            context=_full_context(user_id, project_id),
            settings=AdaptiveSettings(enabled=True),
        )
        repo = FakeAdaptiveRepo()
        service = AdaptiveContextService(provider=provider, settings_repo=repo)

        response = await service.get_context(project_id=project_id, user_id=user_id)

        assert response.enabled is True
        assert response.has_any_signal is True
        assert "dark prose" in response.sources.preference_text
        assert "**Alice**" in response.sources.voice_profiles_text

    @pytest.mark.asyncio
    async def test_returns_response_with_no_signals(self) -> None:
        user_id = uuid4()
        project_id = uuid4()
        provider = FakeAdaptiveProvider(
            context=AdaptiveContext(user_id=user_id, project_id=project_id),
            settings=AdaptiveSettings(),
        )
        repo = FakeAdaptiveRepo()
        service = AdaptiveContextService(provider=provider, settings_repo=repo)

        response = await service.get_context(project_id=project_id, user_id=user_id)

        assert response.has_any_signal is False
        assert response.sources.preference_text == ""


class TestSetEnabled:
    """set_enabled() persists the toggle."""

    @pytest.mark.asyncio
    async def test_persists_enabled_false(self) -> None:
        provider = FakeAdaptiveProvider()
        repo = FakeAdaptiveRepo()
        service = AdaptiveContextService(provider=provider, settings_repo=repo)

        response = await service.set_enabled(project_id=uuid4(), user_id=uuid4(), enabled=False)

        assert response.enabled is False
        assert len(repo.saved) == 1
        assert repo.saved[0][1].enabled is False

    @pytest.mark.asyncio
    async def test_persists_enabled_true(self) -> None:
        provider = FakeAdaptiveProvider()
        repo = FakeAdaptiveRepo()
        service = AdaptiveContextService(provider=provider, settings_repo=repo)

        response = await service.set_enabled(project_id=uuid4(), user_id=uuid4(), enabled=True)

        assert response.enabled is True
        assert repo.saved[0][1].enabled is True


class TestSetWeights:
    """set_weights() clamps + persists."""

    @pytest.mark.asyncio
    async def test_clamps_out_of_range_weights(self) -> None:
        provider = FakeAdaptiveProvider()
        repo = FakeAdaptiveRepo()
        service = AdaptiveContextService(provider=provider, settings_repo=repo)

        response = await service.set_weights(
            project_id=uuid4(),
            user_id=uuid4(),
            weights=AdaptiveWeightsInput(preference=-0.5, voice_fidelity=2.0),
        )

        assert response.weights.preference == 0.0
        assert response.weights.voice_fidelity == 1.0
        assert repo.saved[0][1].weights.preference == 0.0
        assert repo.saved[0][1].weights.voice_fidelity == 1.0

    @pytest.mark.asyncio
    async def test_preserves_in_range_weights(self) -> None:
        provider = FakeAdaptiveProvider()
        repo = FakeAdaptiveRepo()
        service = AdaptiveContextService(provider=provider, settings_repo=repo)

        response = await service.set_weights(
            project_id=uuid4(),
            user_id=uuid4(),
            weights=AdaptiveWeightsInput(preference=0.42, voice_fidelity=0.81),
        )

        assert response.weights.preference == 0.42
        assert response.weights.voice_fidelity == 0.81
