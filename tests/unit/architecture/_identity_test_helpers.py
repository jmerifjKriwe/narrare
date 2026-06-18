"""Shared test helpers for ADR-049 Phase D identity/orphan checker tests.

Extracted to keep individual test files under the RULE-04 400-line limit.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from scripts.architecture.types import CheckResult

if TYPE_CHECKING:
    from pathlib import Path


def write_conformant_project(root: Path) -> None:
    """Create a minimal conformant project that passes all identity gates."""
    core = root / "packages" / "core" / "narrare_core"
    (core / "llm").mkdir(parents=True)
    (core / "prompts").mkdir(parents=True)
    bundled = core / "prompts" / "_bundled"

    (core / "prompts" / "route_table.py").write_text(
        "from narrare_core.llm.intents import LLMIntent\n"
        "from narrare_core.prompts.route_types import PromptRouteConfig\n\n"
        "INTENT_TO_CATEGORY: dict[str, str] = {\n"
        '    LLMIntent.WRITE: "writing",\n'
        "}\n"
        "INTENT_TO_MODE: dict[str, str] = {\n"
        '    LLMIntent.WRITE: "new_chapter",\n'
        "}\n"
        "ROUTE_CONFIGS: dict[str, PromptRouteConfig] = {\n"
        "    LLMIntent.WRITE: PromptRouteConfig(\n"
        '        "writing",\n'
        '        "new_chapter",\n'
        '        allowed_context_modes=frozenset({"new_chapter", "scene_by_scene"}),\n'
        "    ),\n"
        "}\n"
        "NON_ROUTEABLE_INTENTS: dict[str, str] = {\n"
        '    LLMIntent.SENTIMENT: "Deterministic analyzer.",\n'
        "}\n",
        encoding="utf-8",
    )
    (core / "llm" / "intents.py").write_text(
        "from enum import StrEnum\n\n"
        "class LLMIntent(StrEnum):\n"
        '    WRITE = "write"\n'
        '    SENTIMENT = "sentiment"\n',
        encoding="utf-8",
    )
    (core / "prompts" / "variable_registry.py").write_text(
        'USER_CONTENT_VARS = frozenset({"author_instructions"})\n'
        'SYSTEM_VARS = frozenset({"chapter_outline"})\n'
        "FEATURE_DYNAMIC_VARS = frozenset()\n",
        encoding="utf-8",
    )

    for mode in ("new_chapter", "scene_by_scene"):
        tdir = bundled / "writing" / "en" / mode
        tdir.mkdir(parents=True)
        (tdir / "system.md").write_text(
            "---\n"
            "prompt_type: writing\n"
            "prompt_language: en\n"
            'prompt_version: "1.0.0"\n'
            "---\n\n"
            "You are a writing assistant.\n"
            "{{chapter_outline}}\n",
            encoding="utf-8",
        )

    (root / "scripts" / "architecture").mkdir(parents=True)
    (root / "scripts" / "architecture" / "prompt-surface-manifest.yaml").write_text(
        'version: "1.0.0"\n'
        "routes:\n"
        "  - intent: WRITE\n"
        "    routeable: true\n"
        "    category: writing\n"
        "    mode: new_chapter\n"
        "    template: packages/core/narrare_core/prompts/"
        "_bundled/writing/en/new_chapter/system.md\n"
        "    content_type: customizable_feature_prompt\n"
        "    required_variables: [chapter_outline]\n"
        "    optional_variables: []\n"
        "    security:\n"
        "      xml_required: []\n"
        "      generated_suggestions_must_be_labelled: []\n"
        "    fallback_policy: fail_loudly_if_bundled_missing\n"
        "  - intent: SENTIMENT\n"
        "    routeable: false\n"
        "    rationale: Deterministic analyzer.\n"
        "    fallback_policy: raise_route_not_configured\n",
        encoding="utf-8",
    )


def run_identity_checker(root: Path) -> CheckResult:
    """Run the identity checker against *root* and return the result."""
    from scripts.architecture._checkers._check_prompt_identity import check_prompt_identity

    result = CheckResult()
    check_prompt_identity(result, root=root)
    return result


def has_violation(result: CheckResult, rule: str, detail_fragment: str = "") -> bool:
    """Return True if *result* has a violation matching *rule* and *detail_fragment*."""
    return any(
        v.rule == rule and (not detail_fragment or detail_fragment in v.detail)
        for v in result.violations
    )
