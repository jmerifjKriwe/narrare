# FIND-019 — Subjective Analysis Lacks Item-Level Confidence Calibration

> **Status:** `identified` (open)
> **Priority:** P2
> **Source:** CR-01 (ANALYSIS-01), carried by CR-02, CR-03
> **Related:** CR-AUFG-01-11, CR-AUFG-02-13, CR-AUFG-03-11
> **Lifecycle:** `docs/development/finding-lifecycle.md`

---

## Problem

Subjective analysis prompts (beta-reader, beta-reader deep-dive, review)
emit feedback/issues with `text_excerpt` but no `confidence` or equivalent
low-confidence handling in the schema. This conflicts with the
collaborator-not-judge persona in `NarrareMeta` — subjective outputs sound
overly certain without calibration.

## Code References

- **beta_reader:** `packages/core/narrare_core/prompts/_bundled/analysis/en/beta_reader/system.md:119-161`, `172-180` — strengths/feedback/questions with `text_excerpt` but no `confidence` field.
- **beta_reader_deepdive:** `analysis/en/beta_reader_deepdive/system.md:62-85`, `94-103` — detailed feedback/revision suggestions without confidence or false-positive threshold.
- **review:** `analysis/en/review/system.md:60-78` — evidence gate present but schema lacks confidence.
- **Standards admit partial enforcement:** `docs/development/prompt-standards.md:558-568` — evidence/confidence gates only partially enforced.
- **Consistency/voice/coreference/readability** are strong (have evidence gates); the gap is specifically in subjective review outputs.

## Impact

- Subjective feedback (e.g., "this character feels flat") is presented as definitive without confidence calibration.
- Low-confidence subjective opinions may be framed as defects, conflicting with the collaborator persona.
- Users cannot distinguish high-confidence structural issues from low-confidence stylistic preferences.

## Prioritized Remediation

1. **Add confidence/evidence/rationale fields to subjective analysis schemas:**
   ```markdown
   For every issue, recommendation, or reader question, include:
   - evidence: exact excerpt or concrete supplied context
   - confidence: 0.0-1.0 confidence that this is a genuine issue
   - rationale: one sentence explaining why the evidence supports it
   If confidence is below 0.6, do not frame the item as a defect.
   ```
2. **Add eval cases** for false-positive suppression (low-confidence items omitted or labeled as optional considerations).
3. **Extend prompt governance checks** if feasible; current docs mark static enforcement as partial, so eval/manual review must close the gap.

## Alternatives Considered

- **Accept current behavior.** Rejected: uncalibrated subjective feedback conflicts with the collaborator-not-judge persona and can mislead authors.
- **Remove subjective analysis features.** Rejected: beta-reader/review are valuable; the fix is calibration, not removal.
