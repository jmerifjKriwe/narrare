"""Tests for ADR-049 Phase D identity gates: A1/A2/A3/A4.

A1 PROMPT-IDENTITY: route_table ↔ manifest ↔ template path chain
A2 PROMPT-ROOT-MODE: no routeable intent with default_mode=""
A3 PROMPT-PATH-DERIVABILITY: template path derivable from category/mode
A4 PROMPT-FRONTMATTER-MATCH: prompt_type == category

A6 (ORPHAN-TEMPLATE) and D11 (PROMPT-CONTEXT-MODES) tests live in
``test_prompt_orphan_checker.py``.
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
# A1 — PROMPT-IDENTITY (acceptance)
# ---------------------------------------------------------------------------


def test_identity_accepts_conformant_project(tmp_path: Path) -> None:
    """A fully conformant project passes all identity gates."""
    write_conformant_project(tmp_path)
    result = run_identity_checker(tmp_path)
    assert result.violations == [], (
        f"Expected no violations, got: {[v.detail for v in result.violations]}"
    )


# ---------------------------------------------------------------------------
# A2 — PROMPT-ROOT-MODE
# ---------------------------------------------------------------------------


def test_identity_blocks_root_mode_intent(tmp_path: Path) -> None:
    """A2: routeable intent with default_mode='' is flagged."""
    write_conformant_project(tmp_path)
    rt_path = tmp_path / "packages" / "core" / "narrare_core" / "prompts" / "route_table.py"
    rt_path.write_text(
        rt_path.read_text("utf-8").replace(
            'LLMIntent.WRITE: "new_chapter",\n',
            'LLMIntent.WRITE: "",\n',
        ),
        encoding="utf-8",
    )
    result = run_identity_checker(tmp_path)
    assert has_violation(result, "PROMPT-ROOT-MODE", "root-mode")


def test_identity_exempts_aggregate_flow_none_mode(tmp_path: Path) -> None:
    """A2: aggregate flows with absent INTENT_TO_MODE entry are NOT flagged."""
    write_conformant_project(tmp_path)
    rt_path = tmp_path / "packages" / "core" / "narrare_core" / "prompts" / "route_table.py"
    rt_path.write_text(
        "from narrare_core.llm.intents import LLMIntent\n"
        "from narrare_core.prompts.route_types import PromptRouteConfig\n\n"
        "INTENT_TO_CATEGORY: dict[str, str] = {\n"
        '    LLMIntent.WRITE: "writing",\n'
        '    LLMIntent.EXTRACT: "analysis",\n'
        "}\n"
        "INTENT_TO_MODE: dict[str, str] = {\n"
        '    LLMIntent.WRITE: "new_chapter",\n'
        "}\n"
        "ROUTE_CONFIGS: dict[str, PromptRouteConfig] = {\n"
        "    LLMIntent.WRITE: PromptRouteConfig(\n"
        '        "writing",\n'
        '        "new_chapter",\n'
        '        allowed_context_modes=frozenset({"new_chapter"}),\n'
        "    ),\n"
        '    LLMIntent.EXTRACT: PromptRouteConfig("analysis", None),\n'
        "}\n"
        "NON_ROUTEABLE_INTENTS: dict[str, str] = {}\n",
        encoding="utf-8",
    )
    manifest = tmp_path / "scripts" / "architecture" / "prompt-surface-manifest.yaml"
    manifest.write_text(
        manifest.read_text("utf-8") + "  - intent: EXTRACT\n"
        "    routeable: true\n"
        "    category: analysis\n"
        "    mode: null\n"
        "    template: null\n"
        "    content_type: aggregate_assisted_flow\n"
        "    fallback_policy: raise_route_not_configured\n",
        encoding="utf-8",
    )
    result = run_identity_checker(tmp_path)
    assert not has_violation(result, "PROMPT-ROOT-MODE"), (
        "Aggregate flow with absent mode should NOT be flagged as root-mode"
    )


# ---------------------------------------------------------------------------
# A3 — PROMPT-PATH-DERIVABILITY
# ---------------------------------------------------------------------------


def test_identity_blocks_non_derivable_template_path(tmp_path: Path) -> None:
    """A3: manifest template path not under _bundled/{cat}/{lang}/{mode}/ is flagged."""
    write_conformant_project(tmp_path)
    manifest = tmp_path / "scripts" / "architecture" / "prompt-surface-manifest.yaml"
    manifest.write_text(
        manifest.read_text("utf-8").replace(
            "_bundled/writing/en/new_chapter/system.md",
            "_bundled/chat/en/system.md",
        ),
        encoding="utf-8",
    )
    result = run_identity_checker(tmp_path)
    assert has_violation(result, "PROMPT-PATH-DERIVABILITY")


# ---------------------------------------------------------------------------
# A4 — PROMPT-FRONTMATTER-MATCH
# ---------------------------------------------------------------------------


def test_identity_blocks_frontmatter_type_mismatch(tmp_path: Path) -> None:
    """A4: frontmatter prompt_type with non-canonical value is flagged."""
    write_conformant_project(tmp_path)
    template = (
        tmp_path
        / "packages"
        / "core"
        / "narrare_core"
        / "prompts"
        / "_bundled"
        / "writing"
        / "en"
        / "new_chapter"
        / "system.md"
    )
    template.write_text(
        template.read_text("utf-8").replace("prompt_type: writing", "prompt_type: chat"),
        encoding="utf-8",
    )
    result = run_identity_checker(tmp_path)
    assert has_violation(result, "PROMPT-FRONTMATTER-MATCH", "non-canonical")


def test_identity_blocks_frontmatter_category_drift(tmp_path: Path) -> None:
    """A4: frontmatter prompt_type != manifest category (canonical but wrong) is flagged."""
    write_conformant_project(tmp_path)
    template = (
        tmp_path
        / "packages"
        / "core"
        / "narrare_core"
        / "prompts"
        / "_bundled"
        / "writing"
        / "en"
        / "new_chapter"
        / "system.md"
    )
    template.write_text(
        template.read_text("utf-8").replace("prompt_type: writing", "prompt_type: analysis"),
        encoding="utf-8",
    )
    result = run_identity_checker(tmp_path)
    assert has_violation(result, "PROMPT-FRONTMATTER-MATCH", "does not match")


# ---------------------------------------------------------------------------
# Real-repo integration
# ---------------------------------------------------------------------------


def test_identity_checker_passes_on_real_repo() -> None:
    """The identity checker passes on the actual Narrare repo (current clean state)."""
    from scripts.architecture.helpers import ROOT

    result = run_identity_checker(ROOT)
    blocking = [v for v in result.violations if not v.approved]
    assert blocking == [], (
        f"Identity checker found {len(blocking)} blocking violation(s) on real repo: "
        + "; ".join(v.detail[:100] for v in blocking[:5])
    )
