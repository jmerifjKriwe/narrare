"""Regression tests for the Prompt Surface Contract checker.

The checker enforces ADR-037 / INFRA-012 P0 prompt-governance gates:
manifest coverage, route/template drift, variable taxonomy, XML wrapping,
generated-candidate labelling, and production inline fallback prohibition.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from scripts.architecture.types import CheckResult

if TYPE_CHECKING:
    from pathlib import Path


def test_prompt_surface_checker_accepts_conformant_manifest(tmp_path: Path) -> None:
    """A complete manifest matching routes, templates, and security passes."""
    from scripts.architecture._checkers._check_prompt_surface import check_prompt_surface

    _write_minimal_project(tmp_path)

    result = CheckResult()
    check_prompt_surface(result, root=tmp_path)

    assert result.violations == []


def test_prompt_surface_checker_blocks_missing_manifest_entry(tmp_path: Path) -> None:
    """Every production LLMIntent must have a manifest route decision."""
    from scripts.architecture._checkers._check_prompt_surface import check_prompt_surface

    _write_minimal_project(tmp_path, extra_intent='    ANALYSE = "analyse"\n')

    result = CheckResult()
    check_prompt_surface(result, root=tmp_path)

    assert _has_violation(result, "PROMPT-SURFACE", "missing manifest entry")


def test_prompt_surface_checker_blocks_route_table_drift(tmp_path: Path) -> None:
    """Routeable manifest targets must match the runtime route table."""
    from scripts.architecture._checkers._check_prompt_surface import check_prompt_surface

    _write_minimal_project(tmp_path, manifest_mode="extend_chapter")

    result = CheckResult()
    check_prompt_surface(result, root=tmp_path)

    assert _has_violation(result, "PROMPT-ROUTE", "mode drift")


def test_prompt_surface_checker_blocks_unregistered_template_variable(tmp_path: Path) -> None:
    """Variables used by governed templates must exist in the taxonomy."""
    from scripts.architecture._checkers._check_prompt_surface import check_prompt_surface

    _write_minimal_project(tmp_path, extra_template_line="{{missing_context}}")

    result = CheckResult()
    check_prompt_surface(result, root=tmp_path)

    assert _has_violation(result, "PROMPT-VARS", "Unregistered template variable")


def test_prompt_surface_checker_blocks_xml_required_variable_without_wrapper(
    tmp_path: Path,
) -> None:
    """Manifest xml_required variables must be explicitly XML-wrapped."""
    from scripts.architecture._checkers._check_prompt_surface import check_prompt_surface

    _write_minimal_project(
        tmp_path,
        author_line="Author instructions: {{author_instructions}}",
    )

    result = CheckResult()
    check_prompt_surface(result, root=tmp_path)

    assert _has_violation(result, "PROMPT-SECURITY", "not wrapped in XML")


def test_prompt_surface_checker_blocks_unlabelled_generated_suggestion(
    tmp_path: Path,
) -> None:
    """Generated candidates must be labelled as unaccepted/lower-priority."""
    from scripts.architecture._checkers._check_prompt_surface import check_prompt_surface

    _write_minimal_project(
        tmp_path,
        suggestion_block="### Context\n\n{{kb_suggested}}",
    )

    result = CheckResult()
    check_prompt_surface(result, root=tmp_path)

    assert _has_violation(result, "PROMPT-SECURITY", "generated candidate")


def test_prompt_surface_checker_blocks_production_inline_fallback(tmp_path: Path) -> None:
    """Broad production prompt fallbacks must be blocking P0 violations."""
    from scripts.architecture._checkers._check_prompt_surface import check_prompt_surface

    _write_minimal_project(tmp_path)
    service_path = tmp_path / "apps" / "api" / "narrare" / "writing" / "service.py"
    service_path.parent.mkdir(parents=True)
    service_path.write_text(
        "async def build_prompt(registry):\n"
        "    try:\n"
        "        return await registry.resolve("
        "category='writing', language='en', mode='new_chapter')\n"
        "    except Exception:\n"
        "        system_prompt = 'Write a chapter from this inline fallback body.'\n"
        "        return system_prompt\n",
        encoding="utf-8",
    )

    result = CheckResult()
    check_prompt_surface(result, root=tmp_path)

    assert _has_violation(result, "PROMPT-FALLBACK", "inline prompt fallback")


def _write_minimal_project(
    root: Path,
    *,
    extra_intent: str = "",
    manifest_mode: str = "new_chapter",
    extra_template_line: str = "",
    author_line: str = "<user_instructions>{{author_instructions}}</user_instructions>",
    suggestion_block: str = (
        "### Optional Lower-Priority Generated Suggestions\n\n"
        "These are unaccepted candidate suggestions.\n\n"
        "{{kb_suggested}}"
    ),
) -> None:
    """Create a minimal Narrare-like prompt surface under *root*."""
    (root / "packages" / "core" / "narrare_core" / "llm").mkdir(parents=True)
    (root / "packages" / "core" / "narrare_core" / "prompts").mkdir(parents=True)
    bundled = root / "packages" / "core" / "narrare_core" / "prompts" / "_bundled"
    template_dir = bundled / "writing" / "en" / "new_chapter"
    template_dir.mkdir(parents=True)
    (root / "scripts" / "architecture").mkdir(parents=True)

    (root / "packages" / "core" / "narrare_core" / "llm" / "intents.py").write_text(
        "from enum import StrEnum\n\n"
        "class LLMIntent(StrEnum):\n"
        '    WRITE = "write"\n'
        f"{extra_intent}"
        '    SENTIMENT = "sentiment"\n'
        '    EMBED = "embed"\n',
        encoding="utf-8",
    )
    (root / "packages" / "core" / "narrare_core" / "prompts" / "route_table.py").write_text(
        "from narrare_core.llm.intents import LLMIntent\n"
        "from narrare_core.prompts.route_types import PromptRouteConfig\n\n"
        'INTENT_TO_CATEGORY = {LLMIntent.WRITE: "writing"}\n'
        'INTENT_TO_MODE = {LLMIntent.WRITE: "new_chapter"}\n'
        "ROUTE_CONFIGS = {\n"
        "    LLMIntent.WRITE: PromptRouteConfig(\n"
        '        "writing",\n'
        '        "new_chapter",\n'
        '        required_variables=frozenset({"chapter_outline"}),\n'
        '        optional_variables=frozenset({"author_instructions", "kb_suggested"}),\n'
        "    ),\n"
        "}\n"
        "CONTEXT_MODE_REQUIRED_INTENTS = {}\n"
        'NON_ROUTEABLE_INTENTS = {LLMIntent.SENTIMENT: "Deterministic analyzer."}\n',
        encoding="utf-8",
    )
    (root / "packages" / "core" / "narrare_core" / "prompts" / "variable_registry.py").write_text(
        'USER_CONTENT_VARS = frozenset({"author_instructions"})\n'
        'SYSTEM_VARS = frozenset({"chapter_outline", "kb_suggested"})\n'
        "FEATURE_DYNAMIC_VARS = frozenset()\n",
        encoding="utf-8",
    )
    (template_dir / "system.md").write_text(
        "---\n"
        "prompt_type: writing\n"
        "prompt_language: en\n"
        'prompt_version: "1.0.0"\n'
        "---\n\n"
        "## System Prompt\n\n"
        "You are a writing assistant.\n\n"
        "Chapter outline: {{chapter_outline}}\n\n"
        f"{author_line}\n\n"
        f"{suggestion_block}\n\n"
        f"{extra_template_line}\n",
        encoding="utf-8",
    )
    (root / "scripts" / "architecture" / "prompt-surface-manifest.yaml").write_text(
        'version: "1.0.0"\n'
        "routes:\n"
        "  - intent: WRITE\n"
        "    routeable: true\n"
        "    category: writing\n"
        f"    mode: {manifest_mode}\n"
        "    template: packages/core/narrare_core/prompts/"
        "_bundled/writing/en/new_chapter/system.md\n"
        "    content_type: customizable_feature_prompt\n"
        "    output_language_variable: null\n"
        "    required_variables: [chapter_outline]\n"
        "    optional_variables: [author_instructions, kb_suggested]\n"
        "    security:\n"
        "      xml_required: [author_instructions]\n"
        "      generated_suggestions_must_be_labelled: [kb_suggested]\n"
        "    fallback_policy: fail_loudly_if_bundled_missing\n"
        "  - intent: SENTIMENT\n"
        "    routeable: false\n"
        "    rationale: Deterministic analyzer.\n"
        "    fallback_policy: raise_route_not_configured\n",
        encoding="utf-8",
    )


def _has_violation(result: CheckResult, rule: str, detail_fragment: str) -> bool:
    return any(v.rule == rule and detail_fragment in v.detail for v in result.violations)
