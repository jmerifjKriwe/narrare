"""Runtime-wiring tests for ExtractionService world_context (quality-debt item 2).

Verifies that ``extract_from_chapter`` populates the ``{{world_context}}``
prompt variable with real curated KB context (the project's existing entities)
to aid entity disambiguation — and degrades gracefully (RULE-11) when the KB
repository is unavailable.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from narrare_core.llm import ResolvedModelConfig

from ._extraction_helpers import (
    FakeChapterRepo,
    FakeComposer,
    FakeKBRepo,
    FakeModelRegistry,
    make_chapter,
    make_extraction_output,
    make_service,
)
from ._merge_test_helpers import FakeComposedInvocation


def _entry(name: str, entity_type: str = "character") -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        entity_type=entity_type,
        metadata_={"role": "protagonist"},
        body="",
    )


def _composed_invocation() -> FakeComposedInvocation:
    """Build a ``compose_invocation`` result carrying ``composed_prompt``.

    Mirrors the Mode 1 stand-in used by the merge tests (ADR-054): a real
    object with ``.composed_prompt.system`` / ``.composed_prompt.user``
    attributes that the service actually reads — no bare MagicMock
    (RULE-TEST-01).
    """
    return FakeComposedInvocation(system="sys", user="")


@pytest.mark.asyncio
async def test_extract_populates_world_context_from_existing_entities() -> None:
    """extract must supply curated world context for entity disambiguation."""
    config = ResolvedModelConfig(provider_name="test", model_id="m")
    chapter = make_chapter()
    chapter_repo = FakeChapterRepo()
    chapter_repo.get_by_id = AsyncMock(return_value=chapter)

    kb_repo = FakeKBRepo()
    kb_repo.list_entries = AsyncMock(return_value=([_entry("Elara")], 1))

    service = make_service(FakeModelRegistry(), config, chapter_repo, kb_repo, FakeComposer())

    with (
        patch("narrare.kb.extraction_service.ExtractionAgent") as MockAgent,
        patch(
            "narrare_core.ai_invocation.compose_invocation",
            new=AsyncMock(return_value=_composed_invocation()),
        ) as mock_compose,
    ):
        mock_agent = MagicMock(spec=["run"])
        mock_agent.run = AsyncMock(return_value=make_extraction_output())
        MockAgent.return_value = mock_agent

        await service.extract_from_chapter(
            novel_id=uuid4(),
            chapter_id=chapter.id,
            user_id=uuid4(),
        )

    extra = mock_compose.call_args.kwargs["prompt_context"].extra
    assert extra["world_context"] != "", (
        "world_context must be populated with real curated KB context, not omitted/empty."
    )
    assert "Elara" in extra["world_context"]


@pytest.mark.asyncio
async def test_extract_world_context_degrades_gracefully_on_repo_failure() -> None:
    """RULE-11: a KB repo failure must not crash extraction."""
    config = ResolvedModelConfig(provider_name="test", model_id="m")
    chapter = make_chapter()
    chapter_repo = FakeChapterRepo()
    chapter_repo.get_by_id = AsyncMock(return_value=chapter)

    # Both dedup + world_context reads go through list_entries; both must degrade.
    kb_repo = FakeKBRepo()
    kb_repo.list_entries = AsyncMock(side_effect=RuntimeError("offline"))

    service = make_service(FakeModelRegistry(), config, chapter_repo, kb_repo, FakeComposer())

    with (
        patch("narrare.kb.extraction_service.ExtractionAgent") as MockAgent,
        patch(
            "narrare_core.ai_invocation.compose_invocation",
            new=AsyncMock(return_value=_composed_invocation()),
        ) as mock_compose,
    ):
        mock_agent = MagicMock(spec=["run"])
        mock_agent.run = AsyncMock(return_value=make_extraction_output())
        MockAgent.return_value = mock_agent

        result = await service.extract_from_chapter(
            novel_id=uuid4(),
            chapter_id=chapter.id,
            user_id=uuid4(),
        )

    assert result is not None
    assert mock_compose.call_args.kwargs["prompt_context"].extra["world_context"] == ""
