"""Unit tests for SeriesVoiceService (Spec 3 — Series Voice Hierarchy, Task 2).

Fake-based per ADR-030: the series/novel/chapter repositories are the shared
in-memory fakes; the LLM seam (``AuthorVoiceAgent``) is patched via
``patch_author_voice_pipeline`` (the service reuses the existing agent). The
deterministic metric analyzers run on real sample prose (mirrors the
novel-level author-voice tests).

Verifies the Spec 3 contract:
- ``profile_from_novel`` runs the reused ADR-074 pipeline and stores the result
  as ``SeriesSettings.author_voice`` (NOT ``ProjectSettings.author_voice``).
- Ownership + novel-membership anti-enumeration (both → 403).
- RULE-11 graceful degradation: no chapters → ValidationError.
- get / update_override / clear_override on the single column.
"""

from __future__ import annotations

import uuid

import pytest

from narrare_core.profiles.author_voice import AuthorVoiceProfile
from narrare_core.series.schemas import Series
from narrare_core.shared.errors import ForbiddenError, ValidationError
from tests.factories import make_chapter, make_novel

from ._series_voice_test_helpers import (
    SAMPLE_PROSE,
    make_agent_output,
    make_service,
    patch_author_voice_pipeline,
)


def _seed_owned_series(
    series_repo: object, novel_repo: object, chapter_repo: object, *, user_id: uuid.UUID
) -> tuple[uuid.UUID, uuid.UUID]:
    """Seed an owned series + one member novel with 3 chapters of prose.

    Returns ``(series_id, novel_id)``.
    """
    series_id = uuid.uuid4()
    novel_id = uuid.uuid4()
    series_repo.seed(  # type: ignore[attr-defined]
        Series(id=series_id, user_id=user_id, title="The Expanse", writing_language="en")
    )
    novel_repo.seed(  # type: ignore[attr-defined]
        make_novel(id=novel_id, user_id=user_id, series_id=series_id, title="Leviathan Wakes")
    )
    chapter_repo.seed(  # type: ignore[attr-defined]
        *[make_chapter(novel_id=novel_id, content=SAMPLE_PROSE) for _ in range(3)]
    )
    return series_id, novel_id


# ---------------------------------------------------------------------------
# profile_from_novel()
# ---------------------------------------------------------------------------


class TestProfileFromNovel:
    """SeriesVoiceService.profile_from_novel() — happy path + error paths."""

    @pytest.mark.asyncio
    async def test_profiles_and_stores_as_series_author_voice(self) -> None:
        """Happy path: runs agent → stores profile in SeriesSettings.author_voice."""
        user_id = uuid.uuid4()
        service, series_repo, novel_repo, chapter_repo = make_service()
        series_id, novel_id = _seed_owned_series(
            series_repo, novel_repo, chapter_repo, user_id=user_id
        )

        with patch_author_voice_pipeline():
            profile = await service.profile_from_novel(series_id, novel_id, user_id)

        # The returned profile is a full AuthorVoiceProfile (descriptive + metrics).
        assert isinstance(profile, AuthorVoiceProfile)
        assert profile.voice_analysis is not None
        assert profile.author_metrics is not None

        # Storage contract: persisted to SeriesSettings.author_voice (NOT the
        # novel-level ProjectSettings column — the Spec 3 storage target).
        settings = await series_repo.get_settings(series_id)
        assert settings is not None
        assert settings.author_voice is not None
        voice_analysis = settings.author_voice["voice_analysis"]
        assert isinstance(voice_analysis, dict)
        assert voice_analysis["vocabulary_level"] == "complex"

    @pytest.mark.asyncio
    async def test_series_not_owned_raises_forbidden(self) -> None:
        """Anti-enumeration: a not-owned series surfaces as 403 (never 404)."""
        service, series_repo, _novel_repo, _chapter_repo = make_service()
        owner = uuid.uuid4()
        series_repo.seed(Series(id=uuid.uuid4(), user_id=owner, title="Not yours"))

        with (
            patch_author_voice_pipeline(),
            pytest.raises(ForbiddenError),
        ):
            await service.profile_from_novel(uuid.uuid4(), uuid.uuid4(), uuid.uuid4())

    @pytest.mark.asyncio
    async def test_novel_not_in_series_raises_forbidden(self) -> None:
        """A novel not belonging to the series surfaces as 403 (anti-enumeration)."""
        user_id = uuid.uuid4()
        service, series_repo, novel_repo, chapter_repo = make_service()
        series_id, _ = _seed_owned_series(series_repo, novel_repo, chapter_repo, user_id=user_id)
        # A novel owned by the user but NOT in this series.
        other_novel_id = uuid.uuid4()
        novel_repo.seed(make_novel(id=other_novel_id, user_id=user_id, series_id=uuid.uuid4()))

        with (
            patch_author_voice_pipeline(),
            pytest.raises(ForbiddenError),
        ):
            await service.profile_from_novel(series_id, other_novel_id, user_id)

    @pytest.mark.asyncio
    async def test_no_chapters_raises_validation_error(self) -> None:
        """RULE-11: a novel with no chapters cannot be profiled (fail fast)."""
        user_id = uuid.uuid4()
        service, series_repo, novel_repo, chapter_repo = make_service()
        series_id, novel_id = _seed_owned_series(
            series_repo, novel_repo, chapter_repo, user_id=user_id
        )
        # Remove all chapters.
        chapter_repo._store.clear()  # type: ignore[attr-defined]

        with (
            patch_author_voice_pipeline(),
            pytest.raises(ValidationError, match="no chapters"),
        ):
            await service.profile_from_novel(series_id, novel_id, user_id)

    @pytest.mark.asyncio
    async def test_reuses_existing_author_voice_agent(self) -> None:
        """The same Core AuthorVoiceAgent is instantiated (no new agent)."""
        user_id = uuid.uuid4()
        service, series_repo, novel_repo, chapter_repo = make_service()
        series_id, novel_id = _seed_owned_series(
            series_repo, novel_repo, chapter_repo, user_id=user_id
        )

        with patch_author_voice_pipeline() as MockAgent:
            await service.profile_from_novel(series_id, novel_id, user_id)
            # Exactly one agent constructed + one .run() call (one LLM call).
            assert MockAgent.call_count == 1
            assert MockAgent.return_value.run.await_count == 1


