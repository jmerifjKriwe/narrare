"""Contract test: Planning Pydantic schemas match frontend expectations.

The frontend consumes OutlineResponse, StoryboardResponse,
SyncStatusResponse, RemapResponse, etc. Field name and type
mismatches cause runtime crashes.
"""

from __future__ import annotations

import uuid


class TestOutlineResponseContract:
    """OutlineResponse — full chapter outline with all fields.

    PLAN-001 T14: the wire is beat-free (FE de-beated in T13; the beat
    substrate is replaced by the scene aggregate — ADR-096).
    """

    def test_outline_response_has_required_fields(self) -> None:
        from narrare.planning.schemas import OutlineResponse

        field_names = set(OutlineResponse.model_fields.keys())
        expected = {
            "id",
            "chapter_id",
            "stage_assignment",
            "outline_notes",
            "created_at",
            "updated_at",
        }
        missing = expected - field_names
        assert not missing, f"OutlineResponse is missing fields: {missing}"

    def test_outline_response_chapter_id_is_uuid(self) -> None:
        from narrare.planning.schemas import OutlineResponse

        ann = OutlineResponse.model_fields["chapter_id"].annotation
        assert ann is uuid.UUID, f"Expected chapter_id to be UUID, got {ann}"

    def test_outline_response_has_no_planned_beats(self) -> None:
        from narrare.planning.schemas import OutlineResponse

        assert "planned_beats" not in OutlineResponse.model_fields, (
            "OutlineResponse must not carry planned_beats (PLAN-001 T14 beat-free wire)"
        )


class TestBeatRemovalContract:
    """PLAN-001 T14: the beat wire surface is gone (ADR-096 scene substrate)."""

    def test_beat_schema_removed(self) -> None:
        import narrare.planning.schemas as planning_schemas

        assert not hasattr(planning_schemas, "BeatSchema"), (
            "BeatSchema must be removed from the planning schemas (PLAN-001 T14)"
        )

    def test_outline_update_request_has_no_planned_beats(self) -> None:
        from narrare.planning.schemas import OutlineUpdateRequest

        assert "planned_beats" not in OutlineUpdateRequest.model_fields, (
            "OutlineUpdateRequest must not accept planned_beats (scenes are the substrate)"
        )


class TestOutlineUpdateRequestContract:
    """OutlineUpdateRequest — request body for updating an outline."""

    def test_outline_update_all_fields_optional(self) -> None:
        from narrare.planning.schemas import OutlineUpdateRequest

        for field_name in ("stage_assignment", "outline_notes"):
            field = OutlineUpdateRequest.model_fields[field_name]
            assert field.default is None, (
                f"{field_name} should default to None, got {field.default!r}"
            )


class TestStoryboardResponseContract:
    """StoryboardResponse — complete storyboard view for a novel."""

    def test_storyboard_response_has_required_fields(self) -> None:
        from narrare.planning.schemas import StoryboardResponse

        field_names = set(StoryboardResponse.model_fields.keys())
        for f in ("structure_type", "stages"):
            assert f in field_names, f"StoryboardResponse missing field '{f}'"

    def test_storyboard_stages_is_list(self) -> None:
        from narrare.planning.schemas import StoryboardResponse

        ann = StoryboardResponse.model_fields["stages"].annotation
        assert "list" in str(ann).lower(), f"Expected stages to be list type, got {ann}"


class TestStoryboardStageResponseContract:
    """StoryboardStageResponse — a single stage with its chapters."""

    def test_stage_response_has_required_fields(self) -> None:
        from narrare.planning.schemas import StoryboardStageResponse

        field_names = set(StoryboardStageResponse.model_fields.keys())
        for f in ("stage_id", "stage_name", "chapters"):
            assert f in field_names, f"StoryboardStageResponse missing field '{f}'"


class TestChapterInStoryboardContract:
    """ChapterInStoryboard — compact chapter info for the storyboard."""

    def test_chapter_in_storyboard_has_required_fields(self) -> None:
        from narrare.planning.schemas import ChapterInStoryboard

        field_names = set(ChapterInStoryboard.model_fields.keys())
        for f in ("chapter_id", "title", "word_count", "sync_status", "position"):
            assert f in field_names, f"ChapterInStoryboard missing field '{f}'"


