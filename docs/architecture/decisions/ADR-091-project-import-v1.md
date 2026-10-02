# ADR-091 — Project Import v1: Stateless Two-Phase Multipart Import (SETUP-003)

> **Status:** ✅ Accepted
> **Date:** 2026-10-02
> **Deciders:** Architecture Agent (formalizing the approved SETUP-003 brainstorm session with the project owner — all binding decisions made there; this ADR records and justifies them)
> **Supersedes:** none (retires the dormant `import_path` stub — no ADR existed for it)
> **Spec:** `docs/superpowers/specs/2026-10-02-project-import-design.md`
> **Plan:** `docs/superpowers/plans/2026-10-02-project-import.md`

---

## Context

SETUP-003 ("Project Import") is a planned feature: writers arriving at Narrare
with existing manuscripts must be able to bring their chapters in instead of
copy-pasting one by one. The feature file sketched a broad vision (DOCX, KB
extraction, directory import); the approved brainstorm session (2026-10-02,
project owner) scoped a staged **v1**:

- Formats: Markdown (`.md`) and plain text (`.txt`) only. DOCX via pandoc is an
  explicit follow-up slice (IO-001 already ships pandoc in
  `apps/api/narrare/export/renderers/` — the converter exists when needed).
- KB extraction stays with the existing per-chapter UI
  (`POST /novels/{id}/kb/extract/{chapter_id}`); **no bulk extraction in v1**.
- Entry points: Setup Wizard (new projects) AND the novel workspace sidebar
  (existing novels).

A dormant server-side `import_path` mechanism exists today but is dead weight:

- `apps/api/narrare/setup/base_schemas.py` — `Step3StarterRequest.import_path`
  field (+ a validator that validates nothing).
- `apps/api/narrare/setup/_validation.py:87-93` — validates that a
  **server-side** path exists and is a directory.
- `apps/api/narrare/setup/service.py` — `complete()` silently drops
  `starter="import"` into the else-branch: a blank novel is created and the
  user's stated intent (import) is discarded without any signal.
- `packages/web/components/studio/wizard/WizardStep2.tsx:146-168` — a text
  input asking the browser user for a **filesystem path on the API server**.

This is a RULE-20 half-implementation that shipped as a stub. It must be
either completed or removed — v1 removes it.

Distribution context: Narrare ships Docker-only (resolved Q-011, Option A) and
has no external users yet (0.x precedent, Q-012-class rationale: breaking
removals without compatibility shims are acceptable while the user base is
the project owner).

---

## Decision Drivers

- **Docker-only distribution (Q-011):** the API runs inside a container. A
  browser-supplied server path is a footgun — it either points inside the
  container (invisible to the user) or requires volume-mount guesswork.
- **RULE-20:** the dormant `import_path` stub is a half-implementation;
  completing it would mean building a server-path ingestion pipeline nobody
  can use sensibly from the shipped UI. Removing it BE+FE in one slice is the
  RULE-20-conform path.
- **Local-first, single-user:** no object storage, no external brokers
  (ADR-080 in-process model). The upload must fit the existing request/response
  lifecycle.
- **Preview-before-commit UX (binding):** the user must see and adjust
  (rename/include/exclude) detected chapters before anything is written.
- **0.x no-users precedent:** breaking changes to the wire format
  (`Step3StarterRequest.import_path` removal) are acceptable now, without
  deprecation shims.
- **Determinism:** the preview the user approves must be the import that is
  executed — no server-side session state should be able to drift between the
  two phases.

---

## Options Considered

### Option A — Browser multipart upload, stateless two-phase API

`POST /api/v1/import/preview` (parse only, no DB writes) followed by
`POST /api/v1/import/commit` (re-parse the same files deterministically, apply
adjustments, append chapters atomically). First `UploadFile` surface in the API.

**Pros:**
- Works identically in Docker, dev, and any future host — the browser already
  has the bytes.
- Stateless: no staging table, no TTL cleanup, no job substrate; commit is
  idempotent-by-construction (deterministic parser ⇒ same bytes in ⇒ same
  chapters out).
