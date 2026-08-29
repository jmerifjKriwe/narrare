# IDOR Remediation Plan — P-SEC Follow-up Sweep (21 GAP-CRITICALs)

> **EXECUTION RECORD (2026-08-29):** S1–S13 executed on `worktree/green-harbor-c1a3`
> (PR #190, commits `f08e5d0b..b6376f07`, 13 slice commits + batch-review fix wave).
> Batch security review verdict: all 21 GAP-CRITICAL clusters CLOSED except S3/WS
> (deferred per D4:b into the tracked follow-up below); both review findings (N1
> factory pre-gate resolution, N2 decision records) addressed and re-reviewed clean.
> Gates at close: `just verify` 10/10 (incl. Typecheck-Tests after S12b fake-cast fix),
> backend 12 476 passed, frontend 3 567 passed, architecture 2 673 files clean.
> Residual OPEN (tracked): S3/WS ticket follow-up (D1:a/D4:b records below),
> worldbuilding `apply_connections` entries∈novel validation, 16 inert
> `chapter_exists` mocks across 10 test files, `verify_novel_owned` gate
> consolidation, ADR-070 protocol gap (`get_adaptive_snapshots`), KB-002 doc
> staleness, consistency-cache owner dimension.

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans or
> superpowers:subagent-driven-development, slice by slice. Each slice is one
> independently landable unit: regression tests RED → gate → tests GREEN.

**Goal:** Close all 21 GAP-CRITICAL findings of the 2026-08-26 IDOR sweep
(`.superpowers/sdd/2026-08-21-scratchpad/followup-p-sweep-audit.md`) — every API
surface accepting `novel_id` / `series_id` / `project_id` / `chapter_id` /
`session_id` / `request_id` must verify caller ownership BEFORE any data load,
LLM enrichment, or write. Zero behavior change for the rightful owner; foreign
and unknown ids are indistinguishable.

**Fix patterns (verbatim from the audit — no others sanctioned):**

> **Pattern A — user-scoped store gate (chat):** repository/store methods filter
> by `user_id`; unknown and foreign ids both → 404.
> Reference: `chat/conversation_store.py` (`get_conversation` filters
> `ChatConversationModel.user_id == user_id` → `NotFoundError` → 404) and
> `writing/_helpers.py:get_validated_request` (`str(request_model.user_id) != user_id`
> → `NotFoundError`).

> **Pattern B — OwnedLinkLookup / owned-parent gate (notes/chat/analysis):**
> `novel_repo.get_by_id(novel_id, user_id)` (or `OwnedLinkLookupProtocol.get_owned`)
> raises `NotFoundError`/`ForbiddenError` BEFORE any data load or LLM enrichment.
> Reference: `notes/dependencies.py:_NovelOwnedLookup` (adapter over
> `NovelRepository.get_by_id(entity_id, user_id)`); `KBService._verify_novel_ownership`
> (`kb/service.py:61`).

## Global Constraints (every slice)

- **Regression-first TDD:** each slice starts with the foreign-user 404 matrix
  (RED), then the gate, then GREEN. Matrix per endpoint: (1) owner → 200/201
  unchanged, (2) foreign id → 404, (3) unknown id → 404 (byte-identical to (2)),
  (4) **no side effect** on the victim's resource (no row written, no LLM call,
  no feedback event persisted).
- **foreign ≡ unknown anti-enumeration:** ownership failures raise
  `NotFoundError` (core) → HTTP 404 via the global handler — never 403 on
  novel/chapter/session-scoped resources (403 stays reserved for the existing
  series-module semantics; untouched here).
- **RULE-03:** where a slice changes a method covered by a Protocol
  (`writing/contracts.py`, `kb/contracts.py`, module `contracts.py`), the
  contract signature lands FIRST in the slice's first commit.
- **RULE-11:** no swallowed failures. The beta-reader "degrade to defaults on
  auth failure" (`context_assembler.py:248-260`) is the exact anti-pattern —
  authorization gates RAISE. **RULE-23:** no `# type: ignore` to thread `user_id`.
- **Sizing:** ≤3 substantive production files per delegated slice (sub-slices
  where marked). Test files and pure DI-wiring additions (injecting
  `NovelRepository` into an existing factory) don't count, but stay minimal.
  File-size limits per `pyproject.toml` (service 300 / router 150 / repository
  250; `writing/_helpers.py` 290/400 headroom verified).
