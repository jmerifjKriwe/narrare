# ADR-070 — Amendment: Project-Scope the Evidence Model (`novel_id`)

> **Status:** ✅ Accepted (Architecture Specialist draft; awaiting user ADR review)
> **Date:** 2026-07-23
> **Deciders:** Architecture Specialist; User (pending approval)
> **Amends:** ADR-069 Decision 11 (Adaptive Snapshot storage on `invocation_evidence`)
> **Type:** Amendment (non-breaking, additive schema change to a table ADR-069 introduced columns on)
> **Related:**
> ADR-042 (hybrid evidence architecture — the table this amendment extends),
> ADR-045 (evidence correlation columns — the nullable-column precedent this follows),
> CONSTRAINTS.md RULE-03 / RULE-04 / RULE-06 / RULE-07 / RULE-11 / RULE-14

> **Naming note on the task brief:** the dispatch labelled this "RULE-15".
> RULE-15 governs Next.js middleware (`proxy.ts`), not the database. The
> rules actually in force for this change are **RULE-14** (Alembic migration
> ships in the same task as the ORM/Core model change) and **RULE-03**
> (contract before implementation). This ADR cites the correct rules.

---

## Context

### Why this amendment exists

The Phase 5 frontend plan (Task 7 — Adaptive Snapshot History) needs
`GET /api/v1/adaptive/{project_id}/snapshots?limit=20` to render the
"Recent Adaptive Activity" timeline in the Adaptivity Dashboard (LEARN-002,
recalibrated in ADR-069).

ADR-069 **Decision 11** chose to store adaptive provenance as two nullable
JSONB columns (`adaptive_source_summary`, `adaptive_weights`) on the existing
`invocation_evidence` table, and even sketched the dashboard query:

```sql
SELECT * FROM invocation_evidence
WHERE user_id = ? AND project_id = ?
  AND adaptive_source_summary IS NOT NULL
ORDER BY created_at DESC LIMIT 20;
```

But the **scoping columns that query assumes were never added.** The verified
current state of the table is:

| Column needed by the dashboard query | Present on `invocation_evidence`? |
|---|---|
| `adaptive_source_summary` | ✅ Yes (ADR-069 D11, migration 0034) |
| `adaptive_weights` | ✅ Yes (ADR-069 D11, migration 0034) |
| `created_at` | ✅ Yes (`models.py:49`) |
| `project_id` / `novel_id` | ❌ **No** |
| `user_id` | ❌ No |

Without a project/novel scope column, every adaptive snapshot is
**ungroupable** — the dashboard cannot ask "show the adaptive activity for
*this* novel." The write path (`build_invocation_evidence`) also never
captures which novel an invocation served, so the data is structurally
unattributable.

This is the gap the Phase 5 Backend specialist surfaced. This amendment
closes it.

### Root cause (3× Why)

1. **Symptom:** `GET /adaptive/{project_id}/snapshots` cannot be implemented;
   there is no column to scope `invocation_evidence` by novel.
2. **Why is there no scope column?** ADR-069 D11 added the adaptive *payload*
   columns but deferred (and ultimately dropped) the *scoping* columns its own
   example query referenced. The snapshot write path was built (migration
   0034, `update_adaptive_snapshot`, `record_snapshot`) before the read path,
   and the read path was never implemented.
3. **Why was the read path never built?** Phase 4 of ADR-069 shipped the
   Dialogue Coach write side + the adaptive *settings* dashboard; the
   *snapshot history* dashboard was sequenced into LEARN-002 / Phase 5 and
   never pulled forward. The missing column is therefore an **accidentally
   deferred dependency**, not a design disagreement — the design (store
   per-invocation, scope by project) was always the intent.

**Verdict:** Add the scope column the original design already assumed. This
completes ADR-069 D11; it does not revise it.

---

## Decision Drivers

- **RULE-14** — the Alembic migration MUST ship in the same task as the
  ORM/Core model field change. No `create_all()` in tests; migrations are the
  only schema path.
