"""Lazy model-resolution semantics for ExtractionService (ADR-086 L16).

The factory (``kb/dependencies_extraction.py::get_extraction_service``)
wires a ``LazyModelResolution``; this file pins the SERVICE-side lazy
contract:

- no resolution at construction,
- exactly one resolve at first use, idempotent afterwards,
- ``ConfigurationError`` propagates un-swallowed from the entry point
  (RULE-11 — AI-mandatory endpoint), with the ownership gate running
  FIRST (gates stay ahead of resolution),
- the resolved triple reaches the invocation assembly unchanged — the
  eager factory applied no sampling overrides, so none appear (WHAT
  unchanged, only WHEN).

Mirrors ``tests/unit/api/generation/test_name_service_lazy_resolution.py``
(ADR-086 L14 precedent).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from narrare.kb.extraction_service import ExtractionService
from narrare_core.llm.model_config import ResolvedModelConfig
from narrare_core.llm.model_routing import ResolvedModel
from narrare_core.shared.errors import ConfigurationError

from ._extraction_helpers import (
    FakeChapterRepo,
    FakeComposer,
    FakeKBRepo,
    FakeModelRegistry,
    make_chapter,
    make_extraction_output,
    permissive_novel_gate,
)

if TYPE_CHECKING:
    from narrare._app.dependencies_services import ModelResolution
    from narrare.chapters.contracts import ChapterRepositoryProtocol
    from narrare.kb.contracts import KBRepositoryProtocol
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts.composer import PromptComposer


class _CountingResolution:
    """Fake ModelResolution — counts resolve() calls, never caches.

    Exposes the service-level lazy seam (ADR-086): the service must call
    ``resolve()`` exactly once (first use), never at construction.
    """

    def __init__(self, model: ResolvedModel) -> None:
        self._model = model
        self.calls = 0

    async def resolve(self) -> ResolvedModel:
        self.calls += 1
        return self._model


class _RaisingResolution:
    """Fake ModelResolution — the cascade finds no configured provider."""

    async def resolve(self) -> ResolvedModel:
        raise ConfigurationError(
            "No AI provider configured.",
            code="NO_AI_PROVIDER",
        )


def _resolved_model(
    config: ResolvedModelConfig | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> ResolvedModel:
    """A fixed model triple, as the routing cascade would return it."""
    return ResolvedModel(
        config=config or ResolvedModelConfig(provider_name="test", model_id="test-model"),
        api_key=api_key,
        base_url=base_url,
        source="unit-test",
    )


def _make_service(
    model_resolution: ModelResolution,
    registry: FakeModelRegistry | None = None,
    composer: FakeComposer | None = None,
    chapter: object | None = None,
) -> ExtractionService:
    """Build an ExtractionService with the lazy seam injected.

    ``chapter``, when given, is served by the fake chapter repo so the
    entry point flows past the content load into the invocation assembly.
    """
    chapter_repo = FakeChapterRepo()
    if chapter is not None:
        chapter_repo.get_by_id.return_value = chapter
    return ExtractionService(
        registry=cast("ModelRegistry", registry or FakeModelRegistry()),
        model_resolution=model_resolution,
        chapter_repo=cast("ChapterRepositoryProtocol", chapter_repo),
        kb_repo=cast("KBRepositoryProtocol", FakeKBRepo()),
        composer=cast("PromptComposer", composer or FakeComposer()),
        novel_repo=permissive_novel_gate(),
    )


class TestLazyResolutionContract:
    """ADR-086 lazy resolution at the ExtractionService boundary."""

    async def test_no_resolution_at_construction(self) -> None:
        """Construction must not touch the routing cascade."""
        counting = _CountingResolution(_resolved_model())

        _make_service(counting)

        assert counting.calls == 0

    async def test_ensure_resolved_resolves_once_and_is_idempotent(self) -> None:
        """First use resolves exactly once; repeat calls hit the cache."""
        counting = _CountingResolution(_resolved_model())
        service = _make_service(counting)

        first = await service.ensure_resolved()
        second = await service.ensure_resolved()

        assert counting.calls == 1
        assert first is second

    async def test_extract_from_chapter_resolves_exactly_once(self) -> None:
        """The entry point is the first-use seam — one resolve per service."""
        counting = _CountingResolution(_resolved_model())
        chapter = make_chapter()
        service = _make_service(counting, chapter=chapter)

        with patch("narrare.kb.extraction_service.ExtractionAgent") as mock_agent_cls:
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_extraction_output())
            mock_agent_cls.return_value = mock_agent

            await service.extract_from_chapter(
                novel_id=uuid4(), chapter_id=chapter.id, user_id=uuid4()
            )

        assert counting.calls == 1

    async def test_resolver_configuration_error_propagates_un_swallowed(self) -> None:
        """RULE-11 / ADR-086: the cascade's ``ConfigurationError``
        (unconfigured provider) propagates from the entry point — the
        service never swallows it (AI-mandatory endpoint). The ownership
        gate runs FIRST and passes (permissive repo), so the error comes
        from resolution, proving gates stay ahead of resolution."""

        service = _make_service(_RaisingResolution())

        with pytest.raises(ConfigurationError):
            await service.extract_from_chapter(
                novel_id=uuid4(), chapter_id=uuid4(), user_id=uuid4()
            )

    async def test_resolved_triple_flows_into_prepare_unchanged(self) -> None:
        """Timing-only invariant: the eager factory passed
        ``resolved.config`` + credentials into the invocation assembly
        verbatim — the lazy service passes the SAME values (no sampling
        overrides exist for ``KB_EXTRACT``)."""
        resolved_config = ResolvedModelConfig(
            provider_name="zai",
            model_id="glm-4.7",
            temperature=0.7,
            max_tokens=4096,
        )
        registry = FakeModelRegistry()
        counting = _CountingResolution(_resolved_model(resolved_config, api_key="sk-user-key"))
        chapter = make_chapter()
        service = _make_service(counting, registry=registry, chapter=chapter)

        with patch("narrare.kb.extraction_service.ExtractionAgent") as mock_agent_cls:
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_extraction_output())
            mock_agent_cls.return_value = mock_agent

            await service.extract_from_chapter(
                novel_id=uuid4(), chapter_id=chapter.id, user_id=uuid4()
            )

        # FakePrepareMixin threads the triple from prepare() into
        # get_model() — the registry seam where consumption lands.
        call = registry.get_model.await_args
        assert call is not None
        assert call.args[0] is resolved_config
        assert call.kwargs["api_key"] == "sk-user-key"
