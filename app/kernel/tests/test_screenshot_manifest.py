from __future__ import annotations

import re

from scripts.screenshot_manifest import (
    README_SHOTS,
    SHOTS,
    render_index,
    validate_shots,
)


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


def test_index_links_every_master_once() -> None:
    rendered = render_index(SHOTS)
    for shot in SHOTS:
        assert rendered.count(f"../../assets/screenshots/{shot.name}.png") == 1
    assert "/home/" not in rendered
    assert "assets/screenshots/" in rendered
