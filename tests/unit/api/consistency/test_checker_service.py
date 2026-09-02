"""Unit tests for ConsistencyCheckerService — check, check_chapter, errors.

No real DB, no real LLM — all dependencies are mocked per RULE-TEST-01.
"""

from __future__ import annotations

from typing import Any, Protocol
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from narrare.consistency.checker_service import ConsistencyCheckerService
from narrare.consistency.schemas import ConsistencyRequest, ConsistencyResponse
from narrare_core.agents.consistency_types import (
    ConsistencyCheckType,
    ConsistencyIssue,
    ConsistencyOutput,
    ConsistencySeverity,
)
from narrare_core.shared.errors import NotFoundError
from tests.fakes import FakeChapterRepository, FakeNovelRepository
from tests.unit.api._test_helpers import make_chapter, make_kb_entry, make_novel, seed_repos


class _RegistryProto(Protocol):
    async def get_model(
        self,
        config: object,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> object: ...


def _output(**kw) -> ConsistencyOutput:
    defaults: dict[str, Any] = {
        "issues": [],
        "overall_assessment": "No issues.",
        "checked_types": [ConsistencyCheckType.CHARACTER],
    }
    defaults.update(kw)
    return ConsistencyOutput(**defaults)


def _service(
    nr=None,
    cr=None,
    kb=None,
    composer=None,
    rel=None,
) -> ConsistencyCheckerService:
    from narrare_core.llm import ResolvedModelConfig

    kb = kb or AsyncMock(list_entries=AsyncMock(return_value=([], 0)))
    registry = MagicMock(spec=_RegistryProto)
    registry.get_model = AsyncMock(return_value=object())
    composed = MagicMock(spec=["system", "user"])
    composed.system = "Test prompt"
    composed.user = ""
    if composer is None:
        composer = AsyncMock()
        composer.build = AsyncMock(return_value=composed)

    # Timeline repo — returns empty list by default (graceful degradation)
    timeline_repo = AsyncMock()
    timeline_repo.list_by_novel = AsyncMock(return_value=[])

    return ConsistencyCheckerService(
        chapter_repo=cr or FakeChapterRepository(),
        novel_repo=nr or FakeNovelRepository(),
        kb_repo=kb,
        timeline_repo=timeline_repo,
        registry=registry,
        config=ResolvedModelConfig(
            provider_name="test", model_id="test", temperature=0.5, max_tokens=2048
        ),
        composer=composer,
        relationship_repo=rel,
    )


def _setup(novel=None, chapters=None):
    """Seed repos and return (novel, chapters, service)."""
    novel = novel or make_novel()
    chapters = chapters or [make_chapter(novel_id=novel.id)]
    nr, cr = FakeNovelRepository(), FakeChapterRepository()
    seed_repos(novel, *chapters, novel_repo=nr, chapter_repo=cr)
    return novel, chapters, _service(nr, cr)


# --- A. check — happy path ---


class TestCheck:
    @pytest.mark.asyncio
    async def test_check_returns_response(self) -> None:
        novel, (ch, *_), svc = _setup()
        agent = AsyncMock(run=AsyncMock(return_value=_output()))
        with patch("narrare.consistency.legacy_check_runner.ConsistencyAgent", return_value=agent):
            result = await svc.check(
                novel_id=novel.id,
                user_id=novel.user_id,
                request=ConsistencyRequest(
                    chapter_ids=[ch.id], check_types=[ConsistencyCheckType.CHARACTER]
                ),
            )
        assert isinstance(result, ConsistencyResponse)
        assert result.novel_id == novel.id
        assert result.overall_assessment == "No issues."

    @pytest.mark.asyncio
    async def test_check_with_empty_chapter_ids_fetches_all(self) -> None:
        novel, chapters, svc = _setup(
            chapters=[make_chapter(novel_id=None), make_chapter(novel_id=None)]
        )
        novel, chapters, svc = _setup(
            novel=novel, chapters=[make_chapter(novel_id=novel.id), make_chapter(novel_id=novel.id)]
        )
        agent = AsyncMock(run=AsyncMock(return_value=_output()))
        with patch("narrare.consistency.legacy_check_runner.ConsistencyAgent", return_value=agent):
            result = await svc.check(
                novel_id=novel.id, user_id=novel.user_id, request=ConsistencyRequest(chapter_ids=[])
            )
        assert set(result.chapter_ids) == {chapters[0].id, chapters[1].id}

    @pytest.mark.asyncio
    async def test_check_with_specific_chapter_ids(self) -> None:
        novel, chapters, svc = _setup(
            chapters=[make_chapter(novel_id=None), make_chapter(novel_id=None)]
        )
        novel, chapters, svc = _setup(
            novel=novel, chapters=[make_chapter(novel_id=novel.id), make_chapter(novel_id=novel.id)]
        )
        agent = AsyncMock(run=AsyncMock(return_value=_output()))
        with patch("narrare.consistency.legacy_check_runner.ConsistencyAgent", return_value=agent):
            result = await svc.check(
                novel_id=novel.id,
                user_id=novel.user_id,
                request=ConsistencyRequest(chapter_ids=[chapters[0].id]),
            )
        assert result.chapter_ids == [chapters[0].id]

    @pytest.mark.asyncio
    async def test_check_includes_kb_entities(self) -> None:
        novel, (ch, *_), svc = _setup()
        entry = make_kb_entry(novel_id=novel.id)
        kb = AsyncMock(list_entries=AsyncMock(return_value=([entry], 1)))
        svc = _service(kb=kb)
        # Re-seed repos
        nr, cr = FakeNovelRepository(), FakeChapterRepository()
        seed_repos(novel, ch, novel_repo=nr, chapter_repo=cr)
        svc._novel_repo = nr
        svc._chapter_repo = cr

        agent = AsyncMock(run=AsyncMock(return_value=_output()))
        with patch("narrare.consistency.legacy_check_runner.ConsistencyAgent", return_value=agent):
            await svc.check(
                novel_id=novel.id,
                user_id=novel.user_id,
                request=ConsistencyRequest(chapter_ids=[ch.id], include_kb=True),
            )
        kb.list_entries.assert_awaited_once()


# --- B. check_chapter ---


class TestCheckChapter:
    @pytest.mark.asyncio
    async def test_check_single_chapter(self) -> None:
        novel, (ch, *_), svc = _setup()
        issue = ConsistencyIssue(
            check_type=ConsistencyCheckType.CHARACTER,
            severity=ConsistencySeverity.WARNING,
            description="Eye color changes.",
            locations=["Ch 1", "Ch 3"],
            conflicting_facts=["blue", "brown"],
            confidence=0.85,
        )
        agent = AsyncMock(run=AsyncMock(return_value=_output(issues=[issue])))
        with patch("narrare.consistency.legacy_check_runner.ConsistencyAgent", return_value=agent):
            result = await svc.check_chapter(
                novel_id=novel.id,
                chapter_id=ch.id,
                user_id=novel.user_id,
                request=ConsistencyRequest(),
            )
        assert isinstance(result, ConsistencyResponse)
        assert result.chapter_ids == [ch.id]
        assert result.total_issues == 1
        assert result.warning_count == 1


# --- C. Error cases ---


class TestCheckErrors:
    @pytest.mark.asyncio
    async def test_novel_not_found_raises(self) -> None:
        with pytest.raises(NotFoundError, match="Novel"):
            await _service().check(novel_id=uuid4(), user_id=uuid4(), request=ConsistencyRequest())


# --- D. Relationship repo wiring (CR-AUFG-03-01) ---


class TestRelationshipRepoWiring:
    """ConsistencyCheckerService accepts and forwards relationship_repo."""

    def test_service_stores_relationship_repo(self) -> None:
        """relationship_repo passed at construction is stored on the service."""
        rel_repo = AsyncMock()
        rel_repo.get_relationships_with_names = AsyncMock(return_value=[])
        svc = _service(rel=rel_repo)
        assert svc._relationship_repo is rel_repo

    def test_service_defaults_relationship_repo_to_none(self) -> None:
        """Without relationship_repo, the attribute is None (backward compatible)."""
        svc = _service()
        assert svc._relationship_repo is None

    @pytest.mark.asyncio
    async def test_check_forwards_relationship_repo_when_include_kb(self) -> None:
        """check() with include_kb queries the relationship repo (FIND-001)."""
        from narrare.kb.relationship_repository import RelationshipEdgeRow

        novel, (ch, *_), svc = _setup()
        rel_repo = AsyncMock()
        rel_repo.get_relationships_with_names = AsyncMock(
            return_value=[
                RelationshipEdgeRow("Aria", "enemy_of", "feud", "Malachai", "directed"),
            ]
        )
        svc._relationship_repo = rel_repo

        agent = AsyncMock(run=AsyncMock(return_value=_output()))
        with patch("narrare.consistency.legacy_check_runner.ConsistencyAgent", return_value=agent):
            await svc.check(
                novel_id=novel.id,
                user_id=novel.user_id,
                request=ConsistencyRequest(chapter_ids=[ch.id], include_kb=True),
            )
        rel_repo.get_relationships_with_names.assert_awaited_once()