- **No new dependencies, no migrations.** Identity is `CurrentUserIdDep`
  (`_app/dependencies_auth.py:50`, `str`) — convert with `UUID(user_id)` at the
  service boundary (existing pattern: `kb/router_sessions.py:38`).
- English everywhere. Tests follow `tests/unit/api/<module>/test_*_ownership.py`
  (precedent: `tests/unit/api/chat/test_chat_service_project_ownership.py`,
  `tests/unit/api/series/test_ownership_regression.py`). Gates per slice:
  `just test-file <path>`, then `just check-architecture`. Commits via Platform
  specialist, never `--no-verify`.

## Ordering (data-loss / exfiltration first)

S1 export → S2 co-author apply → S3 WS (blocked on D1) → S4 summary →
S5 access helper → S6 writing wiring → S7 KB sessions → S8 KB improve/worldbuilding →
S9 KB graph/suggest/consistency → S10 KB relationships/dismissed/extraction →
S11 settings surfaces → S12 beta-reader + names → S13 minors.
S3 depends on decision D1; S4+ do NOT depend on S3 — execute S4 onward while D1 is open.

---

## S1 — Export: full manuscript exfiltration (worst vector)

**Scope:** POST /export · GET /export/jobs/{job_id} · GET /export/jobs/{job_id}/artifact.
**Files:** S1a: `export/router.py` + `export/service.py` + `export/dependencies.py`
(inject an `OwnedLinkLookupProtocol` adapter — Pattern B, mirror
`notes/dependencies.py:_NovelOwnedLookup`). S1b: `export/registry.py` (+ service/router
pass-through already opened in S1a).
**Fix shape:**
- Router: all three handlers gain `user_id: CurrentUserIdDep` and pass it down.
- S1a `ExportServiceImpl.export(novel_id, options, user_id)`: FIRST statement is
  the owned-lookup gate — `None` → 404 (`errors.py` not-found class) — BEFORE
  `registry.create`. `repository._get_novel` is NOT the gate (task-time only);
  the POST must not create a job for a foreign novel.
- S1b `registry.create(novel_id, user_id, fmt)` stores `owner_user_id` on the job
  record; `get`/`consume_artifact` gain `user_id` and treat owner-mismatch as
  unknown job (404) — closes the stolen-token poll path.
**Tests first:** `tests/unit/api/export/test_export_ownership.py` — foreign novel
POST → 404 AND no job in registry; unknown novel → identical 404; owner → 201;
foreign/unknown user polling or consuming another user's job+token → 404.
**Hazards:** `ExportServiceImpl` has no DB dependency today — the lookup adapter
is the only new wiring. Do NOT gate inside `tasks.py` (job would exist and leak via polling).

## S2 — Co-author apply: arbitrary foreign chapter WRITE + feedback pollution

**Scope:** POST /writing/chapters/{chapter_id}/co-author/apply · .../co-author/feedback.
**Files:** `writing/coauthor_apply_service.py` + `writing/router_coauthor.py`
(apply route already passes `user_id` at line 92; feedback route line ~110 adds `CurrentUserIdDep`).
**Fix shape:**
- `apply_changes` (line 84; `user_id` already in signature, unused): FIRST
  statement `request_model = await get_validated_request(self._repo, request.request_id, user_id)`
  (Pattern A, existing helper `_helpers.py:195`), then verify
  `request_model.chapter_id == chapter_id and request_model.novel_id == novel_id`
  → else `NotFoundError("Chapter", chapter_id)`. The write is bound to a
  generation request the caller owns; keep the existing chapter load after the gate.
- `record_feedback` (line 141): replace bare `self._repo.get_by_id(request_id)`
  with `get_validated_request(...)` — feedback is persisted under the caller,
  never the victim (fixes the `_helpers.py:44-47` pollution).
**Tests first:** `tests/unit/api/writing/test_coauthor_apply_ownership.py` —
foreign request_id → 404, chapter `update_content` NEVER called, zero
FeedbackEvents under victim user_id; chapter/novel mismatch vs request row → 404.
**Hazards:** none — service-internal gate, no wiring changes.

## S3 — WS interactive sessions: impersonation via client-supplied user_id

