# FIND-020 — Variable-Specific Wrapper Semantics Not Enforced

> **Status:** `identified` (open)
> **Priority:** P2
> **Source:** CR-01 (KB-02), carried by CR-02
> **Related:** CR-AUFG-01-08, CR-AUFG-02-10
> **Lifecycle:** `docs/development/finding-lifecycle.md`

---

## Problem

Prompt standards map `{{entry_content}}` to `<user_provided_data>`, but KB
improve/consistency templates wrap it as `<user_provided_text>`. The security
boundary exists (content is wrapped), but the semantic tag is inconsistent.
Current governance checks validate only that the wrapper tag is approved, not
that the variable uses its documented tag.

## Code References

- **Standard mapping:** `docs/development/prompt-standards.md:393-409` — `{{entry_content}}` → `<user_provided_data>`.
- **Template mismatch:** `packages/core/narrare_core/prompts/_bundled/kb/en/improve/system.md:23-28`, `kb/en/consistency/system.md:29-33` — use `<user_provided_text>` instead.
- **Gate gap:** `scripts/prompt_governance_checks.py:31-59` — validates only that the wrapper tag is in the approved vocabulary, not that the variable uses its documented tag.

## Impact

- The security boundary is present (user content is wrapped), so this is not an injection exposure.
- However, semantic inconsistency means the model may treat KB entry content as "text to revise" rather than "data to analyze", depending on wrapper semantics.
- A variable→expected-wrapper mapping would catch future drift where a variable gets an approved-but-wrong tag.

## Prioritized Remediation

1. **Align KB templates to documented semantics:** change `<user_provided_text>` to `<user_provided_data>` for `{{entry_content}}` in KB improve/consistency.
2. **Create a variable→expected-wrapper map** in registry/manifest derived from `USER_CONTENT_VARS`/docs.
3. **Extend `prompt_governance_checks.py`** to validate variable-specific wrapper semantics, not just approved vocabulary.
4. **Update governance tests** to cover the new check.

## Alternatives Considered

- **Update docs to match templates.** Rejected: the docs semantics (`user_provided_data` = KB data for analysis) are correct; the templates should align, not the standard.
- **Accept current wrappers.** Rejected: the semantic mismatch can affect model behavior and is trivially fixable.
