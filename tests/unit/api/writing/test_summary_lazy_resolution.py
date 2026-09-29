"""Lazy wiring contract for ``get_summary_service`` (ADR-086 L38).

The factory (``writing/summary_deps.py::get_summary_service``) wires a
``LazyModelResolution`` around the SUMMARIZE routing cascade plus a deferred
model-runtime composition awaiting BOTH cascades (routing + token limits —
RULE-18/18b: sources unchanged, only timing moves; the M-budget / S4b shape,
``deps_style_variants.py`` L35 precedent). This file pins the FACTORY-side
contract:

- no resolution at construction (0 cascade calls),
- first use runs BOTH cascades exactly once with the eager factory's
  verbatim arguments, idempotent afterwards (``ensure_resolved``),
- the eager factory's verbatim composition (``temperature=0.3``,
  ``max_tokens=limits.output_limit``, per-user credentials) lands on the
  frozen runtime — WHAT unchanged, only WHEN.

The service-side first-use ordering (gate-before-resolution; resolution
ahead of the empty-content early return and outside the generation
try-wrapper) is pinned in ``TestSummaryFirstUseOrdering`` here. Mirrors
``tests/unit/api/series/test_band_summary_lazy_resolution.py`` (L25
precedent).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from narrare.writing._summary_invocation import SummaryModelRuntime
from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm.intents import LLMIntent
from narrare_core.shared.errors import ConfigurationError, NotFoundError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from narrare.chapters.models import Chapter
    from narrare.chapters.repository import ChapterRepository
    from narrare.novels.repository import NovelRepository

pytestmark = pytest.mark.asyncio

TEST_USER_ID = "00000000-0000-0000-0000-0000000000aa"  # novel owner in these tests


# ---------------------------------------------------------------------------
# Harness (ADR-030 fake-first: recorded cascade fakes, real dataclasses)
# ---------------------------------------------------------------------------


@asynccontextmanager
async def _lazy_wiring_harness() -> AsyncIterator[SimpleNamespace]:
    """Patch the factory's eager seams; expose the recorded cascade fakes."""
    resolver = MagicMock(spec=["resolve"], name="ModelRoutingResolver")
    resolver.resolve = AsyncMock(
        return_value=SimpleNamespace(
            config=ResolvedModelConfig(
                provider_name="zai",
                model_id="glm-4.7",
                temperature=0.7,
                max_tokens=4096,
            ),
            api_key="sk-user-key",
            base_url="https://u.example/v1",
        )
    )
    limits_service = MagicMock(spec=["get_resolved_limits"], name="TokenLimitsService")
    limits_service.get_resolved_limits = AsyncMock(
        return_value=SimpleNamespace(output_limit=2048, tier_percentages=None)
    )

    with (
        patch(
            "narrare.writing.summary_deps.get_model_routing_resolver",
            return_value=resolver,
        ),
        patch(
            "narrare.settings.token_limits.service.TokenLimitsService",
            return_value=limits_service,
        ),
        patch(
            "narrare._app.config.get_settings",
            return_value=MagicMock(spec=True, name="Settings"),
        ),
        patch(
            "narrare.writing.summary_deps.get_model_registry",
            return_value=MagicMock(spec=True, name="ModelRegistry"),
        ),
        patch(
            "narrare.writing.summary_deps.get_composer",
            return_value=MagicMock(spec=True, name="PromptComposer"),
        ),
        patch(
            "narrare.writing.summary_deps.get_invocation_pipeline",
            return_value=MagicMock(spec=True, name="InvocationPipeline"),
        ),
    ):
        yield SimpleNamespace(resolver=resolver, limits_service=limits_service)


def _build(**kwargs: Any) -> Any:
    """Run the factory under the harness's wiring (no resolution expected)."""
    from narrare.writing.summary_deps import get_summary_service

    args: dict[str, Any] = {
        "session": MagicMock(spec=AsyncSession, name="session"),
        **kwargs,
    }
    args.setdefault("user_id", TEST_USER_ID)
    args.setdefault("novel_id", uuid4())
    return get_summary_service(**args)


# ---------------------------------------------------------------------------
# Factory-side contract
# ---------------------------------------------------------------------------


