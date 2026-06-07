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

from adoption.scorer_checks import check_infrastructure

if TYPE_CHECKING:
    from prompt_checks import PromptFile

    from adoption.scorer_modes import ModeScore

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
    modes: list[ModeScore] = field(default_factory=list)  # pyright: ignore[reportUnknownVariableType] — circular TYPE_CHECKING dep


@dataclass
class AdoptionReport:
    """Complete adoption report across all feature categories."""

    overall_score: float
    status: str  # "PASS" | "WARN" | "FAIL"
    categories: list[CategoryScore] = field(default_factory=list[CategoryScore])
    total_inline_fallbacks: int = 0
    mode_count: int = 0
    runtime_verified_count: int = 0
    adopted_count: int = 0
    runtime_evidence_gap_count: int = 0


# ── Helpers ────────────────────────────────────────────────────────


def status(score: float) -> str:
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
    evidence_dir: str | None = None,
    evidence_repo: Any | None = None,
) -> AdoptionReport:
    """Compute the full adoption report from registry data and parsed prompts."""
    from adoption.scorer_evidence import (
        load_preference_enrichment_evidence,
        load_probe_evidence,
    )
    from adoption.scorer_modes import normalize_modes as _norm

    pref_evidence: dict[str, set[str]] = {}
    probe_evidence: dict[str, set[str]] = {}
    if evidence_dir:
        pref_evidence = load_preference_enrichment_evidence(evidence_dir)
        probe_evidence = load_probe_evidence(evidence_dir=evidence_dir)
    elif evidence_repo:
        probe_evidence = load_probe_evidence(evidence_repo=evidence_repo)

    features: dict[str, Any] = registry.get("features", {})
    fallbacks: list[dict[str, str]] = registry.get("inline_fallbacks", []) or []
    category_defaults: dict[str, Any] = registry.get("category_defaults", {})

    category_modes: dict[str, list[str]] = {
        name: [mn for mn, _ in _norm(cfg.get("modes", []))] for name, cfg in features.items()
    }
    fallback_counts = _map_fallbacks_to_categories(fallbacks, category_modes)

    categories: list[CategoryScore] = []

    for cat_name, cfg in sorted(features.items()):
        all_vars = _collect_category_vars(prompts, cat_name)
        mode_items = _norm(cfg.get("modes", []))
        mode_names = [name for name, _ in mode_items]
        infra = cfg.get("required_infrastructure", {})
        ctx = cfg.get("context_variables", {})

        must_vars: list[str] = ctx.get("must", []) or []
        should_vars: list[str] = ctx.get("should", []) or []

        # Variable checks.
        missing_must = [v for v in must_vars if v not in all_vars]
        missing_should = [v for v in should_vars if v not in all_vars]

        # i18n check.
        missing_locales, i18n_frac, _, _ = _check_i18n_coverage(prompts, cat_name, mode_names)
        has_prompts = bool([p for p in prompts if p.category == cat_name and p.is_system_md])
        cat_runtime: dict[str, str] = category_defaults.get(cat_name, {}).get(
            "runtime_requirements", {}
        )

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
            detail = check_infrastructure(infra_name, level, all_vars, has_prompts, i18n_frac)
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

        from adoption.scorer_modes import compute_all_mode_scores as _score_modes

        mode_scores = _score_modes(
            mode_items=mode_items,
            infra=infra,
            must_vars=must_vars,
            should_vars=should_vars,
            cat_runtime=cat_runtime,
            all_vars=all_vars,
            i18n_frac=i18n_frac,
            has_prompts=has_prompts,
            fb_count=fb_count,
            probe_evidence=probe_evidence or None,
            feature_id=cat_name,
            preference_evidence=pref_evidence or None,
        )
        categories.append(
            CategoryScore(
                category=cat_name,
                score=score,
                status=status(score),
                details=details,
                missing_must=missing_must,
                missing_should=missing_should,
                missing_locales=missing_locales,
                inline_fallbacks=fb_count,
                modes=mode_scores,
            )
        )

    overall = (sum(c.score for c in categories) / len(categories)) if categories else 1.0
    return AdoptionReport(
        overall_score=overall,
        status=status(overall),
        categories=categories,
        total_inline_fallbacks=len(fallbacks),
        mode_count=sum(len(c.modes) for c in categories),
        runtime_verified_count=sum(1 for c in categories for m in c.modes if m.runtime_verified),
        adopted_count=sum(1 for c in categories for m in c.modes if m.adopted),
        runtime_evidence_gap_count=sum(
            1 for c in categories for m in c.modes if m.requires_runtime_evidence and not m.adopted
        ),
    )