**Scope:** WS /writing/sessions/{chapter_id}.
**Files:** `writing/router_sessions.py` + `writing/ws_handler.py` (+ `deps_ws.py` wiring).
**Fix shape:**
- **Auth half — BLOCKED on D1** (see PO decisions). Do NOT improvise a token scheme.
- Ownership half (after D1): identity comes from the chosen auth mechanism, not
  the `user_id: str = ""` query param (delete it); before `handler.handle(...)`
  run the S5 `verify_chapter_access` helper using the DB session already opened
  at `router_sessions.py:104-136`; on failure close with code 4001 (reuse the
  existing close-on-reject pattern, lines 41-50). Rate-limit key (`ws_key`,
  line 70) switches from spoofable to derived identity.
**Tests first:** `tests/unit/api/writing/test_ws_session_ownership.py` —
foreign/unknown chapter or project → connection closed 4001, zero session rows,
zero mem0 writes; spoofed `user_id` param ignored.
**Hazards:** genuinely hard — browser WS cannot send Authorization headers;
needs an ADR (ticket endpoint vs first-message auth) + frontend change. Flagged D1.

## S4 — Summary: foreign chapter → LLM + summary written to foreign chapter

**Scope:** POST /summary/chapters/{chapter_id}.
**Files:** `writing/summary_router.py` + `summary_service.py` + `summary_deps.py`.
**Fix shape:** Router adds `CurrentUserIdDep` → `summarize(chapter_id,
max_sentences, language, user_id)`. Service (line ~101): after the
`chapter_repo.get(chapter_id)` None-check, gate
`novel_repo.get_by_id(chapter.novel_id, UUID(user_id))` → None →
`NotFoundError("Chapter", chapter_id)` (Pattern B) BEFORE content load, LLM
call, and `update_summary` (line ~166). `summary_deps.py` injects
`NovelRepository`. Router's existing `NotFoundError` → 404 mapping (lines 59-60) stays.
**Tests first:** `tests/unit/api/writing/test_summary_ownership.py` — foreign
chapter → 404, `update_summary` never called on victim chapter, no `agent.run`;
unknown chapter → identical 404; owner → 200.
**Hazards:** none.

## S5 — Writing access helper (foundation for S6/S3)

**Scope:** no endpoints — shared helper only.
**Files:** `writing/_helpers.py` (290/400 headroom verified) + tests.
**Fix shape:** new `verify_chapter_access(chapter_repo, novel_repo, chapter_id,
novel_id, user_id: str) -> Chapter`: chapter exists ∧ `chapter.novel_id ==
novel_id` ∧ `novel_repo.get_by_id(novel_id, UUID(user_id))` is not None →
else `NotFoundError("Chapter", chapter_id)`. Composes EXISTING repo methods
(`ChapterRepository.get`, `NovelRepository.get_by_id`) — zero repo signature
changes. Pure function next to `get_validated_request` (module precedent; no
new Protocol per RULE-03 — it is not a service method).
**Tests first:** `tests/unit/api/writing/test_verify_chapter_access.py` — matrix:
foreign novel / unknown chapter / chapter∉novel / owner (returns Chapter).
**Hazards:** two lookups per call accepted (correctness over micro-optimization).

## S6 — Writing generate/extend/rewrite/co-author/style-variants/suggest wiring

**Scope:** POST /writing/chapters/{chapter_id}/generate · /extend · /rewrite ·
/co-author · /style-variants/regenerate · /suggest.
**Files:** S6a: `writing/service.py` (`start_generation` line ~98 gates BEFORE
`create_if_no_active` — kills request-row pollution + owner-blocking via the
unique active index) + `extend_service.py` (line ~104) + `rewrite_service.py`
(line ~97). S6b: `coauthor_service.py` (line ~108) + `style_variant_service.py`
(line ~97) + `suggest_service.py` (line ~103 — also closes the GAP-MINOR metadata leak).
**Fix shape:** every `validate_*` replaces `await self._repo.chapter_exists(chapter_id)`
(existence-only) with `await verify_chapter_access(self._chapter_repo,
self._novel_repo, chapter_id, novel_id, user_id)`; `suggest` (chapter-only path)
gates `chapter.novel_id → novel_repo.get_by_id(...)`. Routers (`router.py`,
`router_extend.py`, `router_rewrite.py`, `router_coauthor.py`,
`router_style_variants.py`, `router_suggest.py`) thread missing `CurrentUserIdDep`
(mechanical). Services gain `NovelRepository` via their existing deps factories.
This also removes the unscoped `fetch_formatted_relationships(novel_id)` LLM
enrichment vector (`_helpers.py:151`) — the request row can no longer reference
a foreign novel. RULE-03: `WritingServiceProtocol`/`SuggestServiceProtocol`
signature changes land in `writing/contracts.py` FIRST. Validation order:
ownership → input → active-conflict.
**Tests first:** `tests/unit/api/writing/test_generation_access_matrix.py` —
parametrized over the six endpoints: foreign chapter/novel → 404 AND zero
GenerationRequest rows created; owner → 201/200 unchanged.
**Hazards:** all touched `*_service.py` verified well under the 300-line limit.

