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

PERFORMANCE: All imports are at module level (not lazy) to avoid ~1s
cold-start import overhead on the first test invocation of each service
factory function.  See: tests/integration/README.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

# Module-level imports to amortise import cost across all tests in the
# writing integration suite.  Lazy imports inside the factory functions
# added ~1s to the first test that called each service.
from narrare._app.dependencies import get_composer
from narrare.chapters.repository import ChapterRepository
from narrare.novels.repository import NovelRepository
from narrare.writing.extend_service import ExtendService
from narrare.writing.repository import GenerationRepository
from narrare.writing.rewrite_service import RewriteService
from narrare.writing.service import WritingService
from narrare.writing.style_variant_service import StyleVariantService
from narrare.writing.suggest_service import InlineSuggestService
from narrare_core.llm import ResolvedModelConfig
from narrare_core.writing.context_assembler import WritingContextAssembler
from narrare_core.writing.draft_processor import DraftProcessor
from narrare_core.writing.pipeline import WritingPipeline
from tests.fakes.fake_llm_gateway import FakeModelRegistry

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


_assembler = WritingContextAssembler()
_processor = DraftProcessor()


@pytest.fixture(scope="session", autouse=True)
def _prewarm_composer(_no_real_mem0_clients: None) -> None:  # pyright: ignore[reportUnusedFunction]
    """Pre-warm PromptComposer singleton (~750ms cold start).

    ``get_composer()`` calls ``_get_composer_instance()`` which is
    ``@lru_cache``'d.  The first call loads the entire prompt registry
    from disk (YAML prompt files).  This fixture runs once per session,
    so the ~750ms overhead is paid once, not per-test.

    EXPLICIT DEPENDENCY on ``_no_real_mem0_clients`` (ADR-068 Decision 2):
    ``get_composer()`` → ``_get_preference_service_instance()`` would
    create a real ``mem0.AsyncMemory`` client if the guard had not yet
    patched ``is_mem0_available``. Pytest resolves fixture parameters
    before calling the dependent fixture, so declaring this dependency
    guarantees the session-scoped guard is active before any code path
    here can construct a mem0 client. Without it, autouse session fixtures
    have non-deterministic order — the regression that surfaced in
    PR #126's ``test_session_stop_and_recovery.py`` event-loop leak.
    """
    get_composer()


async def _make_writing_service(
    session: AsyncSession,
    user_id: str,
    project_id: object = None,
) -> WritingService:
    """Build a WritingService with real repo + fake pipeline (no LLM calls)."""
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
        context_assembler=_assembler,
        draft_processor=_processor,
    )

    return WritingService(
        repo=repo,
        pipeline=pipeline,
        draft_processor=_processor,
        config=config,
        chapter_repo=ChapterRepository(session),
        novel_repo=NovelRepository(session),
    )


async def _make_writing_service_for_stream(
    session: AsyncSession,
    user_id: str,
    request_id: object = None,
) -> WritingService:
    """Stream-path variant of ``_make_writing_service`` (Task 3e signature).

    The stream endpoint's request-scoped factory takes ``request_id``
    instead of ``project_id``; the fake builder ignores both (no model
    routing in integration tests), so it delegates straight through.
    """
    return await _make_writing_service(session, user_id)


async def _make_extend_service(
    session: AsyncSession,
    user_id: str,
    project_id: object = None,
) -> ExtendService:
    """Build an ExtendService with real repo + fake pipeline (no LLM calls)."""
    from narrare.writing._extend_support import ExtendRuntime

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
        context_assembler=_assembler,
        draft_processor=_processor,
    )

    # ADR-086: the service composes its runtime at first use; the fake
    # chain pins a fixed runtime (render- and outcome-inert — same
    # config/pipeline the eager factory passed).
    runtime = ExtendRuntime(
        config=config,
        api_key=None,
        base_url=None,
        pipeline=pipeline,
    )

    async def _static_runtime() -> ExtendRuntime:
        return runtime

    return ExtendService(
        repo=repo,
        runtime_factory=_static_runtime,
        draft_processor=_processor,
        chapter_repo=ChapterRepository(session),
        novel_repo=NovelRepository(session),
    )


async def _make_rewrite_service(
    session: AsyncSession,
    user_id: str,
    project_id: object = None,
) -> RewriteService:
    """Build a RewriteService with real repo + fake pipeline (no LLM calls)."""
    from narrare.writing._rewrite_support import RewriteRuntime

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
        context_assembler=_assembler,
        draft_processor=_processor,
    )

    # ADR-086: the service composes its runtime at first use; the fake
    # chain pins a fixed runtime (render- and outcome-inert — same
    # config/pipeline the eager factory passed).
    runtime = RewriteRuntime(
        config=config,
        api_key=None,
        base_url=None,
        pipeline=pipeline,
    )

    async def _static_runtime() -> RewriteRuntime:
        return runtime

    return RewriteService(
        repo=repo,
        runtime_factory=_static_runtime,
        draft_processor=_processor,
        chapter_repo=ChapterRepository(session),
        novel_repo=NovelRepository(session),
    )


async def _make_suggest_service(
    session: AsyncSession,
    user_id: str,
    project_id: object = None,
) -> InlineSuggestService:
    """Build an InlineSuggestService with real chapter repo + fake registry."""
    from narrare._app.dependencies_services import StaticModelResolution
    from narrare_core.llm.model_routing import ResolvedModel

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
        # ADR-086: the service resolves a ModelResolution at first use;
        # the integration fake chain pins a fixed resolution (render- and
        # outcome-inert — same config the eager factory passed).
        model_resolution=StaticModelResolution(ResolvedModel(config=config)),
        chapter_repo=chapter_repo,
        novel_repo=NovelRepository(session),
    )


async def _make_style_variant_service(
    session: AsyncSession,
    user_id: str,
    project_id: object = None,
) -> StyleVariantService:
    """Build a StyleVariantService with real repo + fake pipeline (no LLM calls)."""
    repo = GenerationRepository(session)
    fake_registry = FakeModelRegistry()
    # Queue a default stream response with a single <alternative> tag for
    # style-variant tests (count=1 per the service contract).
    fake_registry.returns_stream(
        [
            '<alternative label="Variant">',
            "The night was thick with the scent of rain and old stone, ",
            "every surface humming with cold.",
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
        context_assembler=_assembler,
        draft_processor=_processor,
    )

    return StyleVariantService(
        repo=repo,
        pipeline=pipeline,
        draft_processor=_processor,
        config=config,
        chapter_repo=ChapterRepository(session),
        novel_repo=NovelRepository(session),
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
            "narrare.writing.router.get_writing_service_for_stream",
            new=_make_writing_service_for_stream,
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
            "narrare.writing.router_style_variants.get_style_variant_service",
            new=_make_style_variant_service,
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
