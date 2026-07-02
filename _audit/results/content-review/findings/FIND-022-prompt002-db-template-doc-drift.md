# FIND-022 — PROMPT-002 DB-Template Documentation Drift

> **Status:** `identified` (open)
> **Priority:** P3
> **Source:** CR-00, CR-01 (DOC-01)
> **Related:** CR-AUFG-01-13
> **Lifecycle:** `docs/development/finding-lifecycle.md`

---

## Problem

PROMPT-002 documentation claims DB-backed per-user templates as the highest
active cascade level. The actual runtime active override is a project file;
DB stores append-only prompt history/revisions only, not active cascade SSOT.
Users/reviewers could confuse DB-history with active DB-cascade.

## Code References

- **Docs claim DB templates as active cascade:** `docs/features/prompts/PROMPT-002-db-templates.md:56-115`, `127-149`.
- **Active save path is file-based:** `apps/api/narrare/prompts/router.py:106-124` — `PUT /prompts/{id}` calls `PromptHistoryApiService.save_override_recorded()`, which first writes to file via `core.save_override()`, then best-effort records a DB revision.
- **DB is history only:** `apps/api/narrare/prompts/history_service.py:1-27`, `115-180` — `PromptHistoryApiService` composes core `PromptManagementService` (file, authoritative) + DB repository (append-only revisions).
- **Core management writes files:** `packages/core/narrare_core/prompts/management.py:153-178`, `250-269` — `save_override()` writes project override files.

## Impact

- Documentation misleads reviewers/users into believing DB templates are the active cascade source.
- This is a documentation drift issue, not a PromptComposer runtime bypass — the runtime correctly uses file overrides.
- Risk: confusion about which layer is authoritative could lead to incorrect implementation decisions.

## Prioritized Remediation

1. **Update PROMPT-002 docs** to reflect: active override is file-based; DB stores append-only history/revisions.
2. **Clarify cascade order:** DB template support exists in `PromptRegistry.resolve(db_content=...)` but is not the active save path.
3. **Add doc-drift check** if `check_doc_drift.py` rules cover these files; otherwise add a governance review checklist item.

## Alternatives Considered

- **Implement active DB cascade.** Rejected: the file-based override + DB history model is architecturally correct (RULE-08: file is authoritative for active override); the docs should align, not the runtime.
- **Accept documentation as-is.** Rejected: the drift creates confusion about the active cascade source.
