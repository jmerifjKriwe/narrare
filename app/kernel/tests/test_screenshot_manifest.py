from __future__ import annotations

import re
from typing import Any

import pytest

from scripts.screenshot_manifest import (
    README_SHOTS,
    SHOTS,
    STAND_IN_DISCLOSURE,
    Shot,
    render_index,
    validate_shots,
)


def _shot(**overrides: Any) -> Shot:
    fields: dict[str, Any] = {
        "name": "99-test",
        "title": "Title",
        "caption": "Caption",
        "group": "Writing",
        "theme": "light",
    }
    fields.update(overrides)
    return Shot(**fields)


def test_shot_names_are_unique_and_safe() -> None:
    validate_shots(SHOTS)
    names = [shot.name for shot in SHOTS]
    assert len(names) == len(set(names))
    assert all(re.fullmatch(r"\d{2}-[a-z0-9-]+", name) for name in names)


def test_required_surfaces_and_readme_selection_exist() -> None:
    required = {
        "20-workspace-rebuilt",
        "21-workspace-rebuilt-dark",
        "22-zen",
        "23-zen-dark",
        "24-welcome-setup",
        "25-dossiers",
        "26-sources",
        "27-causality",
        "28-settings-hub",
        "29-ai-rules",
        "30-prompts",
        "31-entity-create",
        "32-entity-create-dark",
        "33-entity-interview",
        "34-entity-interview-dark",
    }
    assert required <= {shot.name for shot in SHOTS}
    assert tuple(shot.name for shot in README_SHOTS) == (
        "20-workspace-rebuilt",
        "21-workspace-rebuilt-dark",
        "22-zen",
        "25-dossiers",
        "27-causality",
        "28-settings-hub",
        "30-prompts",
        "33-entity-interview",
    )
    assert not any(shot.name.startswith("update-") for shot in SHOTS)


def test_index_discloses_the_model_stand_ins() -> None:
    rendered = render_index(SHOTS)
    assert STAND_IN_DISCLOSURE in rendered
    assert "dossiers frame" in STAND_IN_DISCLOSURE
    assert "fake extraction provider" in STAND_IN_DISCLOSURE
    assert "fake provider card" in STAND_IN_DISCLOSURE
    assert "both interview frames (33 and 34)" in STAND_IN_DISCLOSURE
    assert "continuation frame" in STAND_IN_DISCLOSURE
    assert "fake consistency provider" in STAND_IN_DISCLOSURE


def test_index_links_every_master_once() -> None:
    rendered = render_index(SHOTS)
    for shot in SHOTS:
        assert rendered.count(f"../../assets/screenshots/{shot.name}.png") == 1
    assert "/home/" not in rendered
    assert "assets/screenshots/" in rendered


def test_validate_rejects_duplicate_and_unsafe_names() -> None:
    with pytest.raises(ValueError, match="duplicate shot name"):
        validate_shots((_shot(), _shot(title="Another")))
    with pytest.raises(ValueError, match="must match"):
        validate_shots((_shot(name="99 Test"),))


def test_validate_rejects_unknown_theme() -> None:
    with pytest.raises(ValueError, match="unknown theme"):
        validate_shots((_shot(theme="sepia"),))


def test_validate_rejects_unknown_group() -> None:
    with pytest.raises(ValueError, match="unknown group"):
        validate_shots((_shot(group="Setup"),))


def test_validate_rejects_empty_title_and_caption() -> None:
    for field in ("title", "caption"):
        with pytest.raises(ValueError, match="title and a caption"):
            validate_shots((_shot(**{field: "   "}),))


def test_validate_rejects_control_characters_in_text() -> None:
    for field in ("title", "caption"):
        with pytest.raises(ValueError, match="control characters"):
            validate_shots((_shot(**{field: "Two\nlines"}),))


def test_index_renders_captions_as_visible_prose() -> None:
    rendered = render_index((_shot(caption="A caption beside the frame"),))
    assert rendered.count("A caption beside the frame") == 2


def test_index_escapes_markdown_in_titles_and_captions() -> None:
    rendered = render_index((_shot(title="A [title] # here", caption="One ] two # three"),))
    assert "### A \\[title\\] \\# here" in rendered
    assert "![One \\] two \\# three](../../assets/screenshots/99-test.png)" in rendered
    assert "One \\] two \\# three" in rendered.splitlines()[-1]
