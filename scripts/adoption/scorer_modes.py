#!/usr/bin/env python3
"""Mode-level adoption scoring extensions (v2.0.0).

Provides data structures and scoring logic for per-mode adoption tracking,
including static verification, runtime verification, and adoption state.

Introduced with the v2.0.0 adoption-registry.yaml format.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from adoption._scorer_evidence import apply_evidence_override
from adoption.scorer import (
    INLINE_FALLBACK_PENALTY,
    PASS_THRESHOLD,
    WEIGHT_MUST,
    WEIGHT_SHOULD,
    status,
)
from adoption.scorer_checks import check_infrastructure
from adoption.scorer_models import CheckDetail


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
    requires_runtime_evidence: bool = False
    details: list[CheckDetail] = field(default_factory=list[CheckDetail])
    runtime_details: list[RuntimeCheckDetail] = field(default_factory=list[RuntimeCheckDetail])


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


def load_probe_evidence(evidence_dir: str) -> dict[str, set[str]]:
    """Backward-compatible wrapper for the central evidence loader."""
    from adoption.scorer_evidence import load_probe_evidence as _load_probe_evidence

    return _load_probe_evidence(evidence_dir=evidence_dir)


def _check_runtime_requirements(
    runtime_reqs: dict[str, str],
    probe_evidence: dict[str, set[str]] | None = None,
    mode_feature_id: str | None = None,
    mode_name: str | None = None,
    preference_evidence: dict[str, set[str]] | None = None,
    validation_evidence: dict[str, set[str]] | None = None,
    budget_evidence: dict[str, set[str]] | None = None,
    evidence_sink_evidence: dict[str, set[str]] | None = None,
) -> tuple[list[RuntimeCheckDetail], bool]:
    """Check runtime requirements; return (details, all_verified).

    Uses static defaults (see _RUNTIME_EVIDENCE_DEFAULT) with optional
    overrides from probe evidence and preference enrichment evidence.
    """
    details: list[RuntimeCheckDetail] = []
    all_verified = True
    for req, declared in sorted(runtime_reqs.items()):
        evidence = _RUNTIME_EVIDENCE_DEFAULT.get(declared, "missing")
        if evidence not in ("verified", "not_applicable"):
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

    # ── Evidence overrides ──────────────────────────────────────────
    details, all_verified = apply_evidence_override(
        details,
        all_verified,
        evidence_sink_evidence,
        mode_feature_id,
        mode_name,
        "evidence_sink",
        "verified by evidence sink probe",
    )
    details, all_verified = apply_evidence_override(
        details,
        all_verified,
        preference_evidence,
        mode_feature_id,
        mode_name,
        "preference_enrichment",
        "verified by preference enrichment probe",
    )
    details, all_verified = apply_evidence_override(
        details,
        all_verified,
        validation_evidence,
        mode_feature_id,
        mode_name,
        "final_validation",
        "verified by validation probe",
    )
    details, all_verified = apply_evidence_override(
        details,
        all_verified,
        budget_evidence,
        mode_feature_id,
        mode_name,
        "budget_resolution",
        "verified by budget probe",
    )
    details, all_verified = apply_evidence_override(
        details,
        all_verified,
        budget_evidence,
        mode_feature_id,
        mode_name,
        "kb_suggested",
        "budget rejected (verified by budget probe)",
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
    requires_runtime_evidence: bool = True,
    probe_evidence: dict[str, set[str]] | None = None,
    mode_feature_id: str | None = None,
    preference_evidence: dict[str, set[str]] | None = None,
    validation_evidence: dict[str, set[str]] | None = None,
    budget_evidence: dict[str, set[str]] | None = None,
    evidence_sink_evidence: dict[str, set[str]] | None = None,
) -> ModeScore:
    """Compute adoption score for a single mode.

    Static score uses the same ratio formula as category-level scorer.
    Runtime checks use static defaults with optional overrides from
    probe evidence and preference enrichment evidence.

    When *requires_runtime_evidence* is True the ``adopted`` flag requires
    both static and runtime verification (ADR-040 Decision 4).
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
        runtime_details, runtime_verified = _check_runtime_requirements(
            runtime_reqs,
            probe_evidence=probe_evidence,
            mode_feature_id=mode_feature_id,
            mode_name=mode_name,
            preference_evidence=preference_evidence,
            validation_evidence=validation_evidence,
            budget_evidence=budget_evidence,
            evidence_sink_evidence=evidence_sink_evidence,
        )
    else:
        runtime_details, runtime_verified = [], False

    adopted = static_verified and runtime_verified if requires_runtime_evidence else static_verified

    return ModeScore(
        mode=mode_name,
        score=score,
        status=status(score),
        static_verified=static_verified,
        runtime_verified=runtime_verified,
        adopted=adopted,
        requires_runtime_evidence=requires_runtime_evidence,
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
    probe_evidence: dict[str, set[str]] | None = None,
    feature_id: str | None = None,
    preference_evidence: dict[str, set[str]] | None = None,
    validation_evidence: dict[str, set[str]] | None = None,
    budget_evidence: dict[str, set[str]] | None = None,
    evidence_sink_evidence: dict[str, set[str]] | None = None,
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

        # Resolve requires_runtime_evidence from mode config (ADR-040 Decision 4).
        requires_rte = mode_cfg.get("requires_runtime_evidence", True)

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
            requires_runtime_evidence=requires_rte,
            probe_evidence=probe_evidence,
            mode_feature_id=feature_id,
            preference_evidence=preference_evidence,
            validation_evidence=validation_evidence,
            budget_evidence=budget_evidence,
            evidence_sink_evidence=evidence_sink_evidence,
        )
        scores.append(ms)
    return scores