- **RULE-03** — the Core `FeatureInvocationEvidence` field and the ORM column
  are the contract here; both land before the repository/service/router that
  consume them.
- **RULE-07** — the single mapping from invocation-pipeline naming
  (`context.project_id`) to evidence-row naming (`novel_id`) happens at one
  boundary (`build_invocation_evidence`); no backwards `apps/`→`core` import.
- **RULE-11** — graceful degradation: a NULL `novel_id` (legacy rows, or an
  invocation whose context had no project) never breaks the pipeline; such
  rows are simply absent from per-novel snapshot queries.
- **Backward compatibility** — ADR-045 established the nullable-additive
  column pattern (`invocation_id`, fingerprints); this amendment reuses it
  exactly.

---

## Options Considered

### Option α — Name the column `project_id` (match the invocation pipeline)

`PromptInvocationContext.project_id`, `AdaptiveContextProvider.get_context(project_id)`,
and the REST route `/adaptive/{project_id}` all use `project_id`. Naming the
evidence column `project_id` would make the threading a direct assignment
with no boundary rename.

**Pros:**
- Zero-friction threading: `evidence.project_id = context.project_id`.
- Matches the Core invocation-context vocabulary.

**Cons:**
- **Diverges from the DB-schema SSOT.** Every foreign-key-style reference to
  the projects/novels entity on every other table is `novel_id`
  (`Chapter.novel_id`, `ProjectSettings.novel_id`, `ProjectAISettings.novel_id`,
  generation/kb tables). The evidence table would be the lone outlier.
