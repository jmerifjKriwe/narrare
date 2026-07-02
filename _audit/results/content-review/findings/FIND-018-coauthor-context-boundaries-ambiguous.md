# FIND-018 — Co-Author Context Boundaries Ambiguous

> **Status:** `identified` (open)
> **Priority:** P2
> **Source:** CR-01 (WRITING-01), carried by CR-02, CR-03
> **Related:** CR-AUFG-01-09, CR-AUFG-02-11, CR-AUFG-03-10
> **Lifecycle:** `docs/development/finding-lifecycle.md`

---

## Problem

The `co_author` prompt concatenates before/selection/after as three adjacent
`<user_provided_text>` blocks in one line and then asks for the "COMPLETE
revised version of the text". This makes it ambiguous whether the model should
revise only the selection or the entire combined passage.

## Code References

- **Adjacent unlabeled wrappers:** `packages/core/narrare_core/prompts/_bundled/writing/en/co_author/system.md:67-72` — three `<user_provided_text>` blocks concatenated without role labels.
- **Ambiguous output scope:** `co_author/system.md:94-101` — "COMPLETE revised version of the text" without specifying whether this means the selection only or the full passage.
- **Gate gap:** existing gates verify variables are wrapped, but not that runtime context roles are labeled or that output scope matches the intended operation.

## Impact

- The model may revise the entire before+selection+after passage instead of only the selection, producing unexpected output scope.
- Users may get a full-passage rewrite when they expected only the selected text to change.
- This is a quality/security-adjacent ambiguity: unlabeled context roles make it harder for the model to distinguish "use for continuity" from "revise this".

## Prioritized Remediation

1. **Label before/selection/after XML roles:**
   ```markdown
   <user_provided_text role="before_selection">{{context_before}}</user_provided_text>
   <user_provided_text role="selection_to_improve">{{selection_text}}</user_provided_text>
   <user_provided_text role="after_selection">{{context_after}}</user_provided_text>
   ```
2. **State exact output scope:** "Return only the improved replacement for `selection_to_improve`, unless the caller explicitly requests a full passage rewrite."
3. **Add eval/manual checklist** for selection-boundary prompts; static role/scope checks may be heuristic.

## Alternatives Considered

- **Accept current ambiguity.** Rejected: the model's interpretation of "COMPLETE revised version" is unpredictable and can produce scope-mismatched output.
- **Remove before/after context.** Rejected: continuity context is valuable for coherent rewrites; the fix is labeling, not removal.
