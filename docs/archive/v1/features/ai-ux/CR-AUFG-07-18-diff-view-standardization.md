---
id: CR-AUFG-07-18
title: "Standardized Diff View across AI Outputs"
status: planned
area: ai-ux
mvp: false
ui_tooltip: "Review AI changes with one consistent original/suggested/accepted diff pattern."
ui_help_short: |
  Narrare will show AI-proposed changes with a consistent diff vocabulary across
  rewrite, co-author, KB enhancement, and beta-reader revision suggestions.
ui_help_long: |
  The feature standardizes how AI output changes are reviewed. Writers see what
  was original, what the AI suggested, what they accepted or rejected, and what
  remains unchanged without learning a different review UI for every AI feature.
ui_available_in: [editor, kb, analysis]
service: ~
contract: packages/web/lib/ai-diff/contracts.ts#AIDiffViewModel
router: ~
prompt: ~
requires: [WRITE-004, WRITE-006, KB-003, ANAL-001]
---

# CR-AUFG-07-18 — Standardized Diff View across AI Outputs

## Problem / Root cause

**Symptom:** Rewrite, Co-Author, KB Enhance, and Beta Reader expose AI changes with feature-local comparison patterns.

**Warum 1?** Each feature built its own review UI around its local payload shape: rewrite alternatives, co-author change lists, KB field before/after cards, beta-reader feedback items.

**Warum 2?** CR-07 standardized lifecycle and action vocabulary, but not the representation contract for “AI changed this from A to B.”

**Root cause:** Narrare lacks a reusable frontend diff vocabulary that can adapt domain payloads into a shared author-control view without forcing backend schemas into one shape.

## User-facing behavior and acceptance criteria

- Writers see consistent labels for `Original`, `Suggested`, `Accepted`, `Rejected`, and `Unchanged` states using `studio.aiActions.*` plus dedicated diff keys.
- Rewrite and Co-Author use the shared diff primitive for text diffs.
- KB Enhance uses the same state model for field-level before/after comparison without pretending structured fields are prose diffs.
- Beta Reader may show a diff only when a feedback item includes grounded original text plus a concrete suggested revision; otherwise it remains feedback, not fabricated diff.
- Keyboard actions from CR-AUFG-07-13 continue to trigger the same accept/apply handlers as visible buttons.
- Accessibility: additions/deletions are not conveyed by color alone; screen-reader labels describe change type.

## Architecture fit and layer ownership

| Layer | Ownership |
|-------|-----------|
| Core | None for the first increment; no LLM or prompt change. |
| Backend | None unless a later domain needs new grounded location metadata. |
| Frontend | Owns shared contracts and primitives under `packages/web/lib/ai-diff/` and `packages/web/components/shared/ai-diff/`. |
| Platform | Extends AI-UX inventory/checker expectations for shared diff consumers. |
| Docs | Updates UI principles only after implementation evidence exists. |

## API/contract implications

- New frontend-only contract first: `AIDiffViewModel`, `AIDiffSegment`, `AIDiffState`, and feature adapters.
- No backend schema change in the first increment.
- If Beta Reader later adds grounded revision spans, Backend must add Pydantic schema fields and Frontend types in the same change per RULE-17.

## Data model/migration implications

None for the first increment. Diff state remains derived from existing responses and local user choices.

## i18n requirements

- Add DE/EN/FR keys under the registered `studio` namespace for diff-only labels such as `aiDiff.added`, `aiDiff.removed`, `aiDiff.unchanged`, `aiDiff.accepted`, `aiDiff.rejected`, and screen-reader summaries.
- Continue using canonical `studio.aiActions.original` and `studio.aiActions.suggested` where possible.

## AI-UX lifecycle requirements

- Loading/error/cancel/retry remain owned by the underlying operation (`writing.rewrite`, `writing.co_author`, `kb.enhance`, `analysis.beta_reader`).
- The diff primitive never starts AI work itself.
- Partial streaming output may render as provisional diff only when the source operation already preserves partial output; it must visibly distinguish provisional from final.

## Tests/enforcement gates required

- Component tests for shared diff rendering, keyboard equivalence, and screen-reader labels.
- Adapter tests for Rewrite, Co-Author, KB Enhance, and grounded Beta Reader items.
- AI Operation Inventory entries for touched operations must reference the shared diff primitive.
- File-size gate must remain green; feature components should shrink or stay under soft targets.

## Alternatives considered

1. **Backend-normalized universal diff schema.** Rejected for the first increment: it would force unlike domains into one API shape and create unnecessary RULE-17 churn.
2. **Keep feature-local diff UIs.** Rejected: it preserves the root cause and duplicates logic.
3. **Frontend shared view model with domain adapters (chosen).** Best fit: contract-first, no backend churn unless data is missing, and reusable across existing outputs.

## Explicit out-of-scope

- Semantic diff algorithms beyond existing text/field comparisons.
- New dependency for diffing.
- Fabricating Beta Reader text spans when the analysis response does not ground them.

## Dependencies/order constraints

- Should be the first Phase C implementation because CR-AUFG-07-22 and CR-AUFG-07-24 depend on consistent output review vocabulary.
- Must preserve CR-AUFG-07-13 keyboard behavior.
