"""
Factory helpers for creating test model instances.

Plain functions (not pytest fixtures) — import and use in any test.
Each returns a real SQLAlchemy model instance with sensible defaults.

Usage:
    from tests.factories import make_novel, make_chapter, make_user

    novel = make_novel(user_id=user_id)
    chapter = make_chapter(novel_id=novel.id, title="Chapter 1")
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm.attributes import set_attribute


def _set_attrs(obj: Any, attrs: dict[str, Any]) -> Any:
    """Set multiple attributes on a SQLAlchemy model instance."""
    for key, value in attrs.items():
        set_attribute(obj, key, value)
    return obj


def make_novel(**overrides: Any) -> Any:
    """Create a Novel instance with sensible defaults."""
    from narrare.novels.models import Novel

    novel = Novel()
    _set_attrs(
        novel,
        {
            "id": overrides.pop("id", uuid.uuid4()),
            "user_id": overrides.pop("user_id", uuid.uuid4()),
            "title": overrides.pop("title", "Test Novel"),
            "author": overrides.pop("author", "Test Author"),
            "genre": overrides.pop("genre", ""),
            "writing_language": overrides.pop("writing_language", "en"),
            "tone": overrides.pop("tone", ""),
            "story_structure": overrides.pop("story_structure", "three_act"),
            "logline": overrides.pop("logline", ""),
            "synopsis": overrides.pop("synopsis", ""),
            "is_demo": overrides.pop("is_demo", False),
            **overrides,
        },
    )
    return novel


def make_chapter(**overrides: Any) -> Any:
    """Create a Chapter instance with sensible defaults."""
    from narrare.chapters.models import Chapter

    chapter = Chapter()
    _set_attrs(
        chapter,
        {
            "id": overrides.pop("id", uuid.uuid4()),
            "novel_id": overrides.pop("novel_id", uuid.uuid4()),
            "title": overrides.pop("title", "Test Chapter"),
            "content": overrides.pop("content", ""),
            "position": overrides.pop("position", 0),
            "word_count": overrides.pop("word_count", 0),
            "status": overrides.pop("status", "draft"),
            "pov_character_id": overrides.pop("pov_character_id", ""),
            "timeline_position": overrides.pop("timeline_position", ""),
            "embeddings_dirty": overrides.pop("embeddings_dirty", True),
            **overrides,
        },
    )
    return chapter


def make_volume(**overrides: Any) -> Any:
    """Create a Volume instance with sensible defaults."""
    from narrare.volumes.models import Volume

    volume = Volume()
    _set_attrs(
        volume,
        {
            "id": overrides.pop("id", uuid.uuid4()),
            "novel_id": overrides.pop("novel_id", uuid.uuid4()),
            "title": overrides.pop("title", "Test Volume"),
            "position": overrides.pop("position", 0),
            **overrides,
        },
    )
    return volume


def make_user(**overrides: Any) -> Any:
    """Create a User instance with sensible defaults."""
    from datetime import UTC, datetime

    from narrare.auth.models import User

    user = User()
    _set_attrs(
        user,
        {
            "id": overrides.pop("id", uuid.uuid4()),
            "email": overrides.pop("email", "test@example.com"),
            "hashed_password": overrides.pop("hashed_password", "$2b$12$fakehash"),
            "display_name": overrides.pop("display_name", "Test User"),
            "is_active": overrides.pop("is_active", True),
            "is_verified": overrides.pop("is_verified", False),
            "created_at": overrides.pop("created_at", datetime.now(UTC)),
            "updated_at": overrides.pop("updated_at", datetime.now(UTC)),
            **overrides,
        },
    )
    return user


def make_chapter_outline(**overrides: Any) -> Any:
    """Create a ChapterOutline instance with sensible defaults."""
    from datetime import UTC, datetime

    from narrare.planning.models import ChapterOutline

    outline = ChapterOutline()
    _set_attrs(
        outline,
        {
            "id": overrides.pop("id", uuid.uuid4()),
            "chapter_id": overrides.pop("chapter_id", uuid.uuid4()),
            "version_id": overrides.pop("version_id", None),
            "stage_assignment": overrides.pop("stage_assignment", "act-1"),
            "outline_notes": overrides.pop("outline_notes", ""),
            "created_at": overrides.pop("created_at", datetime.now(UTC)),
            "updated_at": overrides.pop("updated_at", datetime.now(UTC)),
            **overrides,
        },
    )
    return outline


def make_scene_plan(**overrides: Any) -> Any:
    """Create a ScenePlan instance with sensible defaults (PLAN-001)."""
    from datetime import UTC, datetime

    from narrare.planning.models import ScenePlan

    scene = ScenePlan()
    _set_attrs(
        scene,
        {
            "id": overrides.pop("id", uuid.uuid4()),
            "chapter_id": overrides.pop("chapter_id", uuid.uuid4()),
            "position": overrides.pop("position", 1),
            "title": overrides.pop("title", "Test Scene"),
            "pov_character_ref": overrides.pop("pov_character_ref", None),
            "location_ref": overrides.pop("location_ref", None),
            "present_characters": overrides.pop("present_characters", []),
            "purpose": overrides.pop("purpose", ""),
            "conflict": overrides.pop("conflict", ""),
            "resolution": overrides.pop("resolution", ""),
            "beats": overrides.pop("beats", []),
            "status": overrides.pop("status", "planned"),
            "created_at": overrides.pop("created_at", datetime.now(UTC)),
            "updated_at": overrides.pop("updated_at", datetime.now(UTC)),
            **overrides,
        },
    )
    return scene


def make_note(**overrides: Any) -> Any:
    """Create a Note instance with sensible defaults (NOTES-001 scratchpad)."""
    from datetime import UTC, datetime

    from narrare.notes.models import Note

    note = Note()
    _set_attrs(
        note,
        {
            "id": overrides.pop("id", uuid.uuid4()),
            "user_id": overrides.pop("user_id", uuid.uuid4()),
            "title": overrides.pop("title", None),
            "content": overrides.pop("content", "note body"),
            "note_type": overrides.pop("note_type", "idea"),
            "tags": overrides.pop("tags", []),
            "novel_id": overrides.pop("novel_id", None),
            "series_id": overrides.pop("series_id", None),
            "created_at": overrides.pop("created_at", datetime.now(UTC)),
            "updated_at": overrides.pop("updated_at", datetime.now(UTC)),
            **overrides,
        },
    )
    return note
