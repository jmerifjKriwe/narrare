"""Infrastructure-level adoption checks.

Extracted from ``scorer.py`` to keep the scoring core under RULE-04 limits.
Contains the infrastructure-verification logic (prompt_composer, i18n, etc.)
and the evidence-variable mapping.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from adoption.scorer import CheckDetail

# Evidence-variable matrix — Model alpha (per-(category, infra_dim) vocab).
#
# Consumer vs. owner distinction (RULE-18b false-control fix; see the cr-05
# follow-up "Adoption-Score-Honesty"). Each ``(category, infra_dim)`` cell
# explicitly declares how THAT category expresses adoption of the dimension:
#
#   - CONSUMER categories (writing, analysis, ...) *receive* entity /
#     relationship data under the generic context-variable names emitted by the
#     KB render layer (``kb_characters`` / ``kb_locations`` / ``kb_factions`` /
#     ``kb_relationships``).
#   - OWNER category (``kb``) *produces* that data and consumes it internally
#     under its own domain variable names (``existing_entity_names`` /
#     ``entity_summaries`` / ``entity_details`` / ``existing_relationships``).
#
# The pre-alpha shape (``dict[infra_dim, set[var]]``) collapsed both roles into one
# flat vocab. That caused a false negative — the owner never emits its own
# consumer-facing var names, so it was scored ``adopted=0.0`` on a ``required``
# dimension — and made the mapping structurally fragile (two independent
# honesty bugs surfaced from it; see the cr-05 follow-up). Model alpha makes the
# role explicit per cell: a variable counts only for its declared category, so
# there is no consumer/owner conflation and no false positives.
#
# Full matrix completeness (every declared ``(category, dim)`` pair) is the
# subject of the follow-up mapping audit; the cells below hold the verified,
# runtime-wired vocab only — no invented variables.
_INFRA_VAR_EVIDENCE: dict[tuple[str, str], set[str]] = {
    # ── mem0_preferences — consumer vocab, identical across categories ──
    ("writing", "mem0_preferences"): {"user_preferences", "avoidance_patterns"},
    ("analysis", "mem0_preferences"): {"user_preferences", "avoidance_patterns"},
    ("kb", "mem0_preferences"): {"user_preferences", "avoidance_patterns"},
    # ── kb_entities ──
    # OWNER (kb) consumes entities under domain var names — verified at
    # apps/api/narrare/kb/{extraction_service,worldbuilding_analyzer,
    # consistency_service}.py. This is the cr-05 owner fix.
    ("kb", "kb_entities"): {
        "existing_entity_names",
        "entity_summaries",
        "entity_details",
    },
    # CONSUMERS receive the rendered entity lists.
    ("writing", "kb_entities"): {"kb_characters", "kb_locations", "kb_factions"},
    # analysis additionally consumes the canonical singular {{kb_entities}} var
    # directly (consistency + fact_extraction prompt_builder, runtime-real) — not
    # just the rendered consumer triple — so credit that too (mapping-audit F1).
    ("analysis", "kb_entities"): {
        "kb_characters",
        "kb_locations",
        "kb_factions",
        "kb_entities",
    },
    # ── kb_relationships ──
    # OWNER (kb) consumes relationships under the domain name — verified in
    # kb/en/{worldbuilding/phase1,worldbuilding/phase2,improve}/system.md.
    # kb declares kb_relationships infrastructure (required); this cell scores
    # it adopted via the owner var (mapping-audit F3).
    ("kb", "kb_relationships"): {"existing_relationships"},
    # CONSUMERS receive the rendered relationship graph.
    ("writing", "kb_relationships"): {"kb_relationships"},
    ("analysis", "kb_relationships"): {"kb_relationships"},
}


def check_infrastructure(
    infra_name: str,
    category: str,
    level: str,
    all_vars: set[str],
    has_prompts: bool,
    i18n_adopted_frac: float,
) -> CheckDetail:
    """Check a single infrastructure item and return its detail.

    *category* selects the evidence vocabulary for *infra_name* per Model alpha
    (see ``_INFRA_VAR_EVIDENCE``). Each category expresses adoption of a
    dimension differently — consumers via rendered context vars, the owner
    (kb) via its own domain vars — so the lookup is per ``(category, infra)``.
    """
    # Lazy import to avoid circular dependency (scorer → scorer_checks → scorer).
    from adoption.scorer import WEIGHT_PARTIAL, WEIGHT_REQUIRED, CheckDetail

    weight = WEIGHT_REQUIRED if level == "required" else WEIGHT_PARTIAL

    # Infrastructure that can be checked via variable presence (Model alpha lookup).
    evidence_vars = _INFRA_VAR_EVIDENCE.get((category, infra_name))
    if evidence_vars is not None:
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
