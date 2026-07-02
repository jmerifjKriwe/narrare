# FIND-025 — `analysis/remap` Utility Prompt Below 9-Section Skeleton Standard

> **Status:** `identified` (open)
> **Priority:** P3
> **Source:** CR-01 (ANALYSIS-02)
> **Related:** CR-AUFG-01-12
> **Lifecycle:** `docs/development/finding-lifecycle.md`

---

## Problem

`analysis/en/remap/system.md` is only 36 lines, far below the documented
9-section prompt skeleton. It lacks front-loaded context, user-language output
directive, and a full quality section. Strict checks pass, so either the
checker permits this mode or the skeleton standard overstates machine
enforcement. No local justification is present in the template.

## Code References

- **Short template:** `packages/core/narrare_core/prompts/_bundled/analysis/en/remap/system.md:7-36` — 36 lines, constrained classifier prompt.
- **Missing sections:** no `### Output Language`, no `### Quality Rules` block, no context precedence.
- **Strict checks pass:** `check_prompt_structure.py --strict` does not flag this template, suggesting either a category/mode exemption or the checker allows short utility prompts.
- **No local justification:** the template does not document why it is intentionally small.

## Impact

- This is a minor documentation/governance gap, not a runtime defect.
- The template works correctly as a constrained classifier (returns a single structure-stage id).
- The gap weakens the "every bundled prompt follows the skeleton" documentation claim.

## Prioritized Remediation

1. **Expand `remap` to the standard skeleton** with a `### Utility Prompt Scope` block explaining its constrained nature, plus `### Quality Rules` and `### Output Language` sections.
2. **Or document a utility-prompt exemption** in the checker/manifest if short classifier prompts are intentionally exempt from the full skeleton.
3. **Align checker behavior with documentation** so the standard and enforcement are consistent.

## Alternatives Considered

- **Accept current template.** Acceptable if the exemption is documented; currently undocumented, so it reads as an oversight.
- **Force full skeleton on all prompts.** Rejected: utility classifier prompts may intentionally be short; the fix is documenting the exemption, not over-engineering.
