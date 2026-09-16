"""Shared test helpers for TimelineExtractionService tests (RULE-04 split).

Provides fakes and fixtures used by both
``test_timeline_extraction_service.py`` (Mode 1 behavioural) and
``test_timeline_extraction_service_compliance.py`` (source-level regression +
RULE-11).

Mirrors the ``_character_arc_test_helpers.py`` pattern (ADR-054 precedent).

Since ADR-086 L24 the service consumes model routing as a
``ModelResolution`` instead of a pre-resolved ``model_config``;
``make_service`` wraps the supplied config into a
``StaticModelResolution`` (the mechanical ctor migration — outcomes
unchanged, mirroring ``_timeline_test_helpers.py`` L22 convention).
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

from narrare._app.dependencies_services import StaticModelResolution
from narrare_core.agents.temporal_extraction_types import (
    ExtractedTemporalExpression,
    TemporalExtractionOutput,
)
from narrare_core.llm.model_routing import ResolvedModel
from narrare_core.prompts.composer import ComposedPrompt

if TYPE_CHECKING:
    from narrare.planning.timeline_extraction_service import TimelineExtractionService
    from narrare_core.llm.model_config import ResolvedModelConfig

# ---------------------------------------------------------------------------
# Fakes (avoid bare MagicMock for domain contracts — RULE-TEST-01)
# ---------------------------------------------------------------------------


class FakeModelRegistry:
    """Fake ModelRegistry returning a stub Model.

    Task-6b-2 bridge: model resolution flows through the ``prepare()``
    single assembly point (which delegates to ``get_model``), so tests
    exercise the migrated service path.
    """

    def __init__(self) -> None:
        self.get_model: AsyncMock = AsyncMock(return_value=MagicMock(spec=object))

    async def prepare(
        self,
        config: object,
        *,
        intent: object = None,
        usage_limits: object = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> object:
        return SimpleNamespace(
            model=await self.get_model(config, api_key=api_key, base_url=base_url),
            model_settings=None,
            usage_limits=usage_limits,
        )


class FakeComposer:
    """Fake PromptComposer for DI wiring.

    The service routes through ``compose_invocation`` (which calls
    ``composer.build`` internally), so this fake only needs to exist for DI
    wiring — its ``build`` is never reached when ``compose_invocation`` is
    patched. Kept as a real object (not a bare MagicMock) so the service's
    ``composer is None`` guard is satisfied.
    """

    def __init__(self) -> None:
        self.build: AsyncMock = AsyncMock(
            return_value=ComposedPrompt(system="COMPOSED-TIMELINE-EXTRACTION-SYSTEM", user="")
        )


class FakeComposedInvocation:
    """Stand-in for ``ComposedInvocation`` (Mode 1).

    The service only reads ``invocation.composed_prompt`` (Mode 1 invariant),
    so a lightweight class with that attribute is sufficient and avoids
    constructing the full ``prepared``/``finalized`` pipeline objects.
    """

    def __init__(self, system: str = "COMPOSED-TIMELINE-EXTRACTION-SYSTEM", user: str = "") -> None:
        self.composed_prompt: ComposedPrompt = ComposedPrompt(system=system, user=user)


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def make_novel(**overrides: object) -> MagicMock:
    """Create a mock novel with the attributes the service reads."""
    from narrare.novels.models import Novel

    defaults: dict[str, object] = {
        "id": overrides.get("id", uuid.uuid4()),
        "title": overrides.get("title", "Test Novel"),
        "genre": overrides.get("genre", "Fantasy"),
        "writing_language": overrides.get("writing_language", "en"),
    }
    defaults.update(overrides)
    novel = MagicMock(spec=Novel)
    for k, v in defaults.items():
        setattr(novel, k, v)
    return novel


def make_chapter(
    *,
    chapter_id: uuid.UUID | None = None,
    position: int = 0,
    title: str = "Chapter 1",
    summary: str = "Three days later, the hero arrived at the castle.",
) -> MagicMock:
    """Create a mock chapter with the attributes the service reads."""
    from narrare.chapters.models import Chapter

    chapter = MagicMock(spec=Chapter)
    chapter.id = chapter_id or uuid.uuid4()
    chapter.position = position
    chapter.title = title
    chapter.summary = summary
    return chapter


def make_agent_output(
    *,
    expression: str = "three days later",
    event_name: str = "Arrival at the castle",
) -> TemporalExtractionOutput:
    """Build a fake TemporalExtractionAgent.run result with one expression."""
    return TemporalExtractionOutput(
        extracted=[
            ExtractedTemporalExpression(
                expression=expression,
                event_name=event_name,
                timestamp_raw="three days later",
                chapter_reference="Chapter 1",
                character_names=["hero"],
                location_name="castle",
                confidence=0.9,
                context="Three days later, the hero arrived at the castle.",
            )
        ],
        chapter_temporal_markers=["three days later"],
        extraction_notes="",
    )


def make_service(
    composer: FakeComposer,
    config: ResolvedModelConfig,
    *,
    chapters: list[MagicMock] | None = None,
    existing_events: list[MagicMock] | None = None,
) -> TimelineExtractionService:
    """Build a TimelineExtractionService wired for Mode 1 prompt resolution.

    The ``chapter_repo`` is an ``AsyncMock`` whose ``list_by_novel`` returns
    the supplied chapters (default: one chapter). The ``event_repo`` is an
    ``AsyncMock`` whose ``list_by_novel`` returns the supplied existing events
    (default: empty). Since ADR-086 L24 the model routing arrives as a
    ``StaticModelResolution`` over the supplied config (lazy ctor shape).
    """
    from narrare.planning.timeline_extraction_service import TimelineExtractionService

    novel_repo = AsyncMock()
    chapter_repo = AsyncMock()
    chapter_repo.list_by_novel = AsyncMock(return_value=chapters or [make_chapter()])
    event_repo = AsyncMock()
    event_repo.list_by_novel = AsyncMock(return_value=existing_events or [])
    return TimelineExtractionService(
        novel_repo=novel_repo,  # type: ignore[arg-type]
        chapter_repo=chapter_repo,  # type: ignore[arg-type]
        model_registry=FakeModelRegistry(),  # type: ignore[arg-type]
        model_resolution=StaticModelResolution(
            ResolvedModel(config=config, api_key=None, base_url=None, source="unit-test")
        ),
        composer=composer,  # type: ignore[arg-type]
        event_repo=event_repo,  # type: ignore[arg-type]
    )
