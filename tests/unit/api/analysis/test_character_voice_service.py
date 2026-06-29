"""Behavioural tests for CharacterVoiceService (ANAL-008).

Verifies the ADR-055 pipeline contract:

- The hybrid pipeline runs (DialogueParser → VoiceMetricsAnalyzer →
  CharacterVoiceAgent → merge → KB write) and yields progress + per-character
  result + done events.
- The write-to-KB contract: ``voice_analysis`` is written to
  ``metadata["speech"]["voice_analysis"]``, ``updated_at`` is bumped, and the
  4 human-authored speech fields are preserved (ANAL-008 augments, never
  overwrites).
- Per-character aggregation: each agent entry maps to one result event.
- RULE-11 graceful degradation: no attributed dialogue → empty result set,
  no LLM call.

Error-handling / RULE-11 tests live in ``test_character_voice_service_errors.py``
(RULE-04 split). Mode-1 prompt-path compliance lives in
``test_character_voice_prompt_path_compliance.py``.

See:
    ADR-055 — Character voice storage contract.
    ADR-054 — Mode 1 (composer-driven) prompt resolution.
    CONSTRAINTS.md RULE-02/02a/02b, RULE-11.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare_core.llm.model_config import ResolvedModelConfig
from tests.unit.api.analysis._character_voice_test_helpers import (
    FakeComposer,
    consume,
    make_agent_output,
    make_chapter,
    make_kb_entry,
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
# Happy path: pipeline runs, yields progress + per-character results + done
# ---------------------------------------------------------------------------


class TestHappyPath:
    """The full pipeline runs and streams the correct event sequence."""

    @pytest.mark.asyncio
    async def test_yields_progress_results_then_done(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        novel = make_novel(title="My Epic", genre="Fantasy", writing_language="en")
        chapter = make_chapter(novel_id=novel.id)
        kb_elena = make_kb_entry(name="Elena")
        kb_marc = make_kb_entry(name="Marc")

        kb_repo = AsyncMock()
        kb_repo.get_by_name = AsyncMock(
            side_effect=lambda _nid, name: {"Elena": kb_elena, "Marc": kb_marc}.get(name)
        )
        kb_repo.update = AsyncMock()

        service = make_service(composer, config, kb_repo=kb_repo)
        service._novel_repo.get_by_id = AsyncMock(return_value=novel)  # type: ignore[attr-defined]
        service._chapter_repo.list_by_novel = AsyncMock(return_value=[chapter])  # type: ignore[attr-defined]

        with patch_mode1() as (MockAgent, _MockDeps, _mc):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_agent_output())
            MockAgent.return_value = mock_agent

            events = await consume(service.analyze(novel.id, None, uuid.uuid4()))  # type: ignore[arg-type]

        event_types = [e.event for e in events]
        assert event_types[0] == "progress"
        assert event_types[-1] == "done"
        assert events[-1].is_final is True
        # Two result events (one per character).
        result_events = [e for e in events if e.event == "result"]
        assert len(result_events) == 2
        names = {e.result.character_name for e in result_events}  # type: ignore[union-attr]
        assert names == {"Elena", "Marc"}

    @pytest.mark.asyncio
    async def test_per_character_result_carries_voice_analysis_and_distinctiveness(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        novel = make_novel()
        chapter = make_chapter(novel_id=novel.id)
        kb_repo = AsyncMock()
        kb_repo.get_by_name = AsyncMock(return_value=make_kb_entry(name="Elena"))
        kb_repo.update = AsyncMock()

        service = make_service(composer, config, kb_repo=kb_repo)
        service._novel_repo.get_by_id = AsyncMock(return_value=novel)  # type: ignore[attr-defined]
        service._chapter_repo.list_by_novel = AsyncMock(return_value=[chapter])  # type: ignore[attr-defined]

        with patch_mode1() as (MockAgent, _MockDeps, _mc):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_agent_output())
            MockAgent.return_value = mock_agent

            events = await consume(service.analyze(novel.id, None, uuid.uuid4()))  # type: ignore[arg-type]

        elena_event = next(
            e
            for e in events
            if e.event == "result" and e.result and e.result.character_name == "Elena"
        )
        assert elena_event.result is not None
        assert elena_event.result.voice_analysis is not None
        assert elena_event.result.voice_analysis.formality == 0.7
        assert elena_event.result.voice_analysis.vocabulary_level == "complex"
        # distinctiveness_notes is display-only (not persisted).
        assert elena_event.result.distinctiveness_notes == "More formal than Marc."


# ---------------------------------------------------------------------------
# Write-to-KB contract (ADR-055 Decision 1)
# ---------------------------------------------------------------------------


class TestWriteToKBContract:
    """voice_analysis is written, updated_at bumped, human fields untouched."""

    @pytest.mark.asyncio
    async def test_writes_voice_analysis_to_speech_block(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        novel = make_novel()
        chapter = make_chapter(novel_id=novel.id)
        human_speech = {
            "typical_phrases": ["By the gods"],
            "dialect": "formal court",
            "vocabulary_quirks": "archaisms",
            "body_language": "measured gestures",
        }
        kb_entry = make_kb_entry(
            name="Elena",
            metadata={"speech": dict(human_speech)},
        )

        kb_repo = AsyncMock()
        kb_repo.get_by_name = AsyncMock(return_value=kb_entry)
        kb_repo.update = AsyncMock()

        service = make_service(composer, config, kb_repo=kb_repo)
        service._novel_repo.get_by_id = AsyncMock(return_value=novel)  # type: ignore[attr-defined]
        service._chapter_repo.list_by_novel = AsyncMock(return_value=[chapter])  # type: ignore[attr-defined]

        with patch_mode1() as (MockAgent, _MockDeps, _mc):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_agent_output())
            MockAgent.return_value = mock_agent

            await consume(service.analyze(novel.id, None, uuid.uuid4()))  # type: ignore[arg-type]

        kb_repo.update.assert_awaited()
        update_data = kb_repo.update.call_args.args[1]
        speech = update_data["metadata_"]["speech"]
        assert "voice_analysis" in speech
        # Human-authored fields are preserved (NOT overwritten).
        assert speech["typical_phrases"] == ["By the gods"]
        assert speech["dialect"] == "formal court"
        assert speech["vocabulary_quirks"] == "archaisms"
        assert speech["body_language"] == "measured gestures"

    @pytest.mark.asyncio
    async def test_bumps_updated_at(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        novel = make_novel()
        chapter = make_chapter(novel_id=novel.id)
        kb_entry = make_kb_entry(name="Elena")

        kb_repo = AsyncMock()
        kb_repo.get_by_name = AsyncMock(return_value=kb_entry)
        kb_repo.update = AsyncMock()

        service = make_service(composer, config, kb_repo=kb_repo)
        service._novel_repo.get_by_id = AsyncMock(return_value=novel)  # type: ignore[attr-defined]
        service._chapter_repo.list_by_novel = AsyncMock(return_value=[chapter])  # type: ignore[attr-defined]

        with patch_mode1() as (MockAgent, _MockDeps, _mc):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_agent_output())
            MockAgent.return_value = mock_agent

            await consume(service.analyze(novel.id, None, uuid.uuid4()))  # type: ignore[arg-type]

        update_data = kb_repo.update.call_args.args[1]
        assert "updated_at" in update_data
        assert update_data["updated_at"] is not None

    @pytest.mark.asyncio
    async def test_no_kb_entry_still_surfaces_result(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        """A character with no KB entry is still surfaced (kb_entry_id=None)."""
        novel = make_novel()
        chapter = make_chapter(novel_id=novel.id)

        kb_repo = AsyncMock()
        kb_repo.get_by_name = AsyncMock(return_value=None)
        kb_repo.update = AsyncMock()

        service = make_service(composer, config, kb_repo=kb_repo)
        service._novel_repo.get_by_id = AsyncMock(return_value=novel)  # type: ignore[attr-defined]
        service._chapter_repo.list_by_novel = AsyncMock(return_value=[chapter])  # type: ignore[attr-defined]

        with patch_mode1() as (MockAgent, _MockDeps, _mc):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_agent_output())
            MockAgent.return_value = mock_agent

            events = await consume(service.analyze(novel.id, None, uuid.uuid4()))  # type: ignore[arg-type]

        result_events = [e for e in events if e.event == "result"]
        assert len(result_events) == 2
        assert all(e.result and e.result.kb_entry_id is None for e in result_events)
        kb_repo.update.assert_not_awaited()


# ---------------------------------------------------------------------------
# RULE-11 graceful degradation: no dialogue → empty result, no LLM call
# ---------------------------------------------------------------------------


class TestGracefulDegradation:
    """No attributed dialogue → sensible empty result, no crash, no LLM call."""

    @pytest.mark.asyncio
    async def test_no_dialogue_yields_empty_result_without_agent_call(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        novel = make_novel()
        chapter = make_chapter(novel_id=novel.id, content="The wind howled. No one spoke.")

        kb_repo = AsyncMock()
        service = make_service(composer, config, kb_repo=kb_repo)
        service._novel_repo.get_by_id = AsyncMock(return_value=novel)  # type: ignore[attr-defined]
        service._chapter_repo.list_by_novel = AsyncMock(return_value=[chapter])  # type: ignore[attr-defined]

        with patch_mode1() as (MockAgent, _MockDeps, _mc):
            events = await consume(service.analyze(novel.id, None, uuid.uuid4()))  # type: ignore[arg-type]

            # Agent must NOT be called when there is no dialogue.
            MockAgent.assert_not_called()

        event_types = [e.event for e in events]
        assert "progress" in event_types
        assert event_types[-1] == "done"
        assert events[-1].is_final is True
        assert not any(e.event == "result" for e in events)
