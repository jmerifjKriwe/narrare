# Frontend Surfaces Implementation Plan (spec §6, phases 3–4)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The book-centric start page (continue-hero over a bookshelf, new-book metadata dialog) and the workbench workspace (chapter rail beside the editor, panel state in the URL, progressive focus) — spec §5.7 and §5.3.

**Architecture:** The backend gains novel metadata (`genre`, `blurb`) and last-touched timestamps (`updated_at` on novels, bumped by chapter writes) in the same phase that consumes them. The frontend adopts TanStack Query for the novels list (the §5.10 invalidation convention starts here), and the `ui/` React-Aria layer lands with its first real consumer (the new-book dialog). The workspace moves chapters from a stacked list to a collapsible rail beside the editor; focus deepens in steps driven by URL state. The dock and its child-route composition are **phase 5** and are not built here.

**Tech Stack:** as phase 1–2 (Vite SPA, React 19, TanStack Router + Query, TipTap, Tailwind tokens, pytest + Playwright) + `react-aria-components` (first use).

**Spec:** `docs/superpowers/specs/2026-10-22-frontend-design.md` — §5.3, §5.7, §5.10, §5.11, §6 phases 3–4. Executor reads both.

**Base:** branch `frontend-foundation` (phases 1–2 landed there). Execute on a new branch from it.

## Global Constraints

- English in code, comments, tests, commit messages. User-visible text only through `i18n/{en,de,fr}.json`, all three files change together; a missing key is a build error.
- Capabilities never import capabilities; capabilities import the shell via `@shell/*`; the shell's UI primitives live in `web/ui/` and are the only RAC import point.
- Capability route contract (controller-ruled in phases 1–2): `app/capabilities/<id>/web/routes.tsx` exports `routes = […] as const`; no `Route[]` annotation (it poisons inference).
- No migrations: schema changes land in `app/kernel/contracts/models.py`; the database is recreated (`db-init` / fresh E2E stack database).
- E2E = real UI, real API, real Postgres; the only fake is the LLM/embeddings vendor. `assert_accessible(page)` ends every flow, new tests included.
- E2E specs of behavior-changing steps are rewritten in scope (the suite reflects the shipped behavior — that is not a regression).
- Autosave contract preserved: typed text survives reload, chapter switch, and panel-state changes; no save button.
- Generated client only (`just generate` after schema changes); generated files keep the DO-NOT-EDIT header.
- No new scripts/gates/hooks; conventional commits; `feat`/`fix` carry a real `User-visible:` line; `--no-verify` forbidden; `just` recipes only.
- **Carry-forward from phases 1–2, binding here:** settings query gets `refetchOnWindowFocus: false` (Task 2); the locale PATCH invalidates `["settings"]` (Task 2); `@source` narrows to `"../app/capabilities/*/web"` (Task 3); the in-page nav paragraph on `/` is deleted with the index rework (Task 3); the skip-link's pre-applied ring gets its one-line comment when TopBar is next touched (Task 4).

## Review Focus

1. **Dialog-mediated creation breaks the existing selector flow** (`Titel` + `Anlegen` now inside a dialog) — pinned by the rewritten `test_novel_created_in_browser_survives_reload` (Task 3, red-first against the old page).
2. **`updated_at` drift: a chapter write must bump the parent novel's `updated_at`** (the hero's "last touched" must be true) — pinned by the service test in Task 1.
3. **URL panel state vs. browser back/forward** (stale rail state after back) — pinned by the back-button assertion in Task 4.
4. **Focus mode must not trap the keyboard** (F9 → chrome-free → Tab/Esc must still work and escape) — pinned by the keyboard-only focus cycle in Task 5, with axe on the chrome-free view.
5. **Dialog accessibility** (focus trap, restore to opener, announcement) — pinned by RAC Dialog + axe-on-open-dialog and keyboard-open assertions in Task 3.

---

### Task 1: Backend — novel metadata and last-touched timestamps

