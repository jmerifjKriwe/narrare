"""Shared fakes and helpers for ExtractionService unit tests.

Extracted from test_extraction_service.py per RULE-04 (file size limits).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

from narrare._app.dependencies_services import StaticModelResolution
from narrare.kb.extraction_service import ExtractionService
from narrare_core.agents.extraction_types import ExtractionItem, ExtractionOutput
from narrare_core.llm._model_settings import build_runtime_model_settings
from narrare_core.llm._prepared_call import PreparedModelCall
from narrare_core.llm.model_routing import ResolvedModel
from narrare_core.prompts.composer import ComposedPrompt

from ._test_fakes import FakeNovelRepo

if TYPE_CHECKING:
    from pydantic_ai.usage import UsageLimits

    from narrare.novels.contracts import NovelRepositoryProtocol
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.intents import LLMIntent


def permissive_novel_gate() -> NovelRepositoryProtocol:
    """Novel repo whose ownership gate always passes (IDOR S10).

    Non-ownership extraction tests act as the novel's owner; the
    ownership matrix lives in
    ``test_relationship_dismissed_extraction_ownership.py``.
    """
    return cast("NovelRepositoryProtocol", FakeNovelRepo())


# ---------------------------------------------------------------------------
# Fake dependency classes (avoid bare MagicMock — RULE-TEST-01)
# ---------------------------------------------------------------------------


class FakePrepareMixin:
    """Mirrors :meth:`ModelRegistry.prepare` on top of a ``get_model`` stub.

    Composes the fake's ``get_model`` with the real
    ``build_runtime_model_settings`` — exactly like the real
    ``ModelRegistry.prepare`` — so wiring tests assert the true settings
    composition (intent-aware thinking policy + ADR-045 output cap)
    flowing into ``agent.run``, not a canned triple.
    """

    get_model: AsyncMock

    async def prepare(
        self,
        config: ResolvedModelConfig,
        *,
        intent: LLMIntent | None = None,
        usage_limits: UsageLimits | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> PreparedModelCall:
        model = await self.get_model(
            config, api_key=api_key, base_url=base_url, usage_limits=usage_limits
        )
        settings = build_runtime_model_settings(config, usage_limits, intent=intent)
        return PreparedModelCall(model=model, model_settings=settings, usage_limits=usage_limits)


class FakeModelRegistry(FakePrepareMixin):
    """Fake ModelRegistry with configurable ``get_model`` + ``prepare``."""

    def __init__(self) -> None:
        self.get_model = AsyncMock(return_value=MagicMock(spec=object))


class FakeComposer:
    """Fake PromptComposer returning configurable system prompt."""

    def __init__(self) -> None:
        self.build = AsyncMock(
            return_value=ComposedPrompt(system="Test system prompt.", user="Test user.")
        )


class FakeChapterRepo:
    """Fake ChapterRepositoryProtocol."""

    def __init__(self) -> None:
        self.get_by_id = AsyncMock()


class FakeKBRepo:
    """Fake KBRepositoryProtocol."""

    def __init__(self) -> None:
        self.list_entries = AsyncMock(return_value=([], 0))


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def static_resolution(
    config: ResolvedModelConfig,
    api_key: str | None = None,
    base_url: str | None = None,
) -> StaticModelResolution:
    """Fixed ModelResolution around a known triple (ADR-086 test harness).

    Single definition site for the mechanical ctor migration of the kb
    extraction unit tests (RULE-06): production wires
    ``LazyModelResolution``, tests wire ``StaticModelResolution``.
    """
    return StaticModelResolution(
        ResolvedModel(config=config, api_key=api_key, base_url=base_url, source="unit-test")
    )


def make_service(
    registry: FakeModelRegistry | object,
    config: ResolvedModelConfig,
    chapter_repo: FakeChapterRepo | object,
    kb_repo: FakeKBRepo | object,
    composer: FakeComposer | object,
    retries: int = 3,
) -> ExtractionService:
    """Build an ExtractionService with the given (mocked) dependencies."""
    return ExtractionService(
        registry=registry,  # type: ignore[arg-type]
        model_resolution=static_resolution(config),
        chapter_repo=chapter_repo,  # type: ignore[arg-type]
        kb_repo=kb_repo,  # type: ignore[arg-type]
        composer=composer,  # type: ignore[arg-type]
        novel_repo=permissive_novel_gate(),
        retries=retries,
    )


def make_chapter(
    chapter_id: UUID | None = None,
    content: str = "Anna walked into the dark forest. The trees whispered.",
    title: str = "Chapter 1",
) -> MagicMock:
    """Create a mock chapter with spec (RULE-TEST-01)."""
    chapter = MagicMock(spec=["id", "content", "title"])
    chapter.id = chapter_id or uuid4()
    chapter.content = content
    chapter.title = title
    return chapter


def make_extraction_output(
    items: list[ExtractionItem] | None = None,
    notes: str = "",
) -> ExtractionOutput:
    """Create a sample ExtractionOutput with sensible defaults."""
    if items is None:
        items = [
            ExtractionItem(
                item_type="new_entity",
                entity_type="location",
                name="Dark Forest",
                confidence=0.95,
                source_text="the dark forest",
            )
        ]
    return ExtractionOutput(results=items, analysis_notes=notes)
