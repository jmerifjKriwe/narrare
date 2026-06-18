"""Unit tests for profiles/contracts.py — Voice Profile SSOT contracts.

Covers (ADR-040 §1 + ADR-050 P1-C — CR-AUFG-04-09):
1. ``VoiceProfileProvider`` — structural Protocol compatibility
2. ``VoiceProfileConsumer`` — structural Protocol compatibility
   (both projections: assemble_for_generation, assemble_for_checking)
3. Provider/consumer binding — same provider instance per invocation
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from narrare_core.profiles.contracts import VoiceProfileConsumer, VoiceProfileProvider
from narrare_core.profiles.models import CharacterVoiceProfile, ProjectWritingProfile

# =====================================================================
# Fake implementations
# =====================================================================


def _make_voice(name: str = "Alice", is_fresh: bool = True) -> CharacterVoiceProfile:
    return CharacterVoiceProfile(
        character_id=f"char-{name.lower()}",
        name=name,
        speech_summary=f"{name}: dialect: Southern; confident tone",
        updated_at="2026-06-01" if is_fresh else "2026-01-01",
        is_fresh=is_fresh,
    )


class FakeVoiceProvider:
    """Fake satisfying VoiceProfileProvider structurally."""

    def __init__(self, voices: list[CharacterVoiceProfile] | None = None) -> None:
        self._voices = voices or []
        self.calls: list[tuple[UUID, int]] = []

    async def get_character_voices(
        self,
        project_id: UUID,
        *,
        max_age_days: int = 30,
    ) -> list[CharacterVoiceProfile]:
        self.calls.append((project_id, max_age_days))
        return list(self._voices)


class FakeVoiceConsumer:
    """Fake satisfying VoiceProfileConsumer structurally.

    Bound to a single provider instance — generation and checking
    share the same data per invocation (ADR-050 P1-C contract).
    """

    def __init__(self, provider: VoiceProfileProvider) -> None:
        self._provider = provider

    @property
    def provider(self) -> VoiceProfileProvider:
        return self._provider

    async def assemble_for_generation(
        self,
        project_id: UUID,
        *,
        max_age_days: int = 30,
    ) -> ProjectWritingProfile:
        voices = await self._provider.get_character_voices(project_id, max_age_days=max_age_days)
        warnings = tuple(f"Stale: {v.name}" for v in voices if not v.is_fresh)
        return ProjectWritingProfile(
            character_voice_profiles=tuple(voices),
            freshness_warnings=warnings,
        )

    async def assemble_for_checking(
        self,
        project_id: UUID,
        *,
        max_age_days: int = 30,
    ) -> list[CharacterVoiceProfile]:
        return await self._provider.get_character_voices(project_id, max_age_days=max_age_days)


# =====================================================================
# VoiceProfileProvider — structural Protocol compatibility
# =====================================================================


class TestVoiceProfileProviderProtocol:
    """VoiceProfileProvider is a @runtime_checkable structural Protocol."""

    def test_fake_provider_satisfies_protocol(self) -> None:
        provider = FakeVoiceProvider()
        assert isinstance(provider, VoiceProfileProvider)

    def test_plain_object_does_not_satisfy(self) -> None:
        assert not isinstance(object(), VoiceProfileProvider)

    @pytest.mark.asyncio
    async def test_get_character_voices_returns_list(self) -> None:
        voices = [_make_voice("Alice"), _make_voice("Bob")]
        provider = FakeVoiceProvider(voices=voices)
        result = await provider.get_character_voices(uuid4())
        assert len(result) == 2
        assert all(isinstance(v, CharacterVoiceProfile) for v in result)

    @pytest.mark.asyncio
    async def test_get_character_voices_empty_when_no_voices(self) -> None:
        provider = FakeVoiceProvider()
        result = await provider.get_character_voices(uuid4())
        assert result == []

    @pytest.mark.asyncio
    async def test_max_age_days_is_honoured(self) -> None:
        """Provider MUST honour max_age_days (freshness contract)."""
        provider = FakeVoiceProvider()
        await provider.get_character_voices(uuid4(), max_age_days=7)
        assert provider.calls[0][1] == 7


# =====================================================================
# VoiceProfileConsumer — structural Protocol compatibility
# =====================================================================


class TestVoiceProfileConsumerProtocol:
    """VoiceProfileConsumer is a @runtime_checkable structural Protocol."""

    def test_fake_consumer_satisfies_protocol(self) -> None:
        provider = FakeVoiceProvider()
        consumer = FakeVoiceConsumer(provider=provider)
        assert isinstance(consumer, VoiceProfileConsumer)

    def test_plain_object_does_not_satisfy(self) -> None:
        assert not isinstance(object(), VoiceProfileConsumer)

    def test_provider_property_returns_bound_provider(self) -> None:
        """Consumer MUST expose the bound provider instance."""
        provider = FakeVoiceProvider()
        consumer = FakeVoiceConsumer(provider=provider)
        assert consumer.provider is provider

    @pytest.mark.asyncio
    async def test_assemble_for_generation_returns_project_profile(self) -> None:
        voices = [_make_voice("Alice"), _make_voice("Bob")]
        provider = FakeVoiceProvider(voices=voices)
        consumer = FakeVoiceConsumer(provider=provider)
        result = await consumer.assemble_for_generation(uuid4())
        assert isinstance(result, ProjectWritingProfile)
        assert len(result.character_voice_profiles) == 2

    @pytest.mark.asyncio
    async def test_assemble_for_checking_returns_structured_profiles(self) -> None:
        """Checking projection returns raw structured profiles, not text."""
        voices = [_make_voice("Alice")]
        provider = FakeVoiceProvider(voices=voices)
        consumer = FakeVoiceConsumer(provider=provider)
        result = await consumer.assemble_for_checking(uuid4())
        assert isinstance(result, list)
        assert all(isinstance(v, CharacterVoiceProfile) for v in result)

    @pytest.mark.asyncio
    async def test_generation_and_checking_share_same_provider(self) -> None:
        """ADR-050 P1-C: both projections use the SAME provider instance."""
        voices = [_make_voice("Alice")]
        provider = FakeVoiceProvider(voices=voices)
        consumer = FakeVoiceConsumer(provider=provider)
        pid = uuid4()
        gen_result = await consumer.assemble_for_generation(pid)
        check_result = await consumer.assemble_for_checking(pid)
        # Same voice data observed by both projections
        gen_names = {v.name for v in gen_result.character_voice_profiles}
        check_names = {v.name for v in check_result}
        assert gen_names == check_names == {"Alice"}

    @pytest.mark.asyncio
    async def test_stale_profiles_surface_in_freshness_warnings(self) -> None:
        """RULE-11: stale profiles MUST NOT be silently dropped."""
        voices = [_make_voice("Alice", is_fresh=False), _make_voice("Bob", is_fresh=True)]
        provider = FakeVoiceProvider(voices=voices)
        consumer = FakeVoiceConsumer(provider=provider)
        result = await consumer.assemble_for_generation(uuid4())
        # Stale profile is still present (not silently dropped)
        assert len(result.character_voice_profiles) == 2
        # But a freshness warning is surfaced
        assert any("Stale" in w for w in result.freshness_warnings)

    @pytest.mark.asyncio
    async def test_checking_includes_stale_profiles(self) -> None:
        """Checking MUST include stale profiles so drift can be detected."""
        voices = [_make_voice("Alice", is_fresh=False)]
        provider = FakeVoiceProvider(voices=voices)
        consumer = FakeVoiceConsumer(provider=provider)
        result = await consumer.assemble_for_checking(uuid4())
        assert len(result) == 1
        assert result[0].is_fresh is False
