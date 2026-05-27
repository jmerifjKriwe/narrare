"""Contract test: Planning Pydantic schemas match frontend expectations.

The frontend consumes OutlineResponse, StoryboardResponse,
SyncStatusResponse, RemapResponse, etc. Field name and type
mismatches cause runtime crashes.
"""

from __future__ import annotations

import uuid


class TestOutlineResponseContract:
    """OutlineResponse — full chapter outline with all fields."""

    def test_outline_response_has_required_fields(self) -> None:
        from narrare.planning.schemas import OutlineResponse

        field_names = set(OutlineResponse.model_fields.keys())
        expected = {
            "id",
            "chapter_id",
            "stage_assignment",
            "planned_beats",
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

    def test_outline_response_planned_beats_is_list(self) -> None:
        from narrare.planning.schemas import OutlineResponse

        ann = OutlineResponse.model_fields["planned_beats"].annotation
        assert "list" in str(ann).lower(), f"Expected planned_beats to be list type, got {ann}"


class TestBeatSchemaContract:
    """BeatSchema — a single beat within a chapter outline."""

    def test_beat_schema_has_required_fields(self) -> None:
        from narrare.planning.schemas import BeatSchema

        field_names = set(BeatSchema.model_fields.keys())
        for f in ("title", "description", "completed"):
            assert f in field_names, f"BeatSchema missing field '{f}'"

    def test_beat_completed_defaults_false(self) -> None:
        from narrare.planning.schemas import BeatSchema

        field = BeatSchema.model_fields["completed"]
        assert field.default is False, f"Expected completed default False, got {field.default}"


class TestOutlineUpdateRequestContract:
    """OutlineUpdateRequest — request body for updating an outline."""

    def test_outline_update_all_fields_optional(self) -> None:
        from narrare.planning.schemas import OutlineUpdateRequest

        for field_name in ("stage_assignment", "planned_beats", "outline_notes"):
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
