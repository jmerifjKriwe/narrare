"""Infrastructure-level adoption checks.

Extracted from ``scorer.py`` to keep the scoring core under RULE-04 limits.
Contains the infrastructure-verification logic (prompt_composer, i18n, etc.)
and the evidence-variable mapping.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from adoption.scorer import CheckDetail

# Mapping infrastructure names to the prompt variables that evidence adoption.
_INFRA_VAR_EVIDENCE: dict[str, set[str]] = {
    "mem0_preferences": {"user_preferences", "avoidance_patterns"},
    "kb_entities": {"kb_characters", "kb_locations", "kb_factions"},
    "kb_relationships": {"kb_relationships"},
}


def check_infrastructure(
    infra_name: str,
    level: str,
    all_vars: set[str],
    has_prompts: bool,
    i18n_adopted_frac: float,
) -> CheckDetail:
    """Check a single infrastructure item and return its detail."""
    # Lazy import to avoid circular dependency (scorer → scorer_checks → scorer).
    from adoption.scorer import WEIGHT_PARTIAL, WEIGHT_REQUIRED, CheckDetail

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
    # This is a file-presence proxy — no code-level evidence that services
    # actually use TokenBudgetManager or injection-defense wrapping.  The
    # ``unverified`` flag makes the assumption visible without changing the
    # score (ratchet discipline).  Future work can add code-scanning to flip
    # unverified → verified.
    adopted = 1.0 if has_prompts else 0.0
    note = (
        "unverified — assumed from bundled prompt presence only, no code-level evidence"
        if has_prompts
        else "no prompts to validate"
    )
    return CheckDetail(
        name=infra_name, weight=weight, adopted=adopted, note=note, unverified=has_prompts
    )
