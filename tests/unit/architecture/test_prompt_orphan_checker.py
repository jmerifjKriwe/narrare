"""Tests for ADR-049 Phase D gates: A6 (ORPHAN-TEMPLATE) + D11 (CONTEXT-MODES).

These tests exercise the ``_check_prompt_orphan`` module, which is called
via ``check_prompt_identity`` (the orchestrator delegates to it).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.unit.architecture._identity_test_helpers import (
    has_violation,
    run_identity_checker,
    write_conformant_project,
)

if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# D11 — PROMPT-CONTEXT-MODES
# ---------------------------------------------------------------------------


def test_orphan_blocks_unallowed_context_mode(tmp_path: Path) -> None:
    """D11: manifest context_mode not in route_table allowed_context_modes is flagged."""
    write_conformant_project(tmp_path)
    manifest = tmp_path / "scripts" / "architecture" / "prompt-surface-manifest.yaml"
    manifest.write_text(
        manifest.read_text("utf-8").replace(
            "    fallback_policy: fail_loudly_if_bundled_missing\n  - intent: SENTIMENT",
            "    fallback_policy: fail_loudly_if_bundled_missing\n"
            "    context_modes:\n"
            "      - mode: unauthorized_mode\n"
            "        template: packages/core/narrare_core/prompts/"
            "_bundled/writing/en/new_chapter/system.md\n"
            "        fallback_policy: fail_loudly_if_bundled_missing\n"
            "  - intent: SENTIMENT",
        ),
        encoding="utf-8",
    )
    result = run_identity_checker(tmp_path)
    assert has_violation(result, "PROMPT-CONTEXT-MODES", "not in route_table")


def test_orphan_accepts_allowed_context_mode(tmp_path: Path) -> None:
    """D11: manifest context_mode IN route_table allowed_context_modes passes."""
    write_conformant_project(tmp_path)
    manifest = tmp_path / "scripts" / "architecture" / "prompt-surface-manifest.yaml"
    manifest.write_text(
        manifest.read_text("utf-8").replace(
            "    fallback_policy: fail_loudly_if_bundled_missing\n  - intent: SENTIMENT",
            "    fallback_policy: fail_loudly_if_bundled_missing\n"
            "    context_modes:\n"
            "      - mode: scene_by_scene\n"
            "        template: packages/core/narrare_core/prompts/"
            "_bundled/writing/en/scene_by_scene/system.md\n"
            "        fallback_policy: fail_loudly_if_bundled_missing\n"
            "  - intent: SENTIMENT",
        ),
        encoding="utf-8",
    )
    result = run_identity_checker(tmp_path)
    assert not has_violation(result, "PROMPT-CONTEXT-MODES")


# ---------------------------------------------------------------------------
# A6 — ORPHAN-TEMPLATE
# ---------------------------------------------------------------------------


def test_orphan_blocks_orphan_template(tmp_path: Path) -> None:
    """A6: a system.md not reachable via manifest/route_table is flagged."""
    write_conformant_project(tmp_path)
    orphan = (
        tmp_path
        / "packages"
        / "core"
        / "narrare_core"
        / "prompts"
        / "_bundled"
        / "writing"
        / "en"
        / "orphan_mode"
        / "system.md"
    )
    orphan.parent.mkdir(parents=True)
    orphan.write_text(
        '---\nprompt_type: writing\nprompt_language: en\nprompt_version: "1.0.0"\n---\n\nOrphan.\n',
        encoding="utf-8",
    )
    result = run_identity_checker(tmp_path)
    assert has_violation(result, "ORPHAN-TEMPLATE", "orphan_mode")


def test_orphan_exempts_capability_categories(tmp_path: Path) -> None:
    """A6: meta/universal/wiki templates are exempt (capability-loaded)."""
    write_conformant_project(tmp_path)
    meta = (
        tmp_path
        / "packages"
        / "core"
        / "narrare_core"
        / "prompts"
        / "_bundled"
        / "meta"
        / "en"
        / "system.md"
    )
    meta.parent.mkdir(parents=True)
    meta.write_text(
        "---\nprompt_type: meta\nprompt_language: en\n"
        'prompt_version: "1.0.0"\n---\n\nMeta prompt.\n',
        encoding="utf-8",
    )
    result = run_identity_checker(tmp_path)
    assert not has_violation(result, "ORPHAN-TEMPLATE"), (
        "meta/ templates should be exempt (capability-loaded per ADR-026)"
    )
