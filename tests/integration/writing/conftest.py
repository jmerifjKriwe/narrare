"""Writing integration test configuration — patches LLM dependency chain.

The writing router calls ``get_writing_service`` directly (not via
FastAPI ``Depends``).  This function internally resolves model routing
from the DB, which requires user AI provider settings that don't exist
for the test user.

This conftest patches ``get_writing_service`` and ``get_extend_service``
at their import sites in the router modules so that:
- The **real** ``GenerationRepository`` is used (DB integration).
- A **fake** ``WritingPipeline`` replaces LLM calls.
- All other service logic runs unmodified.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.writing.extend_service import ExtendService
    from narrare.writing.service import WritingService


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


@pytest.fixture(autouse=True)
def _patch_writing_service() -> object:  # pyright: ignore[reportUnusedFunction]
    """Patch get_writing_service and get_extend_service in all writing router modules."""
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
            "narrare.writing.router_stats.get_writing_service",
            new=_make_writing_service,
        ),
    ):
        yield
