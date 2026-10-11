"""SceneAIService guards, graceful degradation, zero-write tests (T8).

Contract conformance (RULE-03), no-provider degradation (HTTP 200
``ai_unavailable=True``, no raise), uid-scoped ownership guards
(gate-before-resolution), the ZERO-repo-write contract, and mapping
edges. Happy paths live in ``test_scene_ai_service.py``; shared fakes in
``_scene_ai_test_helpers.py``.
"""

from __future__ import annotations

import uuid

import pytest

from narrare_core.shared.errors import NotFoundError
from tests.factories import make_chapter
from tests.fakes import FakeChapterRepository, FakeNovelRepository, FakeScenePlanRepository
from tests.unit.api.planning._scene_ai_test_helpers import (
    _PROPOSED_SCENE,
    RecordingResolution,
    _AiWorld,
    _draft_request,
    _draft_response,
    _refine_request,
    _refine_response,
)


@pytest.fixture
def novel_repo() -> FakeNovelRepository:
    return FakeNovelRepository()


@pytest.fixture
def chapter_repo() -> FakeChapterRepository:
    return FakeChapterRepository()


@pytest.fixture
def scene_repo() -> FakeScenePlanRepository:
    return FakeScenePlanRepository()


class TestContractConformance:
    def test_service_satisfies_scene_ai_service_protocol(self) -> None:
        """SceneAIService is a structural SceneAIServiceProtocol member."""
        from narrare.planning.contracts import SceneAIServiceProtocol

        world = _AiWorld(FakeNovelRepository(), FakeChapterRepository(), FakeScenePlanRepository())
        service = world.service()
        assert isinstance(service, SceneAIServiceProtocol)


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


class TestGracefulNoProvider:
    async def test_draft_without_provider_returns_ai_unavailable(
        self,
        novel_repo: FakeNovelRepository,
        chapter_repo: FakeChapterRepository,
        scene_repo: FakeScenePlanRepository,
    ) -> None:
        world = _AiWorld(novel_repo, chapter_repo, scene_repo)
        world.resolution = RecordingResolution(None)
        service = world.service()

        response = await service.draft(
            world.chapter_id, _draft_request(), world.user_id, novel_id=world.novel_id
        )

        assert response.ai_unavailable is True
        assert response.proposals == []

    async def test_draft_without_provider_never_touches_composer_or_registry(
        self,
        novel_repo: FakeNovelRepository,
        chapter_repo: FakeChapterRepository,
        scene_repo: FakeScenePlanRepository,
    ) -> None:
        world = _AiWorld(novel_repo, chapter_repo, scene_repo)
        world.resolution = RecordingResolution(None)
        service = world.service()

        await service.draft(
            world.chapter_id, _draft_request(), world.user_id, novel_id=world.novel_id
        )

        assert world.composer.build_calls == []
        assert world.registry.prepare_calls == 0

    async def test_refine_without_provider_returns_ai_unavailable(
        self,
        novel_repo: FakeNovelRepository,
        chapter_repo: FakeChapterRepository,
        scene_repo: FakeScenePlanRepository,
    ) -> None:
        world = _AiWorld(novel_repo, chapter_repo, scene_repo)
        world.resolution = RecordingResolution(None)
        service = world.service()

        response = await service.refine(
            world.chapter_id, _refine_request(), world.user_id, novel_id=world.novel_id
        )

        assert response.ai_unavailable is True
        assert response.proposal is None


class TestOwnershipGuards:
    async def test_draft_foreign_novel_returns_404_before_resolution(
        self,
        novel_repo: FakeNovelRepository,
        chapter_repo: FakeChapterRepository,
        scene_repo: FakeScenePlanRepository,
    ) -> None:
        world = _AiWorld(novel_repo, chapter_repo, scene_repo)
        service = world.service()

        with pytest.raises(NotFoundError):
            await service.draft(
                world.chapter_id,
                _draft_request(),
                world.user_id,
                novel_id=world.foreign_novel_id,
            )
        # Gate-before-resolution: the routing cascade never ran.
        assert world.resolution.calls == 0
        assert world.composer.build_calls == []

    async def test_draft_unknown_novel_returns_404(
        self,
        novel_repo: FakeNovelRepository,
        chapter_repo: FakeChapterRepository,
        scene_repo: FakeScenePlanRepository,
    ) -> None:
        world = _AiWorld(novel_repo, chapter_repo, scene_repo)
        service = world.service()

        with pytest.raises(NotFoundError):
            await service.draft(
                world.chapter_id, _draft_request(), world.user_id, novel_id=uuid.uuid4()
            )

    async def test_draft_chapter_of_other_novel_returns_404(
        self,
        novel_repo: FakeNovelRepository,
        chapter_repo: FakeChapterRepository,
        scene_repo: FakeScenePlanRepository,
    ) -> None:
        world = _AiWorld(novel_repo, chapter_repo, scene_repo)
        foreign_chapter = make_chapter(id=uuid.uuid4(), novel_id=world.foreign_novel_id)
        chapter_repo.seed(foreign_chapter)
        service = world.service()

        with pytest.raises(NotFoundError):
            await service.draft(
                foreign_chapter.id, _draft_request(), world.user_id, novel_id=world.novel_id
            )
        assert world.resolution.calls == 0

    async def test_refine_foreign_novel_returns_404(
        self,
        novel_repo: FakeNovelRepository,
        chapter_repo: FakeChapterRepository,
        scene_repo: FakeScenePlanRepository,
    ) -> None:
        world = _AiWorld(novel_repo, chapter_repo, scene_repo)
        service = world.service()

        with pytest.raises(NotFoundError):
            await service.refine(
                world.chapter_id,
                _refine_request(),
                world.user_id,
                novel_id=world.foreign_novel_id,
            )


