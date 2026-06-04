#!/usr/bin/env python3
"""
Adoption score computation — weighted ratio from registry.

Reads the ``adoption-registry.yaml`` and bundled prompt files to compute
per-category and overall feature adoption scores.

Formula (ADR-025 Decision 5):
    Score = sum(weight * adopted) / sum(weight * applicable)

Weights:
    - ``must`` variables:       1.0
    - ``should`` variables:     0.3
    - ``partial`` infrastructure: 0.5
    - ``required`` infrastructure: 1.0
    - ``inline_fallback``:     -0.1 per fallback (penalty)

Thresholds:
    - >= 0.85  -> PASS
    - 0.70-0.85 -> WARN
    - < 0.70  -> FAIL
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from prompt_checks import PromptFile

# ── Constants ──────────────────────────────────────────────────────

PASS_THRESHOLD = 0.85
WARN_THRESHOLD = 0.70

WEIGHT_MUST = 1.0
WEIGHT_SHOULD = 0.3
WEIGHT_REQUIRED = 1.0
WEIGHT_PARTIAL = 0.5
INLINE_FALLBACK_PENALTY = 0.1

# Categories requiring full DE/FR locale bundles (ADR-026 Phase 5).
_LOCALIZED_REQUIRED_CATEGORIES = {"meta", "universal", "universal_rules"}


def _required_locales_for(category: str) -> set[str]:
    """Return required locales for *category* (ADR-026 Phase 5 policy).

    Localized-required categories (meta, universal, universal_rules) need
    ``en``, ``de``, and ``fr`` variants.  All other categories (writing,
    analysis, KB, planning, generation, chat) are EN-only feature prompts.
    """
    if category in _LOCALIZED_REQUIRED_CATEGORIES:
        return {"en", "de", "fr"}
    return {"en"}


# Mapping infrastructure names to the prompt variables that evidence adoption.
_INFRA_VAR_EVIDENCE: dict[str, set[str]] = {
    "mem0_preferences": {"user_preferences", "avoidance_patterns"},
    "kb_entities": {"kb_characters", "kb_locations", "kb_factions"},
    "kb_relationships": {"kb_relationships"},
}


# ── Data structures ────────────────────────────────────────────────


@dataclass
class CheckDetail:
    """One dimension of the adoption check."""

    name: str
    weight: float
    adopted: float  # 0.0-1.0 (for partial: 0.5 when missing)
    applicable: bool = True
    note: str = ""


@dataclass
class CategoryScore:
    """Adoption score for a single feature category."""

    category: str
    score: float
    status: str  # "PASS" | "WARN" | "FAIL"
    details: list[CheckDetail] = field(default_factory=list[CheckDetail])
    missing_must: list[str] = field(default_factory=list[str])
    missing_should: list[str] = field(default_factory=list[str])
    missing_locales: dict[str, list[str]] = field(default_factory=dict[str, list[str]])
    inline_fallbacks: int = 0


@dataclass
class AdoptionReport:
    """Complete adoption report across all feature categories."""

    overall_score: float
    status: str  # "PASS" | "WARN" | "FAIL"
    categories: list[CategoryScore] = field(default_factory=list[CategoryScore])
    total_inline_fallbacks: int = 0


# ── Helpers ────────────────────────────────────────────────────────


def _status(score: float) -> str:
    if score >= PASS_THRESHOLD:
        return "PASS"
    if score >= WARN_THRESHOLD:
        return "WARN"
    return "FAIL"


def _collect_category_vars(
    prompts: list[PromptFile],
    category: str,
) -> set[str]:
    """Union of all variables across EN system.md prompts for *category*."""
    return {
        var
        for p in prompts
        if p.category == category and p.is_system_md and p.locale == "en"
        for var in p.variables
    }


def _check_i18n_coverage(
    prompts: list[PromptFile],
    category: str,
    modes: list[str],
) -> tuple[dict[str, list[str]], float, int, int]:
    """Check locale coverage; return (missing_map, adopted_frac, applicable, adopted)."""
    category_system = [p for p in prompts if p.category == category and p.is_system_md]

    # Group by group_key (category or category/mode).
    groups: dict[str, set[str]] = {}
    for p in category_system:
        groups.setdefault(p.group_key, set()).add(p.locale)

    # For categories with no mode subdirectories (e.g. chat).
    if not groups:
        return {}, 0.0, 0, 0

    required = _required_locales_for(category)

    missing_map: dict[str, list[str]] = {}
    total_applicable = 0
    total_covered = 0

    for key in sorted(groups):
        present = groups[key]
        missing = sorted(required - present)
        total_applicable += len(required)
        total_covered += len(present & required)
        if missing:
            # Show missing for the primary locale's key.
            missing_map[key] = missing

    # Also check modes registered in the registry but missing from filesystem.
    if modes:
        mode_keys_in_fs = {p.group_key for p in category_system}
        for mode in modes:
            expected_key = f"{category}/{mode}"
            # Only flag for localized-required categories (feature
            # categories are EN-only — variable checks cover missing EN).
            if expected_key not in mode_keys_in_fs and required != {"en"}:
                missing_map[expected_key] = sorted(required)

    adopted_frac = total_covered / total_applicable if total_applicable else 0.0
    return missing_map, adopted_frac, total_applicable, total_covered


def _check_infrastructure(
    infra_name: str,
    level: str,
    all_vars: set[str],
    has_prompts: bool,
    i18n_adopted_frac: float,
) -> CheckDetail:
    """Check a single infrastructure item and return its detail."""
    weight = WEIGHT_REQUIRED if level == "required" else WEIGHT_PARTIAL

    # Infrastructure that can be checked via variable presence.
    if infra_name in _INFRA_VAR_EVIDENCE:
        evidence_vars = _INFRA_VAR_EVIDENCE[infra_name]
        present = bool(all_vars & evidence_vars)
        adopted = 1.0 if present else (0.5 if level == "partial" else 0.0)
        note = (
            f"vars present: {sorted(all_vars & evidence_vars)}"
            if present
            else f"no evidence vars found ({sorted(evidence_vars)})"
        )
        return CheckDetail(name=infra_name, weight=weight, adopted=adopted, note=note)

    # prompt_composer / meta_prompt: adopted if bundled prompts exist.
    if infra_name in ("prompt_composer", "meta_prompt"):
        adopted = 1.0 if has_prompts else 0.0
        note = "bundled prompts exist" if has_prompts else "no bundled prompts"
        return CheckDetail(name=infra_name, weight=weight, adopted=adopted, note=note)

    # i18n: adopted proportionally to locale coverage.
    if infra_name == "i18n":
        adopted = i18n_adopted_frac
        note = f"locale coverage: {i18n_adopted_frac:.0%}"
        return CheckDetail(name=infra_name, weight=weight, adopted=adopted, note=note)

    # token_budget / injection_defense: assume adopted if bundled prompts exist.
    adopted = 1.0 if has_prompts else 0.0
    note = "assumed adopted (bundled prompts present)" if has_prompts else "no prompts to validate"
    return CheckDetail(name=infra_name, weight=weight, adopted=adopted, note=note)


def _map_fallbacks_to_categories(
    fallbacks: list[dict[str, str]],
    category_modes: dict[str, list[str]],
) -> dict[str, int]:
    """Heuristically map inline fallback files to feature categories."""
    result: dict[str, str] = {}
    for fb in fallbacks:
        fp = fb.get("file", "")
        # Direct path patterns.
        if "/kb/" in fp or "/consistency/" in fp:
            result[fp] = "kb"
        elif "/writing_" in fp or "/writing/" in fp:
            result[fp] = "writing"
        elif "/analysis/" in fp:
            result[fp] = "analysis"
        elif "/planning/" in fp:
            result[fp] = "planning"
        elif "/generation/" in fp:
            result[fp] = "generation"
        elif "/chat/" in fp:
            result[fp] = "chat"
        else:
            result[fp] = ""  # unmapped

    counts: dict[str, int] = {}
    for cat in category_modes:
        counts[cat] = sum(1 for v in result.values() if v == cat)
    return counts


# ── Public API ─────────────────────────────────────────────────────


def compute_adoption_report(
    registry: dict[str, Any],
    prompts: list[PromptFile],
) -> AdoptionReport:
    """Compute the full adoption report from registry data and parsed prompts."""
    features: dict[str, Any] = registry.get("features", {})
    fallbacks: list[dict[str, str]] = registry.get("inline_fallbacks", []) or []

    category_modes: dict[str, list[str]] = {
        name: list(cfg.get("modes", [])) for name, cfg in features.items()
    }
    fallback_counts = _map_fallbacks_to_categories(fallbacks, category_modes)

    categories: list[CategoryScore] = []

    for cat_name, cfg in sorted(features.items()):
        all_vars = _collect_category_vars(prompts, cat_name)
        modes = cfg.get("modes", [])
        infra = cfg.get("required_infrastructure", {})
        ctx = cfg.get("context_variables", {})

        must_vars: list[str] = ctx.get("must", []) or []
        should_vars: list[str] = ctx.get("should", []) or []

        # Variable checks.
        missing_must = [v for v in must_vars if v not in all_vars]
        missing_should = [v for v in should_vars if v not in all_vars]

        # i18n check.
        missing_locales, i18n_frac, _, _ = _check_i18n_coverage(prompts, cat_name, modes)

        has_prompts = bool([p for p in prompts if p.category == cat_name and p.is_system_md])

        # ── Score computation ──────────────────────────────────
        numerator = 0.0
        denominator = 0.0
        details: list[CheckDetail] = []

        # MUST variables (weight 1.0).
        if must_vars:
            present_count = len(must_vars) - len(missing_must)
            numerator += WEIGHT_MUST * present_count
            denominator += WEIGHT_MUST * len(must_vars)
            details.append(
                CheckDetail(
                    name="must_vars",
                    weight=WEIGHT_MUST,
                    adopted=float(present_count),
                    note=(
                        f"{present_count}/{len(must_vars)} present"
                        if missing_must
                        else "all present"
                    ),
                )
            )

        # SHOULD variables (weight 0.3).
        if should_vars:
            present_count = len(should_vars) - len(missing_should)
            numerator += WEIGHT_SHOULD * present_count
            denominator += WEIGHT_SHOULD * len(should_vars)
            details.append(
                CheckDetail(
                    name="should_vars",
                    weight=WEIGHT_SHOULD,
                    adopted=float(present_count),
                    note=(
                        f"{present_count}/{len(should_vars)} present"
                        if missing_should
                        else "all present"
                    ),
                )
            )

        # Infrastructure items.
        for infra_name, level in infra.items():
            detail = _check_infrastructure(infra_name, level, all_vars, has_prompts, i18n_frac)
            details.append(detail)
            numerator += detail.weight * detail.adopted
            denominator += detail.weight

        # Inline fallback penalty.
        fb_count = fallback_counts.get(cat_name, 0)
        penalty = INLINE_FALLBACK_PENALTY * fb_count
        numerator -= penalty
        if fb_count:
            details.append(
                CheckDetail(
                    name="inline_fallbacks",
                    weight=INLINE_FALLBACK_PENALTY,
                    adopted=0.0,
                    note=f"{fb_count} registered fallback(s), penalty: -{penalty:.1f}",
                )
            )

        score = numerator / denominator if denominator > 0 else 1.0
        score = max(0.0, min(1.0, score))  # clamp to [0, 1]

        categories.append(
            CategoryScore(
                category=cat_name,
                score=score,
                status=_status(score),
                details=details,
                missing_must=missing_must,
                missing_should=missing_should,
                missing_locales=missing_locales,
                inline_fallbacks=fb_count,
            )
        )

    # Overall score: simple average of category scores.
    overall = (sum(c.score for c in categories) / len(categories)) if categories else 1.0

    return AdoptionReport(
        overall_score=overall,
        status=_status(overall),
        categories=categories,
        total_inline_fallbacks=len(fallbacks),
    )
