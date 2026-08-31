# Open Questions — Index

> Location: `docs/architecture/questions/INDEX.md`
> Maintained by: Architecture Agent
> **Note:** Resolved questions live in the [`resolved/`](resolved/) subfolder. This folder holds only open questions.

---

## Status Legend

| Symbol | Meaning |
|--------|---------|
| 🔴 | Blocking — blocks specific implementation |
| 🟡 | Open — needs resolution before relevant phase |
| 🔵 | In Discussion |
| ✅ | Resolved — see question file for resolution |
| 🗄️ | Archived |

---

## Active Questions

| ID | Question | Status | Blocks | Raised |
|----|---------|--------|--------|--------|
| [Q-001](Q-001-to-Q-002.md#q-001--how-does-mcp-authenticate-against-the-api) | How does MCP authenticate against the API? | 🟡 | `apps/mcp/` (post-MVP) | init |
| [Q-002](Q-001-to-Q-002.md#q-002--does-a2a-require-streaming-support) | Does A2A protocol require streaming support? | 🟡 | `apps/a2a/` (post-MVP) | init |
| [Q-020](Q-020-swc-helpers-standalone-tracing.md) | When can the temporary @swc/helpers standalone-tracing workaround (`outputFileTracingIncludes`) be removed? | 🟡 | Workaround removal in `packages/web/next.config.ts` (re-evaluate per Next bump) | 2026-08-20 |

---

## Resolved Questions

> Resolved question files live in [`resolved/`](resolved/).

| ID | Question | Resolution | ADR |
|----|---------|-----------|-----|
| [Q-003](resolved/Q-003-to-Q-004.md#q-003--embedding-provider-abstraction-from-day-one) | Should embeddings be provider-agnostic from day one? | → Embedding Provider Protocol abstraction | ADR-020 |
| [Q-004](resolved/Q-003-to-Q-004.md#q-004--celery-vs-arq-for-background-tasks) | Celery vs arq for background tasks? | → TaskIQ | ADR-007 |
| [Q-005](resolved/Q-005-resolved.md) | Does pydantic-ai support GLM-5.1 via z.ai? | → Yes, OpenAI-compatible | — |
| [Q-006](resolved/Q-006-configurable-model-routing.md) | Should Model Routing be configurable per user/project/intent? | → Runtime cascade with multi-provider support | ADR-001 (updated) |
| [Q-007](resolved/Q-007-writing-context-data-loader.md) | Writing Context Data Loader | → Resolved via `WritingContextAssembler` | — |
| [Q-008](resolved/Q-008-auth-store-hydration.md) | Auth Store wird nach Page Reload nicht rehydriert | → Resolved via `AuthProvider.tsx` in Root Layout | — |
| [Q-009](resolved/Q-009-to-Q-010.md#q-009--should-chat-conversations-be-project-scoped-or-user-scoped) | Should Chat Conversations Be Project-Scoped or User-Scoped? | → Project-scoped (Option A) | ADR-024 |
| [Q-010](resolved/Q-009-to-Q-010.md#q-010--should-the-chat-prompt-support-defr-from-day-one-or-english-only-v1) | Should the Chat Prompt Support DE/FR from Day One or English-Only v1? | → English-only v1 (Option A) | ADR-024 |
| [Q-011](resolved/Q-011-distribution-strategy.md) | Wie wird Narrare für nicht-technische Nutzer zugänglich? | → **Option A bindend (Docker-only Self-Host, ehrliche Tech-Savvy-Positionierung; Review-05 ⭐⭐ als akzeptierter Trade-off)**. D→B2→C-Leiter demoted zu unkommittiertem Optionskatalog (ADR-080-Kontext: Footprint seit Raise geschrumpft). Revisit nur bei nachweislichem Scheitern ≥1 realen nicht-technischen Nutzers an der Docker-Barriere. Committed Follow-up: interaktives Bootstrap-Skript (`setup.sh`/`update.sh`, Paperless-ngx-Muster) als eigener künftiger Platform-Slice. PO decision. | — |
| [Q-012](resolved/Q-012-prompt-variable-ux.md) | Wie erklären wir dem Nutzer Prompt-Variablen und ermöglichen Reset-to-Default? | → Option A (Manifest) via PROMPT-003 (Post-MVP) | — |
| [Q-013](resolved/Q-013-i18n-tone-drift.md) | i18n Tone Drift in Bundled Universal/Meta Prompts (DE/FR) | → universal/{de,fr} aligned to Du/tu (matching meta prompts); §8 Formality Register added to prompt-content-standards.md | — |
| [Q-014](resolved/Q-014-cascade-policy-location.md) | Sollte die Model-Routing-Cascade-Logik in Core oder API leben? | → Cascade bleibt in API (Protocol in core, DB-Impl in API ist korrekt per RULE-07) | — |
| [Q-015](resolved/Q-015-user-selectable-copy-tone.md) | User-selectable UI copy tone (familiar vs. neutral) | → **Feature Spec [I-Copy-001](../../features/i18n/I-Copy-001-formality-register.md) (Overlay-Merge)**; PO re-approved after external-AI consultation (2/3) confirmed low-effort infrastructure + zero duplication. Loader-level deep-merge of sparse `formality/{de,fr}.json` over base messages; `next-intl` + all call sites untouched; `en` unchanged; setting = `formality` (not `tone`); cookie-only persistence (no backend/migration v1); RULE-02 boundary verified. Round-1 "not low-effort" applied to the suffix-resolver only; the one real cost is editorial (~150–300 formal DE/FR variants). | — |
| [Q-016](resolved/Q-016-wiki-listener-producers.md) | Wire producers or remove dormant `WikiEventListener` subscriptions (ADR-080 follow-up) | → **Option A — re-wire producers in-process** (closes the staleness gap). Deeper root-cause read: ADR-080 severed the chain → entity edit fires no event → summary stays `fresh` with OLD content → raw-data fallback (stale/pending only) does NOT engage → AI writes against stale character view silently (correctness gap, not just UX). Option A publishes `kb.entry.updated` / `chapter.finalized` / `wiki.prompt.changed` to the lifespan `EventPublisher` (ADR-080 in-process boundary kept); dormant listener becomes live again. Also: remove orphaned `WIKI_SYNC_REQUESTED`. (A prior "fix `listeners.py` `SyntaxError`" item was disproven — the `except ValueError, TypeError:` line is valid Python 3.14 per PEP 758; see the question file's §7 correction.) Option B (remove) retained as rejected alt (leaves gap open). PO decision. | — |
| [Q-017](resolved/Q-017-session-not-found-error.md) | Typed `SessionNotFoundError` vs bare `ValueError` (ADR-052 race) | → **Option A**: typed `SessionNotFoundError(NotFoundError)` raised from `_load_or_raise`; precise catch in stream tail + split at `handle_save`. Closes a latent `JSONDecodeError`-swallow + a two-source ValueError conflation. | — |
| [Q-018](resolved/Q-018-per-test-database-isolation.md) | Per-test-DB isolation vs two-phase serial for schema-mutating tests | → **Option B**: keep enforced two-phase serial (guard prevents silent lapse). Root cause contained, not fixed; per-test-DB (Option A) revisited at break-point (≥ 5 modules or > 60 s phase-2). | — |
| [Q-019](resolved/Q-019-xdist-worker-crash-oom.md) | xdist worker OOM crash under `-n auto` on < 16 GB RAM | → **Option A**: add `just test-lowmem` (`-n 2`) recipe for constrained machines; default unchanged (CI = 16 GB). Options B/D are non-fixes; C-only rejected (working mitigation exists). | — |
