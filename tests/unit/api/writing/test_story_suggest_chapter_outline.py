"""§7 integration test: story-suggest ``chapter_outline`` is FED, not stubbed.

The ``chapter_outline`` slot was a documented §7 GAP (literal ``""``); Wave 3
wires it from the injected :class:`OutlineRepository` via the
:func:`render_chapter_outline` helper, populated only when a ``chapter_id``
is targeted. This test closes the gap for real: it asserts that when
``StorySuggestService`` runs with a ``chapter_id`` whose outline exists, the
composed ``PromptContext.extra["chapter_outline"]`` is **NON-EMPTY at
runtime** and carries the stage/beats/notes — the model genuinely receives
it, not a literal ``""``.

The empty case (no ``chapter_id``) is legitimate RULE-11: story-suggest is a
project-level tool and a chapter need not be selected. That case stays
allowlisted as a confirmed-optional var (the literal ``""`` is retained in
the dict by design so template substitution always succeeds).

See:
    .opencode/context/narrare-dev/standards/architectural-discipline.md §7
    CONSTRAINTS.md RULE-11 (graceful degradation)
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from narrare.planning.models import ChapterOutline
from narrare_core.llm.model_config import ResolvedModelConfig
from tests.fakes import FakeOutlineRepository
from tests.unit.api.writing._story_suggest_test_helpers import (
    FakeComposedInvocation,
    FakeComposer,
    FakeModelRegistry,
    make_agent_output,
    make_novel,
    make_request,
)

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


def _make_outline(chapter_id: uuid.UUID) -> ChapterOutline:
    """Build a ChapterOutline carrying stage + beats + notes."""
    return ChapterOutline(
        id=uuid.uuid4(),
        chapter_id=chapter_id,
        stage_assignment="act-1",
        planned_beats=[
            {"text": "Lyra arrives at the keep"},
            {"text": "The storm breaks over the valley"},
        ],
        outline_notes="Establish tension before the betrayal.",
    )


def _build_service(outline_repo: object | None) -> object:
    """Build a StorySuggestService wired with the given outline repo."""
    from narrare._app.dependencies_services import StaticModelResolution
    from narrare.writing.story_suggest_service import StorySuggestService
    from narrare_core.llm.model_routing import ResolvedModel

    novel_repo = AsyncMock()
    novel_repo.get_by_id.return_value = make_novel()
    return StorySuggestService(
        novel_repo=novel_repo,  # type: ignore[arg-type]
        model_registry=FakeModelRegistry(),  # type: ignore[arg-type]
        model_resolution=StaticModelResolution(
            ResolvedModel(
                config=ResolvedModelConfig(provider_name="test", model_id="test-model"),
                api_key=None,
                base_url=None,
                source="unit-test",
            )
        ),
        composer=FakeComposer(),  # type: ignore[arg-type]
        outline_repo=outline_repo,  # type: ignore[arg-type]
    )


async def _chapter_outline(service: object, request: object) -> str:
    """Run suggest and return the rendered ``chapter_outline`` slot value."""
    captured: dict[str, object] = {}

    async def _fake_compose(*, prompt_context: object, **_kwargs: object) -> object:
        captured["ctx"] = prompt_context
        return FakeComposedInvocation()

    with (
        patch("narrare_core.agents.story_suggest_agent.StorySuggestAgent") as MockAgent,
        patch("narrare_core.agents.story_suggest_types.StorySuggestDeps"),
        patch(
            "narrare_core.ai_invocation.compose_invocation",
            new=AsyncMock(side_effect=_fake_compose),
        ),
    ):
        mock_agent = MagicMock(spec=["run"])
        mock_agent.run = AsyncMock(return_value=make_agent_output())
        MockAgent.return_value = mock_agent
        async for _ in service.suggest(uuid.uuid4(), uuid.uuid4(), request):  # type: ignore[arg-type]
            pass

    extra = getattr(captured["ctx"], "extra", {})
    return str(extra.get("chapter_outline", ""))


# ---------------------------------------------------------------------------
# §7 proof: chapter_outline NON-EMPTY at runtime when chapter_id + outline
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chapter_outline_non_empty_when_chapter_targeted() -> None:
    """A request with a chapter_id whose outline exists renders a non-empty
    ``chapter_outline`` carrying the stage, beats, and notes — the model
    receives the data, not a stub."""
    chapter_id = uuid.uuid4()
    outline_repo = FakeOutlineRepository()
    outline_repo.seed(_make_outline(chapter_id))
    service = _build_service(outline_repo)
    request = make_request(chapter_id=chapter_id)

    value = await _chapter_outline(service, request)
    assert value != "", (
        "chapter_outline must be non-empty at runtime when a chapter is "
        "targeted and its outline exists (§7: fed, not stubbed)."
    )
    # Real outline data reaches the slot (not proxy padding).
    assert "act-1" in value
    assert "Lyra arrives at the keep" in value
    assert "The storm breaks" in value
    assert "Establish tension" in value


@pytest.mark.asyncio
async def test_chapter_outline_empty_when_no_chapter_id() -> None:
    """RULE-11: no chapter_id targeted → slot stays empty. Story-suggest is a
    project-level tool and a chapter need not be selected (allowlisted)."""
    service = _build_service(FakeOutlineRepository())
    request = make_request()  # no chapter_id

    value = await _chapter_outline(service, request)
    assert value == ""


@pytest.mark.asyncio
async def test_chapter_outline_empty_when_outline_missing() -> None:
    """RULE-11: chapter_id set but no outline row → slot stays empty."""
    outline_repo = FakeOutlineRepository()  # nothing seeded
    service = _build_service(outline_repo)
    request = make_request(chapter_id=uuid.uuid4())

    value = await _chapter_outline(service, request)
    assert value == ""


@pytest.mark.asyncio
async def test_chapter_outline_empty_when_no_outline_repo() -> None:
    """RULE-11: no outline_repo wired → slot stays empty even with a chapter."""
    service = _build_service(None)
    request = make_request(chapter_id=uuid.uuid4())

    value = await _chapter_outline(service, request)
    assert value == ""
