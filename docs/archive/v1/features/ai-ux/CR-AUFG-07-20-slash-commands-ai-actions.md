---
id: CR-AUFG-07-20
title: "Slash Commands for AI Actions"
status: planned
area: ai-ux
mvp: false
ui_tooltip: "Trigger governed AI actions from the editor with discoverable slash commands."
ui_help_short: |
  Slash commands let writers type commands such as `/continue` or `/rewrite`
  inside the editor and route them to existing AI actions without bypassing
  lifecycle, cancel, i18n, or prompt contracts.
ui_help_long: |
  The feature adds a command-discovery layer over existing AI operations. It does
  not create new prompt paths. Commands select existing actions and prefill their
  UI when appropriate.
ui_available_in: [editor]
service: ~
contract: packages/web/components/studio/editor/slash-commands/contracts.ts#AISlashCommandDefinition
router: ~
prompt: ~
requires: [WRITE-002, WRITE-003, WRITE-004, WRITE-006, CHAT-001, CR-AUFG-07-18]
---

# CR-AUFG-07-20 — Slash Commands for AI Actions

## Problem / Root cause

**Symptom:** AI actions are available through buttons, panels, and shortcuts, but command discovery is fragmented and slows keyboard-first writers.

**Warum 1?** Feature entry points were added per surface: toolbar generation, bubble-menu rewrite, co-author panel, chat panel.

**Warum 2?** CR-07 standardized action labels and keyboard acceptance, but not command invocation grammar.

**Root cause:** Narrare lacks a governed command registry that maps editor text commands to existing AI operation hooks without duplicating operation logic.

## User-facing behavior and acceptance criteria

- Typing `/` in an appropriate empty paragraph opens a localized command menu.
- Commands are discoverable by label, alias, and description.
- Initial command set routes to existing operations: continue, generate draft, rewrite selection, co-author selection, ask chat, and explain selection.
- Commands requiring selection are disabled with actionable guidance when no valid selection exists.
- Command execution opens or triggers the existing governed UI; it does not call transport/API directly.
- TipTap keyboard shortcuts and text entry remain unaffected; `/` can still be typed as prose when dismissed.

## Architecture fit and layer ownership

| Layer | Ownership |
|-------|-----------|
| Core | None; no new LLM intents or prompt routes. |
| Backend | None for first increment; commands call existing frontend flows. |
| Frontend | Owns command registry, parser, TipTap plugin/component, and dispatch adapters to existing hooks. |
| Platform | Adds tests/checker evidence that commands reference inventory operation IDs and existing lifecycle owners. |
| Docs | Adds user help after implementation. |

## API/contract implications

- Frontend contract first: `AISlashCommandDefinition` with `id`, `operationId`, `labelKey`, `descriptionKey`, `aliases`, `requiresSelection`, `availability`, and `dispatch`.
- No backend endpoint in first increment.
- Commands must reference existing AI Operation Inventory `operation_id` values.

## Data model/migration implications

None. Command preferences may use existing settings only if a later approved spec adds customization.

## i18n requirements

- DE/EN/FR keys under `studio.slashCommands.*` for labels, descriptions, aliases where localized, empty state, disabled reasons, and help text.
- Visible action labels still use `studio.aiActions.*` in output UIs.

## AI-UX lifecycle requirements

- Slash commands do not own loading/cancel/error; they delegate to existing `useAIOperation` or WebSocket/session owners.
- If command dispatch opens an AI operation panel, loading feedback must appear within 200ms after explicit command confirmation.
- Retry/partial output semantics are exactly those of the routed operation.

## Tests/enforcement gates required

- Parser tests for command detection, escaping, aliases, and prose dismissal.
- Component tests for menu navigation, disabled commands, and dispatch.
- Conflict tests with TipTap shortcuts and text-entry contexts.
- Inventory consistency test: every AI slash command references a valid operation or documented non-operation UI command.

## Alternatives considered

1. **Backend command interpreter.** Rejected: it would create a second AI action routing layer and risk bypassing existing UI lifecycle hooks.
2. **Hardcoded command menu inside the editor component.** Rejected: it violates RULE-06 and would become untestable as commands grow.
3. **Frontend registry dispatching existing operations (chosen).** Best fit: discoverability without new LLM/prompt paths.

## Explicit out-of-scope

- Natural-language command parsing.
- User-defined custom slash commands.
- Commands that execute hidden AI calls without showing the governed operation UI.

## Dependencies/order constraints

- Should follow CR-AUFG-07-18 so review commands use standardized output states.
- Should not precede CR-AUFG-07-21 if session commands include stop/reconnect semantics.
