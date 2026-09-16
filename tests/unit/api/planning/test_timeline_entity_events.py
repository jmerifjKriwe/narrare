"""§7 integration test: timeline ``entity_events`` is FED, not stubbed.

Architectural-discipline §7 distinguishes "the template declares a slot"
from "the runtime actually feeds it". The ``entity_events`` slot was a
documented §7 GAP (assigned a literal ``""``); Wave 3 wires it from the
already-injected :class:`TimelineEventRepository` via the shared
:func:`render_confirmed_events` assembler. This test closes that gap for
real: it asserts that when ``TimelineAnalysisService`` runs for a novel with
confirmed timeline events, the composed ``PromptContext.extra["entity_events"]``
is **NON-EMPTY at runtime** and carries the event data — the model genuinely
receives it, not a literal ``""``.

Only the repositories are faked; the real render path
(``render_compact_events``) is exercised end-to-end (no proxy padding).
RULE-11 is covered by the no-events / no-repo cases: no exception, the slot
degrades to an empty string.

See:
    .opencode/context/narrare-dev/standards/architectural-discipline.md §7
    CONSTRAINTS.md RULE-11 (graceful degradation)
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from narrare.planning.models import TimelineEvent
from narrare.planning.timeline_analysis_service import TimelineAnalysisService
from tests.unit.planning._timeline_test_helpers import (
    FakeComposer,
    make_chapter,
    make_mock_agent,
    make_novel_model,
    make_static_resolution,
)

# ---------------------------------------------------------------------------
# Test doubles — only the repositories are faked; the render path is real.
# ---------------------------------------------------------------------------


def _make_event(
    *,
    event_name: str = "Battle of the Keep",
    event_type: str = "plot_point",
    description: str = "The siege began at dawn.",
    timestamp_raw: str = "Day 3",
    character_refs: list[dict[str, object]] | None = None,
    location_ref: dict[str, object] | None = None,
    is_confirmed: bool = True,
) -> TimelineEvent:
    """Build a real TimelineEvent with the fields the renderer reads."""
    return TimelineEvent(
        id=uuid.uuid4(),
        novel_id=uuid.uuid4(),
        event_name=event_name,
        event_type=event_type,
        description=description,
        timestamp_raw=timestamp_raw,
        character_refs=list(character_refs or []),
        location_ref=location_ref,
        is_confirmed=is_confirmed,
    )


class _FakeEventRepo:
    """Fake TimelineEventRepository — only ``list_by_novel`` is exercised.

    Faithfully applies the ``event_type`` / ``is_confirmed`` filters the
    assembler uses, so the §7 proof exercises the real selection path.
    """

    def __init__(self, events: list[TimelineEvent]) -> None:
        self._events = events

    async def list_by_novel(
        self,
        novel_id: uuid.UUID,
        *,
        event_type: str | None = None,
        chapter_id: uuid.UUID | None = None,
        source: str | None = None,
        is_confirmed: bool | None = None,
    ) -> list[TimelineEvent]:
        del novel_id, chapter_id, source  # unused filters in this fake
        result = list(self._events)
        if event_type is not None:
            result = [e for e in result if e.event_type == event_type]
        if is_confirmed is not None:
            result = [e for e in result if e.is_confirmed == is_confirmed]
        return result


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def novel_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def mock_novel_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_chapter_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_registry() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def composer() -> FakeComposer:
    return FakeComposer()


def _wire_common(
    mock_novel_repo: AsyncMock,
    mock_chapter_repo: AsyncMock,
    mock_registry: AsyncMock,
    novel_id: uuid.UUID,
) -> None:
    """Wire the novel/chapter/registry mocks shared by every run."""
    mock_novel_repo.get_by_id.return_value = make_novel_model(
        id=novel_id, title="My Epic", genre="fantasy"
    )
    mock_chapter_repo.list_by_novel.return_value = [make_chapter(position=0, title="Ch 1")]
    mock_registry.get_model.return_value = MagicMock(spec=[])


# ---------------------------------------------------------------------------
# §7 proof: entity_events NON-EMPTY at runtime when confirmed events exist
# ---------------------------------------------------------------------------


class TestTimelineEntityEventsFedAtRuntime:
    """The ``entity_events`` slot is genuinely fed when the novel has
    confirmed timeline events — the documented≠implemented gap is closed."""

    @pytest.mark.asyncio
    async def test_entity_events_non_empty_when_events_exist(
        self,
        mock_novel_repo: AsyncMock,
        mock_chapter_repo: AsyncMock,
        mock_registry: AsyncMock,
        composer: FakeComposer,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        """A novel with confirmed events renders a non-empty ``entity_events``
        carrying the event name — the model receives the data, not a stub."""
        events = [
            _make_event(
                event_name="Coronation of Elara",
                character_refs=[{"id": "c1", "name": "Elara"}],
                location_ref={"id": "l1", "name": "The Shimmering Keep"},
            ),
            _make_event(event_name="The Long Winter", event_type="background"),
        ]

        _wire_common(mock_novel_repo, mock_chapter_repo, mock_registry, novel_id)
        service = TimelineAnalysisService(
            novel_repo=mock_novel_repo,
            chapter_repo=mock_chapter_repo,
            model_registry=mock_registry,
            model_resolution=make_static_resolution(),
            composer=composer,  # type: ignore[arg-type]
            event_repo=_FakeEventRepo(events),  # type: ignore[arg-type]
        )

        with (
            patch("narrare_core.agents.timeline_agent.TimelineAgent") as MockAgent,
            patch("narrare_core.agents.timeline_agent.TimelineDeps"),
        ):
            MockAgent.return_value = make_mock_agent()
            await service.generate_timeline(novel_id, user_id)

        ctx = composer.last_context
        assert ctx is not None, "PromptComposer.build must receive a context."
        extra = getattr(ctx, "extra", {})
        assert extra["entity_events"] != "", (
            "entity_events must be non-empty at runtime (§7: fed, not stubbed)."
        )
        # Real event data reaches the slot (not proxy padding).
        assert "Coronation of Elara" in extra["entity_events"]
        assert "Elara" in extra["entity_events"]
        assert "Shimmering Keep" in extra["entity_events"]


# ---------------------------------------------------------------------------
# RULE-11: empty-but-valid (no exception) when no events / no repo
# ---------------------------------------------------------------------------


class TestTimelineEntityEventsGracefulDegradation:
    """RULE-11: no confirmed events or no event_repo never raises; the
    ``entity_events`` slot degrades to an empty string so the template still
    composes."""

    @pytest.mark.asyncio
    async def test_empty_when_no_confirmed_events(
        self,
        mock_novel_repo: AsyncMock,
        mock_chapter_repo: AsyncMock,
        mock_registry: AsyncMock,
        composer: FakeComposer,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        _wire_common(mock_novel_repo, mock_chapter_repo, mock_registry, novel_id)
        service = TimelineAnalysisService(
            novel_repo=mock_novel_repo,
            chapter_repo=mock_chapter_repo,
            model_registry=mock_registry,
            model_resolution=make_static_resolution(),
            composer=composer,  # type: ignore[arg-type]
            event_repo=_FakeEventRepo([]),  # type: ignore[arg-type]
        )

        with (
            patch("narrare_core.agents.timeline_agent.TimelineAgent") as MockAgent,
            patch("narrare_core.agents.timeline_agent.TimelineDeps"),
        ):
            MockAgent.return_value = make_mock_agent()
            await service.generate_timeline(novel_id, user_id)

        assert getattr(composer.last_context, "extra", {})["entity_events"] == ""

    @pytest.mark.asyncio
    async def test_empty_when_no_event_repo_wired(
        self,
        mock_novel_repo: AsyncMock,
        mock_chapter_repo: AsyncMock,
        mock_registry: AsyncMock,
        composer: FakeComposer,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        """event_repo=None → entity_events degrades to "" (RULE-11)."""
        _wire_common(mock_novel_repo, mock_chapter_repo, mock_registry, novel_id)
        service = TimelineAnalysisService(
            novel_repo=mock_novel_repo,
            chapter_repo=mock_chapter_repo,
            model_registry=mock_registry,
            model_resolution=make_static_resolution(),
            composer=composer,  # type: ignore[arg-type]
            # event_repo intentionally omitted → None (RULE-11).
        )

        with (
            patch("narrare_core.agents.timeline_agent.TimelineAgent") as MockAgent,
            patch("narrare_core.agents.timeline_agent.TimelineDeps"),
        ):
            MockAgent.return_value = make_mock_agent()
            await service.generate_timeline(novel_id, user_id)

        assert getattr(composer.last_context, "extra", {})["entity_events"] == ""
