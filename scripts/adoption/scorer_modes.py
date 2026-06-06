#!/usr/bin/env python3
"""Mode-level adoption scoring extensions (v2.0.0).

Provides data structures and scoring logic for per-mode adoption tracking,
including static verification, runtime verification, and adoption state.

Introduced with the v2.0.0 adoption-registry.yaml format.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from adoption.scorer import (
    INLINE_FALLBACK_PENALTY,
    PASS_THRESHOLD,
    WEIGHT_MUST,
    WEIGHT_SHOULD,
    CheckDetail,
    check_infrastructure,
    status,
)


@dataclass
class RuntimeCheckDetail:
    """One dimension of a runtime requirement check."""

    requirement: str
    declared: str
    evidence_status: str  # "verified" | "missing" | "not_applicable"
    note: str


@dataclass
class ModeScore:
    """Adoption score for a single feature mode."""

    mode: str
    score: float
    status: str  # "PASS" | "WARN" | "FAIL"
    static_verified: bool
    runtime_verified: bool
    adopted: bool
    details: list[CheckDetail] = field(default_factory=list[CheckDetail])
    runtime_details: list[RuntimeCheckDetail] = field(default_factory=list[RuntimeCheckDetail])


# TODO(P1): Replace with test probe JSON reading in follow-up; currently
# defaults to 'missing' for required runtime checks.
_RUNTIME_EVIDENCE_DEFAULT: dict[str, str] = {
    "none": "verified",
    "optional": "verified",
    "provided": "verified",
    "required": "missing",
    "not_applicable": "not_applicable",
    "budget_rejected": "missing",
}

_RUNTIME_NOTE: dict[str, str] = {
    "none": "no runtime requirement to verify",
    "optional": "runs if available; no mandatory probe needed",
    "provided": "provided by the system; no runtime check needed",
    "required": "test probe needed but not yet available",
    "not_applicable": "does not apply to this mode",
    "budget_rejected": "feature requested but rejected by budget manager",
}


def _check_runtime_requirements(
    runtime_reqs: dict[str, str],
) -> tuple[list[RuntimeCheckDetail], bool]:
    """Check runtime requirements; return (details, all_verified).

    For P1 CI, this uses static defaults (see _RUNTIME_EVIDENCE_DEFAULT).
    A follow-up will replace this with test probe JSON reading.
    """
    details: list[RuntimeCheckDetail] = []
    all_verified = True
    for req, declared in sorted(runtime_reqs.items()):
        evidence = _RUNTIME_EVIDENCE_DEFAULT.get(declared, "missing")
        if evidence != "verified":
            all_verified = False
        note = _RUNTIME_NOTE.get(declared, f"declared '{declared}'")
        details.append(
            RuntimeCheckDetail(
                requirement=req,
                declared=declared,
                evidence_status=evidence,
                note=note,
            )
        )
    return details, all_verified


def compute_mode_score(
    mode_name: str,
    must_vars: list[str],
    should_vars: list[str],
    infra: dict[str, str],
    runtime_reqs: dict[str, str],
    all_vars: set[str],
    i18n_frac: float,
    has_prompts: bool,
    fb_count: int,
) -> ModeScore:
    """Compute adoption score for a single mode.

    Static score uses the same weighted-ratio formula as the category-level
    scorer.  Runtime-requirement checks use static defaults for P1 CI.
    """
    details: list[CheckDetail] = []
    numerator = 0.0
    denominator = 0.0

    # MUST variables (weight 1.0).
    if must_vars:
        present_count = sum(1 for v in must_vars if v in all_vars)
        numerator += WEIGHT_MUST * present_count
        denominator += WEIGHT_MUST * len(must_vars)
        missing = [v for v in must_vars if v not in all_vars]
        details.append(
            CheckDetail(
                name="must_vars",
                weight=WEIGHT_MUST,
                adopted=float(present_count),
                note=(f"{present_count}/{len(must_vars)} present" if missing else "all present"),
            )
        )

    # SHOULD variables (weight 0.3).
    if should_vars:
        present_count = sum(1 for v in should_vars if v in all_vars)
        numerator += WEIGHT_SHOULD * present_count
        denominator += WEIGHT_SHOULD * len(should_vars)
        details.append(
            CheckDetail(
                name="should_vars",
                weight=WEIGHT_SHOULD,
                adopted=float(present_count),
                note=f"{present_count}/{len(should_vars)} present",
            )
        )

    # Infrastructure items.
    for infra_name, level in infra.items():
        detail = check_infrastructure(infra_name, level, all_vars, has_prompts, i18n_frac)
        details.append(detail)
        numerator += detail.weight * detail.adopted
        denominator += detail.weight

    # Inline fallback penalty.
    if fb_count:
        penalty = INLINE_FALLBACK_PENALTY * fb_count
        numerator -= penalty
        details.append(
            CheckDetail(
                name="inline_fallbacks",
                weight=INLINE_FALLBACK_PENALTY,
                adopted=0.0,
                note=f"{fb_count} registered fallback(s), penalty: -{penalty:.1f}",
            )
        )

    score = numerator / denominator if denominator > 0 else 1.0
    score = max(0.0, min(1.0, score))
    static_verified = score >= PASS_THRESHOLD

    # Runtime checks.
    if runtime_reqs:
        runtime_details, runtime_verified = _check_runtime_requirements(runtime_reqs)
    else:
        runtime_details, runtime_verified = [], False

    adopted = static_verified and runtime_verified

    return ModeScore(
        mode=mode_name,
        score=score,
        status=status(score),
        static_verified=static_verified,
        runtime_verified=runtime_verified,
        adopted=adopted,
        details=details,
        runtime_details=runtime_details,
    )


def normalize_modes(
    modes_raw: dict[str, Any] | list[Any],
) -> list[tuple[str, dict[str, object]]]:
    """Normalize modes to ``[(name, config), ...]``.

    Supports both the v2.0.0 dict format (where each mode has optional
    overrides) and the legacy list-of-strings format for backward compat.
    """
    if isinstance(modes_raw, dict):
        return list(modes_raw.items())
    # Backward compat: list[str] → [(name, {})]
    return [(mode, {}) for mode in modes_raw]


def compute_all_mode_scores(
    mode_items: list[tuple[str, dict[str, Any]]],
    infra: dict[str, str],
    must_vars: list[str],
    should_vars: list[str],
    cat_runtime: dict[str, str],
    all_vars: set[str],
    i18n_frac: float,
    has_prompts: bool,
    fb_count: int,
) -> list[ModeScore]:
    """Compute ModeScores for all modes in a category."""
    scores: list[ModeScore] = []
    for mode_name, mode_cfg in mode_items:
        overrides = mode_cfg.get("overrides", {})

        # Resolve infrastructure overrides.
        merged_infra = {**infra, **(overrides.get("required_infrastructure", {}))}

        # Resolve context variable overrides (partial — only keys present).
        override_ctx = overrides.get("context_variables", {})
        mode_must = override_ctx.get("must", must_vars)
        mode_should = override_ctx.get("should", should_vars)

        # Resolve runtime requirements (category defaults + mode overrides).
        merged_runtime = {**cat_runtime, **(overrides.get("runtime_requirements", {}))}

        ms = compute_mode_score(
            mode_name=mode_name,
            must_vars=mode_must,
            should_vars=mode_should,
            infra=merged_infra,
            runtime_reqs=merged_runtime,
            all_vars=all_vars,
            i18n_frac=i18n_frac,
            has_prompts=has_prompts,
            fb_count=fb_count,
        )
        scores.append(ms)
    return scores