- Blocks a future `REFERENCES novels(id)` constraint (the FK column name would
  not match the referenced entity's conventional name).
- The "project" vs "novel" dual vocabulary is an *existing* inconsistency;
  enshrining a third spelling on the evidence table deepens it rather than
  resolving it.

**Rejected.**

### Option β — Name the column `novel_id` (match the DB schema) — CHOSEN

Add `novel_id` (nullable, indexed) to `invocation_evidence`. The single
boundary mapping `novel_id = context.project_id` lives in
`build_invocation_evidence` (the one function that already constructs
`FeatureInvocationEvidence` from a `PromptInvocationContext`).

**Pros:**
- Consistent with every other table that references the novels entity —
  `Chapter.novel_id`, `ProjectSettings.novel_id`, etc.
- Leaves the door open for a future `REFERENCES novels(id)` FK.
- The Core `FeatureInvocationEvidence` field is `novel_id`; the ORM column is
  `novel_id`; the mapper is a 1:1 `novel_id ↔ novel_id`. Only the *source*
  (`PromptInvocationContext.project_id`) uses the other spelling, and that
  rename is localised to one line in one function.

**Cons:**
- One boundary rename (`project_id → novel_id`) in `_evidence.py`.
- Perpetuates the "novel ≡ project" identity in the schema (already true
  everywhere else; this is not new coupling).

### Option γ — Add BOTH `novel_id` AND `user_id`

Store both scoping columns the ADR-069 example query referenced.

**Pros:**
- Exact match to the original sketched query.
- Strongest tenant isolation if novels ever become multi-user.

**Cons:**
- **Scope creep / YAGNI.** Narrare novels are single-owner today; ownership
  is already gated at the REST boundary (auth + novel ownership, same as the
  existing `/adaptive/{project_id}/context` endpoint that also stores no
  `user_id` on its data). `novel_id`-only scoping is sufficient and matches
  the precedent set by `ProjectSettings`/`Chapter`.
- Adds a second nullable column + a second threading path with no current
  consumer — the dashboard query gains nothing it cannot get from `novel_id`
  + auth.

**Rejected now** (revisit if/when multi-user novel collaboration lands; see
Consequences).

### Option δ — Embed `novel_id` inside the existing `adaptive_source_summary` JSONB

Stuff `{"novel_id": "...", "summary": "..."}` into the JSONB column ADR-069
D11 already added, avoiding a new column.

**Pros:** No migration.

**Cons:**
- Unindexable for the dashboard's `WHERE novel_id = ? ORDER BY created_at
  DESC LIMIT 20` access pattern — a JSONB containment/extraction scan over a
  growing append-only table.
- Mixes identity (which novel) with payload (what signals) in one blob,
  violating RULE-06 at the column level.
- Cannot be NULL-discriminated independently of the payload.

**Rejected.**

---

## Decision

**Option β.** Add a single nullable, indexed `novel_id` column
(`UUID(as_uuid=True)`) to `invocation_evidence` via Alembic migration `0035`
(revises `0034_evidence_adaptive_columns`), and matching optional fields on the
Core `FeatureInvocationEvidence`: `novel_id: UUID | None` and
`created_at: datetime | None`.

The write path threads `novel_id = context.project_id` in exactly one place:
`build_invocation_evidence()` in
`packages/core/narrare_core/ai_invocation/_evidence.py`.

### Asymmetric Core fields (RULE-06 modelling)

`novel_id` and `created_at` are both optional on the Core model, but they have
**different write/read semantics** — this asymmetry is deliberate, not a smell:

| Field | Write path (`domain_to_orm`) | Read path (`orm_to_domain`) |
|---|---|---|
| `novel_id` | **Set** by `build_invocation_evidence` from `context.project_id`; mapped through to the column. | Restored from the column. |
| `created_at` | **Ignored** — the column has `server_default=func.now()`; PostgreSQL stamps it on INSERT. Setting it on write would be silently dropped (correct). | **Populated** from the ORM row, so snapshot reads return the timestamp without a parallel projection type. |

This keeps the snapshot read returning `list[FeatureInvocationEvidence]`
(consistent with the existing `get_by_feature_and_mode`) rather than
introducing a new projection DTO for one extra field. The write contract is
unchanged: `domain_to_orm` continues to omit `created_at`, letting the DB
default win. The field is documented as read-only (DB-set).

The read path adds `EvidenceRepositoryImpl.get_adaptive_snapshots(novel_id,
limit)` (filter `novel_id == ? AND adaptive_source_summary IS NOT NULL`,
`ORDER BY created_at DESC LIMIT ?`), exposed via
`AdaptiveContextService.get_adaptive_snapshots(project_id, user_id, limit)`
and `GET /api/v1/adaptive/{project_id}/snapshots?limit=20`.

### Why `novel_id` (not `project_id`) — the identity statement

In Narrare, **"novel" and "project" are the same entity** (a project *is* a
novel; the `novels` table is the projects table). Both spellings circulate:

| Vocabulary | Where it appears |
|---|---|
| `novel_id` | DB schema / ORM: `Chapter.novel_id`, `ProjectSettings.novel_id`, `ProjectAISettings.novel_id`, REST `/novels/{novel_id}/chapters` |
| `project_id` | Invocation pipeline / adaptivity: `PromptInvocationContext.project_id`, `AdaptiveContextProvider.get_context`, REST `/adaptive/{project_id}` |

For a **column on a DB table that references the novels entity**, the
schema convention (`novel_id`) wins — it matches every sibling table and
permits a future FK. The invocation pipeline's `project_id` is simply the
upstream spelling of the same UUID; the rename happens at the single
evidence-construction boundary. This is the same kind of vocabulary seam the
codebase already tolerates (e.g. the `/adaptive/{project_id}` route and the
`ProjectSettings.novel_id` it ultimately reads), and localising it to one
line is cleaner than introducing a schema outlier.

---

## RULE-XX Compliance

| Rule | Status | Nachweis |
|------|--------|----------|
| RULE-03 | ✅ | Core `FeatureInvocationEvidence.novel_id` + ORM column + mapper land in Task 1, before the repository/service/router that consume them. |
| RULE-04 | ✅ | No file grows past its limit: `_evidence.py` (+1 line), `models.py` (+4), `evidence_models.py` (+3), `_mappers.py` (+2). All well under caps. |
| RULE-06 | ✅ | `EvidenceRepositoryImpl` keeps only SQL; `AdaptiveContextService` keeps only orchestration; router only delegates. Identity/payload column separation documented. |
| RULE-07 | ✅ | Single boundary mapping in Core `_evidence.py`; no `apps/`→`core` import; repository owns all `invocation_evidence` SQL. |
| RULE-11 | ✅ | NULL `novel_id` (legacy rows / context without project) never breaks the write path; such rows are merely absent from per-novel queries. Snapshot write already best-effort. |
| RULE-14 | ✅ | Migration `0035` ships in the same task (Task 1) as the ORM + Core model field. No `create_all()`; integration conftest runs `alembic upgrade head`. |
| RULE-09 | ✅ | All new/changed public methods fully type-annotated (`novel_id: UUID`, `limit: int`, `-> list[AdaptiveSnapshotItem]`). |

---

## Consequences

### Positive

- The ADR-069 D11 dashboard query becomes implementable as designed.
- Future per-novel AI analytics (adoption rates, audit-state breakdowns,
  adaptive-weight drift) reuse the same index — one column unlocks a family
  of queries.
- Write path change is one line; the existing best-effort sink semantics are
  untouched.
- Fully backward compatible (nullable additive column, ADR-045 precedent).

### Negative / Trade-offs

- One new nullable column on a shared append-only table (accepted; matches
  the established ADR-045/069 column pattern).
- Legacy rows (pre-0035) have NULL `novel_id` and are silently excluded from
  per-novel snapshot queries. This is **correct**, not a bug: those rows are
  genuinely unattributable (the write path never captured the novel), and
  the dashboard is a "recent activity" view, not a historical audit.

### Risks

- **Risk: silently unattributed invocations.** Any feature service that builds
  a `PromptInvocationContext` *without* setting `project_id` will produce
  evidence rows with NULL `novel_id`, invisible to the dashboard.
  **Mitigation:** documented in the plan (Task 2 test asserts
  `context.project_id` flows through); a follow-up audit can assert all
  adaptive-consuming services set `project_id`. Out of scope for this
  amendment — the threading is correct; adoption is a wiring-audit task.
- **Risk: no `user_id` → cross-user leakage if novels become multi-user.**
  Today novels are single-owner and the REST boundary gates ownership (same
  model as `ProjectSettings`, `Chapter`). **Mitigation:** documented as a
  future-consideration; if multi-user collaboration lands, add `user_id` in a
  follow-up amendment (Option γ) — the schema is additive, so this is cheap.

### Migration strategy

- Migration `0035_evidence_project_scoping`: `ADD COLUMN novel_id UUID
  NULLABLE` + `CREATE INDEX ix_invocation_evidence_novel_id`. Downgrade
  reverses both. No data backfill (legacy rows stay NULL by design).
- Down-revision: `0034_evidence_adaptive_columns`.

### Sustainability check

1. **Correct in 3 months?** Yes — the column matches every sibling table's
   novel reference; per-novel queries are the obvious and only access pattern.
2. **Hard-to-undo coupling?** None — one nullable column + index, one-line
   write-path mapping, one repository method, one endpoint. All reversible.
3. **Simplest correct solution?** Yes — single column, single boundary rename,
   reuses ADR-045/069 patterns and the existing sink/repository/router.
4. **Design intent clear?** Yes — the column name documents the reference;
   this ADR documents the novel≡project identity and the boundary seam.

---

## Review Trigger

Revisit this amendment if:
- Multi-user novel collaboration is introduced (add `user_id`, Option γ).
- A `REFERENCES novels(id)` FK is desired (verify `novel_id` is never NULL on
  new rows; consider a `NOT NULL` follow-up migration + backfill).
- Evidence grows large enough that `ORDER BY created_at DESC LIMIT 20` under a
  `novel_id` scan needs a composite index `(novel_id, created_at DESC)`.
