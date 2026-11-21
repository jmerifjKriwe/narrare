---
id: CR-AUFG-07-22
title: "Regenerate with Style Variants"
status: planned
area: ai-ux
mvp: false
ui_tooltip: "Regenerate AI output as controlled style variants without changing provider settings."
ui_help_short: |
  Writers can ask Narrare to regenerate an AI output in a specific style variant,
  compare alternatives, and accept one while the normal model/settings cascade
  remains authoritative.
ui_help_long: |
  Style variants are author-facing creative directions such as more lyrical,
  leaner, tenser, or more intimate. They are not model routing shortcuts and do
  not bypass prompt customization or settings.
ui_available_in: [editor]
service: apps/api/narrare/writing/style_variant_service.py
contract: apps/api/narrare/writing/contracts.py#StyleVariantRegenerationProtocol
router: apps/api/narrare/writing/router_style_variants.py
prompt: core/prompts/_bundled/writing/en/style_variant/system.md
requires: [WRITE-002, WRITE-003, WRITE-004, WRITE-006, SET-003, CR-AUFG-07-18]
---

# CR-AUFG-07-22 — Regenerate with Style Variants

## Problem / Root cause

**Symptom:** Writers can regenerate or rewrite, but variant intent is scattered across tone settings, rewrite modes, custom instructions, and manual prompt edits.

**Warum 1?** Existing generation supports tone and rewrite modes, while Co-Author and generated drafts have separate review flows.

**Warum 2?** No shared variant taxonomy defines which creative differences are safe to expose consistently across AI outputs.

**Root cause:** Narrare lacks a style-variant contract that sits above operation-specific prompts while respecting model routing and prompt cascade boundaries.

## User-facing behavior and acceptance criteria

- Eligible AI outputs offer `Regenerate as…` with a finite variant taxonomy: `leaner`, `more_lyrical`, `more_tense`, `more_intimate`, `more_dialogue`, `more_sensory`.
- The original output remains visible and unchanged until a variant is accepted.
- Variants are compared through the shared diff/review primitive.
- Accept/reject/rate semantics feed existing feedback mechanisms where available.
- The selected variant flows into the service request and is observable in tests.
- Model/provider/token settings continue to resolve through existing settings cascade; variants do not change providers.

## Architecture fit and layer ownership

| Layer | Ownership |
|-------|-----------|
| Core | Defines style-variant value objects and prompt variables only if prompt templates require them; PromptComposer remains the only prompt path. |
| Backend | Owns variant request schemas, service orchestration, and typed validation. |
| Frontend | Owns variant picker, compare UI, and accept/reject integration. |
| Platform | Adds request-contract and inventory tests proving variant flow. |
| Docs | Updates relevant writing help after implementation. |

## API/contract implications

- Contract first: `StyleVariantRegenerationProtocol.regenerate_variant(...)` or explicit extensions to existing writing protocols if Architecture review chooses reuse.
- Request fields: source operation id, source output id/text, variant id, optional author instruction, chapter/project identifiers.
- Response uses existing streaming output contracts where output is generated.
- If implemented as increments, each increment must be complete:
  - Increment A: Rewrite + generated draft variants.
  - Increment B: Co-Author/session variants after A is stable.

## Data model/migration implications

- No required SQL migration for transient variants.
- If variants are persisted for later comparison, reuse existing generation/request records or add a migration with source-output linkage and rollback tests.

## i18n requirements

- DE/EN/FR variant labels/descriptions under `studio.styleVariants.*`.
- Actions use canonical `studio.aiActions.retry`, `accept`, `reject`, `replace`, `insertAsNew`.

## AI-UX lifecycle requirements

- Streaming is required for generated variants when the underlying operation streams.
- Visible cancel must abort the variant transport.
- Partial variant output is preserved on connection loss and clearly marked incomplete.
- Retry reuses the same variant id and source output unless the writer changes it.

## Tests/enforcement gates required

- Backend schema/service tests proving variant id validation and settings cascade preservation.
- Streaming tests proving cancel signal reaches transport.
- Frontend tests proving selected variant appears in API request and review UI.
- Prompt variable/manifest checks if a new prompt mode or variable is introduced.
- Inventory update for each variant-enabled AI operation.

## Alternatives considered

1. **Freeform “try again differently” only.** Rejected: untestable and inconsistent across features.
2. **Model-temperature variants.** Rejected: violates settings cascade semantics and confuses style with provider config.
3. **Finite style taxonomy flowing through existing operation contracts (chosen).** Best fit: user-understandable, testable, and settings-safe.

## Explicit out-of-scope

- Automatic best-variant ranking.
- New model/provider selection logic.
- LEARN-002 full author style profiling implementation.

## Dependencies/order constraints

- Depends on CR-AUFG-07-18 shared diff for comparison.
- Should follow CR-AUFG-07-24 if rating is attached to variants in the first implementation slice.