## S7 — KB creation sessions: session_id-only access

**Scope:** POST/GET/PATCH /novels/{novel_id}/kb/sessions[...], suggest,
interview, enhance, DELETE, complete (8 endpoints).
**Files:** `kb/session_service.py` + `kb/router_sessions.py` +
`kb/router_sessions_complete.py` (both routers ALREADY pass `novel_id` +
`CurrentUserIdDep` — verified lines 28-48; only service threading).
**Fix shape:** Pattern A at the single choke point: `_get_or_raise(session_id)`
(line 262) → `_get_or_raise(session_id, novel_id, user_id)` filtering
`session.novel_id == novel_id AND session.user_id == UUID(user_id)` →
`NotFoundError("KB creation session", session_id)`. `create_session` (line 46)
FIRST gates `novel_repo.get_by_id(novel_id, user_id)` (Pattern B) — closes
attacker-driven `complete_session` writes into the victim's KB (line ~227
stores entries as `session.user_id`).
**Tests first:** `tests/unit/api/kb/test_session_ownership.py` — every verb with
foreign/unknown session_id → 404; create with foreign novel → 404 + no row;
complete on foreign session → zero KBEntry rows for victim.
**Hazards:** none — routers already carry identity.

## S8 — KB improve + worldbuilding

**Scope:** POST /kb improve analyze/apply; worldbuilding analyze/apply.
**Files:** `kb/improve_service.py` + `kb/improve_analyzer.py` + `kb/worldbuilding_service.py`.
**Fix shape:** service-entry gate `novel_repo.get_by_id(novel_id, user_id)` →
`NotFoundError` (Pattern B) in improve `analyze`/`apply` (before
`analyzer.get_cached_analysis` / `kb_repo.get_by_id(entry_id)` at lines ~78-96 —
additionally assert `entry.novel_id == novel_id` after entry load) and in
worldbuilding analyze/apply (the unused `user_id` param in `apply_connections`
becomes the gate input). The analyzer itself stays gate-free (runs post-gate only).
**Tests first:** `tests/unit/api/kb/test_improve_worldbuilding_ownership.py` —
foreign novel → 404 before any analyzer/LLM call; foreign entry under own novel
→ 404; apply writes nothing on failure.
**Hazards:** gate must run BEFORE the `get_cached_analysis(entry_id)` cache lookup too.

## S9 — KB graph + suggestions + consistency

**Scope:** GET /kb graph + shortest-path; POST /kb suggestions; POST /kb consistency check.
**Files:** `kb/graph_service.py` + `kb/suggest_service.py` + `kb/consistency_service.py`.
**Fix shape:** all three carry a `user_id` param documented "(for authorization)"
that is never used — make it real: first-line gate `novel_repo.get_by_id(novel_id,
user_id)` → `NotFoundError` in `get_graph`, `get_shortest_path`, kb-suggest
(replacing the chapter↔novel-only check at `suggest_service.py:75` with the
S5-style chapter∈novel ∧ novel∈user compound), and `consistency_service.check`
(currently user_id only suppresses mem0).
**Tests first:** `tests/unit/api/kb/test_graph_suggest_consistency_ownership.py` —
foreign novel → 404 with zero entries/relationships/adjacency fetched (assert
repo not queried after gate); matrix per endpoint.
**Hazards:** consistency has unscoped phases — the `check()` entry gate covers all of them.

## S10 — KB relationships + dismissed + extraction