# ---------------------------------------------------------------------------
# get()
# ---------------------------------------------------------------------------


class TestGet:
    """SeriesVoiceService.get() — load current profile."""

    @pytest.mark.asyncio
    async def test_returns_none_when_no_profile(self) -> None:
        user_id = uuid.uuid4()
        service, series_repo, _novel_repo, _chapter_repo = make_service()
        series_id = uuid.uuid4()
        series_repo.seed(Series(id=series_id, user_id=user_id, title="Empty"))

        result = await service.get(series_id, user_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_stored_profile(self) -> None:
        user_id = uuid.uuid4()
        service, series_repo, _novel_repo, _chapter_repo = make_service()
        series_id = uuid.uuid4()
        series_repo.seed(Series(id=series_id, user_id=user_id, title="Has voice"))
        # Seed a profile directly via the repo.
        profile = make_agent_output()
        from narrare.analysis.author_voice_profile_assembler import (
            assemble_author_voice_profile,
        )
        from narrare_core.analysis.author_metrics import AuthorMetricsAnalyzer
        from narrare_core.analysis.voice_metrics import VoiceMetricsAnalyzer

        vm = VoiceMetricsAnalyzer(language="en").analyze_text([SAMPLE_PROSE])
        am = AuthorMetricsAnalyzer().analyze([SAMPLE_PROSE])
        assembled = assemble_author_voice_profile(
            descriptive=profile, voice_metrics=vm, author_metrics=am
        )
        await series_repo.update_settings(
            series_id, {"author_voice": assembled.model_dump(mode="json")}
        )

        result = await service.get(series_id, user_id)

        assert result is not None
        assert result.voice_analysis is not None
        assert result.voice_analysis.vocabulary_level == "complex"

    @pytest.mark.asyncio
    async def test_get_not_owned_raises_forbidden(self) -> None:
        service, series_repo, _novel_repo, _chapter_repo = make_service()
        series_repo.seed(Series(id=uuid.uuid4(), user_id=uuid.uuid4(), title="Not yours"))

        with pytest.raises(ForbiddenError):
            await service.get(uuid.uuid4(), uuid.uuid4())


# ---------------------------------------------------------------------------
# update_override() / clear_override()
# ---------------------------------------------------------------------------


class TestOverride:
    """SeriesVoiceService.update_override() / clear_override()."""

    @pytest.mark.asyncio
    async def test_update_override_stores_validated_profile(self) -> None:
        user_id = uuid.uuid4()
        service, series_repo, _novel_repo, _chapter_repo = make_service()
        series_id = uuid.uuid4()
        series_repo.seed(Series(id=series_id, user_id=user_id, title="Override target"))
        # A valid AuthorVoiceProfile dict.
        override_dict: dict[str, object] = {
            "voice_analysis": {
                "formality": 0.7,
                "vocabulary_level": "accessible",
                "voice_metrics": None,
            },
            "author_examples": ["A curated sentence."],
        }

        result = await service.update_override(series_id, user_id, override_dict)

        assert isinstance(result, AuthorVoiceProfile)
        assert result.voice_analysis is not None
        assert result.voice_analysis.vocabulary_level == "accessible"
        settings = await series_repo.get_settings(series_id)
        assert settings is not None
        assert settings.author_voice is not None

    @pytest.mark.asyncio
    async def test_update_override_invalid_dict_raises_validation(self) -> None:
        user_id = uuid.uuid4()
        service, series_repo, _novel_repo, _chapter_repo = make_service()
        series_id = uuid.uuid4()
        series_repo.seed(Series(id=series_id, user_id=user_id, title="Override target"))

        with pytest.raises(ValidationError, match="valid author-voice profile"):
            # A dict that cannot validate as AuthorVoiceProfile (wrong types).
            await service.update_override(series_id, user_id, {"voice_analysis": "not-a-dict"})

    @pytest.mark.asyncio
    async def test_clear_override_nulls_author_voice(self) -> None:
        user_id = uuid.uuid4()
        service, series_repo, _novel_repo, _chapter_repo = make_service()
        series_id = uuid.uuid4()
        series_repo.seed(Series(id=series_id, user_id=user_id, title="Clear target"))
        # Start with a profile present.
        await series_repo.update_settings(
            series_id, {"author_voice": {"voice_analysis": {"formality": 0.5}}}
        )

        await service.clear_override(series_id, user_id)

        settings = await series_repo.get_settings(series_id)
        assert settings is not None
        assert settings.author_voice is None

    @pytest.mark.asyncio
    async def test_clear_override_not_owned_raises_forbidden(self) -> None:
        service, series_repo, _novel_repo, _chapter_repo = make_service()
        series_repo.seed(Series(id=uuid.uuid4(), user_id=uuid.uuid4(), title="Not yours"))

        with pytest.raises(ForbiddenError):
            await service.clear_override(uuid.uuid4(), uuid.uuid4())
