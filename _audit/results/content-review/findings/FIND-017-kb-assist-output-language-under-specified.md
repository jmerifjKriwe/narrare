# FIND-017 — KB Assist Output Language Under-Specified

> **Status:** `identified` (open)
> **Priority:** P2
> **Source:** CR-01 (KB-01), carried by CR-02, CR-03
> **Related:** CR-AUFG-01-07, CR-AUFG-02-09, CR-AUFG-03-09
> **Lifecycle:** `docs/development/finding-lifecycle.md`

---

## Problem

KB assist prompts (interview, suggest, enhance, improve) do not carry
`{{writing_language}}`, and `KBAssistService` builds context with
`language="en"`. This can produce English questions/suggestions for non-English
projects, creating a persona/output inconsistency despite correct global
capabilities.

## Code References

- **KB assist prompts omit writing_language:** `packages/core/narrare_core/prompts/_bundled/kb/en/interview/system.md:74-86`, `suggest/system.md:78-89`, `enhance/system.md:97-108` — preferences/avoidance sections present but no output-language directive.
- **Service hardcodes English:** `apps/api/narrare/kb/assist_service.py:122-128`, `143-152` — builds `PromptContext(language="en")`.
- **Gate gap:** `scripts/prompt_vars.py:32`, `85-89` — KB category requirements do not require `writing_language`.
- **Existing checks miss it:** `check_prompt_structure.py --strict` and `prompt_governance_checks.py` do not catch this because KB category requirements don't require `writing_language`.

## Impact

- Non-English project users receive English KB interview questions, suggestions, and enhancement proposals.
- Persona inconsistency: `NarrareMeta` defines a collaborator stance, but KB assist responds in the wrong language, breaking the coherent assistant experience.
- JSON field names/enum values must stay schema-stable, but user-facing text (questions, reasoning, notes) should follow project `writing_language`.

## Prioritized Remediation

1. **Pass project writing language into KB assist `PromptContext`:** `assist_service.py` should use the novel/project's `writing_language` instead of hardcoded `"en"`.
2. **Add output-language directive to KB assist templates:** interview, suggest, enhance, improve should include:
   ```markdown
   ### Output Language
   Write all user-facing questions, suggestions, reasoning, and notes in
   {{writing_language}}. Keep JSON field names and enum values exactly as
   specified by the output schema.
   ```
3. **Add manifest/content check** for user-facing KB output language requirement.
4. **Add test** proving non-English project language produces non-English KB assist output.

## Alternatives Considered

- **Create DE/FR feature prompt copies.** Rejected: ADR-026 strategy is EN-only feature prompts with output language via `{{writing_language}}`; no localized feature prompt copies needed.
- **Accept English-only KB assist.** Rejected: breaks persona coherence for non-English projects and contradicts the `writing_language` variable system.