# ---------------------------------------------------------------------------
# ZERO DB writes (spec §5.2 — generator only)
# ---------------------------------------------------------------------------

_READ_METHODS = frozenset(
    {
        # novel repo
        "get",
        "get_by_id",
        "list_by_user",
        # chapter repo
        "list_by_novel",
        "max_position",
        "get_latest_version_number",
        "list_versions",
        "get_version",
        # scene repo
        "list_by_chapter",
    }
)


class TestZeroWrites:
    async def test_draft_and_refine_perform_zero_repo_writes(
        self,
        novel_repo: FakeNovelRepository,
        chapter_repo: FakeChapterRepository,
        scene_repo: FakeScenePlanRepository,
    ) -> None:
        world = _AiWorld(novel_repo, chapter_repo, scene_repo)
        service = world.service()

        await service.draft(
            world.chapter_id, _draft_request(), world.user_id, novel_id=world.novel_id
        )
        world.registry._respond = lambda: _refine_response(_PROPOSED_SCENE)
        await service.refine(
            world.chapter_id, _refine_request(), world.user_id, novel_id=world.novel_id
        )

        for repo in (novel_repo, chapter_repo, scene_repo):
            writes = [call.method for call in repo.calls if call.method not in _READ_METHODS]
            assert writes == [], f"AI path performed repo writes: {writes}"

    async def test_scene_repo_is_never_written_even_on_graceful_path(
        self,
        novel_repo: FakeNovelRepository,
        chapter_repo: FakeChapterRepository,
        scene_repo: FakeScenePlanRepository,
    ) -> None:
        world = _AiWorld(novel_repo, chapter_repo, scene_repo)
        world.resolution = RecordingResolution(None)
        service = world.service()

        await service.draft(
            world.chapter_id, _draft_request(), world.user_id, novel_id=world.novel_id
        )

        assert scene_repo.call_count("bulk_replace") == 0


# ---------------------------------------------------------------------------
# Misc mapping edges
# ---------------------------------------------------------------------------


class TestRunPromptEmptyBlockDegrade:
    """``_xml_block`` omits blocks whose content is entirely empty — a bare
    draft (no context, no instruction) produces no empty XML wrappers;
    populated content keeps the exact wrapper shape (FU5)."""

    def test_draft_prompt_with_fully_empty_request_contains_no_wrappers(self) -> None:
        from narrare.planning._scene_ai_support import build_draft_run_prompt
        from narrare.planning.schemas_scenes import SceneDraftRequest

        prompt = build_draft_run_prompt(SceneDraftRequest())

        assert prompt == ""
        assert "<chapter_context>" not in prompt
        assert "<instruction>" not in prompt

    def test_draft_prompt_with_empty_context_keeps_instruction_block(self) -> None:
        from narrare.planning._scene_ai_support import build_draft_run_prompt
        from narrare.planning.schemas_scenes import SceneDraftRequest

        prompt = build_draft_run_prompt(SceneDraftRequest(instruction="Plan 3 tense scenes."))

        assert prompt == "<instruction>\nPlan 3 tense scenes.\n</instruction>"
        assert "<chapter_context>" not in prompt

    def test_draft_prompt_populated_context_keeps_exact_wrapper_shape(self) -> None:
        from narrare.planning._scene_ai_support import build_draft_run_prompt
        from narrare.planning.schemas_scenes import SceneDraftRequest

        prompt = build_draft_run_prompt(
            SceneDraftRequest(
                structure_type="three_act",
                outline_notes="Escape sequence.",
                instruction="Plan 3 tense scenes.",
                scene_count=3,
            )
        )

        assert prompt == (
            "<chapter_context>\n"
            "Structure type: three_act\n"
            "Outline notes: Escape sequence.\n"
            "Scene count: 3\n"
            "</chapter_context>\n"
            "<instruction>\n"
            "Plan 3 tense scenes.\n"
            "</instruction>"
        )

    def test_refine_prompt_with_empty_context_omits_chapter_context_block(self) -> None:
        from narrare.planning._scene_ai_support import build_refine_run_prompt
        from tests.unit.api.planning._scene_ai_test_helpers import _payload_scene

        prompt = build_refine_run_prompt(
            _refine_request(
                scene=_payload_scene(),
                prev_scene_summary="",
                next_scene_summary="",
                chapter_summary="",
                instruction="",
            )
        )

        assert "<scene_plan>" in prompt
        assert "</scene_plan>" in prompt
        assert "<chapter_context>" not in prompt
        assert "<instruction>" not in prompt


class TestProposalMapping:
    async def test_empty_names_map_to_none_refs(
        self,
        novel_repo: FakeNovelRepository,
        chapter_repo: FakeChapterRepository,
        scene_repo: FakeScenePlanRepository,
    ) -> None:
        world = _AiWorld(novel_repo, chapter_repo, scene_repo)
        world.registry._respond = lambda: _draft_response(
            [{**_PROPOSED_SCENE, "pov_character_name": "", "location_name": ""}]
        )
        service = world.service()

        response = await service.draft(
            world.chapter_id, _draft_request(), world.user_id, novel_id=world.novel_id
        )

        proposal = response.proposals[0]
        assert proposal.pov_character_ref is None
        assert proposal.location_ref is None
