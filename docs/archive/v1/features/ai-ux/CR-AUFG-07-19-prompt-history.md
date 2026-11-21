---
id: CR-AUFG-07-19
title: "Prompt History"
status: planned
area: ai-ux
mvp: false
ui_tooltip: "Review, compare, and restore previous prompt override versions."
ui_help_short: |
  Prompt History keeps local versions of prompt overrides so writers can compare
  changes and restore a previous version without affecting the active prompt until
  they explicitly restore it.
ui_help_long: |
  Prompt History extends the existing PROMPT-003 prompt route tree. It records
  user/project prompt override revisions, shows differences through the shared
  diff view, and restores only when the writer confirms.
ui_available_in: [settings]
service: apps/api/narrare/prompts/history_service.py
contract: apps/api/narrare/prompts/contracts.py#PromptHistoryServiceProtocol
router: apps/api/narrare/prompts/router_prompt_history.py
prompt: ~
requires: [PROMPT-001, PROMPT-002, PROMPT-003, CR-AUFG-07-18]
---

# CR-AUFG-07-19 — Prompt History

## Problem / Root cause

**Symptom:** PROMPT-003 lets users preview, live-test, reset, and edit prompts, but it does not give them durable confidence to experiment over time.

**Warum 1?** Prompt overrides currently represent the effective saved value, not a user-facing revision history with compare/restore semantics.

**Warum 2?** Existing governance distinguishes preview from live test, but not active prompt state from historical prompt snapshots.

**Root cause:** Prompt customization has safe preview/test mechanics but lacks a version contract for user-authored override evolution.

## User-facing behavior and acceptance criteria

- A Prompt History panel lists saved revisions for the selected `prompt_id` and scope (user/project).
- Each entry shows timestamp, actor/source, scope, short change summary, and whether it is currently active.
- Compare opens the standardized diff view between any two revisions or active vs historical.
- Restore requires confirmation and creates a new active revision; it does not mutate historical records in place.
- Clearing history is explicit and does not delete the active prompt override.
- Live-test outputs are never stored as prompt history.

## Architecture fit and layer ownership

| Layer | Ownership |
|-------|-----------|
| Core | Prompt text validation/types only if existing PROMPT-003 core preview types need a history-safe value object. No provider/model imports. |
| Backend | Owns history service, repository, schemas, thin router, and restore transaction under the existing PROMPT-003 `/api/v1/prompts/{prompt_id:path}` route tree. |
| Frontend | Extends PromptEditor with a focused `PromptHistoryPanel` and uses shared diff. |
| Platform | API↔Frontend contract tests, migration tests, and no-provider invariant preservation. |
| Docs | Updates PROMPT-003 history/status text after implementation. |

## API/contract implications

Contracts before implementation:

- `PromptHistoryServiceProtocol.list_history(...)`
- `PromptHistoryServiceProtocol.compare_revisions(...)`
- `PromptHistoryServiceProtocol.restore_revision(...)`
- `PromptHistoryServiceProtocol.clear_history(...)`

Expected endpoints:

- `GET /api/v1/prompts/{prompt_id:path}/history`
- `GET /api/v1/prompts/{prompt_id:path}/history/compare?from=&to=`
- `POST /api/v1/prompts/{prompt_id:path}/history/{revision_id}/restore`
- `DELETE /api/v1/prompts/{prompt_id:path}/history`

All response schemas need matching `packages/web/types/prompts.ts` entries and contract tests.

## Data model/migration implications

- Add a prompt revision table or append-only revision records tied to existing PROMPT-002 override identity.
- Required fields: revision id, prompt override id/scope, `prompt_id`, prompt content hash, prompt content, actor/user id, created_at, change reason/source, restored_from revision id nullable.
- Retention policy: local append-only history keeps the latest 100 revisions per `prompt_id`/scope by default; explicit clear removes historical revisions only.
- Migration and rollback required in the same implementation task.

## i18n requirements

- DE/EN/FR `studio.settings.prompts.promptHistory.*` keys for list, compare, restore, clear, confirmation, empty state, and error text.
- No hardcoded fallback strings; Phase A fallback checker remains authoritative.

## AI-UX lifecycle requirements

- Prompt History is primarily CRUD/compare and does not call AI.
- Compare/restore must show loading within 200ms, typed actionable errors, retry for transient failures, and confirmation for destructive clear.
- If a restore triggers a preview refresh, preview uses the PROMPT-003 provider-free path and remains separate from live test.

## Tests/enforcement gates required

- Backend service unit tests for append-only restore semantics and active prompt non-mutation until restore.
- Migration test proving table/schema exists and rollback works.
- API integration tests for list/compare/restore/clear.
- API↔Frontend field parity test.
- Frontend component tests for compare, restore confirmation, empty state, and no live-test persistence.

## Alternatives considered

1. **Audit log reuse only.** Rejected: audit/evidence systems are not user-facing restore tools and should not be overloaded with prompt content UX.
2. **Git/file history for prompts.** Rejected: PROMPT-002 DB overrides are user/project settings; requiring filesystem history would break local-first UI expectations.
3. **Dedicated prompt history table (chosen).** Best fit: clear user-facing contract, restore semantics, and migration/test enforcement.

## Explicit out-of-scope

- Storing live-test generated outputs.
- Branching/merge workflow for prompt versions.
- Provider-specific prompt quality scoring.

## Dependencies/order constraints

- Depends on PROMPT-003 stable contracts and CR-AUFG-07-18 for diff comparison; Prompt History extends the existing PROMPT-003 prompt route tree rather than introducing a separate settings prompt API tree.
- Should not start before Phase B PROMPT-003 evidence remains stable.
