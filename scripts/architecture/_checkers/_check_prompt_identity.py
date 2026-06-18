"""PROMPT-IDENTITY · Prompt-Surface Identity & Path Contract checker (ADR-049 Phase D).

Enforces the identity/path invariants that would have caught FIND-010
(Chat Prompt Surface Drift) and prevent its recurrence for any future intent:

1. **PROMPT-IDENTITY (A1)** — End-to-end identity chain for every routeable
   intent: route_table → manifest → template path → frontmatter →
   management-id. All links must agree.
2. **PROMPT-ROOT-MODE (A2)** — No routeable intent may have ``default_mode=""``.
   Aggregate flows use ``default_mode=None`` with
   ``fallback_policy: raise_route_not_configured`` and are exempt.
3. **PROMPT-PATH-DERIVABILITY (A3)** — Manifest ``template:`` path must equal
   ``_bundled/{category}/{lang}/{mode}/system.md``.
4. **PROMPT-FRONTMATTER-MATCH (A4)** — Template frontmatter ``prompt_type``
   must equal the manifest ``category`` and be in the canonical enumeration.

Gates A6 (ORPHAN-TEMPLATE) and D11 (PROMPT-CONTEXT-MODES) live in the
sibling module ``_check_prompt_orphan.py`` (extracted for RULE-04 compliance).

See: ``docs/architecture/decisions/ADR-049-prompt-surface-identity-path-contract.md``
      (Checker Acceptance Criteria A1-A4, lines 590-641)
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, cast

from scripts.architecture._checkers._ast_helpers import (
    parse_non_routeable_intents,
    parse_route_table_dicts,
)
from scripts.architecture._checkers._simple_yaml import parse_simple_yaml
from scripts.architecture.types import CheckResult, Violation

if TYPE_CHECKING:
    from pathlib import Path

    from scripts.architecture._checkers._manifest_types import ManifestEntry

# ---------------------------------------------------------------------------
# Constants (shared with _check_prompt_orphan.py — public, no underscore)
# ---------------------------------------------------------------------------

# Canonical prompt_type enumeration per ADR-049 A4 / prompt-standards.md §1.
CANONICAL_PROMPT_TYPES: frozenset[str] = frozenset(
    {"writing", "kb", "analysis", "planning", "meta", "generation", "wiki", "universal"}
)

# Capability-loaded categories (ADR-026): templates loaded by Capabilities,
# not via PromptComposer routing.
CAPABILITY_CATEGORIES: frozenset[str] = frozenset({"meta", "universal", "wiki"})

# Default language for bundled templates.
DEFAULT_LANGUAGE = "en"

# Frontmatter delimiter regex.
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


# ---------------------------------------------------------------------------
# Shared helpers (used by both this module and _check_prompt_orphan.py)
# ---------------------------------------------------------------------------


def parse_frontmatter(content: str) -> dict[str, str]:
    """Parse simple YAML frontmatter from a template file."""
    match = _FRONTMATTER_RE.match(content)
    if match is None:
        return {}
    metadata: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            metadata[key.strip()] = value.strip().strip('"').strip("'")
    return metadata


def expected_template_path(category: str, language: str, mode: str) -> str:
    """Return the expected relative template path for a (category, lang, mode).

    Per ADR-049 D4: ``packages/core/narrare_core/prompts/_bundled/{cat}/{lang}/{mode}/system.md``
    """
    return f"packages/core/narrare_core/prompts/_bundled/{category}/{language}/{mode}/system.md"


def check_frontmatter(
    result: CheckResult,
    template_path: Path,
    template_rel: str,
    intent_name: str,
    expected_category: str,
) -> None:
    """A4 — PROMPT-FRONTMATTER-MATCH for a single template."""
    try:
        content = template_path.read_text(encoding="utf-8")
    except OSError:
        return

    fm = parse_frontmatter(content)
    prompt_type = fm.get("prompt_type", "")

    if not prompt_type:
        result.violations.append(
            Violation(
                file=template_path,
                line=0,
                rule="PROMPT-FRONTMATTER-MATCH",
                detail=(
                    f"Template {template_rel} (intent {intent_name}) has no "
                    f"prompt_type in frontmatter. Required: prompt_type: {expected_category}"
                ),
            )
        )
        return

    if prompt_type not in CANONICAL_PROMPT_TYPES:
        result.violations.append(
            Violation(
                file=template_path,
                line=0,
                rule="PROMPT-FRONTMATTER-MATCH",
                detail=(
                    f"Template {template_rel} has non-canonical prompt_type "
                    f"{prompt_type!r}. Valid values: "
                    f"{sorted(CANONICAL_PROMPT_TYPES)}. "
                    f"(ADR-049 A4 / prompt-standards.md §1)"
                ),
            )
        )
        return

    if prompt_type != expected_category:
        result.violations.append(
            Violation(
                file=template_path,
                line=0,
                rule="PROMPT-FRONTMATTER-MATCH",
                detail=(
                    f"Template {template_rel} frontmatter prompt_type={prompt_type!r} "
                    f"does not match manifest category={expected_category!r} "
                    f"for intent {intent_name}. (ADR-049 D5)"
                ),
            )
        )


# ---------------------------------------------------------------------------
# Gate implementations: A1 / A2 / A3
# ---------------------------------------------------------------------------


def _check_root_mode(
    result: CheckResult,
    route_table: dict[str, dict[str, Any]],
    non_routeable: set[str],
    manifest_path: Path,
) -> None:
    """A2 — PROMPT-ROOT-MODE: no routeable intent with ``default_mode=""``.

    Aggregate flows use ``default_mode=None`` (absent from INTENT_TO_MODE)
    and are exempt.  Only explicit empty-string modes are forbidden.
    """
    for intent_name, info in sorted(route_table.items()):
        if intent_name in non_routeable:
            continue
        if not info.get("has_explicit_mode", False):
            continue
        mode = info.get("mode")
        if mode == "":
            result.violations.append(
                Violation(
                    file=manifest_path,
                    line=0,
                    rule="PROMPT-ROOT-MODE",
                    detail=(
                        f"Routeable intent {intent_name} has default_mode='' "
                        f"(root-mode). Root-mode is forbidden for routeable "
                        f"intents per ADR-049 D3 — use a non-empty mode or "
                        f"set default_mode=None with "
                        f"fallback_policy=raise_route_not_configured for "
                        f"aggregate flows."
                    ),
                )
            )


def _check_identity_chain(
    result: CheckResult,
    manifest_by_intent: dict[str, ManifestEntry],
    route_table: dict[str, dict[str, Any]],
    root: Path,
    manifest_path: Path,
) -> None:
    """A1/A3/A4 — PROMPT-IDENTITY + PATH-DERIVABILITY + FRONTMATTER-MATCH."""
    for intent_name in sorted(manifest_by_intent):
        entry = manifest_by_intent[intent_name]
        if not entry.get("routeable", False):
            continue

        m_cat = entry.get("category", "")
        m_mode = entry.get("mode")
        if m_mode is None:
            continue  # aggregate flow
        m_mode_str = str(m_mode)

        # --- A1 link 3: route_table consistency ---
        runtime = route_table.get(intent_name)
        if runtime is not None:
            rt_cat = runtime.get("category", "")
            rt_mode = runtime.get("mode", "")
            if rt_cat != m_cat or str(rt_mode) != m_mode_str:
                result.violations.append(
                    Violation(
                        file=manifest_path,
                        line=0,
                        rule="PROMPT-IDENTITY",
                        detail=(
                            f"Identity chain broken for {intent_name}: "
                            f"manifest says category={m_cat!r} mode={m_mode_str!r}, "
                            f"route_table has category={rt_cat!r} mode={rt_mode!r}"
                        ),
                    )
                )

        # --- A3: path derivability ---
        template_rel = entry.get("template", "")
        if template_rel:
            expected = expected_template_path(m_cat, DEFAULT_LANGUAGE, m_mode_str)
            if template_rel != expected:
                result.violations.append(
                    Violation(
                        file=manifest_path,
                        line=0,
                        rule="PROMPT-PATH-DERIVABILITY",
                        detail=(
                            f"Manifest template path for {intent_name} is not "
                            f"derivable from category/mode. Expected "
                            f"{expected!r}, got {template_rel!r}. "
                            f"(ADR-049 D4)"
                        ),
                    )
                )

            # --- A4: frontmatter match ---
            template_path = root / template_rel
            if template_path.is_file():
                check_frontmatter(result, template_path, template_rel, intent_name, m_cat)

        # --- A1 link 5: management-id derivability ---
        if not m_cat or not m_mode_str:
            result.violations.append(
                Violation(
                    file=manifest_path,
                    line=0,
                    rule="PROMPT-IDENTITY",
                    detail=(
                        f"Management-id not derivable for {intent_name}: "
                        f"category={m_cat!r} mode={m_mode_str!r} — "
                        f"both must be non-empty for a 3-segment id."
                    ),
                )
            )


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


def check_prompt_identity(result: CheckResult, root: Path) -> None:
    """Run all ADR-049 Phase D identity/path checks (A1-A4).

    Delegates A6 (ORPHAN-TEMPLATE) and D11 (PROMPT-CONTEXT-MODES) to
    ``_check_prompt_orphan.check_prompt_orphan_and_context_modes``.
    """
    manifest_path = root / "scripts" / "architecture" / "prompt-surface-manifest.yaml"
    route_table_path = root / "packages" / "core" / "narrare_core" / "prompts" / "route_table.py"

    if not manifest_path.is_file():
        return

    manifest_text = manifest_path.read_text(encoding="utf-8")
    manifest = parse_simple_yaml(manifest_text)
    routes_raw = manifest.get("routes", [])
    if not isinstance(routes_raw, list):
        routes_raw = []
    manifest_routes = cast("list[ManifestEntry]", routes_raw)

    manifest_by_intent: dict[str, ManifestEntry] = {}
    for entry in manifest_routes:
        name = entry.get("intent", "")
        if name:
            manifest_by_intent[name] = entry

    route_table = parse_route_table_dicts(route_table_path)
    non_routeable = parse_non_routeable_intents(route_table_path)

    # A2: PROMPT-ROOT-MODE
    _check_root_mode(result, route_table, non_routeable, manifest_path)

    # A1/A3/A4: identity chain + path derivability + frontmatter
    _check_identity_chain(result, manifest_by_intent, route_table, root, manifest_path)

    # A6/D11: orphan templates + context modes (delegated to sibling module)
    from scripts.architecture._checkers._check_prompt_orphan import (
        check_prompt_orphan_and_context_modes,
    )

    check_prompt_orphan_and_context_modes(result, root)
