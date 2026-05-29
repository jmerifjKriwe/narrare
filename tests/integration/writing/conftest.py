"""Writing integration test configuration — patches LLM dependency chain.

The writing router calls ``get_writing_service`` directly (not via
FastAPI ``Depends``).  This function internally resolves model routing
from the DB, which requires user AI provider settings that don't exist
for the test user.

This conftest patches ``get_writing_service``, ``get_extend_service``,
``get_rewrite_service``, and ``get_suggest_service`` at their import
sites in the router modules so that:
- The **real** ``GenerationRepository`` is used (DB integration).
- A **fake** ``WritingPipeline`` / ``FakeModelRegistry`` replaces LLM calls.
- All other service logic runs unmodified.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.writing.extend_service import ExtendService
    from narrare.writing.rewrite_service import RewriteService
    from narrare.writing.service import WritingService
    from narrare.writing.suggest_service import InlineSuggestService


async def _make_writing_service(
    session: AsyncSession,
    user_id: str,
    project_id: object = None,
) -> WritingService:
    """Build a WritingService with real repo + fake pipeline (no LLM calls)."""
    from narrare._app.dependencies import get_composer
    from narrare.writing.repository import GenerationRepository
    from narrare.writing.service import WritingService
    from narrare_core.llm.intents import ResolvedModelConfig
    from narrare_core.writing.context_assembler import WritingContextAssembler
    from narrare_core.writing.draft_processor import DraftProcessor
    from narrare_core.writing.pipeline import WritingPipeline
    from tests.fakes.fake_llm_gateway import FakeModelRegistry

    repo = GenerationRepository(session)
    fake_registry = FakeModelRegistry()
    config = ResolvedModelConfig(
        provider_name="test",
        model_id="test-model",
        temperature=0.7,
        max_tokens=4000,
    )

    pipeline = WritingPipeline(
        registry=fake_registry,
        composer=get_composer(),
        context_assembler=WritingContextAssembler(),
        draft_processor=DraftProcessor(),
    )

    return WritingService(
        repo=repo,
        pipeline=pipeline,
        draft_processor=DraftProcessor(),
        config=config,
    )


async def _make_extend_service(
    session: AsyncSession,
    user_id: str,
    project_id: object = None,
) -> ExtendService:
    """Build an ExtendService with real repo + fake pipeline (no LLM calls)."""
    from narrare._app.dependencies import get_composer
    from narrare.writing.extend_service import ExtendService
    from narrare.writing.repository import GenerationRepository
    from narrare_core.llm.intents import ResolvedModelConfig
    from narrare_core.writing.context_assembler import WritingContextAssembler
    from narrare_core.writing.draft_processor import DraftProcessor
    from narrare_core.writing.pipeline import WritingPipeline
    from tests.fakes.fake_llm_gateway import FakeModelRegistry

    repo = GenerationRepository(session)
    fake_registry = FakeModelRegistry()
    # Queue a default stream response for extend tests.
    fake_registry.returns_stream(["The storm raged on through the night."])
    config = ResolvedModelConfig(
        provider_name="test",
        model_id="test-model",
        temperature=0.7,
        max_tokens=4000,
    )

    pipeline = WritingPipeline(
        registry=fake_registry,
        composer=get_composer(),
        context_assembler=WritingContextAssembler(),
        draft_processor=DraftProcessor(),
    )

    return ExtendService(
        repo=repo,
        pipeline=pipeline,
        draft_processor=DraftProcessor(),
        config=config,
    )


async def _make_rewrite_service(
    session: AsyncSession,
    user_id: str,
    project_id: object = None,
) -> RewriteService:
    """Build a RewriteService with real repo + fake pipeline (no LLM calls)."""
    from narrare._app.dependencies import get_composer
    from narrare.writing.repository import GenerationRepository
    from narrare.writing.rewrite_service import RewriteService
    from narrare_core.llm.intents import ResolvedModelConfig
    from narrare_core.writing.context_assembler import WritingContextAssembler
    from narrare_core.writing.draft_processor import DraftProcessor
    from narrare_core.writing.pipeline import WritingPipeline
    from tests.fakes.fake_llm_gateway import FakeModelRegistry

    repo = GenerationRepository(session)
    fake_registry = FakeModelRegistry()
    # Queue a default stream response with <alternative> tags for rewrite tests.
    fake_registry.returns_stream(
        [
            '<alternative label="Rewritten text">',
            "The night enveloped the old house in a shroud of silence, ",
            "its windows dark and unseeing.",
            "</alternative>",
        ]
    )
    config = ResolvedModelConfig(
        provider_name="test",
        model_id="test-model",
        temperature=0.7,
        max_tokens=4000,
    )

    pipeline = WritingPipeline(
        registry=fake_registry,
        composer=get_composer(),
        context_assembler=WritingContextAssembler(),
        draft_processor=DraftProcessor(),
    )

    return RewriteService(
        repo=repo,
        pipeline=pipeline,
        draft_processor=DraftProcessor(),
        config=config,
    )


async def _make_suggest_service(
    session: AsyncSession,
    user_id: str,
    project_id: object = None,
) -> InlineSuggestService:
    """Build an InlineSuggestService with real chapter repo + fake registry."""
    from narrare._app.dependencies import get_composer
    from narrare.chapters.repository import ChapterRepository
    from narrare.writing.suggest_service import InlineSuggestService
    from narrare_core.llm.intents import ResolvedModelConfig
    from tests.fakes.fake_llm_gateway import FakeModelRegistry

    fake_registry = FakeModelRegistry()
    # Queue a default short stream response for suggest tests.
    fake_registry.returns_stream(
        [
            "his footsteps echoing through the empty corridor.",
        ]
    )
    config = ResolvedModelConfig(
        provider_name="test",
        model_id="test-model",
        temperature=0.3,
        max_tokens=60,
    )

    chapter_repo = ChapterRepository(session)

    return InlineSuggestService(
        registry=fake_registry,
        composer=get_composer(),
        config=config,
        chapter_repo=chapter_repo,
    )


@pytest.fixture(autouse=True)
def _patch_writing_service() -> object:  # pyright: ignore[reportUnusedFunction]
    """Patch service factories in all writing router modules."""
    with (
        patch(
            "narrare.writing.router.get_writing_service",
            new=_make_writing_service,
        ),
        patch(
            "narrare.writing.router_extend.get_extend_service",
            new=_make_extend_service,
        ),
        patch(
            "narrare.writing.router_rewrite.get_rewrite_service",
            new=_make_rewrite_service,
        ),
        patch(
            "narrare.writing.router_stats.get_writing_service",
            new=_make_writing_service,
        ),
        patch(
            "narrare.writing.router_suggest.get_suggest_service",
            new=_make_suggest_service,
        ),
    ):
        yield
