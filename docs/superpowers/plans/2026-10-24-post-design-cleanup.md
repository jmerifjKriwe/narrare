# Post-Design Cleanup Implementation Plan (the parked minors)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retire the parked minor findings whose triggers have fired — every item is pre-decided with a named owner from the phase reviews; nothing new enters, nothing beyond the list gets fixed.

**Architecture:** Four surgical tasks along file-ownership lines (generator+writing routes; knowledge panels; writing editor carries; backend/test pins). Items whose triggers have NOT fired (JobStatus result copy, fake marker vocabulary — both owed to the second job kind) stay parked and are out of scope here.

**Tech Stack:** as landed (phases 1–6).
**Spec:** `docs/superpowers/specs/2026-10-22-frontend-design.md` (context; this plan's authority is the parked-findings ledger `mem_1792828089112` + the phase ledgers).
**Base:** branch `frontend-foundation` @ 99dffc49. Execute on a new branch `post-design-cleanup` from it.

## Global Constraints

- Pre-decided scope ONLY: the parked list below. Anything else found en route gets parked in the ledger, not fixed (anti-goal: scope creep into a cleanup plan).
- English everywhere; user-visible text only via all three catalogs together (de du-form).
- All standing contracts: tolerant validateSearch, function-form writes, dockRoutes conventions, RAC only in `web/ui/`, ghost seam, at-least-once jobs.
- E2E real stack; `assert_accessible(page)` ends every new/changed flow; editor component tests zero mocks.
- Conventional commits; `feat`/`fix` carry a real `User-visible:` line; `--no-verify` forbidden; `just` recipes only; generate stays drift-free.

## Review Focus

1. **Esc forwarding with `code` must not double-fire** — the window witness sees exactly one event per physical Esc (component test).
2. **Ghost-swap announcement fires once per supersede**, never per delta (component test with two offers).
3. **Entities error state distinguishes outage from emptiness** — loading/empty/error are three visible states; an outage never reads as „Noch keine Entitäten" (E2E drives a real outage via `stack.stop_api()`).
4. **Duplicate dock paths fail generate loudly** — two same-path docks → `SystemExit` naming both (generator test).
5. **ChatPanel abort leaves no zombie updates** — closing the dock mid-stream issues no further state writes (component or E2E assertion).

---

### Task 1: Generator + writing routes — fired triggers

**Files:**
- Modify: `scripts/generate_capabilities.py` (duplicate-path guard ACROSS capabilities in `scan_docks` — two docks resolving to the same path → `SystemExit` naming both capabilities; test via direct invocation like the existing guard tests)
- Modify: `app/capabilities/writing/web/routes.tsx` (drop the inert `dock` key from `validateSearch` output entirely — parse stays tolerant, output never carries it; update the adjacent comment)
- Modify: `app/capabilities/chat/e2e/test_chat_e2e.py` (re-add the mid-test dock-route assertion in the rail/focus test: after the Esc step, URL `endswith("/chat")` — the ride-along pin)

**Interfaces:** none beyond the existing conventions.

- [ ] **Step 1: Failing tests first** — generator duplicate-path test (red: guard absent); chat e2e assertion (red against current). Run red.
- [ ] **Step 2: Implement** both changes.
- [ ] **Step 3: Green** — generator tests, full `just test-e2e` (URLs must stay clean: no `dock=` anywhere the suite produces), typecheck, build, generate drift-free.
- [ ] **Step 4: Commit**

```
fix(web): loud duplicate-dock guard; the dock key leaves the URL

Two docks resolving to the same path now stop generation naming both
capabilities. The dock search param is inert in output — parsing
stays tolerant, nothing writes it, and the suite's URLs carry no
dock= at all. The rail/focus test re-pins the dock route's survival
across focus stepping.

User-visible: none.
```

### Task 2: Knowledge panels — honest error states + keyboard review

**Files:**
- Modify: `app/capabilities/knowledge/web/EntitiesPanel.tsx` (three states: loading, empty, error — error names the outage like `novels.errorLoad` does, new key `knowledge.errorLoad` ×3)
- Modify: `app/capabilities/knowledge/web/ExtractionPanel.tsx` (a failed/unanswered job poll shows an error state with a working retry — the trigger re-opens instead of locking; reuses the same error key family)
- Modify: `web/lib/query.ts` (only if the retry needs a query option change — `refetchOnWindowFocus` alone is not the fix; make the error path explicit)
- Modify: `app/capabilities/knowledge/e2e/test_knowledge_dock_e2e.py` (outage test: `stack.stop_api()` → error text visible, NOT the empty-state text → `start_api()` → recovery; keyboard-only review variant: open dock, extract, accept AND discard by keyboard alone)
- Modify: `i18n/{en,de,fr}.json` (new keys ×3)

- [ ] **Step 1: Failing E2E first** (outage distinguishes from empty; keyboard review flow). Run red.
- [ ] **Step 2: Implement** the three-state panels + retry.
- [ ] **Step 3: Green** — knowledge E2E module, full suite, typecheck, build.
- [ ] **Step 4: Commit**

```
fix(knowledge): panels name outages, and review works keyboard-only

An unreachable service reads as an outage, never as an empty list;
a failed job poll offers a retry instead of a locked button. The
review flow is pinned end-to-end without a mouse.

User-visible: errors in the Wissen dock are named and recoverable;
accept and discard work from the keyboard.
```

### Task 3: Writing editor carries — the four parked items

**Files:**
- Modify: `app/capabilities/writing/web/ghostText.ts` (the forwarded Esc carries `code`/`keyCode` mirroring the physical key)
- Modify: `app/capabilities/writing/web/ChapterEditor.tsx` + `web/lib/announce.ts` context (a superseding offer/stream replacing a pending ghost announces `editor.ghostReplaced` — once per supersede, never per delta; a failed stream announces `editor.ghostFailed` instead of the discard copy)
- Modify: `app/capabilities/chat/web/ChatPanel.tsx` (AbortController: closing the dock/unmounting the panel aborts the in-flight ask; no state writes after unmount)
- Modify: `app/capabilities/writing/web/ChapterEditor.test.tsx` (witness: one window event per Esc; swap-announcement once per supersede)
- Modify: `i18n/{en,de,fr}.json` (`editor.ghostReplaced`, `editor.ghostFailed` ×3)

- [ ] **Step 1: Failing component tests first** (Esc code field + single window event; replaced-announce once; failed-stream copy distinct). Run red.
- [ ] **Step 2: Implement** the four items.
- [ ] **Step 3: Green** — component tests, full suite (the continuation E2E's announcements may need copy updates — in scope for this item), typecheck, build.
- [ ] **Step 4: Commit**

```
fix(writing): honest ghost announcements and a clean chat abort

A superseded suggestion announces its replacement once, a failed
stream no longer claims the user discarded it, the forwarded Esc
carries its code for future listeners, and closing the chat dock
aborts the in-flight answer instead of writing into a dead panel.

User-visible: screen readers hear what actually happened; closing
the dock mid-answer leaves no half-written conversation.
```

### Task 4: Backend/test pins — the small contracts

**Files:**
- Modify: `app/capabilities/knowledge/jobs.py` (`parse_entities`: name length ≤ 200 pre-validated → `MalformedAnswerError`, not a DB `DataError`)
- Modify: `app/capabilities/knowledge/tests/test_extraction.py` (empty-array answer pin: valid `[]` → done, `{"suggestions": 0}`, zero rows; helpers assert the 202 on enqueue; progress-scale pin: after a done extraction job, `0 ≤ progress ≤ 100` and specifically `100` — the cross-layer anchor for JobStatus's ÷100)
- Modify: `app/kernel/tests/test_jobs.py` (one comment on the claim-exclusivity test stating it proves exclusivity, not skip-vs-wait — no code change)

- [ ] **Step 1: Failing tests first** (length validation; empty-array; 202-assert; progress pin). Run red.
- [ ] **Step 2: Implement** (the pins and the one-line length check).
- [ ] **Step 3: Green** — knowledge + kernel tests, full suite.
- [ ] **Step 4: Commit**

```
test(knowledge): pin the small contracts around extraction

Name length is validated on the contract path (not the DB's);
an empty entity array is pinned as a valid outcome; the helpers
assert the enqueue 202; a done job's progress is pinned at 100 —
the cross-layer anchor for the UI's percent scale.

User-visible: none.
```

---

## Self-review notes

Scope = the parked ledger exactly: T1 items 1–3 (fired triggers), T2 items 1–2 + keyboard consistency note + the fix-wave poll-lock edge, T3 items 1–4 (writing carries), T4 items 1–5 (pins + comment). Deliberately OUT (triggers not fired): JobStatus result copy, fake marker vocabulary (both owed to the second job kind — parked stays). Deliberately OUT (product, not craft): dock search box, manual entity CRUD — they belong to the merit rounds. No new architecture; every change touches files its owner named.