- Mirrors the export feature's shape (IO-001: request-scoped, no durable job
  state for the synchronous path).

**Cons:**
- Files are uploaded twice (preview + commit). Bounded by guardrails
  (≤ 25 MB total) — acceptable on a local-first LAN deployment.
- Requires a multipart-aware frontend client (the current `fetchApi` wrapper
  hard-codes `Content-Type: application/json`).
- First multipart endpoint ⇒ new proxy-path verification obligation
  (Next.js rewrite, see Consequences).

### Option B — Keep and complete the server-side `import_path` mechanism

**Pros:**
- No upload path at all; one request.

**Cons:**
- In Docker-only distribution the path is nearly always wrong or inaccessible
  (Q-011 footgun); requires volume-mount documentation per deployment.
- Path handling on the server = arbitrary filesystem read surface for the
  authenticated user; needs its own sandboxing story.
- The UI stub proves it was never usable end-to-end; "completing" it builds
  the wrong feature.

### Option C — Staged upload (disk/blob + background job)

Upload once to a staging area, preview from a staged ID, commit from the same
ID (ADR-080 in-process task).

**Pros:**
- Single upload; staging ID pins the exact bytes the user approved.

**Cons:**
- Introduces durable(ish) staging state + TTL cleanup + job bookkeeping for a
  25 MB-bounded, single-user feature — complexity out of proportion.
- Re-imports are rare, small, and interactive; the double upload cost is
  seconds.

**Decision on transfer:** **Option A.**

### Parser placement — Option P1: pure Core (`packages/core/narrare_core/importing/``)

Detection heuristics (heading/marker split, frontmatter mapping, fallback
titles) as a pure, I/O-free, deterministic unit in Core.

**Pros:**
- RULE-07 placement: domain logic with no HTTP/DB concern belongs in Core,
  where API, future MCP/CLI clients (RULE-12) and tests all reach it.
- Testable without the FastAPI app; mirrors the ADR-081 precedent
  (`core/export/` normalizer pure in Core, renderers in API).
- The deterministic re-parse contract is enforced by construction: one pure
  function, no hidden state.

**Cons:**
- One more Core package to export/maintain.

### Parser placement — Option P2: API-local (`apps/api/narrare/importing/parsing/`)

**Pros:**
- Fewer packages; parsing is (today) only consumed by the API.

**Cons:**
- Couples detection policy to the app layer; a future CLI/MCP import would
  either duplicate it or import from `apps/` (a RULE-07 inversion at the
  workspace level).
- Golden tests drag in the API package for no benefit.

**Decision on parser placement:** **P1 — pure Core.**

---

## Decision

1. **New module pair.**
   - `packages/core/narrare_core/importing/` — pure, deterministic parser:
     `models.py` (`DetectedChapter`), `splitting.py` (ATX/markers),
     `detector.py` (`detect_chapters(filename, text)`). No I/O, no deps
     beyond `narrare_core.shared.frontmatter.parse_frontmatter`.
   - `apps/api/narrare/importing/` — standard module structure
     (`contracts.py` → `schemas.py` → `constants.py` → `service.py` →
     `repository.py` → `router.py` → `dependencies.py`), routers delegate
     immediately (RULE-06), `SessionDep` factories (RULE-19). The name
     `importing` avoids the Python keyword `import`.

2. **Stateless two-phase multipart API with deterministic re-parse contract.**
   - `POST /api/v1/import/preview` (multipart `files[]`, authenticated): runs
     guardrails → decode → parse; **no DB writes**; returns preview items
     (`index`, `suggested_title`, `word_count`, `source_file`).
   - `POST /api/v1/import/commit` (multipart `files[]` + `novel_id` +
     `adjustments` JSON): guardrails → **re-parses deterministically** →
     applies `excluded_indices` / `title_overrides` (index-based) →
     ownership gate (`verify_novel_owned`, foreign ≡ unknown → 404) →
     appends `Chapter` rows atomically.
   - **Contract:** the parser is pure, therefore identical file sets in
     identical order yield identical chapter lists. The client MUST send the
     exact `File[]` it previewed (the shared `ImportPreviewPanel` holds the
     `File[]` in component state, making drift impossible by construction).
     The server enforces structural validity of adjustments (index range,
     title length ≤ 500) — a mismatched file set surfaces as 422, never as a
     silently wrong import. There is NO server-side session state.