class TestSummaryFactoryLazyWiring:
    """ADR-086 L38 — no resolution at construction; both cascades at first use."""

    async def test_no_resolution_at_construction(self) -> None:
        """Construction must not touch either cascade (0 resolve + 0 limits)."""
        async with _lazy_wiring_harness() as harness:
            await _build()

        assert harness.resolver.resolve.await_args_list == []
        assert harness.limits_service.get_resolved_limits.await_args_list == []

    async def test_first_use_resolves_both_cascades_with_verbatim_args(self) -> None:
        """First use runs BOTH cascades once, with the eager factory's exact
        arguments (SUMMARIZE / user uuid / novel — routing; str-cast ids —
        limits)."""
        user_id, novel_id = str(uuid4()), uuid4()
        async with _lazy_wiring_harness() as harness:
            service = await _build(user_id=user_id, novel_id=novel_id)
            assert harness.resolver.resolve.await_args_list == []

            runtime = await service.ensure_resolved()

            assert harness.resolver.resolve.await_args_list == [
                ((LLMIntent.SUMMARIZE, UUID(user_id), novel_id),)
            ]
            assert harness.limits_service.get_resolved_limits.await_args_list == [
                ({"user_id": user_id, "project_id": str(novel_id)},)
            ]
            assert runtime.api_key == "sk-user-key"
            assert runtime.base_url == "https://u.example/v1"

    async def test_none_novel_scope_passes_project_id_none(self) -> None:
        """Edge: no novel query param → the limits cascade sees ``project_id=None``
        while routing still pins the user scope."""
        user_id = str(uuid4())
        async with _lazy_wiring_harness() as harness:
            service = await _build(user_id=user_id, novel_id=None)

            await service.ensure_resolved()

            assert harness.limits_service.get_resolved_limits.await_args_list == [
                ({"user_id": user_id, "project_id": None},)
            ]

    async def test_ensure_resolved_composes_once_and_is_idempotent(self) -> None:
        """Repeat first use hits the cache — cascade counts stay at exactly 1."""
        async with _lazy_wiring_harness() as harness:
            service = await _build()

            first = await service.ensure_resolved()
            second = await service.ensure_resolved()

            assert first is second
            assert harness.resolver.resolve.await_count == 1
            assert harness.limits_service.get_resolved_limits.await_count == 1

    async def test_composition_applies_eager_overlay_exactly_once(self) -> None:
        """Timing-only invariant: the frozen runtime carries the eager
        factory's verbatim sampling overlay (``temperature=0.3``, cascade
        ``output_limit``) over the resolved config — no other transformation.
        """
        async with _lazy_wiring_harness():
            service = await _build()
            runtime = await service.ensure_resolved()

        assert isinstance(runtime, SummaryModelRuntime)
        assert runtime.config.temperature == 0.3
        assert runtime.config.max_tokens == 2048
        # Untouched cascade passthroughs:
        assert runtime.config.provider_name == "zai"
        assert runtime.config.model_id == "glm-4.7"
        assert runtime.api_key == "sk-user-key"


# ---------------------------------------------------------------------------
# Service-side first-use ordering
# ---------------------------------------------------------------------------


class _FakeChapterRepo:
    """In-memory ``ChapterRepository`` stand-in (``get`` only)."""

    def __init__(self, chapter: Chapter | None) -> None:
        self._chapter = chapter

    async def get(self, chapter_id: UUID) -> Chapter | None:
        return self._chapter


class _FakeNovelRepo:
    """In-memory ``NovelRepository`` stand-in mapping novel → owner."""

    def __init__(self, owner_id: UUID | None) -> None:
        self._owner_id = owner_id

    async def get_by_id(self, novel_id: UUID, user_id: UUID) -> object | None:
        if self._owner_id != user_id:
            return None
        return object()  # service only checks existence


async def _exploding_runtime_factory() -> SummaryModelRuntime:
    raise AssertionError("runtime composition ran at the wrong point")


def _ordering_service(
    chapter_repo: _FakeChapterRepo,
    novel_repo: _FakeNovelRepo,
    runtime_factory: Any,
) -> Any:
    """Build the service directly with a pinning runtime factory."""
    from narrare.writing.summary_service import ChapterSummaryService

    return ChapterSummaryService(
        registry=MagicMock(spec=True, name="ModelRegistry"),
        runtime_factory=runtime_factory,
        chapter_repo=cast("ChapterRepository", chapter_repo),
        novel_repo=cast("NovelRepository", novel_repo),
        composer=MagicMock(spec=True, name="PromptComposer"),
    )


class TestSummaryFirstUseOrdering:
    """Resolution runs after the ownership gate, before the degradation exits."""

    async def test_summarize_resolves_after_ownership_gate(self) -> None:
        """Gate-before-resolution: a FOREIGN chapter 404s before either
        cascade runs — the runtime factory must never be invoked."""
        from tests.factories import make_chapter

        chapter = make_chapter(content="Private content...", title="Ch 1")
        service = _ordering_service(
            _FakeChapterRepo(chapter),
            _FakeNovelRepo(owner_id=uuid4()),  # not TEST_USER_ID → gate closed
            _exploding_runtime_factory,
        )

        with pytest.raises(NotFoundError, match="Chapter"):
            await service.summarize(chapter.id, user_id=TEST_USER_ID)

    async def test_summarize_resolves_before_empty_content_exit(self) -> None:
        """Degradation-path loudness: an owned EMPTY chapter must surface the
        cascades' ``ConfigurationError`` (loud 400), not the empty-content
        200 — resolution precedes the graceful early return."""
        from tests.factories import make_chapter

        async def _unconfigured() -> SummaryModelRuntime:
            raise ConfigurationError("No AI provider configured")

        chapter = make_chapter(content="", title="Empty")
        service = _ordering_service(
            _FakeChapterRepo(chapter),
            _FakeNovelRepo(owner_id=UUID(TEST_USER_ID)),
            _unconfigured,
        )

        with pytest.raises(ConfigurationError, match="No AI provider"):
            await service.summarize(chapter.id, user_id=TEST_USER_ID)