**Files:**
- Modify: `app/kernel/contracts/models.py:27-47` (Novel gains `genre: Mapped[str | None] = mapped_column(String(80))`, `blurb: Mapped[str | None] = mapped_column(Text)`, `updated_at: Mapped[datetime]` with `default=utc-now, onupdate=utc-now`; Chapter gains the same `updated_at`)
- Modify: `app/capabilities/writing/schemas.py` (`NovelCreate` accepts optional `genre`/`blurb`; `NovelRead` returns `genre`/`blurb`/`updated_at`; `ChapterRead` returns `updated_at`)
- Modify: `app/capabilities/writing/repository.py` (chapter create/update also bumps the parent novel row's `updated_at` — the ORM `onupdate` covers the chapter row, not the parent)
- Modify: `app/capabilities/writing/service.py` only where it maps fields (pass-through)
- Test: `app/capabilities/writing/tests/test_novels.py`, `app_chapters.py` additions

**Interfaces:**
- Produces: `NovelRead = { id, title, genre: str | null, blurb: str | null, created_at, updated_at }`; `ChapterRead = { …, updated_at }` — the shapes Tasks 2–4 consume via the generated client (`just generate` refreshes `web/lib/api/schema.d.ts` and `openapi.json`).

- [ ] **Step 1: Write the failing tests** — novel create persists `genre`/`blurb` and returns `updated_at`; chapter body update advances the parent novel's `updated_at` (create → read `updated_at`, edit chapter, re-read, assert strictly greater).
- [ ] **Step 2: Run red** — `just test-file app/capabilities/writing/tests/test_novels.py` — FAIL (fields unknown).
- [ ] **Step 3: Implement** models + schemas + repository bump; recreate the dev DB (`just db-reset`); regenerate the client (`just generate`).
- [ ] **Step 4: Green** — the two writing test files pass; `just test-e2e` stays green (schema additive).
- [ ] **Step 5: Commit**

```
feat(writing): novel metadata and last-touched timestamps

Novels carry genre and blurb; novels and chapters expose updated_at,
and chapter writes bump the parent novel's. The start page's
continue-hero and shelf (next task) read them.

User-visible: a novel records its genre, blurb and when it was last
written in; editing a chapter counts as writing.
```

### Task 2: Novels through TanStack Query + settings-query carries

**Files:**
- Modify: `web/lib/query.ts` (add `useNovelsQuery(): UseQueryResult<Novel[]>` on key `["novels"]`, and `useCreateNovel(): UseMutationResult` that invalidates `["novels"]`; settings query gains `refetchOnWindowFocus: false` with a comment naming the outage-refetch trap)
- Modify: `web/components/TopBar.tsx:30-40` (successful locale PATCH → `queryClient.invalidateQueries({ queryKey: ["settings"] })` — the §5.10 convention's first mutation)
- Modify: `app/capabilities/writing/web/NovelsPage.tsx` (list load via `useNovelsQuery`; create via `useCreateNovel`; behavior identical)

**Interfaces:**
- Consumes: `NovelRead` shape from Task 1.
- Produces: `useNovelsQuery` / `useCreateNovel` for Task 3's shelf and dialog.

- [ ] **Step 1: Migrate `NovelsPage`'s load and create to the hooks** (no visual change).
- [ ] **Step 2: Verify** — `just typecheck && just test-e2e` green (the locale tests cover the PATCH path; selectors unchanged).
- [ ] **Step 3: Commit**

```
refactor(web): novels list through TanStack Query; settings cache honest

The ["novels"] key and its invalidation convention start here (spec
5.10). Settings query stops refetching on window focus: an outage
refetch answered {locale: null}, erasing the adopted locale (parked
finding from the phase-1/2 final review). The locale PATCH now
invalidates ["settings"] so cache and row cannot disagree.

User-visible: none.
```

### Task 3: Start page — hero, shelf, new-book dialog (`ui/` layer lands)

**Files:**
- Create: `web/ui/Dialog.tsx`, `web/ui/TextField.tsx` (RAC wrappers styled with the shell tokens; `react-aria-components` enters as a web dependency)
- Modify: `app/capabilities/writing/web/NovelsPage.tsx` (rewrite: "Mach weiter" hero over the last-touched novel from `useNovelsQuery`; shelf cards with title, genre, relative `updated_at`; "Neues Buch" opens the dialog — Titel/Genre/Klappentext → `useCreateNovel`; the in-page nav paragraph is deleted)
- Modify: `web/globals.css` (narrow `@source` to `"../app/capabilities/*/web"`)
- Modify: `i18n/{en,de,fr}.json` (keys: `novels.new`, `novels.genre`, `novels.blurb`, `novels.continue`, `novels.lastTouched`, `novels.createBook` — values set per catalog)
- Test: `app/capabilities/writing/e2e/test_novels_e2e.py` (rewrite `test_novel_created_in_browser_survives_reload` for the dialog; add hero + genre + dialog-a11y tests)

**Interfaces:**
- Consumes: `useNovelsQuery`, `useCreateNovel` (Task 2), `NovelRead` (Task 1).
- Produces: `web/ui/Dialog.tsx` exporting `Dialog({ title, triggerLabel, children })` and `web/ui/TextField.tsx` exporting `TextField({ label, value, onChange })` — the shapes later surfaces reuse.

- [ ] **Step 1: Write the failing E2E** — dialog-mediated creation (open "Neues Buch", fill Titel/Genre, submit, shelf card shows title + genre, reload survives); hero shows the last-touched novel's title; `assert_accessible` runs with the dialog open; keyboard-only open (Tab to trigger, Enter).
- [ ] **Step 2: Run red** against the current page (no dialog, no hero, no genre).
- [ ] **Step 3: Implement** `ui/` wrappers, page rewrite, tokens/globals carry, catalogs; regenerate nothing (client already current).
- [ ] **Step 4: Green** — full `just test-e2e` (the rewritten novels test included), `just typecheck && just build`.
- [ ] **Step 5: Commit**

```
feat(web): book-centric start page — hero, shelf, new-book dialog

The web/ui React-Aria layer lands with its first consumers (Dialog,
TextField). The continue-hero names the last-touched novel; the shelf
shows genre and last-touched; new books take metadata up front. The
in-page nav paragraph goes: the top bar owns navigation.

User-visible: the start page becomes a bookshelf — continue where you
left off, see your books, create one with genre and blurb.
```

### Task 4: Workspace — chapter rail beside the editor, panel state in the URL

**Files:**
- Modify: `app/capabilities/writing/web/NovelPage.tsx` (layout: collapsible `aside` rail (chapter list, "Neues Kapitel") beside the editor; state in URL search params)
- Modify: `app/capabilities/writing/web/routes.tsx` (novel route gains `validateSearch: (s) => ({ rail: s.rail === "0" ? false : true })`)
- Modify: `web/components/TopBar.tsx` (one-line comment on the skip-link's pre-applied ring — parked carry)
- Modify: `i18n/{en,de,fr}.json` (`workspace.collapseRail`, `workspace.expandRail`)
- Test: `app/capabilities/writing/e2e/test_chapters_e2e.py` (add: rail and editor simultaneously visible without scrolling; `?rail=0` renders collapsed; back-button restores; typed text survives a chapter switch)

**Interfaces:**
- Consumes: `ChapterRead.updated_at` (Task 1) for the active-chapter restore (latest-touched chapter opens first).
- Produces: the URL panel-state convention `?rail=0|1` that phase 5's dock state (`?dock=…`) extends.

- [ ] **Step 1: Write the failing E2E** (rail beside editor; `?rail=0`; back-button; chapter-switch autosave).
- [ ] **Step 2: Run red.**
- [ ] **Step 3: Implement** the rail layout, search-param state via `useSearch`/`navigate`, latest-chapter restore.
- [ ] **Step 4: Green** — full suite, typecheck, build.
- [ ] **Step 5: Commit**

```
feat(web): workbench rail beside the editor, panel state in the URL

Chapters sit in a collapsible rail next to the text instead of above
it; the collapse lives in the URL so a workspace state is linkable and
the back button undoes it. The latest-touched chapter opens first.

User-visible: writing no longer scrolls past the chapter list; a
collapsed rail is a shareable URL state.
```

### Task 5: Progressive focus and the keyboard contract

**Files:**
- Modify: `app/capabilities/writing/web/NovelPage.tsx` (focus steps: workbench → panels hidden → chrome-free; F9 deepens, Esc restores stepwise; state in `focus=0|1|2` search param; the shell top bar hides at `focus=2` via a body-level attribute the shell reads)
- Modify: `app/capabilities/writing/web/routes.tsx` (`validateSearch` gains `focus`)
- Modify: `i18n/{en,de,fr}.json` (`workspace.focus`, `workspace.unfocus`)
- Test: `app/capabilities/writing/e2e/test_focus_e2e.py` (new: keyboard-only cycle — open novel, type, F9 → rail+panels gone, F9 → chrome-free, Tab still moves within the page, Esc → restored stepwise; `assert_accessible` at each depth; `?focus=2` renders chrome-free directly)

**Interfaces:**
- Consumes: URL panel state (Task 4).
- Produces: the focus contract (`focus=0|1|2`, F9/Esc) that phase 5's ghost-text Esc layering sits **above** (Esc discards a suggestion first, then steps focus — layered Esc, builder settles the exact stacking).

- [ ] **Step 1: Write the failing E2E** (the keyboard-only cycle above).
- [ ] **Step 2: Run red.**
- [ ] **Step 3: Implement** the step machine; no layout thrash (transitions are visibility, not reflow).
- [ ] **Step 4: Green** — full suite, typecheck, build.
- [ ] **Step 5: Commit**

```
feat(web): progressive focus mode with a keyboard contract

F9 collapses in steps — panels first, then all chrome — until only the
text remains; Esc walks it back. The depth lives in the URL. Mouse
never required.

User-visible: a distraction-free writing mode that deepens and
releases with one key each.
```

---

## Self-review notes

Spec coverage: §5.7 start page → Tasks 1–3 (backend fields + hero/shelf/dialog); §5.3 workspace → Tasks 4–5 (rail, URL state, progressive focus, keyboard contract); §5.10 invalidation convention starts (Task 2); `ui/` layer lands with real consumers (Task 3), spacing/type-scale tokens deferred again **deliberately**: Tailwind 4's utility scale still covers every surface here; a parallel token set without a consumer would be the anti-goal the spec bans. First genuine consumer expected in phase 5 (editor toolbar) — recorded so the deferral is a decision, not an omission. Dock + child-route composition (design flag from the phase-1/2 final review: parent-by-route-id vs shell-owned layout route) is phase-5 scope; Task 4's route shape (search params, no child routes yet) precludes neither. Autosave untouched in behavior, only re-verified (Tasks 4). All five phase-1/2 carries placed (see Global Constraints). Proportion: five tasks, each independently rejectable, each landing with the full suite green.
