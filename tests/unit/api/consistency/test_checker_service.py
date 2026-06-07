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
from narrare_core.prompts import PromptComposer, PromptRegistry
from narrare_core.shared.errors import NotFoundError, PromptNotFoundError
from tests.fakes import FakeChapterRepository, FakeNovelRepository
from tests.unit.api._test_helpers import make_chapter, make_kb_entry, make_novel, seed_repos


class _RegistryProto(Protocol):
    async def get_model(self, config: object) -> object: ...


def _output(**kw) -> ConsistencyOutput:
    defaults: dict[str, Any] = {
        "issues": [],
        "overall_assessment": "No issues.",
        "checked_types": [ConsistencyCheckType.CHARACTER],
    }
    defaults.update(kw)
    return ConsistencyOutput(**defaults)


def _service(nr=None, cr=None, kb=None, composer=None) -> ConsistencyCheckerService:
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
        with patch("narrare.consistency.checker_service.ConsistencyAgent", return_value=agent):
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
        with patch("narrare.consistency.checker_service.ConsistencyAgent", return_value=agent):
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
        with patch("narrare.consistency.checker_service.ConsistencyAgent", return_value=agent):
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
        with patch("narrare.consistency.checker_service.ConsistencyAgent", return_value=agent):
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
        with patch("narrare.consistency.checker_service.ConsistencyAgent", return_value=agent):
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


# --- D. PromptComposer resolution ---


class TestResolveSystemPrompt:
    @pytest.mark.asyncio
    async def test_resolve_system_prompt_uses_composer(self) -> None:
        """_resolve_system_prompt returns PromptComposer output, not fallback."""
        _, _, svc = _setup()

        # Spy on composer.build to verify it's the prompt source.
        svc._composer.build = AsyncMock(
            return_value=MagicMock(spec=["system"], system="Bundled consistency prompt"),
        )

        result = await svc._resolve_system_prompt("en")

        assert result == "Bundled consistency prompt"
        svc._composer.build.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_resolve_system_prompt_correct_intent(self) -> None:
        """_resolve_system_prompt calls composer.build with CONSISTENCY intent."""
        _, _, svc = _setup()

        svc._composer.build = AsyncMock(
            return_value=MagicMock(spec=["system"], system="prompt"),
        )

        await svc._resolve_system_prompt("en")

        intent_arg = svc._composer.build.call_args[0][0]
        assert intent_arg.name == "CONSISTENCY"

    @pytest.mark.asyncio
    async def test_resolve_system_prompt_passes_language(self) -> None:
        """_resolve_system_prompt passes the language to PromptContext."""
        _, _, svc = _setup()

        svc._composer.build = AsyncMock(
            return_value=MagicMock(spec=["system"], system="prompt"),
        )

        await svc._resolve_system_prompt("de")

        ctx_arg = svc._composer.build.call_args[0][1]
        assert ctx_arg.language == "de"

    @pytest.mark.asyncio
    async def test_check_with_real_composer_uses_bundled_template_variables(self) -> None:
        """Production path routes consistency data through bundled templates."""
        novel, (ch, *_), _ = _setup()
        composer = PromptComposer(PromptRegistry())
        nr, cr = FakeNovelRepository(), FakeChapterRepository()
        seed_repos(novel, ch, novel_repo=nr, chapter_repo=cr)
        svc = _service(nr=nr, cr=cr, composer=composer)

        agent = AsyncMock(run=AsyncMock(return_value=_output()))
        with patch(
            "narrare.consistency.checker_service.ConsistencyAgent", return_value=agent
        ) as MockAgent:
            await svc.check(
                novel_id=novel.id,
                user_id=novel.user_id,
                request=ConsistencyRequest(
                    chapter_ids=[ch.id], check_types=[ConsistencyCheckType.CHARACTER]
                ),
            )

        system_prompt = MockAgent.call_args.kwargs["system_prompt"]
        assert "You are a consistency checker" in system_prompt
        assert ch.content in system_prompt
        agent_prompt = agent.run.call_args.kwargs["prompt"]
        assert "Analyze the chapters" not in agent_prompt
        assert "Return structured findings" not in agent_prompt

    @pytest.mark.asyncio
    async def test_check_when_prompt_missing_propagates_typed_error(self) -> None:
        """Missing Composer templates are not replaced with inline fallback bodies."""
        novel, (ch, *_), _ = _setup()
        composer = AsyncMock()
        composer.build = AsyncMock(side_effect=PromptNotFoundError("analysis", "en", "consistency"))
        nr, cr = FakeNovelRepository(), FakeChapterRepository()
        seed_repos(novel, ch, novel_repo=nr, chapter_repo=cr)
        svc = _service(nr=nr, cr=cr, composer=composer)

        with (
            patch("narrare.consistency.checker_service.ConsistencyAgent") as MockAgent,
            pytest.raises(PromptNotFoundError),
        ):
            await svc.check(
                novel_id=novel.id,
                user_id=novel.user_id,
                request=ConsistencyRequest(chapter_ids=[ch.id]),
            )

        MockAgent.assert_not_called()


# --- C. Error cases ---


class TestCheckErrors:
    @pytest.mark.asyncio
    async def test_novel_not_found_raises(self) -> None:
        with pytest.raises(NotFoundError, match="Novel"):
            await _service().check(novel_id=uuid4(), user_id=uuid4(), request=ConsistencyRequest())