3. **`import_path` removal (BE + FE in one slice, RULE-20).** Remove
   `Step3StarterRequest.import_path`, `WizardState.import_path`, the
   `_validation.py` IMPORT branch, the WizardStep2 path input, the WizardStep5
   `importFrom` row, `wizardStore` state, and the related i18n keys.
   `StarterContent.IMPORT` (the enum value / starter choice) **stays**: after
   v1, `complete()` with `starter="import"` creates an empty novel by design —
   the frontend then commits files via `/import/commit` with the new
   `novel_id`.

4. **Guardrails (ratified):** ≤ 100 files per upload, ≤ 25 MB total,
   single file ≤ 5 MB, zero detected chapters → 422 (with the offending
   filename where applicable). UTF-8 strict, BOM tolerated
   (`utf-8-sig` decode); undecodable file → 422 naming the file. No charset
   detection in v1.

5. **Import semantics: append, atomic, no dedup, no undo.** New chapters get
   `position = max(existing)+1 .. +n` (existing `ChapterRepository.max_position`
   semantics; empty novel ⇒ 0-based). All rows are created in the request
   transaction — any failure rolls back completely. Running import twice
   duplicates chapters (documented, like DemoLoader behavior). Chapter
   `status` from frontmatter if present, else `"draft"`; `volume_id` stays
   NULL (mirrors DemoLoader).

6. **Scope boundary to IO-002.** IO-002 ("Project Import & Analysis" — deep
   AI-assisted understanding of imported projects) remains a separate future
   feature. SETUP-003 v1 imports **chapters only**; no KB extraction, no DOCX,
   no split/merge boundary editing, no directory upload, no undo.

---

## Rationale

The transfer decision follows from Q-011: Docker-only distribution makes
server paths unusable-by-design from the shipped UI, and the stub's dormancy
shows no latent demand for it. Between A and C, the stateless design wins
because the deterministic pure-Core parser already guarantees
preview≡commit for identical inputs — staging state would only buy us the
omission of a bounded, seconds-cheap second upload at the cost of TTL/job
machinery in an intentionally substrate-free deployment (ADR-080). The
double-upload cost is bounded by the guardrails that must exist anyway.

Parser placement follows RULE-07's core-vs-app test: detection heuristics are
I/O-free domain policy, not HTTP orchestration. Core placement makes the
deterministic re-parse contract a property of a pure function rather than a
service discipline, and keeps the golden tests fast and app-independent
(ADR-081 `core/export/` precedent).

The removal slice is RULE-20 applied retroactively: a dormant stub that
silently swallows user intent (`starter="import"` → blank novel) is worse
than no feature. Removing it BE+FE in one slice avoids a compatibility
surface for a wire format that has no external consumers (0.x, Q-012-class
precedent).

---

## Consequences

**Positive:**
- First `UploadFile` surface lands with contract-first structure and guard
  rails; establishes the multipart pattern for the future DOCX slice.
- The wizard import path and the sidebar import path share one component
  (`ImportPreviewPanel`/`ImportModal`) — one detection UX, two entries.
- Removing the stub eliminates a silent-intent-loss bug class and dead i18n.
- No DB migration (Chapter model reused as-is; `volume_id` already nullable).

**Negative / Tradeoffs:**
- Files are uploaded twice per import (bounded ≤ 25 MB) — accepted.
- Wire break for `Step3StarterRequest`/`WizardState` (`import_path` field
  removed) — accepted under the 0.x no-users precedent.
