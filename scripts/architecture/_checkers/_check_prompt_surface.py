"""PROMPT-SURFACE · Prompt Surface Contract manifest checker (ADR-037 / INFRA-012).

Enforces P0 prompt-governance gates:

1. **Manifest coverage** — every governed LLMIntent must have a manifest entry
   (PROMPT-SURFACE).
2. **Route/template drift** — routeable manifest targets must match the runtime
   route table's category and mode (PROMPT-ROUTE).
3. **Variable taxonomy** — template variables must be registered in the variable
   taxonomy (PROMPT-VARS).
4. **XML wrapping** — variables declared xml_required in the manifest must be
   wrapped in explicit XML tags inside the template (PROMPT-SECURITY).
5. **Generated-candidate labelling** — variables declared in
   generated_suggestions_must_be_labelled must have appropriate labels
   in the template (PROMPT-SECURITY).
6. **Production inline fallback** — routeable production prompts must not have
   inline fallback bodies in service code (PROMPT-FALLBACK).

The manifest lives at ``scripts/architecture/prompt-surface-manifest.yaml`` and
is the governance SSOT.  Core remains the runtime owner; this checker only
reads Core sources for comparison — never imported by Core.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, cast

from scripts.architecture._checkers._ast_helpers import (
    parse_frozenset_names,
    parse_non_routeable_intents,
    parse_route_table_dicts,
    parse_str_enum_members,
)
from scripts.architecture._checkers._simple_yaml import parse_simple_yaml
from scripts.architecture.types import CheckResult, Violation

if TYPE_CHECKING:
    from pathlib import Path

    from scripts.architecture._checkers._manifest_types import ManifestEntry

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TEMPLATE_VAR_RE = re.compile(r"\{\{(\w+)\}\}")
_XML_TAG_RE = re.compile(r"<(\w+)[^>]*>\s*\{\{(\w+)\}\}\s*</\1>", re.DOTALL)

_GENERATED_LABEL_FRAGMENTS = (
    "unaccepted candidate",
    "unaccepted generated candidate",
    "lower-priority generated",
    "optional lower-priority",
    "lower-priority suggestion",
)

# Intents that are infrastructure-level and never governed by the manifest.
_INFRASTRUCTURE_INTENTS: frozenset[str] = frozenset({"EMBED"})

# Inline-fallback detection patterns.
_FALLBACK_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"except\s+\w*Exception\w*\s*:\s*\n"
            r"(?:(?!\b(?:return|raise|log)\b)[^\n]*\n){0,3}"
            r'[^\n]*(?:system_prompt|prompt)\s*=\s*["\']',
            re.MULTILINE,
        ),
        "bare except with inline prompt string",
    ),
    (
        re.compile(r'system_prompt\s*=\s*["\'][^"\']{10,}["\']'),
        "inline prompt fallback string assignment",
    ),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_xml_wrapped(template_content: str, var: str) -> bool:
    """Check if ``{{var}}`` appears inside an XML tag pair."""
    return any(match.group(2) == var for match in _XML_TAG_RE.finditer(template_content))


def _has_generated_label(template_content: str, var: str) -> bool:
    """Check if the template labels a generated-candidate variable."""
    lower = template_content.lower()
    var_pos = lower.find("{{" + var + "}}")
    if var_pos == -1:
        return False
    window = lower[max(0, var_pos - 1000) : var_pos]
    return any(frag in window for frag in _GENERATED_LABEL_FRAGMENTS)


def _scan_inline_fallbacks(result: CheckResult, root: Path) -> None:
    """Scan apps/api Python files for inline prompt fallback patterns."""
    api_dir = root / "apps" / "api"
    if not api_dir.is_dir():
        return

    for py_file in api_dir.rglob("*.py"):
        try:
            source = py_file.read_text(encoding="utf-8")
        except OSError:
            continue

        lines = source.splitlines()
        for lineno, line_text in enumerate(lines, start=1):
            for pattern, description in _FALLBACK_PATTERNS:
                if pattern.search(line_text):
                    result.violations.append(
                        Violation(
                            file=py_file,
                            line=lineno,
                            rule="PROMPT-FALLBACK",
                            detail=(f"Production inline prompt fallback detected: {description}"),
                        )
                    )


# ---------------------------------------------------------------------------
# Main checker
# ---------------------------------------------------------------------------


def check_prompt_surface(result: CheckResult, root: Path) -> None:
    """Run all prompt-surface contract checks against the manifest."""
    manifest_path = root / "scripts" / "architecture" / "prompt-surface-manifest.yaml"
    intents_path = root / "packages" / "core" / "narrare_core" / "llm" / "intents.py"
    route_table_path = root / "packages" / "core" / "narrare_core" / "prompts" / "route_table.py"
    var_reg_path = root / "packages" / "core" / "narrare_core" / "prompts" / "variable_registry.py"

    # --- Load manifest -------------------------------------------------------
    if not manifest_path.is_file():
        result.violations.append(
            Violation(
                file=manifest_path,
                line=0,
                rule="PROMPT-SURFACE",
                detail=(
                    "Manifest file not found: scripts/architecture/prompt-surface-manifest.yaml"
                ),
            )
        )
        return

    manifest_text = manifest_path.read_text(encoding="utf-8")
    manifest = parse_simple_yaml(manifest_text)
    _routes_raw = manifest.get("routes", [])
    if not isinstance(_routes_raw, list):
        _routes_raw = []
    manifest_routes = cast("list[ManifestEntry]", _routes_raw)

    manifest_by_intent: dict[str, ManifestEntry] = {}
    for entry in manifest_routes:
        name = entry.get("intent", "")
        manifest_by_intent[name] = entry

    # --- Parse runtime sources -----------------------------------------------
    intents = parse_str_enum_members(intents_path)
    route_table = parse_route_table_dicts(route_table_path)
    non_routeable = parse_non_routeable_intents(route_table_path)
    var_registries = parse_frozenset_names(var_reg_path)

    all_registered: set[str] = set()
    for s in var_registries.values():
        all_registered.update(s)

    # --- Gate 1: Manifest coverage -------------------------------------------
    governed = (
        set(route_table.keys()) | non_routeable | set(intents.keys())
    ) - _INFRASTRUCTURE_INTENTS

    for intent_name in sorted(governed):
        if intent_name not in manifest_by_intent:
            result.violations.append(
                Violation(
                    file=manifest_path,
                    line=0,
                    rule="PROMPT-SURFACE",
                    detail=f"missing manifest entry for intent {intent_name}",
                )
            )

    # --- Gate 2: Route/table drift -------------------------------------------
    for intent_name, entry in manifest_by_intent.items():
        if not entry.get("routeable", False):
            continue

        m_cat = entry.get("category", "")
        m_mode = entry.get("mode", "")
        runtime = route_table.get(intent_name)
        if runtime is None:
            continue

        if runtime["category"] != m_cat or runtime["mode"] != m_mode:
            result.violations.append(
                Violation(
                    file=manifest_path,
                    line=0,
                    rule="PROMPT-ROUTE",
                    detail=(
                        f"mode drift for intent {intent_name}: "
                        f"manifest says category={m_cat!r} mode={m_mode!r}, "
                        f"runtime has category={runtime['category']!r} "
                        f"mode={runtime['mode']!r}"
                    ),
                )
            )

    # --- Gate 3-5: Template checks -------------------------------------------
    for intent_name, entry in manifest_by_intent.items():
        if not entry.get("routeable", False):
            continue

        template_rel = entry.get("template", "")
        if not template_rel:
            continue

        template_path = root / template_rel
        if not template_path.is_file():
            result.violations.append(
                Violation(
                    file=manifest_path,
                    line=0,
                    rule="PROMPT-SURFACE",
                    detail=(f"missing template for intent {intent_name}: {template_rel}"),
                )
            )
            continue

        try:
            tcontent = template_path.read_text(encoding="utf-8")
        except OSError:
            continue

        tvars = set(_TEMPLATE_VAR_RE.findall(tcontent))

        # Gate 3: Unregistered variables
        for var in sorted(tvars):
            if var not in all_registered:
                result.violations.append(
                    Violation(
                        file=template_path,
                        line=0,
                        rule="PROMPT-VARS",
                        detail=(
                            f"Unregistered template variable '{{{{{var}}}}}' in {template_rel}"
                        ),
                    )
                )

        # Gate 4: XML-required variables
        security = entry.get("security", {}) or {}
        xml_required = security.get("xml_required", []) or []
        for var in xml_required:
            if var not in tvars:
                continue
            if not _is_xml_wrapped(tcontent, var):
                result.violations.append(
                    Violation(
                        file=template_path,
                        line=0,
                        rule="PROMPT-SECURITY",
                        detail=(
                            f"Variable '{{{{{var}}}}}' is xml_required but "
                            f"not wrapped in XML tags in {template_rel}"
                        ),
                    )
                )

        # Gate 5: Generated-candidate labelling
        gen_labelled = security.get("generated_suggestions_must_be_labelled", []) or []
        for var in gen_labelled:
            if var not in tvars:
                continue
            if not _has_generated_label(tcontent, var):
                result.violations.append(
                    Violation(
                        file=template_path,
                        line=0,
                        rule="PROMPT-SECURITY",
                        detail=(
                            f"generated candidate variable '{{{{{var}}}}}' "
                            f"must be labelled as unaccepted/lower-priority "
                            f"in {template_rel}"
                        ),
                    )
                )

    # --- Gate 6: Production inline fallback ----------------------------------
    _scan_inline_fallbacks(result, root)
