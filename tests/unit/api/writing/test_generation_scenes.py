"""Unit tests for structured scene input on the generation path (PLAN-001 T10).

Covers spec §8.2 write integration: ``GenerateRequest.scenes`` (optional,
identity-free), the JSONB payload/row translation used between POST and
stream, repository persistence, and ``build_pipeline_request`` threading
the persisted rows into the Core ``SceneSpec`` tuple. Scene-less requests
must keep the exact legacy behavior (``scenes=None`` end to end).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from narrare.writing.models import GenerationRequest
from narrare.writing.repository import GenerationRepository
from narrare.writing.schemas import GenerateRequest, GenerationModeEnum
from narrare_core.shared.errors import ValidationError

if TYPE_CHECKING:
    from narrare.writing.service import WritingService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SCENE_DICT: dict[str, Any] = {
    "title": "The Warning",
    "pov_character_name": "John",
    "location_name": "Gatehouse",
    "present_characters": [{"name": "John", "goal": "warn the guard"}],
    "purpose": "Raise the stakes",
    "conflict": "The guard refuses to listen",
    "resolution": "John forces his way in",
    "beats": ["John arrives", "Guard refuses"],
    "status": "in_progress",
}


def _make_request(**overrides: Any) -> GenerateRequest:
    defaults: dict[str, Any] = {
        "mode": GenerationModeEnum.SCENE_BY_SCENE,
        "prompt": "Write it",
        "scenes": [_SCENE_DICT],
    }
    defaults.update(overrides)
    # Dict-splat construction (house pattern, test_writing_service.py):
    # exercises the real pydantic validation without over-constraining.
    return GenerateRequest(**defaults)


def _make_mock_session() -> AsyncMock:
    """Mock AsyncSession with a chainable execute() (test_repository pattern)."""
    session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock(spec=["scalar_one_or_none", "one", "first", "scalar"])
    mock_result.scalar_one_or_none.return_value = None
    mock_result.one.return_value = MagicMock(
        spec=[], total=0, success_rate=0, avg_tokens=0, avg_word_count=0
    )
    mock_result.first.return_value = None
    mock_result.scalar.return_value = 0
    session.execute.return_value = mock_result
    session.flush = AsyncMock()
    session.add = MagicMock(spec=[])
    session.refresh = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# Schemas — GenerateSceneSchema / GenerateRequest.scenes
# ---------------------------------------------------------------------------


class TestGenerateSceneSchema:
    def test_defaults_are_empty_and_planned(self) -> None:
        from narrare.writing.schemas_scenes import GenerateSceneSchema

        scene = GenerateSceneSchema()
        assert scene.title == ""
        assert scene.pov_character_name == ""
        assert scene.location_name == ""
        assert scene.present_characters == []
        assert scene.purpose == ""
        assert scene.conflict == ""
        assert scene.resolution == ""
        assert scene.beats == []
        assert scene.status == "planned"

    def test_status_is_plain_str_no_literal_validation(self) -> None:
        # Carry-forward from T9 review: SceneSpec.status is an unvalidated
        # transport string — the API schema mirrors it (no Literal).
        from narrare.writing.schemas_scenes import GenerateSceneSchema

        scene = GenerateSceneSchema(status="in_progress")
        assert type(scene.status) is str
        assert scene.status == "in_progress"

    def test_full_construction_round_trips_model_dump(self) -> None:
        from narrare.writing.schemas_scenes import GenerateSceneSchema

        scene = GenerateSceneSchema(**_SCENE_DICT)
        assert scene.model_dump() == _SCENE_DICT


class TestGenerateRequestScenes:
    def test_scenes_default_is_none(self) -> None:
        request = _make_request(mode=GenerationModeEnum.FULL_DRAFT, prompt="x", scenes=None)
        assert request.scenes is None

    def test_scenes_accepts_scene_dicts(self) -> None:
        request = _make_request()
        assert request.scenes is not None
        assert request.scenes[0].title == "The Warning"
        assert request.scenes[0].present_characters == [{"name": "John", "goal": "warn the guard"}]

    def test_legacy_constructor_without_scenes_valid(self) -> None:
        request = _make_request(mode=GenerationModeEnum.FULL_DRAFT, prompt="x", scenes=None)
        assert request.prompt == "x"


# ---------------------------------------------------------------------------
# Payload/row translation (_pipeline_request_support)
# ---------------------------------------------------------------------------


class TestScenesPayload:
    def test_request_with_scenes_serializes_to_row_dicts(self) -> None:
        from narrare.writing._pipeline_request_support import scenes_payload

        payload = scenes_payload(_make_request())
        assert payload == [_SCENE_DICT]

    def test_request_without_scenes_gives_none(self) -> None:
        from narrare.writing._pipeline_request_support import scenes_payload

        assert scenes_payload(_make_request(scenes=None)) is None

    def test_empty_scenes_gives_none(self) -> None:
        from narrare.writing._pipeline_request_support import scenes_payload

        assert scenes_payload(_make_request(scenes=[])) is None


class TestScenesFromRow:
    def test_rows_map_to_scene_spec_tuple(self) -> None:
        from narrare.writing._pipeline_request_support import scenes_from_row
        from narrare_core.writing.requests import SceneSpec

        specs = scenes_from_row([_SCENE_DICT, {"title": "The Blockade", "status": "planned"}])
        assert specs is not None
        first, second = specs
        assert isinstance(first, SceneSpec)
        assert first.title == "The Warning"
        assert first.pov_character_name == "John"
        assert first.location_name == "Gatehouse"
        assert first.present_characters == (("John", "warn the guard"),)
        assert first.purpose == "Raise the stakes"
        assert first.beats == ("John arrives", "Guard refuses")
        assert first.status == "in_progress"
        assert second.title == "The Blockade"
        assert second.status == "planned"
        assert second.purpose == ""  # defaults for missing keys

    def test_none_rows_give_none(self) -> None:
        from narrare.writing._pipeline_request_support import scenes_from_row

        assert scenes_from_row(None) is None

    def test_empty_rows_give_none(self) -> None:
        from narrare.writing._pipeline_request_support import scenes_from_row

        assert scenes_from_row([]) is None

    def test_non_dict_entries_are_skipped(self) -> None:
        from narrare.writing._pipeline_request_support import scenes_from_row
        from narrare_core.writing.requests import SceneSpec

        specs = scenes_from_row(["garbage", _SCENE_DICT])
        assert specs is not None
        assert len(specs) == 1
        assert isinstance(specs[0], SceneSpec)

    def test_malformed_rows_degrade_to_defaults_not_crash(self) -> None:
        from narrare.writing._pipeline_request_support import scenes_from_row

        specs = scenes_from_row([{"present_characters": "not-a-list", "beats": None}])
        assert specs is not None
        assert specs[0].present_characters == ()
        assert specs[0].beats == ()


# ---------------------------------------------------------------------------
# Repository persistence
# ---------------------------------------------------------------------------


class TestRepositoryPersistsScenes:
    async def test_create_if_no_active_persists_scenes_rows(self) -> None:
        session = _make_mock_session()
        repo = GenerationRepository(session=session)
        repo._flush_and_refresh = AsyncMock(
            side_effect=lambda entity: setattr(entity, "id", uuid.uuid4())
        )

        scenes: list[dict[str, object]] = [_SCENE_DICT]
        await repo.create_if_no_active(
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), "scene_by_scene", "balanced", scenes=scenes
        )

        added = session.add.call_args.args[0]
        assert added.scenes == scenes

    async def test_create_if_no_active_without_scenes_keeps_none(self) -> None:
        session = _make_mock_session()
        repo = GenerationRepository(session=session)
        repo._flush_and_refresh = AsyncMock(
            side_effect=lambda entity: setattr(entity, "id", uuid.uuid4())
        )

        await repo.create_if_no_active(
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), "full_draft", "balanced"
        )

        added = session.add.call_args.args[0]
        assert added.scenes is None


# ---------------------------------------------------------------------------
# Threading — POST persistence + stream-time pipeline request
# ---------------------------------------------------------------------------


class TestStartGenerationThreadsScenes:
    async def test_start_generation_persists_scene_rows(
        self,
        service: WritingService,
        mock_repo: AsyncMock,
    ) -> None:
        """POST with scenes → the repo insert receives the dumped rows."""
        await service.start_generation(
            uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4()), _make_request()
        )
        assert mock_repo.create_if_no_active.call_args.kwargs["scenes"] == [_SCENE_DICT]

    async def test_start_generation_without_scenes_passes_none(
        self,
        service: WritingService,
        mock_repo: AsyncMock,
    ) -> None:
        """Scene-less POST → scenes=None (legacy behavior end to end)."""
        await service.start_generation(
            uuid.uuid4(),
            uuid.uuid4(),
            str(uuid.uuid4()),
            _make_request(scenes=None),
        )
        assert mock_repo.create_if_no_active.call_args.kwargs["scenes"] is None


class TestBuildPipelineRequestScenes:
    def _make_row(self, scenes: list[dict[str, object]] | None) -> GenerationRequest:
        return GenerationRequest(
            id=uuid.uuid4(),
            chapter_id=uuid.uuid4(),
            novel_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            mode="scene_by_scene",
            tone="balanced",
            status="pending",
            scenes=scenes,
        )

    def test_persisted_rows_become_core_scene_specs(self) -> None:
        from narrare.writing._pipeline_request_support import build_pipeline_request
        from narrare_core.writing._enums import GenerationMode
        from narrare_core.writing.requests import SceneSpec

        pipeline_request = build_pipeline_request(
            self._make_row([_SCENE_DICT]), GenerationMode.SCENE_BY_SCENE
        )
        scenes = pipeline_request.scenes
        assert scenes is not None
        assert isinstance(scenes[0], SceneSpec)
        assert scenes[0].title == "The Warning"
        assert scenes[0].present_characters == (("John", "warn the guard"),)
        assert scenes[0].beats == ("John arrives", "Guard refuses")
        assert scenes[0].status == "in_progress"

    def test_scene_less_row_keeps_none(self) -> None:
        from narrare.writing._pipeline_request_support import build_pipeline_request
        from narrare_core.writing._enums import GenerationMode

        pipeline_request = build_pipeline_request(
            self._make_row(None), GenerationMode.SCENE_BY_SCENE
        )
        assert pipeline_request.scenes is None

    def test_fields_threaded_unchanged(self) -> None:
        from narrare.writing._pipeline_request_support import build_pipeline_request
        from narrare_core.writing._enums import GenerationMode

        row = self._make_row(None)
        pipeline_request = build_pipeline_request(row, GenerationMode.SCENE_BY_SCENE)
        assert pipeline_request.id == row.id
        assert pipeline_request.chapter_id == row.chapter_id
        assert pipeline_request.project_id == row.novel_id
        assert pipeline_request.user_id == row.user_id
        assert pipeline_request.tone == "balanced"


# ---------------------------------------------------------------------------
# Validation contract — scenes are optional INPUT, never a required source
# ---------------------------------------------------------------------------


class TestValidateGenerationInputUnchanged:
    def test_scenes_only_request_still_rejected(self) -> None:
        # Plan binding: validate_generation_input UNCHANGED — scenes do not
        # count as an input source (spec §8.2 snapshot semantics).
        from narrare.writing._helpers import validate_generation_input

        request = _make_request(prompt=None)
        with pytest.raises(ValidationError, match="At least one"):
            validate_generation_input(request)

    def test_scenes_plus_prompt_accepted(self) -> None:
        from narrare.writing._helpers import validate_generation_input

        validate_generation_input(_make_request())  # does not raise
