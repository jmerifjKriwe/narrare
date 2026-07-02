# FIND-024 — Prompt Customization UI Category Discoverability Incomplete

> **Status:** `identified` (open)
> **Priority:** P3
> **Source:** CR-00, CR-01 (UI-01)
> **Related:** CR-AUFG-01-14
> **Lifecycle:** `docs/development/finding-lifecycle.md`

---

## Problem

The prompt customization UI filter lists only `generation`, `writing`,
`analysis`, `kb` as filter categories, while bundled prompt categories also
include `planning` and `wiki`. Core management can list all bundled prompts,
but UI discoverability is incomplete — users cannot filter to `planning` or
`wiki` prompts in the settings UI.

## Code References

- **UI filter constants:** `packages/web/components/studio/settings/PromptsTab.tsx:12-15` (per CR-00; line 14 in CR-01) — lists only `generation`, `writing`, `analysis`, `kb`.
- **Bundled categories include `planning` and `wiki`:** CR-00 inventory — `packages/core/narrare_core/prompts/_bundled/` contains `planning/` (5 modes) and `wiki/` (2 modes) directories.
- **Core management lists all:** `PromptManagementService.list()` can enumerate all bundled categories.

## Impact

- Users cannot discover or customize `planning` or `wiki` prompts through the UI filter pills.
- This is a UX discoverability gap, not a Core prompt-path break — the prompts are runtime-loaded and customizable via API/CLI.
- Low severity: `planning` and `wiki` prompts are less frequently customized than `writing`/`kb`.

## Prioritized Remediation

1. **Decide whether UI should expose all core prompt categories.** If yes: add `planning` and `wiki` filter categories with i18n labels and tests. If no: document intentional non-exposure.
2. **If exposing:** add filter pills + i18n keys in `packages/i18n/messages/{de,en,fr}/studio.json`.
3. **Add test** verifying UI filter categories match bundled prompt categories.

## Alternatives Considered

- **Accept current filter set.** Acceptable if documented as intentional; currently undocumented, so it reads as an oversight.
- **Remove `planning`/`wiki` from Core.** Rejected: these categories are runtime-used and valuable; the UI should catch up.
