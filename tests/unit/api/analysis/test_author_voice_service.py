"""Behavioural tests for AuthorVoiceService (ANAL-007 / ADR-074).

Verifies the ADR-074 pipeline contract:

- The hybrid pipeline runs (load chapters → VoiceMetricsAnalyzer.analyze_text
  → AuthorMetricsAnalyzer.analyze → AuthorVoiceAgent → assemble profile →
  repository.save) and yields progress + result + done events.
- The write-to-storage contract: the assembled AuthorVoiceProfile is saved
  via AuthorVoiceRepository (no raw column access — ADR-074 binding).
- The assembled profile carries BOTH the descriptive group (from the agent)
  AND the metric group (from the analyzers) — the descriptive/metric boundary
  is enforced at the consumer contract, not the persisted shape.

Pipeline edge cases (profile assembly, min-chapter warning, RULE-11 graceful
degradation) live in ``test_author_voice_service_pipeline.py`` (RULE-04 split).
Error-handling / RULE-11 tests live in ``test_author_voice_service_errors.py``.
Mode-1 prompt-path compliance lives in
``test_author_voice_prompt_path_compliance.py``.

See:
    ADR-074 — Author Voice Storage Contract.
    ADR-054 — Mode 1 (composer-driven) prompt resolution.
    CONSTRAINTS.md RULE-02/02a/02b, RULE-07, RULE-11.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare_core.llm.model_config import ResolvedModelConfig
from narrare_core.profiles.author_voice import AuthorVoiceProfile
from tests.unit.api.analysis._author_voice_test_helpers import (
    FakeAuthorVoiceRepository,
    FakeComposer,
    consume,
    make_agent_output,
    make_chapter,
    make_novel,
    make_service,
    patch_mode1,
)


@pytest.fixture
def composer() -> FakeComposer:
    return FakeComposer()


@pytest.fixture
def config() -> ResolvedModelConfig:
    return ResolvedModelConfig(provider_name="test", model_id="test-model")


# ---------------------------------------------------------------------------
# Happy path: pipeline runs, yields progress + result + done
# ---------------------------------------------------------------------------


class TestHappyPath:
    """The full pipeline runs and streams the correct event sequence."""

    @pytest.mark.asyncio
    async def test_yields_progress_result_then_done(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        novel = make_novel(title="My Epic", genre="Fantasy", writing_language="en")
        chapters = [
            make_chapter(novel_id=novel.id, content=f"Chapter {i} prose. Wind in grass.")
            for i in range(3)
        ]
        repository = FakeAuthorVoiceRepository()

        service = make_service(composer, config, repository=repository)
        service._novel_repo.get_by_id = AsyncMock(return_value=novel)  # type: ignore[attr-defined]
        service._chapter_repo.list_by_novel = AsyncMock(return_value=chapters)  # type: ignore[attr-defined]

        with patch_mode1() as (MockAgent, _MockDeps, _mc):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_agent_output())
            MockAgent.return_value = mock_agent

            events = await consume(service.analyze(novel.id, None, uuid.uuid4()))  # type: ignore[arg-type]

        event_types = [e.event for e in events]
        assert event_types[0] == "progress"
        assert event_types[-1] == "done"
        assert events[-1].is_final is True
        # Exactly one result event (single profile per novel).
        result_events = [e for e in events if e.event == "result"]
        assert len(result_events) == 1

    @pytest.mark.asyncio
    async def test_result_carries_assembled_profile(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        novel = make_novel()
        chapters = [make_chapter(novel_id=novel.id) for _ in range(3)]
        repository = FakeAuthorVoiceRepository()

        service = make_service(composer, config, repository=repository)
        service._novel_repo.get_by_id = AsyncMock(return_value=novel)  # type: ignore[attr-defined]
        service._chapter_repo.list_by_novel = AsyncMock(return_value=chapters)  # type: ignore[attr-defined]

        agent_output = make_agent_output(
            formality=0.8,
            vocabulary_level="complex",
            sentence_profile="long",
            author_examples=["The wind moved through the long grass."],
        )
        with patch_mode1() as (MockAgent, _MockDeps, _mc):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=agent_output)
            MockAgent.return_value = mock_agent

            events = await consume(service.analyze(novel.id, None, uuid.uuid4()))  # type: ignore[arg-type]

        result_event = next(e for e in events if e.event == "result")
        assert result_event.result is not None
        assert result_event.result.profile is not None
        profile: AuthorVoiceProfile = result_event.result.profile
        # Descriptive group from the agent.
        assert profile.voice_analysis is not None
        assert profile.voice_analysis.formality == 0.8
        assert profile.voice_analysis.vocabulary_level == "complex"
        assert profile.voice_analysis.sentence_profile == "long"
        assert profile.author_examples == ["The wind moved through the long grass."]
        # Metric group from the analyzers (non-None because the sample prose
        # is real text the analyzers can tokenise).
        assert profile.voice_analysis.voice_metrics is not None
        assert profile.author_metrics is not None
        # Freshness.
        assert profile.updated_at is not None
        assert profile.is_fresh is True

    @pytest.mark.asyncio
    async def test_result_carries_novel_id(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        novel = make_novel()
        chapters = [make_chapter(novel_id=novel.id) for _ in range(3)]

        service = make_service(composer, config)
        service._novel_repo.get_by_id = AsyncMock(return_value=novel)  # type: ignore[attr-defined]
        service._chapter_repo.list_by_novel = AsyncMock(return_value=chapters)  # type: ignore[attr-defined]

        with patch_mode1() as (MockAgent, _MockDeps, _mc):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_agent_output())
            MockAgent.return_value = mock_agent

            events = await consume(service.analyze(novel.id, None, uuid.uuid4()))  # type: ignore[arg-type]

        result_event = next(e for e in events if e.event == "result")
        assert result_event.result is not None
        assert result_event.result.novel_id == str(novel.id)


# ---------------------------------------------------------------------------
# Write-to-storage contract (ADR-074 binding — repository, no raw column)
# ---------------------------------------------------------------------------


class TestWriteToStorageContract:
    """The assembled profile is saved via the repository (ADR-074 binding)."""

    @pytest.mark.asyncio
    async def test_persists_profile_via_repository(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        novel = make_novel()
        chapters = [make_chapter(novel_id=novel.id) for _ in range(3)]
        repository = FakeAuthorVoiceRepository()

        service = make_service(composer, config, repository=repository)
        service._novel_repo.get_by_id = AsyncMock(return_value=novel)  # type: ignore[attr-defined]
        service._chapter_repo.list_by_novel = AsyncMock(return_value=chapters)  # type: ignore[attr-defined]

        with patch_mode1() as (MockAgent, _MockDeps, _mc):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_agent_output())
            MockAgent.return_value = mock_agent

            await consume(service.analyze(novel.id, None, uuid.uuid4()))  # type: ignore[arg-type]

        # The repository received exactly one save call with the novel_id.
        assert len(repository.save_calls) == 1
        saved_novel_id, saved_profile = repository.save_calls[0]
        assert saved_novel_id == novel.id
        assert isinstance(saved_profile, AuthorVoiceProfile)
        # The persisted profile carries BOTH groups (descriptive + metric).
        assert saved_profile.voice_analysis is not None
        assert saved_profile.voice_analysis.voice_metrics is not None
        assert saved_profile.author_metrics is not None

    @pytest.mark.asyncio
    async def test_repository_save_called_before_done_event(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        """The profile is persisted BEFORE the result event is yielded."""
        novel = make_novel()
        chapters = [make_chapter(novel_id=novel.id) for _ in range(3)]
        repository = FakeAuthorVoiceRepository()

        service = make_service(composer, config, repository=repository)
        service._novel_repo.get_by_id = AsyncMock(return_value=novel)  # type: ignore[attr-defined]
        service._chapter_repo.list_by_novel = AsyncMock(return_value=chapters)  # type: ignore[attr-defined]

        save_call_count_at_result: list[int] = []

        with patch_mode1() as (MockAgent, _MockDeps, _mc):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_agent_output())
            MockAgent.return_value = mock_agent

            async for event in service.analyze(novel.id, None, uuid.uuid4()):  # type: ignore[arg-type]
                if event.event == "result":
                    save_call_count_at_result.append(len(repository.save_calls))

        # By the time the result event fires, the save has already happened.
        assert save_call_count_at_result == [1]
