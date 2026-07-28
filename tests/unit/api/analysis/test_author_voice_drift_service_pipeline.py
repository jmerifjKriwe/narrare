"""RULE-11 graceful-path tests for AuthorVoiceDriftService (ANAL-009 Phase 2B / ADR-074).

Split from ``test_author_voice_drift_service.py`` for RULE-04 compliance
(test file < 300 lines). Covers the graceful-degradation edge cases the
happy-path file does not:

- No stored profile -> no_profile (no_stored_profile), no agent call.
- Profile present but missing metric blocks -> no_profile (no_profile_metrics).
- No chapters at all -> progress + done, no agent call.
- Profile + metrics but all chapters blank -> no_profile (no_chapters_with_prose).

Mirrors ``test_author_voice_service_pipeline.py`` (ADR-055 / ADR-074 precedent).

See:
    ADR-074 — Author Voice Storage Contract.
    CONSTRAINTS.md RULE-04 / RULE-11.
"""

from __future__ import annotations

import uuid

import pytest

from narrare.analysis.schemas_author_voice_drift import AuthorVoiceDriftRequest
from narrare_core.llm.model_config import ResolvedModelConfig
from tests.unit.api.analysis._author_voice_drift_test_helpers import (
    FakeChapter,
    consume,
    make_author_profile,
    make_chapter,
    make_novel,
    make_service,
    patch_mode1,
)


@pytest.fixture
def config() -> ResolvedModelConfig:
    return ResolvedModelConfig(provider_name="test", model_id="test-model")


def _two_chapters(novel_id: uuid.UUID) -> list[FakeChapter]:
    return [
        make_chapter(
            novel_id=novel_id,
            title="Chapter 1",
            content=(
                "The wind moved through the long grass like a rumour. She "
                'paused at the threshold. "You came," she said quietly.'
            ),
        ),
        make_chapter(
            novel_id=novel_id,
            title="Chapter 2",
            content=(
                "Evening deepened around them, patient and full of unspoken "
                "things. The candles guttered as the storm drew closer."
            ),
        ),
    ]


class TestAuthorVoiceDriftGracefulPaths:
    """No profile / no metrics / no prose produce explicit graceful events."""

    @pytest.mark.asyncio
    async def test_no_stored_profile_yields_no_profile(
        self,
        config: ResolvedModelConfig,
    ) -> None:
        """No stored AuthorVoiceProfile → no_profile (no_stored_profile), no agent."""
        novel = make_novel()
        chapters = _two_chapters(novel.id)
        service = make_service(novel=novel, chapters=chapters, profile=None, config=config)

        with patch_mode1() as (MockAgent, _mock_compose):
            events = await consume(
                service.run_stream(novel.id, uuid.uuid4(), AuthorVoiceDriftRequest())
            )

        no_profile_events = [event for event in events if event.event == "no_profile"]
        assert len(no_profile_events) == 1
        assert no_profile_events[0].no_profile is not None
        assert no_profile_events[0].no_profile.reason == "no_stored_profile"
        assert events[-1].event == "done"
        assert events[-1].is_final is True
        MockAgent.assert_not_called()

    @pytest.mark.asyncio
    async def test_profile_missing_metrics_yields_no_profile(
        self,
        config: ResolvedModelConfig,
    ) -> None:
        """Profile present but missing metric blocks → no_profile (no_profile_metrics)."""
        novel = make_novel()
        chapters = _two_chapters(novel.id)
        profile = make_author_profile(with_metrics=False)
        service = make_service(novel=novel, chapters=chapters, profile=profile, config=config)

        with patch_mode1() as (MockAgent, _mock_compose):
            events = await consume(
                service.run_stream(novel.id, uuid.uuid4(), AuthorVoiceDriftRequest())
            )

        no_profile_events = [event for event in events if event.event == "no_profile"]
        assert len(no_profile_events) == 1
        assert no_profile_events[0].no_profile is not None
        assert no_profile_events[0].no_profile.reason == "no_profile_metrics"
        MockAgent.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_chapters_yields_progress_done_without_agent_call(
        self,
        config: ResolvedModelConfig,
    ) -> None:
        """A novel with no chapters → progress + done, no agent call."""
        novel = make_novel()
        profile = make_author_profile()
        service = make_service(novel=novel, chapters=[], profile=profile, config=config)

        with patch_mode1() as (MockAgent, _mock_compose):
            events = await consume(
                service.run_stream(novel.id, uuid.uuid4(), AuthorVoiceDriftRequest())
            )

        assert [event.event for event in events] == ["progress", "done"]
        assert events[-1].is_final is True
        MockAgent.assert_not_called()

    @pytest.mark.asyncio
    async def test_chapters_without_prose_yields_no_profile(
        self,
        config: ResolvedModelConfig,
    ) -> None:
        """Profile + metrics but all chapters blank → no_profile (no_chapters_with_prose)."""
        novel = make_novel()
        chapters = [
            make_chapter(novel_id=novel.id, content="   "),
            make_chapter(novel_id=novel.id, content=""),
        ]
        profile = make_author_profile()
        service = make_service(novel=novel, chapters=chapters, profile=profile, config=config)

        with patch_mode1() as (MockAgent, _mock_compose):
            events = await consume(
                service.run_stream(novel.id, uuid.uuid4(), AuthorVoiceDriftRequest())
            )

        no_profile_events = [event for event in events if event.event == "no_profile"]
        # A progress event fires first, then the no_profile, then done.
        assert len(no_profile_events) == 1
        assert no_profile_events[0].no_profile is not None
        assert no_profile_events[0].no_profile.reason == "no_chapters_with_prose"
        MockAgent.assert_not_called()