- New verification obligation: multipart bodies traverse the Next.js rewrite
  (`next.config.ts` `/api/v1/:path*` → API), NOT `proxy.ts` (route protection
  only; its matcher never matches `/api`). Starlette/uvicorn impose no default
  request-body limit and Next.js `bodySizeLimit` applies to Server Actions
  only, but the plan must verify a real > 1 MB multipart upload through the
  rewrite (dev) before relying on it; production CORS is closed, so the
  rewrite is the only viable browser→API path in Docker deployments.
  - **Update 2026-10-02 (post-implementation):** this risk materialized — see
    the *Post-implementation Amendment* section below.
- Import is append-only without undo — documented UX contract; users verify
  the preview.

**Constraints introduced:**
- RULE-03: `importing/contracts.py` Protocols written before service impl.
- RULE-04: file size limits per type apply to the new modules.
- RULE-06/07: router → service → repository; Core parser stays I/O-free.
- RULE-17: `ImportPreview*`/`ImportCommit*` Pydantic schemas must exactly
  match `packages/web/types/importing.ts` in the same commits.
- RULE-16: new `importing` i18n namespace registered in
  `packages/web/lib/i18n/request.ts` + en/de/fr files.

---

## Implementation Notes

- Ownership gate: reuse `narrare.novels.ownership.verify_novel_owned`
  (canonical, IDOR-consolidated W3) — do not write a local gate.
- Error mapping: `narrare_core.shared.errors.ValidationError` → 422,
  `NotFoundError` → 404 via the app-level `NarrareError` handler
  (`{"detail", "code"}` shape) — no router-level try/except.
