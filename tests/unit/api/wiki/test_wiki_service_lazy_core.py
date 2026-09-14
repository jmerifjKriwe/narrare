"""Lazy core-service construction tests for APIWikiService (ADR-086 L30).

Split per the L08/L10/L11 convention: covers the lazy seam the wiki
migration introduced — the user plane composes the core WikiService
(per-user routing resolve + PreparedWikiAgent assembly) on FIRST AI use,
never at DI construction:

- No core-service build at construction (counting factory: 0 calls).
- First AI use builds exactly once; idempotent afterwards.
- Read-only paths never build the core service.
- Unconfigured provider -> ConfigurationError propagates un-swallowed
  (loud RULE-11 — wiki is NOT a graceful-degradation ledger entry).
- Ctor wiring: exactly one of eager core / lazy factory.
- ChapterWikiService construction defers to first chapter AI use and
  shares the lazily built core instance.

See: ADR-086 (lazy model resolution), migration plan slice B2/L30.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from narrare.wiki.service import APIWikiService
from narrare_core.shared.errors import ConfigurationError
from narrare_core.wiki.types import WikiEntityOutput
from tests.fakes import (
    FakeChapterRepository,
    FakeCoreWikiService,
    FakeKBRepository,
    FakeNovelRepository,
    FakeRelationshipRepository,
    FakeWikiRepository,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from narrare.kb.contracts import KBRepositoryProtocol, RelationshipRepositoryProtocol
    from narrare.novels.contracts import NovelRepositoryProtocol
    from narrare.wiki.repository import WikiRepository
    from narrare_core.wiki.contracts import WikiServiceProtocol

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_USER_ID = uuid.uuid4()
_NOVEL_ID = uuid.uuid4()
_ENTITY_ID = uuid.uuid4()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entity_output(**overrides: Any) -> WikiEntityOutput:
    """Create a WikiEntityOutput with test defaults."""
    return WikiEntityOutput(
        narrative_summary="A wise wizard who guards the Crystal of Eternity.",
        role_in_story="Mentor to the protagonist.",
        key_attributes=["wise", "ancient", "powerful"],
        relationships=[{"entity_id": str(uuid.uuid4()), "rel_type": "ally"}],
        character_arc="From isolation to mentorship.",
        **overrides,
    )


def _make_persisted_summary(**overrides: Any) -> dict[str, Any]:
    """Return a dict that WikiSummaryResponse.model_validate accepts."""
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    data: dict[str, Any] = {
        "id": uuid.uuid4(),
        "novel_id": _NOVEL_ID,
        "entity_id": _ENTITY_ID,
        "narrative_summary": "A wise wizard who guards the Crystal of Eternity.",
        "role_in_story": "Mentor to the protagonist.",
        "key_attributes": ["wise", "ancient", "powerful"],
        "relationships": [],
        "chapter_references": None,
        "character_arc": "From isolation to mentorship.",
        "status": "fresh",
        "version": 1,
        "generated_at": now,
        "refreshed_at": None,
    }
    data.update(overrides)
    return data


class CountingCoreFactory:
    """Fake core-service factory — counts invocations (ADR-086 seam).

    Exposes the service-level lazy seam: the user-plane service must
    invoke the factory exactly once (first AI use), never at
    construction, and cache the built core service.
    """

    def __init__(
        self,
        core: WikiServiceProtocol | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        self._core = core if core is not None else FakeCoreWikiService()
        self._error = error
        self.calls = 0

    async def __call__(self) -> WikiServiceProtocol:
        self.calls += 1
        if self._error is not None:
            raise self._error
        return self._core


def _seeded_repos(
    *,
    novel: bool = True,
    entity: bool = True,
) -> tuple[FakeWikiRepository, FakeKBRepository, FakeNovelRepository, FakeRelationshipRepository]:
    """Build the fake repo quartet with the standard seeds."""
    wiki_repo = FakeWikiRepository()
    wiki_repo.configure("upsert_summary", _make_persisted_summary())
    kb_repo = FakeKBRepository()
    novel_repo = FakeNovelRepository()
    if novel:
        from narrare.novels.models import Novel

        novel_repo.seed(Novel(id=_NOVEL_ID, user_id=_USER_ID, writing_language="en"))
    if entity:
        from narrare.kb.models import KBEntry

        kb_repo.seed(
            KBEntry(
                id=_ENTITY_ID,
                novel_id=_NOVEL_ID,
                entity_type="character",
                name="Eldrin the Wise",
                body="Eldrin is an ancient wizard.",
            )
        )
    return wiki_repo, kb_repo, novel_repo, FakeRelationshipRepository()


def _make_lazy_service(
    factory: Callable[[], Awaitable[WikiServiceProtocol]],
    *,
    chapter_repo: Any | None = None,
    system_mode: bool = False,
    wiki_repo: FakeWikiRepository | None = None,
) -> APIWikiService:
    """Build a user-plane APIWikiService wired with a lazy core factory."""
    seeded = _seeded_repos()
    if wiki_repo is None:
        wiki_repo = seeded[0]
    return APIWikiService(
        session=AsyncMock(spec=AsyncSession),
        wiki_repo=cast("WikiRepository", wiki_repo),
        kb_repo=cast("KBRepositoryProtocol", seeded[1]),
        novel_repo=cast("NovelRepositoryProtocol", seeded[2]),
        relationship_repo=cast("RelationshipRepositoryProtocol", seeded[3]),
        core_service_factory=factory,
        chapter_repo=chapter_repo,
        system_mode=system_mode,
    )


# ---------------------------------------------------------------------------
# ADR-086: lazy core-service construction at the service boundary
# ---------------------------------------------------------------------------


class TestLazyCoreServiceConstruction:
    """Core service composes on first AI use — never at construction."""

    async def test_no_core_service_build_at_construction(self) -> None:
        factory = CountingCoreFactory()
        _make_lazy_service(factory)
        assert factory.calls == 0

    async def test_ensure_core_service_builds_once_and_is_idempotent(self) -> None:
        factory = CountingCoreFactory()
        service = _make_lazy_service(factory)

        first = await service._ensure_core_service()
        second = await service._ensure_core_service()

        assert factory.calls == 1
        assert first is second

    async def test_generate_entity_summary_builds_core_lazily_exactly_once(self) -> None:
        core = FakeCoreWikiService()
        core.configure("generate_entity_summary", _make_entity_output())
        factory = CountingCoreFactory(core)
        service = _make_lazy_service(factory)

        await service.generate_entity_summary(_ENTITY_ID, _NOVEL_ID, _USER_ID)
        await service.generate_entity_summary(_ENTITY_ID, _NOVEL_ID, _USER_ID)

        assert factory.calls == 1
        assert service._core is core
        assert core.call_count("generate_entity_summary") == 2

    async def test_read_only_paths_never_build_core(self) -> None:
        factory = CountingCoreFactory()
        service = _make_lazy_service(factory)

        await service.get_summaries(_NOVEL_ID, _USER_ID)
        await service.get_wiki_index(_NOVEL_ID, _USER_ID)
        await service.mark_all_stale(_NOVEL_ID, _USER_ID)

        assert factory.calls == 0

    async def test_refresh_fresh_short_circuit_never_builds_core(self) -> None:
        """Without force, a fresh summary short-circuits before any AI use."""
        factory = CountingCoreFactory()
        wiki_repo, _kb, _novel, _rel = _seeded_repos()
        from .conftest import _make_wiki_summary_row

        wiki_repo.configure("get_summary", _make_wiki_summary_row(status="fresh"))
        service = _make_lazy_service(factory, wiki_repo=wiki_repo)

        result = await service.refresh_summary(_ENTITY_ID, _NOVEL_ID, _USER_ID, force=False)

        assert result.status == "fresh"
        assert factory.calls == 0


# ---------------------------------------------------------------------------
# RULE-11: unconfigured provider propagates loudly (wiki is AI-mandatory)
# ---------------------------------------------------------------------------


class TestLoudPropagation:
    """ConfigurationError from the routing cascade is never swallowed."""

    async def test_resolver_configuration_error_propagates_from_generate(self) -> None:
        factory = CountingCoreFactory(
            error=ConfigurationError("No AI provider configured.", code="NO_AI_PROVIDER")
        )
        service = _make_lazy_service(factory)

        with pytest.raises(ConfigurationError):
            await service.generate_entity_summary(_ENTITY_ID, _NOVEL_ID, _USER_ID)

    async def test_resolver_configuration_error_propagates_from_refresh(self) -> None:
        factory = CountingCoreFactory(
            error=ConfigurationError("No AI provider configured.", code="NO_AI_PROVIDER")
        )
        service = _make_lazy_service(factory)

        with pytest.raises(ConfigurationError):
            await service.refresh_summary(_ENTITY_ID, _NOVEL_ID, _USER_ID, force=True)


# ---------------------------------------------------------------------------
# Ctor wiring validation
# ---------------------------------------------------------------------------


class TestCtorWiringValidation:
    """Exactly one of eager core service / lazy factory is required."""

    async def test_both_eager_and_factory_rejected(self) -> None:
        wiki_repo, kb_repo, novel_repo, rel_repo = _seeded_repos()
        with pytest.raises(ValueError, match="Exactly one"):
            APIWikiService(
                session=AsyncMock(spec=AsyncSession),
                wiki_repo=wiki_repo,
                kb_repo=kb_repo,
                novel_repo=novel_repo,
                relationship_repo=rel_repo,
                core_wiki_service=FakeCoreWikiService(),
                core_service_factory=CountingCoreFactory(),
            )

    async def test_neither_eager_nor_factory_rejected(self) -> None:
        wiki_repo, kb_repo, novel_repo, rel_repo = _seeded_repos()
        with pytest.raises(ValueError, match="Exactly one"):
            APIWikiService(
                session=AsyncMock(spec=AsyncSession),
                wiki_repo=wiki_repo,
                kb_repo=kb_repo,
                novel_repo=novel_repo,
                relationship_repo=rel_repo,
            )


# ---------------------------------------------------------------------------
# ChapterWikiService lazy wiring (user plane)
# ---------------------------------------------------------------------------


class TestChapterServiceLazyWiring:
    """Chapter service composes at first chapter AI use, sharing the core."""

    async def test_chapter_service_built_on_first_use_shares_core(self) -> None:
        factory = CountingCoreFactory()
        service = _make_lazy_service(factory, chapter_repo=FakeChapterRepository())
        assert service._chapter_wiki_service is None

        result = await service.generate_chapter_summary(uuid.uuid4(), _NOVEL_ID, _USER_ID)

        assert result is None  # chapter unknown — but the wiring ran
        assert service._chapter_wiki_service is not None
        assert service._chapter_wiki_service._core is service._core
        assert factory.calls == 1

    async def test_chapter_service_inherits_system_mode(self) -> None:
        factory = CountingCoreFactory()
        service = _make_lazy_service(
            factory, chapter_repo=FakeChapterRepository(), system_mode=True
        )

        await service.generate_chapter_summary(uuid.uuid4(), _NOVEL_ID, _USER_ID)

        assert service._chapter_wiki_service is not None
        assert service._chapter_wiki_service._system_mode is True

    async def test_chapter_not_configured_degradation_preserved(self) -> None:
        """No chapter repo -> 'not configured' degradation, no core build."""
        factory = CountingCoreFactory()
        service = _make_lazy_service(factory, chapter_repo=None)

        result = await service.generate_chapter_summary(uuid.uuid4(), _NOVEL_ID, _USER_ID)

        assert result is None
        assert factory.calls == 0
