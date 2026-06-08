"""RULE-17 Contract Test: Backend DemoProjectInfo fields match Frontend TypeScript interface.

Verifies that the Pydantic model in apps/api and the TypeScript interface
in packages/web/types/wizard.ts stay in sync. Any field addition/removal
on one side must be reflected on the other.
"""

from __future__ import annotations

from narrare.setup.base_schemas import DemoProjectInfo


def test_demo_project_info_field_match() -> None:
    """RULE-17: Backend DemoProjectInfo fields match Frontend TypeScript interface.

    Frontend interface (packages/web/types/wizard.ts):
        id, title, writing_language, genre, chapter_count,
        character_count, word_count, description, author,
        logline, pov, tags
    """
    be_fields = set(DemoProjectInfo.model_fields.keys())
    fe_fields = {
        "id",
        "title",
        "writing_language",
        "genre",
        "chapter_count",
        "character_count",
        "word_count",
        "description",
        "author",
        "logline",
        "pov",
        "tags",
    }
    assert be_fields == fe_fields, (
        f"Field mismatch: "
        f"BE has {be_fields - fe_fields} extra, "
        f"FE has {fe_fields - be_fields} extra"
    )


def test_demo_project_info_all_fields_serialized() -> None:
    """Verify all fields appear in model_dump() output (no excluded fields)."""
    from narrare.setup.base_schemas import StarterContent

    info = DemoProjectInfo(
        id=StarterContent.DEMO_FANTASY,
        title="Test",
        writing_language="en",
        genre="Fantasy",
        chapter_count=4,
        character_count=5,
        word_count=3130,
        description="Test description",
        author="Author",
        logline="A logline",
        pov="Third Person",
        tags=["fantasy"],
    )
    dumped = info.model_dump()
    expected_keys = {
        "id",
        "title",
        "writing_language",
        "genre",
        "chapter_count",
        "character_count",
        "word_count",
        "description",
        "author",
        "logline",
        "pov",
        "tags",
    }
    assert set(dumped.keys()) == expected_keys