class TestSyncStatusResponseContract:
    """SyncStatusResponse — sync status for a single chapter."""

    def test_sync_status_has_required_fields(self) -> None:
        from narrare.planning.schemas import SyncStatusResponse

        field_names = set(SyncStatusResponse.model_fields.keys())
        for f in ("chapter_id", "sync_status"):
            assert f in field_names, f"SyncStatusResponse missing field '{f}'"


class TestRemapResponseContract:
    """RemapResponse — response for remap preview or confirmation."""

    def test_remap_response_has_required_fields(self) -> None:
        from narrare.planning.schemas import RemapResponse

        field_names = set(RemapResponse.model_fields.keys())
        for f in ("new_structure", "remapped", "confirmed"):
            assert f in field_names, f"RemapResponse missing field '{f}'"

    def test_remap_response_confirmed_defaults_false(self) -> None:
        from narrare.planning.schemas import RemapResponse

        field = RemapResponse.model_fields["confirmed"]
        assert field.default is False, f"Expected confirmed default False, got {field.default}"


class TestRemapRequestContract:
    """RemapRequest — request to preview or confirm a structure remap."""

    def test_remap_request_has_new_structure(self) -> None:
        from narrare.planning.schemas import RemapRequest

        field_names = set(RemapRequest.model_fields.keys())
        for f in ("new_structure", "confirm"):
            assert f in field_names, f"RemapRequest missing field '{f}'"

    def test_remap_request_confirm_defaults_false(self) -> None:
        from narrare.planning.schemas import RemapRequest

        field = RemapRequest.model_fields["confirm"]
        assert field.default is False, f"Expected confirm default False, got {field.default}"


class TestRemapPreviewItemContract:
    """RemapPreviewItem — single chapter remap preview."""

    def test_remap_preview_has_required_fields(self) -> None:
        from narrare.planning.schemas import RemapPreviewItem

        field_names = set(RemapPreviewItem.model_fields.keys())
        for f in ("chapter_id", "chapter_title", "old_stage", "new_stage"):
            assert f in field_names, f"RemapPreviewItem missing field '{f}'"


class TestScenePlanAggregateResponseContract:
    """ScenePlanAggregateResponse — whole-chapter scene aggregate (PLAN-001)."""

    def test_scene_plan_aggregate_has_required_fields(self) -> None:
        from narrare.planning.schemas_scenes import ScenePlanAggregateResponse

        field_names = set(ScenePlanAggregateResponse.model_fields.keys())
        for f in ("chapter_id", "scenes", "version_updated_at"):
            assert f in field_names, f"ScenePlanAggregateResponse missing field '{f}'"

    def test_scene_plan_aggregate_chapter_id_is_uuid(self) -> None:
        from narrare.planning.schemas_scenes import ScenePlanAggregateResponse

        ann = ScenePlanAggregateResponse.model_fields["chapter_id"].annotation
        assert ann is uuid.UUID, f"Expected chapter_id to be UUID, got {ann}"


class TestSceneSchemaContract:
    """SceneSchema — one scene; doubles as the whole-aggregate save item."""

    def test_scene_schema_has_required_fields(self) -> None:
        from narrare.planning.schemas_scenes import SceneSchema

        field_names = set(SceneSchema.model_fields.keys())
        for f in (
            "id",
            "position",
            "title",
            "pov_character_ref",
            "location_ref",
            "present_characters",
            "purpose",
            "conflict",
            "resolution",
            "beats",
            "status",
            "created_at",
            "updated_at",
        ):
            assert f in field_names, f"SceneSchema missing field '{f}'"

    def test_scene_schema_status_is_limited_to_spec_values(self) -> None:
        from narrare.planning.schemas_scenes import SceneSchema

        ann = str(SceneSchema.model_fields["status"].annotation)
        for value in ("planned", "in_progress", "complete"):
            assert value in ann, f"SceneSchema.status missing Literal value '{value}': {ann}"


class TestScenePlanSaveRequestContract:
    """ScenePlanSaveRequest — whole-aggregate PUT body."""

    def test_save_request_has_scenes_list(self) -> None:
        from narrare.planning.schemas_scenes import ScenePlanSaveRequest

        field_names = set(ScenePlanSaveRequest.model_fields.keys())
        assert "scenes" in field_names, "ScenePlanSaveRequest missing field 'scenes'"

        ann = str(ScenePlanSaveRequest.model_fields["scenes"].annotation)
        assert "list" in ann.lower(), f"Expected scenes to be list type, got {ann}"