- Bulk insert pattern: mirror `setup/demo_loader.py` (`session.add` +
  single flush inside the caller's transaction), but keep SQL inside
  `importing/repository.py` (RULE-06; the DemoLoader predates the split).
- Detection heuristics (normative): file-per-chapter baseline; `.md` splits
  on ATX `#`/`##` headings (frontmatter honored: `title`, `status`);
  `.txt` splits on `^(chapter|kapitel)\s+(arabic|roman)` markers
  (case-insensitive, EN/DE); no headings/markers ⇒ single chapter titled from
  frontmatter/filename stem. Full edge-case table in the design spec §6.
- Frontend: `fetchApiUpload` (multipart variant without `Content-Type`
  override) in `lib/api/core.ts`; `ImportSelection` (File[] + adjustments)
  lives in component/store state only — never serialized into
  `setupApi.complete`.
- Wizard completion order: capture selection → `setupApi.complete` →
  (starter=import) `importApi.commit(files, novel_id, adjustments)` →
  reset + navigate. Commit failure after novel creation is a documented
  degrade path: banner + retry via the sidebar ImportModal (sessionStorage
  flag `narrare:importFailed:{novel_id}`).

**ADR Implementation Completeness Gate (Gate 12):** Before marking this ADR as
"✅ Implemented", verify all items in the Gate 12 checklist at
`.opencode/context/narrare-dev/processes/quality-gates.md`. An ADR is not
implemented until it is fully wired, tested, consumed, and documented.

---

## Post-implementation Amendment (2026-10-02) — R1 materialized: Next.js proxy body-size cap

During Plan Task 2 Step 6 (mandatory live multipart verification through the
Next.js dev rewrite) the "new verification obligation" risk above
materialized, was root-caused, and is resolved by a config amendment.

**Observed (coordinator-run, live):** a 2 MB body passed (API 200, correct
preview JSON); a ~6.8 MB single file was correctly rejected by the per-file
guard (422 naming the file). But 14.4 MB and 28.8 MB bodies (6 files à
~4.8 MB, each under the 5 MB per-file guard) failed with HTTP 500 after
exactly 30 s, while the API logged 400 on a *truncated* multipart stream with
`socket hang up`/`ECONNRESET`. The Next dev log carried the smoking gun:
`Request body exceeded 10MB for /api/v1/import/preview. Only the first 10MB
will be available unless configured.` Direct calls against the API (bypassing
Next) reproduced none of this — the service guard pipeline answered correctly
in 0.18 s (422, naming the file). The API side is sound; the proxy hop is not.

**Root cause:** Next.js 16 buffers request bodies to make them re-readable
across the proxy/rewrite hand-off (`getCloneableBody`). The buffer is capped
at **10 MB by default**, controlled by `experimental.proxyClientMaxBodySize`
(installed `next@16.3.6` evidence: key declared in `ExperimentalConfig` —
`dist/server/config-shared.d.ts`; read in `dist/server/next-server.js` and
`dist/server/lib/router-utils/resolve-routes.js`; default + truncation in
`dist/server/body-streams.js`). On overflow, both clone streams are cut and
the warning is logged — the API receives a mutilated multipart body and
correctly rejects it; Next surfaces the 500. This is a *different* knob from
Server-Action `experimental.bodySizeLimit`, so the original Consequences text
above remains true — it simply enumerated the wrong knob as "no limit". The
warning URL still names `middlewareClientMaxBodySize`: in 16.3.6 that is the
**deprecated alias** (`@deprecated Use proxyClientMaxBodySize instead`), which
is auto-mapped by `config.js`; setting both keys throws (E879). Because the
proxy ceiling (10 MB) sat **below** the API guard `MAX_TOTAL_BYTES` (25 MiB,
`apps/api/narrare/importing/constants.py`), bodies legal per the API contract
were truncated by the proxy.

**Fix (amended into the Decision):** `packages/web/next.config.ts` gains

```ts
experimental: {
  proxyClientMaxBodySize: "30mb",
},
```

**Coupling rule (binding):** `experimental.proxyClientMaxBodySize` MUST stay
≥ `MAX_TOTAL_BYTES` (25 MiB) + multipart envelope allowance (~1 MiB for
boundaries, per-part headers, and the commit-phase `adjustments` JSON — real
worst case ≈ 100 KiB; floor: **26 MiB**). A regression test in `packages/web`
imports the composed next config and asserts the parsed value is ≥ 26 MiB
(27,262,976 bytes). Whenever either constant changes, the other MUST be
reviewed in the same change (see Review Trigger).

**Value/format evidence (installed `next@16.3.6`):** the key lives in
`ExperimentalConfig` (`dist/server/config-shared.d.ts:1137`) — it must be
nested under `experimental` (top-level placement is a TypeScript error; the
`NextConfig` interface does not declare it). The value type is `SizeLimit`
(`dist/types.d.ts:51`): either a `number` (bytes) or a template string with a
size suffix (string format is the documented recommendation; units
`b`/`kb`/`mb`/`gb` — installed doc page
`dist/docs/01-app/03-api-reference/05-config/01-next-config-js/proxyClientMaxBodySize.md`).
`'30mb'` = 31,457,280 bytes ≈ 120 % of the 25 MiB guard. The same key governs
`next dev` and the standalone production server, so one value covers both.

**No interaction with Q-020:** that workaround lives under
`outputFileTracingIncludes` (build-time output tracing);
`proxyClientMaxBodySize` lives under `experimental` (runtime request-body
buffering). Different mechanisms, different subtrees — no conflict, and
removing the Q-020 block later will not affect this key.

---

## Review Trigger

- [ ] When `MAX_TOTAL_BYTES` (`apps/api/narrare/importing/constants.py`) or
      `experimental.proxyClientMaxBodySize`
      (`packages/web/next.config.ts`) changes: re-align the other side of the
      coupling rule — proxy cap ≥ API total guard + 1 MiB envelope (floor
      26 MiB), pinned by the `packages/web` regression test
      (Post-implementation Amendment, 2026-10-02).
- [ ] When the DOCX follow-up slice is picked up (pandoc conversion reuses
      this module pair; revisit guardrail sizes for DOCX weight).
- [ ] When a multi-user / hosted deployment is pursued (guardrails + stateless
      double-upload may need the staging design of Option C).
- [ ] When import is used for > ~500-chapter manuscripts (position int and
      preview payload size re-check).
