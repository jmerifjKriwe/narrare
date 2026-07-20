"""Tests for the Backend AdaptiveContextProviderImpl (Phase 2 scaffold).

Phase 2 scope: composes PreferenceProvider + ProfileProvider;
returns default AdaptiveSettings (no persistence); derives simple
style_constraints_text + avoidance_patterns_text from PreferenceProfile.

Phase 3 will add: ProjectSettings.adaptive_settings JSONB persistence,
invocation_evidence.adaptive_* snapshot writes, richer derivation
tuned by Eval.

See: ADR-069 Decision 3, ADR-067 (KBContextProvider pattern),
CONSTRAINTS.md RULE-07/RULE-08/RULE-11.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import pytest

from narrare.adaptive.adaptive_context_provider import (
    AdaptiveContextProviderImpl,
)
from narrare_core.ai_invocation.adaptive_context import (
    AdaptiveContext,
    AdaptiveSettings,
)
from narrare_core.memory.models import PreferenceProfile
from narrare_core.profiles.models import (
    CharacterVoiceProfile,
    ProjectWritingProfile,
)


class FakePreferenceProvider:
    """Async fake PreferenceProvider (mirrors production fake pattern)."""

    def __init__(
        self,
        profile: PreferenceProfile | None = None,
        *,
        raises: Exception | None = None,
    ) -> None:
        self._profile = profile
        self._raises = raises
        self.calls: list[tuple[object, object]] = []

    async def get_preferences(
        self,
        user_id: object,
        project_id: object,
    ) -> PreferenceProfile:
        self.calls.append((user_id, project_id))
        if self._raises is not None:
            raise self._raises
        if self._profile is None:
            return PreferenceProfile(
                user_id=cast("UUID", user_id),
                project_id=cast("UUID", project_id),
                event_count=0,
                confidence=0.0,
                style={},
                content={},
                constraints=[],
                last_updated=datetime.now(UTC),
            )
        return self._profile

    async def reset(self, user_id: object, project_id: object) -> None:
        del user_id, project_id


class FakeProfileProvider:
    """Async fake ProfileProvider (Core Protocol from contracts.py)."""

    def __init__(
        self,
        profile: ProjectWritingProfile | None = None,
        *,
        raises: Exception | None = None,
    ) -> None:
        self._profile = profile
        self._raises = raises
        self.calls: list[object] = []

    async def get_profile(self, project_id: object) -> ProjectWritingProfile | None:
        self.calls.append(project_id)
        if self._raises is not None:
            raise self._raises
        return self._profile


def _make_preference_profile(
    user_id: object,
    project_id: object,
    *,
    style: dict[str, str] | None = None,
    constraints: list[str] | None = None,
) -> PreferenceProfile:
    return PreferenceProfile(
        user_id=cast("UUID", user_id),
        project_id=cast("UUID", project_id),
        event_count=5,
        confidence=0.8,
        style=style if style is not None else {"tone": "prefers dark prose"},
        content={},
        constraints=constraints if constraints is not None else ["avoid passive voice"],
        last_updated=datetime.now(UTC),
    )


def _make_writing_profile() -> ProjectWritingProfile:
    return ProjectWritingProfile(
        writing_language="en",
        genre="Fantasy",
        character_voice_profiles=(
            CharacterVoiceProfile(
                character_id="ch-1",
                name="Alice",
                speech_summary="terse, ironic",
            ),
        ),
    )


class TestProtocolConformance:
    """AdaptiveContextProviderImpl satisfies the Core Protocol."""

    def test_satisfies_protocol(self) -> None:
        impl = AdaptiveContextProviderImpl(
            preference_provider=None,
            profile_provider=None,
        )
        assert hasattr(impl, "get_context")
        assert hasattr(impl, "get_settings")
        assert callable(impl.get_context)
        assert callable(impl.get_settings)


class TestGetSettingsPhase2Scaffold:
    """Phase 2: get_settings returns defaults (no persistence)."""

    @pytest.mark.asyncio
    async def test_returns_default_adaptive_settings(self) -> None:
        impl = AdaptiveContextProviderImpl(
            preference_provider=None,
            profile_provider=None,
        )
        settings = await impl.get_settings(user_id=uuid4(), project_id=uuid4())
        assert isinstance(settings, AdaptiveSettings)
        assert settings.enabled is True
        assert settings.weights.preference == 0.7


class TestGetContextHappyPath:
    """Both providers return data — full AdaptiveContext assembled."""

    @pytest.mark.asyncio
    async def test_assembles_preference_and_voice(self) -> None:
        user_id = uuid4()
        project_id = uuid4()
        impl = AdaptiveContextProviderImpl(
            preference_provider=FakePreferenceProvider(
                _make_preference_profile(user_id, project_id),
            ),
            profile_provider=FakeProfileProvider(_make_writing_profile()),
        )

        ctx = await impl.get_context(user_id=user_id, project_id=project_id)

        assert isinstance(ctx, AdaptiveContext)
        assert ctx.user_id == user_id
        assert ctx.project_id == project_id
        # preference_text comes from PreferenceProfile.to_prompt_text():
        assert "dark prose" in ctx.preference_text.lower() or ctx.preference_text != ""
        # voice_profiles_text comes from formatted_voice_profiles (descriptive only):
        assert "Alice" in ctx.voice_profiles_text
        # ADR-055/057 boundary — no voice_metrics in the result:
        assert not hasattr(ctx, "voice_metrics")
        # Derived fields are non-empty when PreferenceProfile has style/constraints:
        assert ctx.style_constraints_text != ""
        assert ctx.avoidance_patterns_text != ""

    @pytest.mark.asyncio
    async def test_source_summary_mentions_signal_sources(self) -> None:
        user_id = uuid4()
        project_id = uuid4()
        impl = AdaptiveContextProviderImpl(
            preference_provider=FakePreferenceProvider(
                _make_preference_profile(user_id, project_id),
            ),
            profile_provider=FakeProfileProvider(_make_writing_profile()),
        )

        ctx = await impl.get_context(user_id=user_id, project_id=project_id)
        # source_summary is a heuristic human-readable string; it should
        # reference at least one signal source.
        assert ctx.source_summary != ""


class TestGetContextGracefulDegradation:
    """RULE-11: missing data does NOT crash — returns empty fields."""

    @pytest.mark.asyncio
    async def test_no_preference_provider(self) -> None:
        impl = AdaptiveContextProviderImpl(
            preference_provider=None,
            profile_provider=FakeProfileProvider(_make_writing_profile()),
        )
        ctx = await impl.get_context(user_id=uuid4(), project_id=uuid4())
        assert ctx.preference_text == ""
        assert ctx.style_constraints_text == ""
        assert ctx.avoidance_patterns_text == ""
        # Voice profiles still present:
        assert "Alice" in ctx.voice_profiles_text

    @pytest.mark.asyncio
    async def test_no_profile_provider(self) -> None:
        user_id = uuid4()
        project_id = uuid4()
        impl = AdaptiveContextProviderImpl(
            preference_provider=FakePreferenceProvider(
                _make_preference_profile(user_id, project_id),
            ),
            profile_provider=None,
        )
        ctx = await impl.get_context(user_id=user_id, project_id=project_id)
        assert ctx.voice_profiles_text == ""
        # Preferences still present:
        assert ctx.preference_text != ""

    @pytest.mark.asyncio
    async def test_no_providers_at_all(self) -> None:
        impl = AdaptiveContextProviderImpl(
            preference_provider=None,
            profile_provider=None,
        )
        ctx = await impl.get_context(user_id=uuid4(), project_id=uuid4())
        assert ctx.preference_text == ""
        assert ctx.voice_profiles_text == ""
        assert ctx.style_constraints_text == ""
        assert ctx.avoidance_patterns_text == ""
        assert ctx.has_any_signal is False

    @pytest.mark.asyncio
    async def test_preference_provider_raises_returns_empty_preference(self) -> None:
        """RULE-11: provider failure does NOT crash; returns empty fields."""
        impl = AdaptiveContextProviderImpl(
            preference_provider=FakePreferenceProvider(raises=RuntimeError("mem0 down")),
            profile_provider=FakeProfileProvider(_make_writing_profile()),
        )
        ctx = await impl.get_context(user_id=uuid4(), project_id=uuid4())
        # Provider failed — preference-derived fields are empty:
        assert ctx.preference_text == ""
        assert ctx.style_constraints_text == ""
        assert ctx.avoidance_patterns_text == ""
        # Profile provider still succeeded — voice profiles present:
        assert "Alice" in ctx.voice_profiles_text

    @pytest.mark.asyncio
    async def test_profile_provider_raises_returns_empty_voice(self) -> None:
        """RULE-11: profile provider failure does NOT crash."""
        user_id = uuid4()
        project_id = uuid4()
        impl = AdaptiveContextProviderImpl(
            preference_provider=FakePreferenceProvider(
                _make_preference_profile(user_id, project_id),
            ),
            profile_provider=FakeProfileProvider(raises=RuntimeError("DB down")),
        )
        ctx = await impl.get_context(user_id=user_id, project_id=project_id)
        assert ctx.voice_profiles_text == ""
        # Preference provider still succeeded:
        assert ctx.preference_text != ""

    @pytest.mark.asyncio
    async def test_profile_provider_returns_none(self) -> None:
        """ProfileProvider returns None for project without writing profile."""
        user_id = uuid4()
        project_id = uuid4()
        impl = AdaptiveContextProviderImpl(
            preference_provider=FakePreferenceProvider(
                _make_preference_profile(user_id, project_id),
            ),
            profile_provider=FakeProfileProvider(profile=None),
        )
        ctx = await impl.get_context(user_id=user_id, project_id=project_id)
        assert ctx.voice_profiles_text == ""
        assert ctx.preference_text != ""


class TestDerivationHeuristic:
    """Phase 2 derivation: style_constraints from PreferenceProfile.style,
    avoidance_patterns from PreferenceProfile.constraints.

    The exact format is heuristic and tunable in Phase 3 via Eval.
    Phase 2 establishes the contract: non-empty when source data exists.
    """

    @pytest.mark.asyncio
    async def test_style_dict_produces_constraints_text(self) -> None:
        user_id = uuid4()
        project_id = uuid4()
        impl = AdaptiveContextProviderImpl(
            preference_provider=FakePreferenceProvider(
                _make_preference_profile(
                    user_id,
                    project_id,
                    style={"tone": "dark", "pov": "first-person"},
                    constraints=[],
                ),
            ),
            profile_provider=None,
        )
        ctx = await impl.get_context(user_id=user_id, project_id=project_id)
        assert ctx.style_constraints_text != ""
        # Avoidance empty since no constraints:
        assert ctx.avoidance_patterns_text == ""

    @pytest.mark.asyncio
    async def test_constraints_list_produces_avoidance_text(self) -> None:
        user_id = uuid4()
        project_id = uuid4()
        impl = AdaptiveContextProviderImpl(
            preference_provider=FakePreferenceProvider(
                _make_preference_profile(
                    user_id,
                    project_id,
                    style={},
                    constraints=["no passive voice", "no adverbs"],
                ),
            ),
            profile_provider=None,
        )
        ctx = await impl.get_context(user_id=user_id, project_id=project_id)
        assert ctx.avoidance_patterns_text != ""
        # Style empty since no style dict entries:
        assert ctx.style_constraints_text == ""

    @pytest.mark.asyncio
    async def test_empty_preference_profile_produces_empty_derived(self) -> None:
        user_id = uuid4()
        project_id = uuid4()
        impl = AdaptiveContextProviderImpl(
            preference_provider=FakePreferenceProvider(
                _make_preference_profile(
                    user_id,
                    project_id,
                    style={},
                    constraints=[],
                ),
            ),
            profile_provider=None,
        )
        ctx = await impl.get_context(user_id=user_id, project_id=project_id)
        assert ctx.style_constraints_text == ""
        assert ctx.avoidance_patterns_text == ""