**Scope:** relationships create/delete/list/inverse; dismissed dismiss/undismiss/list; extraction POST extract.
**Files:** `kb/relationship_service.py` + `kb/dismissed_service.py` + `kb/extraction_service.py`.
**Fix shape:** Pattern B novel gate at each public method entry
(`relationship_service.py:47-130` — entry→novel linkage is NOT user scope;
`dismissed_service.py:135-160` before `repo.dismiss/undismiss/list_dismissed`;
`extraction_service.py:95-99` — delete the false "scoped by novel_id for
ownership" comment, gate chapter∈novel ∧ novel∈user before content load).
Routers thread `CurrentUserIdDep` where missing (mechanical;
`dependencies_extraction.py` wiring).
**Tests first:** `tests/unit/api/kb/test_relationship_dismissed_extraction_ownership.py` —
foreign novel → 404 with zero KBRelationship rows created, dismissal state
untouched, no extraction result returned.
**Hazards:** none.

## S11 — Settings project surfaces: foreign config WRITE (3 sub-slices)

**Scope:** GET/PATCH /settings/novels/{novel_id}; PUT+GET
/settings/token-limits/project/{project_id}; GET/PATCH /settings/ai/novels/{novel_id};
adaptive /toggle, /weights, snapshots read.
**Files:** S11a: `settings/dependencies.py` (NEW dependency `verify_novel_owned` —
precedent `kb/dependencies.py:84 verify_novel_in_owned_series`: resolves
`NovelRepository` + `CurrentUserIdDep`, raises 404) + `settings/router.py` (apply
to GET/PATCH `/novels/{novel_id}` — `user_id` param exists but is unused;
`ProjectSettingsRepository.get/update(novel_id)` stays novel-keyed — the
DEPENDENCY is the gate). S11b: `settings/token_limits/router.py`
(`update_project_limits` line ~98 — same dependency; `project_id: str` → UUID) +
`settings/router_ai.py` + `settings/project_ai_settings_service.py` (gate
`novel_repo.get_by_id(novel_id, user_id)` in `get_settings`/`update_settings` —
docstring says "(for authorization)", make it true). S11c: `adaptive/service.py`
— `set_enabled`/`set_weights` (lines ~164-196) gate via injected
`NovelRepository`; DELETE the false `del user_id  # ownership handled at router`
comment (line ~205) and gate `get_adaptive_snapshots` too (closes the MINOR).
Wiring: `adaptive/dependencies.py`.
**Tests first:** `tests/unit/api/settings/test_project_settings_ownership.py` +
`tests/unit/api/adaptive/test_adaptive_settings_ownership.py` — foreign/unknown
novel or project → 404, settings row unchanged (incl. `adaptive_settings` column
and token-limit overrides).
**Hazards:** `ProjectSettingsRepository.get` auto-creates a row on read — the
dependency MUST run before the repo is touched, else a foreign novel id
materializes a settings row (FK 500s on truly-unknown ids — the gate fixes that too).

## S12 — Beta-reader assembler + generation names

**Scope:** POST /analysis/beta-reader · /beta-reader/deep-dive; POST /generation/names.
**Files:** S12a: `analysis/context_assembler.py` + `analysis/beta_reader_service.py`.
S12b: `generation/name_service.py` + `generation/router.py`.
**Fix shape:**
- S12a: `build_context`: `user_id` becomes REQUIRED (`UUID`, no `None`
  fallback); ownership check moves to Step 0 — BEFORE `chapter_repo.list_by_novel`
  (line ~111) and `_fetch_kb_context` (line ~128); `_fetch_novel_metadata`
  (lines 248-260) loses the try/except-degrade — lookup `None` → raise
  `NotFoundError("Novel", novel_id)` (RULE-11: graceful-degrade may never carry
  an authorization decision). `ChapterNotFoundError` stays for
  chapter-not-in-novel (client error, not auth). Deep-dive shares the path
  (`beta_reader_service.py:200`).
- S12b: `generate_names(request, user_id)` — when `request.project_id` is set,
  gate `novel_repo.get_by_id(project_id, user_id)` BEFORE `_fetch_existing_names`
  (line ~169, foreign KB names into LLM) and before model-routing resolution;
  router passes `CurrentUserIdDep`.
**Tests first:** `tests/unit/api/analysis/test_context_assembler_ownership.py`
(foreign novel → NotFoundError before ANY chapter/KB fetch — assert repos not
queried) + `tests/unit/api/generation/test_name_service_ownership.py`.
**Hazards:** check other `context_assembler` callers for `user_id=None` — if a
background/system caller exists it must pass a system identity explicitly
(escalate if found; none known at plan time).

## S13 — Minors (optional, after all CRITICALs)

- `writing/service.py:get_stats(novel_id, user_id)` — `user_id` already in
  signature, ignored: add the novel gate (one line).
- Embeddings admin (`embeddings/router.py` GET status/{novel_id} · POST
  reprocess): add the S11a-style ownership dependency (currently inert but
  unscoped) — or remove, per D3.
- Export job status read: already closed by S1b.
- Prompts global overrides (`prompts/router.py:107-140`): NOT mechanical — D2.

---

## Decisions needed from PO (blockers — do NOT improvise)

1. **D1 — WS authentication strategy (blocks S3):** browser WebSockets cannot
   send Authorization headers; `get_current_user_id` is HTTPBearer-only
   (`_app/dependencies_auth.py:15`). Options: (a) short-lived signed ticket
   fetched via authenticated REST, sent as `token` query param on WS connect
   (recommended — standard, revocable); (b) first-message auth frame after
   connect (reject-all-until-authed); (c) mTLS/subprotocol hacks (rejected —
   non-standard). Requires an ADR + `packages/web` change. ~~Until decided, S3
   stays open and the WS endpoint remains the one unauthenticated surface.~~
   RESOLVED 2026-08-27 → **D1:a** (see Decision Records below).
2. **D2 — Prompts global overrides (MINOR):** overrides are global files — any
   authenticated user rewrites them for ALL users. Either scope override
   storage per user (real multi-user stance) or keep global under a documented
   single-user-trust assumption (local-first product stance). Product call.
3. **D3 — Embeddings admin endpoints (MINOR):** ownership-gate them, restrict
   to an admin flag, or delete the dead surface (`reprocess` is inert from the
   router). Pick one.

**Decisions (resolved by PO before S13):**
- **D2 → (a)** prompts global overrides stay GLOBAL under a documented
  single-user-trust assumption (local-first product stance) — documented on
  the override surface (`prompts/router.py` docstrings); no code change.
- **D3 → (a)** embeddings admin endpoints get the same ownership gating as
  everything else: `status/{novel_id}` + `reprocess/{novel_id}` are
  novel-scoped → S11a-style `verify_novel_owned` route gate; `model` is
  global-inert → minimal authenticated-user gate, documented.

**Totals: 12 critical slices (+S13 minors) · every slice independently landable ·
S3 partially blocked on D1 · S13 depends on D2/D3.**

---

## Decision Records (post-batch review, 2026-08-29)

Decisions taken after the batch review of PR #190 — recorded here so the
plan's "decisions needed" section no longer reads as open where it is not.

### D1:a — WS authentication via REST-issued short-lived ticket (RESOLVED)

**Decision (PO, 2026-08-27):** option (a). The browser fetches a
short-lived signed ticket from an authenticated REST endpoint and passes
it as the `token` query parameter on the WebSocket connect. Standard
pattern, revocable, avoids first-message-auth race windows.

**Still required (not part of PR #190):** an ADR documenting the ticket
format/lifetime/revocation semantics and the `packages/web` change that
fetches and forwards the ticket.

### D4:b — S3 executes as a separate follow-up task outside PR #190 (RESOLVED)

**Decision (PO, 2026-08-27):** with D1 resolved to (a), the WS slice is
no longer blocked, but it lands as a SEPARATE follow-up task rather
than inside PR #190 — the PR is the IDOR remediation batch and stays
reviewable; the WS surface needs its own ADR-gated cycle.

**Follow-up slice scope (S3 + D1:a combined):**

1. **Ticket issuance endpoint** — authenticated REST route issuing a
   short-lived signed ticket (define TTL + revocation in the ADR).
2. **WS handshake validation** — `router_sessions.py` accepts the
   `token` query param, validates the ticket, derives the identity
   (replacing `get_current_user_id`'s HTTPBearer-only path for WS).
3. **Spoofable `user_id` query param removal** — delete the
   `user_id: str = ""` query param from the WS route; identity comes
   exclusively from the validated ticket. Rate-limit key (`ws_key`)
   switches from the spoofable param to the derived identity.
4. **Ownership gate at handshake** — run the S5 `verify_chapter_access`
   helper before `handler.handle(...)`; failure → close 4001 (existing
   close-on-reject pattern).
5. **ADR** — WS auth strategy (D1:a) with ticket semantics; referenced
   from the code sites it governs.
6. **`packages/web` change** — client fetches the ticket and appends it
   to the WS URL.

**Tests (from S3, unchanged):** `tests/unit/api/writing/test_ws_session_ownership.py`
— foreign/unknown chapter or project → connection closed 4001, zero session
rows, zero mem0 writes; spoofed `user_id` param ignored/rejected.

**Status until the follow-up lands:** the WS endpoint remains the one
unauthenticated surface — tracked by the follow-up task, NOT by this plan
batch.
