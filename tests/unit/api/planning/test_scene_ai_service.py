"""SceneAIService happy-path behaviour tests (PLAN-001 T8).

Draft/refine through the REAL ``ScenePlanAgent`` (FunctionModel-backed
seam — no LLM, RULE-01b): governed-mode composition, XML-wrapped run
prompts, prepared-triple plumbing, output mapping. Guards, graceful
degradation, zero-write and mapping edges live in
``test_scene_ai_guards.py``; shared fakes in
``_scene_ai_test_helpers.py``.
"""

from __future__ import annotations

import pytest

from narrare_core.llm.intents import LLMIntent
from tests.fakes import FakeChapterRepository, FakeNovelRepository
from tests.unit.api.planning._scene_ai_test_helpers import (
    _PROPOSED_SCENE,
    _AiWorld,
    _draft_request,
    _refine_request,
    _refine_response,
)


@pytest.fixture
def novel_repo() -> FakeNovelRepository:
    return FakeNovelRepository()


@pytest.fixture
def chapter_repo() -> FakeChapterRepository:
    return FakeChapterRepository()


class TestDraftHappyPath:
    async def test_draft_returns_mapped_proposals_without_ids(
        self,
        novel_repo: FakeNovelRepository,
        chapter_repo: FakeChapterRepository,
    ) -> None:
        world = _AiWorld(novel_repo, chapter_repo)
        service = world.service()

        response = await service.draft(
            world.chapter_id, _draft_request(), world.user_id, novel_id=world.novel_id
        )

        assert response.ai_unavailable is False
        assert len(response.proposals) == 1
        proposal = response.proposals[0]
        assert proposal.title == "The Ambush at the Gate"
        assert proposal.purpose == "John must reach the gate before dawn."
        # Proposals carry NO id (client assigns UUIDs on insert — spec §5.2).
        assert "id" not in proposal.model_dump()
        # Name-only hybrid refs: the AI cannot know KB ids.
        assert proposal.pov_character_ref is not None
        assert proposal.pov_character_ref.name == "John Smith"
        assert proposal.pov_character_ref.id is None
        assert proposal.location_ref is not None
        assert proposal.location_ref.name == "The Castle"
        assert proposal.present_characters[0].name == "John Smith"
        assert proposal.present_characters[0].goal == "wants to warn the guard"
        assert proposal.beats == ["John reaches the gate", "The horn sounds"]

    async def test_draft_composes_governed_mode_and_binds_system_prompt(
        self,
        novel_repo: FakeNovelRepository,
        chapter_repo: FakeChapterRepository,
    ) -> None:
        world = _AiWorld(novel_repo, chapter_repo)
        service = world.service()

        await service.draft(
            world.chapter_id, _draft_request(), world.user_id, novel_id=world.novel_id
        )

        assert world.composer.build_calls == [(LLMIntent.PLAN, "scene_plan_draft")]
        # The composed system prompt reached the agent as the system channel;
        # the run prompt stays the XML-wrapped data (channel separation).
        assert world.registry.run_prompts != []
        assert not world.registry.run_prompts[0].startswith("SYSTEM[")

    async def test_draft_run_prompt_carries_xml_wrapped_chapter_context(
        self,
        novel_repo: FakeNovelRepository,
        chapter_repo: FakeChapterRepository,
    ) -> None:
        world = _AiWorld(novel_repo, chapter_repo)
        service = world.service()

        await service.draft(
            world.chapter_id, _draft_request(), world.user_id, novel_id=world.novel_id
        )

        prompt = world.registry.run_prompts[0]
        assert "<chapter_context>" in prompt
        assert "</chapter_context>" in prompt
        assert "<instruction>" in prompt
        assert "Plan 3 tense scenes." in prompt
        assert "Escape sequence." in prompt
        assert "John races to the gate." in prompt
        assert "Prev: John flees. Next: The gate falls." in prompt

    async def test_draft_resolves_lazily_exactly_once(
        self,
        novel_repo: FakeNovelRepository,
        chapter_repo: FakeChapterRepository,
    ) -> None:
        world = _AiWorld(novel_repo, chapter_repo)
        service = world.service()
        request = _draft_request()
        await service.draft(world.chapter_id, request, world.user_id, novel_id=world.novel_id)
        await service.draft(world.chapter_id, request, world.user_id, novel_id=world.novel_id)
        assert world.resolution.calls == 1
        assert world.registry.prepare_calls == 2


class TestRefineHappyPath:
    async def test_refine_returns_mapped_proposal(
        self,
        novel_repo: FakeNovelRepository,
        chapter_repo: FakeChapterRepository,
    ) -> None:
        world = _AiWorld(novel_repo, chapter_repo)
        world.registry._respond = lambda: _refine_response(_PROPOSED_SCENE)
        service = world.service()

        response = await service.refine(
            world.chapter_id, _refine_request(), world.user_id, novel_id=world.novel_id
        )

        assert response.ai_unavailable is False
        assert response.proposal is not None
        assert "id" not in response.proposal.model_dump()
        assert response.proposal.title == "The Ambush at the Gate"

    async def test_refine_composes_governed_refine_mode(
        self,
        novel_repo: FakeNovelRepository,
        chapter_repo: FakeChapterRepository,
    ) -> None:
        world = _AiWorld(novel_repo, chapter_repo)
        world.registry._respond = lambda: _refine_response(_PROPOSED_SCENE)
        service = world.service()

        await service.refine(
            world.chapter_id, _refine_request(), world.user_id, novel_id=world.novel_id
        )

        assert world.composer.build_calls == [(LLMIntent.PLAN, "scene_plan_refine")]

    async def test_refine_run_prompt_wraps_rendered_scene_and_neighbors(
        self,
        novel_repo: FakeNovelRepository,
        chapter_repo: FakeChapterRepository,
    ) -> None:
        world = _AiWorld(novel_repo, chapter_repo)
        world.registry._respond = lambda: _refine_response(_PROPOSED_SCENE)
        service = world.service()

        await service.refine(
            world.chapter_id, _refine_request(), world.user_id, novel_id=world.novel_id
        )

        prompt = world.registry.run_prompts[0]
        assert "<scene_plan>" in prompt
        assert "</scene_plan>" in prompt
        # Rendered scene block (Core renderer, spec §6.3): position header +
        # labeled sections from the carried scene.
        assert "Scene 2: The Ambush at the Gate" in prompt
        assert "Purpose: John must reach the gate before dawn." in prompt
        assert "  1. John reaches the gate" in prompt
        assert "<chapter_context>" in prompt
        assert "John flees the city." in prompt
        assert "The gate falls." in prompt
        assert "<instruction>" in prompt
        assert "Make the conflict sharper." in prompt
