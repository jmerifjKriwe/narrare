"""PROMPT-ORPHAN · Orphan-Template + Context-Modes gates (ADR-049 Phase D A6/D11).

Extracted from ``_check_prompt_identity.py`` to keep both modules under the
RULE-04 400-line hard limit.  This module owns two gates:

1. **PROMPT-CONTEXT-MODES (D11)** — Each manifest ``context_modes`` entry must
   be in the route_table's ``allowed_context_modes`` and have a valid template.
2. **ORPHAN-TEMPLATE (A6)** — Every ``system.md`` under ``_bundled/`` must be
   reachable via manifest, context_modes, route_table modes, or be a
   capability-loaded category.

See: ``docs/architecture/decisions/ADR-049-prompt-surface-identity-path-contract.md``
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from scripts.architecture._checkers._ast_helpers import (
    parse_route_configs_context_modes,
    parse_route_table_dicts,
)
from scripts.architecture._checkers._simple_yaml import parse_simple_yaml
from scripts.architecture.types import CheckResult, Violation

if TYPE_CHECKING:
    from pathlib import Path

    from scripts.architecture._checkers._manifest_types import (
        ManifestContextMode,
        ManifestEntry,
    )

from scripts.architecture._checkers._check_prompt_identity import (
    CAPABILITY_CATEGORIES,
    DEFAULT_LANGUAGE,
    check_frontmatter,
    expected_template_path,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Documented orphan exemptions (ADR-049 A6).
#
# Each entry lists a (category, mode) pair that is NOT reachable via manifest,
# context_modes, or route_table — but is acknowledged as a known pre-existing
# orphan with a documented cleanup rationale.  This prevents the ORPHAN-TEMPLATE
# gate from blocking CI on known debt while making that debt explicit and
# auditable (no silent suppression).
#
# **Adding an entry here is technical debt.** Each entry must have:
# - A tracking reference (AUFG-XX or FIND-XX)
# - A concrete cleanup action
# - An owner (which layer is responsible)
_ORPHAN_EXEMPTIONS: dict[tuple[str, str], str] = {
    # WRITE-009: the ("writing", "story_suggest") exemption was removed —
    # the template is now reachable via the SUGGEST route with
    # context_mode="story_suggest" (manifest context_modes + route_table
    # allowed_context_modes).  No known orphan exemptions remain.
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _manifest_context_modes(entry: ManifestEntry) -> list[ManifestContextMode]:
    """Extract the optional ``context_modes`` list from a manifest entry."""
    raw = entry.get("context_modes")
    if not raw:
        return []
    return list(raw)


def _build_reachable_pairs(
    route_table: dict[str, dict[str, Any]],
    route_configs: dict[str, frozenset[str]],
) -> set[tuple[str, str]]:
    """Build the set of (category, mode) pairs reachable via route_table.

    Includes default modes and ``allowed_context_modes``.
    """
    reachable: set[tuple[str, str]] = set()
    for intent_name, info in route_table.items():
        category = info.get("category", "")
        mode = info.get("mode")
        if category and mode:
            reachable.add((category, str(mode)))
        context_modes = route_configs.get(intent_name, frozenset())
        for cm in context_modes:
            reachable.add((category, cm))
    return reachable


# ---------------------------------------------------------------------------
# D11 — PROMPT-CONTEXT-MODES
# ---------------------------------------------------------------------------


def _check_context_modes(
    result: CheckResult,
    manifest_by_intent: dict[str, ManifestEntry],
    route_configs: dict[str, frozenset[str]],
    root: Path,
    manifest_path: Path,
) -> None:
    """D11 — Validate manifest ``context_modes`` entries."""
    for intent_name in sorted(manifest_by_intent):
        entry = manifest_by_intent[intent_name]
        if not entry.get("routeable", False):
            continue

        context_modes = _manifest_context_modes(entry)
        if not context_modes:
            continue

        m_cat = entry.get("category", "")
        allowed = route_configs.get(intent_name)

        for cm in context_modes:
            cm_mode = str(cm.get("mode", ""))

            if allowed is not None and cm_mode not in allowed:
                result.violations.append(
                    Violation(
                        file=manifest_path,
                        line=0,
                        rule="PROMPT-CONTEXT-MODES",
                        detail=(
                            f"Manifest context_mode {cm_mode!r} for intent "
                            f"{intent_name} is not in route_table "
                            f"allowed_context_modes {sorted(allowed)}. "
                            f"(ADR-049 D7/D11)"
                        ),
                    )
                )

            cm_template = cm.get("template", "")
            if not cm_template:
                result.violations.append(
                    Violation(
                        file=manifest_path,
                        line=0,
                        rule="PROMPT-CONTEXT-MODES",
                        detail=(
                            f"Manifest context_mode {cm_mode!r} for intent "
                            f"{intent_name} has no template path."
                        ),
                    )
                )
                continue

            expected = expected_template_path(m_cat, DEFAULT_LANGUAGE, cm_mode)
            if cm_template != expected:
                result.violations.append(
                    Violation(
                        file=manifest_path,
                        line=0,
                        rule="PROMPT-PATH-DERIVABILITY",
                        detail=(
                            f"Context-mode template for {intent_name}/{cm_mode} "
                            f"is not derivable. Expected {expected!r}, "
                            f"got {cm_template!r}."
                        ),
                    )
                )

            template_path = root / cm_template
            if not template_path.is_file():
                result.violations.append(
                    Violation(
                        file=manifest_path,
                        line=0,
                        rule="PROMPT-CONTEXT-MODES",
                        detail=(
                            f"Context-mode template missing for "
                            f"{intent_name}/{cm_mode}: {cm_template}"
                        ),
                    )
                )
                continue

            check_frontmatter(result, template_path, cm_template, intent_name, m_cat)


# ---------------------------------------------------------------------------
# A6 — ORPHAN-TEMPLATE
# ---------------------------------------------------------------------------


def _check_orphan_templates(
    result: CheckResult,
    manifest_by_intent: dict[str, ManifestEntry],
    reachable_pairs: set[tuple[str, str]],
    root: Path,
) -> None:
    """A6 — Every system.md under _bundled/ must be reachable."""
    bundled_dir = root / "packages" / "core" / "narrare_core" / "prompts" / "_bundled"
    if not bundled_dir.is_dir():
        return

    # Build the set of reachable (category, mode) pairs from manifest entries
    manifest_pairs: set[tuple[str, str]] = set()
    for entry in manifest_by_intent.values():
        if not entry.get("routeable", False):
            continue
        m_cat = entry.get("category", "")
        m_mode = entry.get("mode")
        if m_cat and m_mode:
            manifest_pairs.add((m_cat, str(m_mode)))
        for cm in _manifest_context_modes(entry):
            cm_mode = cm.get("mode", "")
            if m_cat and cm_mode:
                manifest_pairs.add((m_cat, str(cm_mode)))

    all_reachable = manifest_pairs | reachable_pairs

    for template_path in sorted(bundled_dir.rglob("system.md")):
        rel = template_path.relative_to(bundled_dir)
        parts = rel.parts
        if len(parts) < 3:
            category = parts[0] if parts else ""
            if category in CAPABILITY_CATEGORIES:
                continue
            result.violations.append(
                Violation(
                    file=template_path,
                    line=0,
                    rule="ORPHAN-TEMPLATE",
                    detail=(
                        f"Template {rel} has a root-mode path "
                        f"(only {len(parts)} segments). Root-mode templates "
                        f"are forbidden for routeable intents (ADR-049 D3)."
                    ),
                )
            )
            continue

        category = parts[0]
        mode = "/".join(parts[2:-1])

        if category in CAPABILITY_CATEGORIES:
            continue

        if (category, mode) in _ORPHAN_EXEMPTIONS:
            continue

        if (category, mode) not in all_reachable:
            result.violations.append(
                Violation(
                    file=template_path,
                    line=0,
                    rule="ORPHAN-TEMPLATE",
                    detail=(
                        f"Orphan template {rel}: not reachable via any manifest "
                        f"entry, context_mode, route_table mode, or capability "
                        f"category. (category={category!r}, mode={mode!r}). "
                        f"Either add it to the manifest, register it as a "
                        f"context_mode, or document an exemption. (ADR-049 A6)"
                    ),
                )
            )


# ---------------------------------------------------------------------------
# Public orchestrator
# ---------------------------------------------------------------------------


def check_prompt_orphan_and_context_modes(result: CheckResult, root: Path) -> None:
    """Run the A6 ORPHAN-TEMPLATE and D11 PROMPT-CONTEXT-MODES gates.

    Loads the manifest and route_table, builds the reachable-template set,
    and validates context_modes entries + orphan detection.
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
    route_configs = parse_route_configs_context_modes(route_table_path)

    _check_context_modes(result, manifest_by_intent, route_configs, root, manifest_path)

    reachable_pairs = _build_reachable_pairs(route_table, route_configs)
    _check_orphan_templates(result, manifest_by_intent, reachable_pairs, root)
