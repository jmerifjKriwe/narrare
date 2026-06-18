"""Tests for ProfileAssembler.

Covers:
1. No provider configured → minimal profile
2. Provider returning voices → full profile
3. Empty voices from provider
4. Stale voices → freshness warnings
5. Fresh voices → no warnings
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from narrare_core.profiles.assembly import ProfileAssembler
from narrare_core.profiles.models import CharacterVoiceProfile, ProjectWritingProfile

# ---------------------------------------------------------------------------
# Fake provider
# ---------------------------------------------------------------------------


class FakeVoiceProfileProvider:
    """In-memory fake for VoiceProfileProvider protocol."""

    def __init__(self, voices: list[CharacterVoiceProfile] | None = None) -> None:
        self._voices = voices or []
        self.calls: list[object] = []

    async def get_character_voices(
        self,
        project_id: UUID,
        *,
        max_age_days: int = 30,
    ) -> list[CharacterVoiceProfile]:
        del max_age_days
        self.calls.append(project_id)
        return list(self._voices)


# ---------------------------------------------------------------------------
# Tests: No provider
# ---------------------------------------------------------------------------


class TestProfileAssemblerNoProvider:
    """ProfileAssembler without a provider returns minimal profile."""

    @pytest.mark.asyncio
    async def test_returns_minimal_profile(self) -> None:
        assembler = ProfileAssembler(provider=None)
        profile = await assembler.assemble(project_id=uuid4())
        assert isinstance(profile, ProjectWritingProfile)
        assert profile.writing_language == "en"
        assert profile.character_voice_profiles == ()
        assert profile.freshness_warnings == ()

    @pytest.mark.asyncio
    async def test_passes_through_settings(self) -> None:
        assembler = ProfileAssembler(provider=None)
        profile = await assembler.assemble(
            project_id=uuid4(),
            writing_language="de",
            genre="fantasy",
            tone="dark",
            style_profile="literary",
        )
        assert profile.writing_language == "de"
        assert profile.genre == "fantasy"
        assert profile.tone == "dark"
        assert profile.style_profile == "literary"

    @pytest.mark.asyncio
    async def test_no_voice_profiles(self) -> None:
        assembler = ProfileAssembler(provider=None)
        profile = await assembler.assemble(project_id=uuid4())
        assert profile.has_voice_profiles is False
        assert profile.formatted_voice_profiles == ""


# ---------------------------------------------------------------------------
# Tests: With provider
# ---------------------------------------------------------------------------


class TestProfileAssemblerWithProvider:
    """ProfileAssembler with a provider delegates correctly."""

    @pytest.mark.asyncio
    async def test_delegates_to_provider(self) -> None:
        provider = FakeVoiceProfileProvider()
        assembler = ProfileAssembler(provider=provider)
        project_id = uuid4()
        await assembler.assemble(project_id=project_id)
        assert provider.calls == [project_id]

    @pytest.mark.asyncio
    async def test_empty_voices_returns_no_profiles(self) -> None:
        provider = FakeVoiceProfileProvider(voices=[])
        assembler = ProfileAssembler(provider=provider)
        profile = await assembler.assemble(project_id=uuid4())
        assert profile.has_voice_profiles is False
        assert profile.formatted_voice_profiles == ""

    @pytest.mark.asyncio
    async def test_fresh_voices_no_warnings(self) -> None:
        voices = [
            CharacterVoiceProfile("c1", "Alice", "dialect: Southern"),
            CharacterVoiceProfile("c2", "Bob", "dialect: Northern"),
        ]
        provider = FakeVoiceProfileProvider(voices=voices)
        assembler = ProfileAssembler(provider=provider)
        profile = await assembler.assemble(project_id=uuid4())
        assert profile.has_voice_profiles is True
        assert len(profile.character_voice_profiles) == 2
        assert profile.freshness_warnings == ()

    @pytest.mark.asyncio
    async def test_stale_voices_produce_warnings(self) -> None:
        voices = [
            CharacterVoiceProfile(
                "c1",
                "Alice",
                "dialect: Southern",
                updated_at="2025-01-01T00:00:00+00:00",
                is_fresh=False,
            ),
        ]
        provider = FakeVoiceProfileProvider(voices=voices)
        assembler = ProfileAssembler(provider=provider)
        profile = await assembler.assemble(project_id=uuid4(), max_age_days=30)
        assert len(profile.freshness_warnings) == 1
        assert "Voice profile for 'Alice'" in profile.freshness_warnings[0]

    @pytest.mark.asyncio
    async def test_stale_without_updated_at_no_warning(self) -> None:
        """Stale voice with no updated_at → no warning (graceful)."""
        voices = [
            CharacterVoiceProfile(
                "c1",
                "Alice",
                "dialect: Southern",
                updated_at=None,
                is_fresh=False,
            ),
        ]
        provider = FakeVoiceProfileProvider(voices=voices)
        assembler = ProfileAssembler(provider=provider)
        profile = await assembler.assemble(project_id=uuid4(), max_age_days=30)
        assert profile.freshness_warnings == ()

    @pytest.mark.asyncio
    async def test_mixed_freshness(self) -> None:
        voices = [
            CharacterVoiceProfile("c1", "Alice", "dialect: Southern"),
            CharacterVoiceProfile(
                "c2",
                "Bob",
                "dialect: Northern",
                updated_at="2025-01-01T00:00:00+00:00",
                is_fresh=False,
            ),
        ]
        provider = FakeVoiceProfileProvider(voices=voices)
        assembler = ProfileAssembler(provider=provider)
        profile = await assembler.assemble(project_id=uuid4())
        assert len(profile.character_voice_profiles) == 2
        assert len(profile.freshness_warnings) == 1
        assert "Bob" in profile.freshness_warnings[0]

    @pytest.mark.asyncio
    async def test_settings_combined_with_voices(self) -> None:
        voices = [CharacterVoiceProfile("c1", "Alice", "dialect: Southern")]
        provider = FakeVoiceProfileProvider(voices=voices)
        assembler = ProfileAssembler(provider=provider)
        profile = await assembler.assemble(
            project_id=uuid4(),
            writing_language="fr",
            genre="mystery",
            tone="suspenseful",
        )
        assert profile.writing_language == "fr"
        assert profile.genre == "mystery"
        assert profile.tone == "suspenseful"
        assert profile.has_voice_profiles is True
