#!/usr/bin/env python3
"""Mode-level adoption scoring extensions (v2.0.0).

Provides data structures and scoring logic for per-mode adoption tracking,
including static verification, runtime verification, and adoption state.

Introduced with the v2.0.0 adoption-registry.yaml format.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from narrare.evidence.contracts import EvidenceRepository

from adoption.scorer import (
    INLINE_FALLBACK_PENALTY,
    PASS_THRESHOLD,
    WEIGHT_MUST,
    WEIGHT_SHOULD,
    CheckDetail,
    status,
)
from adoption.scorer_checks import check_infrastructure


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


# Now partially replaced by probe evidence (evidence_sink + optional final_validation).
# Remaining requirements (preference_enrichment, required final_validation) need dedicated probes.
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


_KNOWN_FEATURES: list[str] = [
    "writing",
    "analysis",
    "kb",
    "planning",
    "generation",
    "memory",
    "chat",
]


def _load_from_repo(evidence_repo: EvidenceRepository) -> dict[str, set[str]]:
    """Load probe evidence from an EvidenceRepository.

    Calls ``get_distinct_modes()`` for each known feature and returns
    the same ``dict[str, set[str]]`` format as the file-based loader.

    Returns ``{}`` if the repo raises.
    """
    known = _KNOWN_FEATURES

    async def _query() -> dict[str, set[str]]:
        result: dict[str, set[str]] = {}
        for fid in known:
            modes = await evidence_repo.get_distinct_modes(fid)
            if modes:
                result[fid] = set(modes)
        return result

    try:
        return asyncio.run(_query())
    except Exception:
        return {}


def load_probe_evidence(
    evidence_dir: str | Path | None = None,
    evidence_repo: Any | None = None,
) -> dict[str, set[str]]:
    """Load probe evidence from file or repository.

    When *evidence_repo* is provided, queries the ``EvidenceRepository``
    for distinct modes per known feature.  Otherwise falls back to
    reading from ``invocations.jsonl`` under *evidence_dir*.

    Returns mapping: feature_id -> {mode1, mode2, ...}
    Returns empty dict if no evidence source is available.
    """
    if evidence_repo is not None:
        return _load_from_repo(evidence_repo)

    if evidence_dir is not None:
        evidence_file = Path(evidence_dir) / "invocations.jsonl"
        if not evidence_file.exists():
            return {}

        result: dict[str, set[str]] = {}
        with evidence_file.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                fid = record.get("feature_id")
                mode = record.get("mode")
                if fid and mode:
                    result.setdefault(fid, set()).add(mode)
        return result

    return {}


def _check_runtime_requirements(
    runtime_reqs: dict[str, str],
    probe_evidence: dict[str, set[str]] | None = None,
    mode_feature_id: str | None = None,
    mode_name: str | None = None,
) -> tuple[list[RuntimeCheckDetail], bool]:
    """Check runtime requirements; return (details, all_verified).

    Uses static defaults (see _RUNTIME_EVIDENCE_DEFAULT) with optional
    overrides from probe evidence.
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

    # ── Probe evidence overrides ─────────────────────────────────
    if (
        probe_evidence
        and mode_feature_id
        and mode_name
        and mode_name in probe_evidence.get(mode_feature_id, set())
    ):
        for detail in details:
            if detail.requirement == "evidence_sink" and detail.evidence_status == "missing":
                detail.evidence_status = "verified"
                detail.note = "verified by probe evidence"
                if all_verified is False:
                    # Check if this was the only failing requirement
                    all_verified = all(d.evidence_status == "verified" for d in details)
            if (
                detail.requirement == "final_validation"
                and detail.declared == "optional"
                and detail.evidence_status == "missing"
            ):
                detail.evidence_status = "verified"
                detail.note = "optional validator skipped, pipeline stable"

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
) -> ModeScore:
    """Compute adoption score for a single mode.

    Static score uses the same weighted-ratio formula as the category-level
    scorer.  Runtime-requirement checks use static defaults for P1 CI,
    with optional overrides from probe evidence.

    When *requires_runtime_evidence* is True the ``adopted`` flag requires
    both static and runtime verification.  When False, static verification
    alone is sufficient (ADR-040 Decision 4).
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
        )
        scores.append(ms)
    return scores
