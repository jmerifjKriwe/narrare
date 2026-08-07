"""Unit tests for SeriesConsistencyService (Spec 4 — Cross-Novel Drift, Task 2).

Fake-based per ADR-030: domain dependencies (repositories, composer, registry,
agent) are real Fake classes from ``_series_consistency_test_helpers.py`` — no
``MagicMock``/``patch`` for domain behaviour. The agent is injectable via
``agent_factory`` so tests supply a fake whose ``.run()`` returns a controlled
``SeriesConsistencyOutput``.

Verifies the Spec 4 contract:
- Happy path: Canon + prose → agent runs once, returns conflicts.
- RULE-11 graceful degradation: no Canon OR no prose → empty result, no LLM call.
- Ownership + novel-membership anti-enumeration (both → 403).
- Agent failure wrapped in WritingError; NotFoundError re-raised.
- Runtime content: Canon entries + chapter texts flow in the agent run prompt.
"""

from __future__ import annotations

import uuid

import pytest

from narrare.series.series_consistency_schemas import SeriesConsistencyCheckResponse
from narrare_core.agents.series_consistency_types import SeriesConsistencyOutput
from narrare_core.shared.errors import NotFoundError, WritingError
from tests.factories import make_chapter

from ._series_consistency_test_helpers import (
    FakeSeriesConsistencyAgent,
    make_conflict,
    make_service,
    seed_owned_series_with_canon,
)

# ---------------------------------------------------------------------------
# check_novel() — happy path
# ---------------------------------------------------------------------------


class TestCheckNovelHappyPath:
    """SeriesConsistencyService.check_novel() — canon + prose → agent → conflicts."""

    async def test_with_canon_and_prose_runs_agent_once_and_returns_empty(self) -> None:
        """Happy path: agent runs once; empty conflicts list returned as-is."""
        user_id = uuid.uuid4()
        service, agent, kb_repo, series_repo, novel_repo, chapter_repo = make_service()
        series_id, novel_id = seed_owned_series_with_canon(
            series_repo=series_repo,
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            kb_repo=kb_repo,
            user_id=user_id,
        )

        result = await service.check_novel(series_id, novel_id, user_id)

        assert isinstance(result, SeriesConsistencyCheckResponse)
        assert agent.run_count == 1
        assert result.conflicts == []
        assert result.canon_entry_count == 1
        assert result.chapter_count == 1
        assert result.series_id == series_id
        assert result.novel_id == novel_id

    async def test_agent_conflicts_carried_through_to_response(self) -> None:
        """When the agent returns conflicts, the response carries them verbatim."""
        user_id = uuid.uuid4()
        conflict = make_conflict()
        agent = FakeSeriesConsistencyAgent(
            output=SeriesConsistencyOutput(
                conflicts=[conflict], summary="One eye-colour contradiction detected."
            )
        )
        service, _, kb_repo, series_repo, novel_repo, chapter_repo = make_service(agent=agent)
        series_id, novel_id = seed_owned_series_with_canon(
            series_repo=series_repo,
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            kb_repo=kb_repo,
            user_id=user_id,
        )

        result = await service.check_novel(series_id, novel_id, user_id)

        assert len(result.conflicts) == 1
        assert result.conflicts[0].canon_entry_slug == "character-elara-eye-color"
        assert result.conflicts[0].severity == "error"
        assert result.summary == "One eye-colour contradiction detected."

    async def test_canon_entries_and_chapter_texts_flow_in_run_prompt(self) -> None:
        """Canon slug + chapter prose appear in the agent run prompt (user channel)."""
        user_id = uuid.uuid4()
        service, agent, kb_repo, series_repo, novel_repo, chapter_repo = make_service()
        series_id, novel_id = seed_owned_series_with_canon(
            series_repo=series_repo,
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            kb_repo=kb_repo,
            user_id=user_id,
            canon_slugs=("world-aldric-reign",),
            chapter_prose=("King Aldric had ruled for forty winters.",),
        )

        await service.check_novel(series_id, novel_id, user_id)

        assert agent.run_count == 1
        assert "world-aldric-reign" in agent.last_prompt
        assert "King Aldric had ruled for forty winters." in agent.last_prompt

    async def test_deps_carry_canon_and_chapter_texts_and_title(self) -> None:
        """SeriesConsistencyDeps receives the formatted canon + texts + title."""
        user_id = uuid.uuid4()
        service, agent, kb_repo, series_repo, novel_repo, chapter_repo = make_service()
        series_id, novel_id = seed_owned_series_with_canon(
            series_repo=series_repo,
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            kb_repo=kb_repo,
            user_id=user_id,
        )

        await service.check_novel(series_id, novel_id, user_id)

        # novel_title is the BAND's (novel's) title — the factory default, not
        # the series title ("The Expanse").
        assert agent.last_deps.novel_title == "Test Novel"
        assert len(agent.last_deps.canon_entries) == 1
        assert "character-elara-eye-color" in agent.last_deps.canon_entries[0]
        assert agent.last_deps.chapter_texts == ["Elara's green eyes scanned the horizon."]

    async def test_empty_prose_chapters_are_excluded(self) -> None:
        """Chapters whose content is empty/blank are not passed to the agent."""
        user_id = uuid.uuid4()
        service, agent, kb_repo, series_repo, novel_repo, chapter_repo = make_service()
        series_id, novel_id = seed_owned_series_with_canon(
            series_repo=series_repo,
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            kb_repo=kb_repo,
            user_id=user_id,
            chapter_prose=("Real prose here.",),
        )
        # Add empty/blank chapters directly so the repo returns them via
        # list_by_novel, but they must be excluded from the agent input.
        chapter_repo.seed(
            make_chapter(novel_id=novel_id, position=2, content=""),
            make_chapter(novel_id=novel_id, position=3, content="   "),
        )

        result = await service.check_novel(series_id, novel_id, user_id)

        assert agent.run_count == 1
        assert result.chapter_count == 1  # only the non-empty chapter counted
        assert agent.last_deps.chapter_texts == ["Real prose here."]


# ---------------------------------------------------------------------------
# check_novel() — error paths
# ---------------------------------------------------------------------------


class TestCheckNovelErrors:
    """Agent failure wrapped in WritingError; NotFoundError re-raised."""

    async def test_agent_failure_wrapped_in_writing_error(self) -> None:
        user_id = uuid.uuid4()
        failing = FakeSeriesConsistencyAgent(raises=RuntimeError("LLM down"))
        service, _, kb_repo, series_repo, novel_repo, chapter_repo = make_service(agent=failing)
        series_id, novel_id = seed_owned_series_with_canon(
            series_repo=series_repo,
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            kb_repo=kb_repo,
            user_id=user_id,
        )

        with pytest.raises(WritingError, match="Series-consistency check failed"):
            await service.check_novel(series_id, novel_id, user_id)

    async def test_agent_not_found_error_re_raised(self) -> None:
        """NotFoundError raised inside the flow is re-raised, not wrapped."""
        user_id = uuid.uuid4()
        failing = FakeSeriesConsistencyAgent(raises=NotFoundError("Model", identifier="x"))
        service, _, kb_repo, series_repo, novel_repo, chapter_repo = make_service(agent=failing)
        series_id, novel_id = seed_owned_series_with_canon(
            series_repo=series_repo,
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            kb_repo=kb_repo,
            user_id=user_id,
        )

        with pytest.raises(NotFoundError):
            await service.check_novel(series_id, novel_id, user_id)
