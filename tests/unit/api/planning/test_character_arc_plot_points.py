"""§7 integration test: character-arc ``existing_plot_points`` is FED, not stubbed.

The ``existing_plot_points`` slot was a documented §7 GAP (literal ``""``);
Wave 3 wires it from the injected :class:`TimelineEventRepository` via the
shared :func:`render_confirmed_events` assembler, filtered to confirmed
``plot_point`` events. This test closes the gap for real: it asserts that
when ``CharacterArcService`` runs for a novel with confirmed plot-point
events, the composed ``PromptContext.extra["existing_plot_points"]`` is
**NON-EMPTY at runtime** and carries only confirmed plot-point events (the
``event_type`` + ``is_confirmed`` filters are genuinely applied), not a
literal ``""``.

Only the event repository is faked; the real render path
(``render_compact_events``) is exercised (no proxy padding). RULE-11 is
covered by the no-events / no-repo cases: no exception, slot degrades to "".

See:
    .opencode/context/narrare-dev/standards/architectural-discipline.md §7
    CONSTRAINTS.md RULE-11 (graceful degradation)
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from narrare.planning.models import TimelineEvent
from narrare_core.llm.model_config import ResolvedModelConfig
from tests.unit.api.planning._character_arc_test_helpers import (
    FakeComposedInvocation,
    FakeComposer,
    FakeModelRegistry,
    make_agent_output,
    make_novel,
    make_request,
)

# ---------------------------------------------------------------------------
# Test doubles — only the event repository is faked; the render path is real.
# ---------------------------------------------------------------------------


def _make_event(
    *,
    event_name: str = "Coronation",
    event_type: str = "plot_point",
    description: str = "A pivotal turning point.",
    timestamp_raw: str = "Day 5",
    is_confirmed: bool = True,
) -> TimelineEvent:
    return TimelineEvent(
        id=uuid.uuid4(),
        novel_id=uuid.uuid4(),
        event_name=event_name,
        event_type=event_type,
        description=description,
        timestamp_raw=timestamp_raw,
        character_refs=[],
        location_ref=None,
        is_confirmed=is_confirmed,
    )


class _FakeEventRepo:
    """Fake TimelineEventRepository — faithfully applies the
    ``event_type`` / ``is_confirmed`` filters the assembler uses."""

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
        del novel_id, chapter_id, source
        result = list(self._events)
        if event_type is not None:
            result = [e for e in result if e.event_type == event_type]
        if is_confirmed is not None:
            result = [e for e in result if e.is_confirmed == is_confirmed]
        return result


def _build_service(events: list[TimelineEvent] | None) -> object:
    """Build a CharacterArcService wired with the given fake event repo.

    ``events=None`` leaves the event_repo unwired (RULE-11 degradation path).
    """
    from narrare.planning.character_arc_service import CharacterArcService

    novel_repo = AsyncMock()
    novel_repo.get_by_id.return_value = make_novel()
    return CharacterArcService(
        novel_repo=novel_repo,  # type: ignore[arg-type]
        model_registry=FakeModelRegistry(),  # type: ignore[arg-type]
        model_config=ResolvedModelConfig(provider_name="test", model_id="test-model"),
        composer=FakeComposer(),  # type: ignore[arg-type]
        event_repo=_FakeEventRepo(events) if events is not None else None,  # type: ignore[arg-type]
    )


async def _existing_plot_points(service: object) -> str:
    """Run generate_character_arc and return the rendered slot value."""
    captured: dict[str, object] = {}

    async def _fake_compose(*, prompt_context: object, **_kwargs: object) -> object:
        captured["ctx"] = prompt_context
        return FakeComposedInvocation()

    with (
        patch("narrare_core.agents.character_arc_agent.CharacterArcAgent") as MockAgent,
        patch("narrare_core.agents.character_arc_agent.CharacterArcDeps"),
        patch(
            "narrare_core.ai_invocation.compose_invocation",
            new=AsyncMock(side_effect=_fake_compose),
        ),
    ):
        mock_agent = MagicMock(spec=["run"])
        mock_agent.run = AsyncMock(return_value=make_agent_output())
        MockAgent.return_value = mock_agent
        await service.generate_character_arc(uuid.uuid4(), uuid.uuid4(), make_request())  # type: ignore[arg-type]

    extra = getattr(captured["ctx"], "extra", {})
    return str(extra.get("existing_plot_points", ""))


# ---------------------------------------------------------------------------
# §7 proof: existing_plot_points NON-EMPTY and plot_point-filtered
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_existing_plot_points_non_empty_and_filtered() -> None:
    """A novel with confirmed plot-point events renders a non-empty
    ``existing_plot_points`` carrying ONLY confirmed plot-point events — the
    ``event_type``/``is_confirmed`` filters are genuinely applied."""
    service = _build_service(
        [
            _make_event(event_name="The Betrayal at Dawn", event_type="plot_point"),
            _make_event(event_name="The Long Winter", event_type="background"),
            _make_event(
                event_name="Unconfirmed skirmish",
                event_type="plot_point",
                is_confirmed=False,
            ),
        ]
    )

    value = await _existing_plot_points(service)
    assert value != "", "existing_plot_points must be non-empty at runtime (§7: fed, not stubbed)."
    assert "The Betrayal at Dawn" in value
    # The background event and the unconfirmed event are filtered out — the
    # event_type="plot_point" + is_confirmed=True filters genuinely apply.
    assert "The Long Winter" not in value
    assert "Unconfirmed skirmish" not in value


@pytest.mark.asyncio
async def test_existing_plot_points_empty_when_no_plot_points() -> None:
    """RULE-11: no confirmed plot-point events → slot degrades to ""."""
    service = _build_service([_make_event(event_name="Background lore", event_type="background")])
    assert await _existing_plot_points(service) == ""


@pytest.mark.asyncio
async def test_existing_plot_points_empty_when_no_event_repo() -> None:
    """RULE-11: no event_repo wired → slot degrades to ""."""
    service = _build_service(None)
    assert await _existing_plot_points(service) == ""
