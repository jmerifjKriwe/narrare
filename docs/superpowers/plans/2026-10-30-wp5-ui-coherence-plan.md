# WP5 — UI Coherence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One coherent surface: a settings area with clustered sub-pages, the workspace on Query with honest failure states, chapter and dock selections as URL state, and the ⌘K palette over targets and commands.

**Architecture:** The settings route becomes the generator's second host (like the workspace hosts docks); commands become capability contributions aggregated by a third generated view; the palette is a shell component that navigates and hosts modals but owns no command. Server state moves onto TanStack Query under three failure rules; selections move into URLs, deleting one bus.

**Tech Stack:** FastAPI · TanStack Router/Query · React Aria Components · Vitest/Testing Library · Playwright E2E on the kernel testing stack · `scripts/generate_capabilities.py`.

**Spec:** `docs/superpowers/specs/2026-10-30-wp5-ui-coherence-design.md` (arrives there from `~/.opencode/plan/2026-10-30-wp5-ui-coherence-design.md`; the build session moves it with this plan — move, never copy). The plan argues from the spec; executors read both.

## Global Constraints

- Capabilities never import capabilities; capability → `@shell` is the one allowed direction. Shared UI lives in `web/ui/`; the palette is shell (`web/components/`).
- Generated files are DO-NOT-EDIT: every contract change runs `just generate`, and the generated output is committed in the same commit as the contract that produced it.
- Every new user-visible string ships in en, de and fr in the same commit; `fr` may carry the English string as a placeholder until Task 11.
- TDD: each task writes its failing test first, sees red, implements, sees green. `just check` before every commit; `just test-file <path>` for the Python inner loop; `pnpm --dir web test <name-filter>` for web.
- Conventional commits; `feat`/`fix` carry a real `User-visible:` line. `--no-verify` and force push are forbidden. Nothing is committed before the branch review is green.
- A task stays inside its `Files` list; anything beyond goes back to the coordinator as a ruling, not silently into the diff.
- Findings close from the fix commit that lands them (`Closes #<n>`); nothing found is dropped for being minor.
- E2E is the done gate: `assert_accessible` (axe, WCAG A/AA) on every page a flow visits.

## Review Focus

1. **Unsaved text lost on a URL-driven chapter switch.** Back button, palette jump, rail link — all become `?chapter=` navigations the old blocker ignored. Expected: every navigation while `unsavedStatus` flushes first and confirms only on failure. Pinned by Task 6's E2E (back-button switch inside the debounce) and Task 12's palette variant.
2. **A failed refresh wiping a loaded book.** With data cached, a refetch error must not show `chapters.errorLoad` over text that is on screen. Expected: a quiet note, editor stays. Pinned by Task 5's component test (data + `isError`).
3. **A failed save refetching the server's old text over the retained body.** Expected: invalidation only after a successful save. Pinned by Task 5's component test (`onSaved` fires → invalidate; simulated failure → no invalidation).
4. **The palette searching stale wording after a mid-session language switch.** Expected: search text is built from all three catalogs, so the index is locale-independent. Pinned by Task 9's component test (filter, switch locale via `applyLocale`, filter again).
5. **The viewport gate passing on a squeezed column.** Expected: prose measured as the editor's *content box* (padding excluded), overlays proven by the editor's width not shrinking. Pinned by Task 10's helper and its E2E at 360/768/1024/1280 px.

(Also watched, pinned where it lands: a dead `?chapter=` or `?entity=` link must degrade to the fallback and clean the param, never blank the page — Tasks 6 and 7.)

---

### Task 1: the web pre-commit hooks fire for capability web files

Closes #399. Do this first: every later task commits capability web code.

**Files:**
- Modify: `.pre-commit-config.yaml` (the two `files: ^web/` filters)

**Interfaces:** none.

- [ ] **Step 1: Show the gap** — `pre-commit run web-typecheck --files app/capabilities/prompts/web/PromptsPage.tsx`; expected output says the hook was *skipped* (that is the defect).
- [ ] **Step 2: Fix** — both web hooks (`web-typecheck`, `web-tests`): `files: ^web/` → `files: (^web/|app/capabilities/|i18n/)`. The catalogs and the generated tables are web build inputs; a commit touching them is a web commit.
- [ ] **Step 3: Verify** — the same `pre-commit run` now executes tsc (and vitest for `web-tests`) against the capability file and passes; a `web/`-only file still triggers both (behaviour for the old path unchanged).
- [ ] **Step 4: Commit** — `fix(repo): capability web commits can no longer skip the web hooks`

```
User-visible: none — a repo gate, not a product change; the effect is that
tsc and vitest run on every commit that touches capability web code.
```

---

### Task 2: the generator learns the settings host

**Files:**
- Modify: `scripts/generate_capabilities.py`
- Test: `app/api/test_capability_views.py` (the file that already tests generation)

**Interfaces:**
- Produces: `SettingsScan` dataclass (`host: str | None`, `rows: tuple[SettingsPage, …]` with `SettingsPage(id, path, title_key)`), `scan_settings(sources: dict[str, str]) -> SettingsScan`, `typescript_settings_pages(root: Path) -> str`, and the write-dict entry `"web/lib/generated/settingsPages.ts": typescript_settings_pages(root)`. `typescript_routes` additionally wires `settingsRoutes` factories under the `settingsRoute` host. Contract mirrors the dock scan: exactly one capability exports `settingsRoute` (it must alias a readable `const … = createRoute(` path literal); a capability with `export const settingsRoutes` contributes exactly one row (exactly one `path:` literal before `] as const;`); `title_key` is `{capability}.settingsTitle` by convention; `SystemExit` on two hosts, rows without a host, unreadable paths, duplicate full paths.
- Consumes: the existing `route_sources`, `_workspace_path`/`_dock_path` regex style, `DockScan`/`scan_docks` as the pattern.

- [ ] **Step 1: Write the failing tests** — fixture sources (dicts of `routes.tsx` text, as the dock tests build them): a host plus one contributor scans to one row with full path `/settings/prompts` and `title_key "prompts.settingsTitle"`; two hosts → `SystemExit`; a contributor without a host → `SystemExit`; `typescript_settings_pages` emits the rows as an `as const satisfies` table shaped like `docks.ts`; empty sources → empty registry and byte-identical `typescript_routes` output to today (no settings block when nothing contributes).
- [ ] **Step 2: Run red** — `just test-file app/api/test_capability_views.py`.
- [ ] **Step 3: Implement** the scan, the view, and the `typescript_routes` wiring (imports `settingsRoutes as {capability}Settings`, consts calling them with `settingsRoute`, spread after the settings route — the same parent-before-child note the dock block carries). Mirror `_dock_path`'s one-literal guard as `_settings_path`.
- [ ] **Step 4: Run green**; then `just generate` on the untouched repo: `git diff` must be **empty** (settings exports nothing yet — the no-contributor output is today's output).
- [ ] **Step 5: Commit** — `feat(tooling): a second route host — settings pages parent under settings`

```
User-visible: none — generator groundwork; the design doc's three statements
for this skeleton point are its governance record.
```

---

### Task 3: the settings area — layout, hub, language and provider pages

**Files:**
- Modify: `app/capabilities/settings/web/routes.tsx` (layout + index + two child routes)
- Modify: `app/capabilities/settings/web/SettingsPage.tsx` → becomes the hub
- Create: `app/capabilities/settings/web/SettingsLayout.tsx`, `LanguagePage.tsx`, `ProviderPage.tsx`
- Modify: `i18n/en.json`, `i18n/de.json`, `i18n/fr.json`
- Test: `app/capabilities/settings/web/SettingsHub.test.tsx`
- Modify: `app/capabilities/settings/e2e/` (every `page.goto` that targeted the old one-page `/settings` provider surface now targets `/settings/provider`)

**Interfaces:**
- Produces: `export const settingsRoute` in settings' `routes.tsx` (aliasing a `const settingsLayoutRoute = createRoute(…)` at `path: "/settings"`, component `SettingsLayout`), child routes `languageRoute` (`path: "language"`), `providerRoute` (`path: "provider"`), and an index child rendering the hub. Later tasks rely on `/settings/language` and `/settings/provider` existing and on `settingsRoute` being importable by the generated table.
- Consumes: Task 2's generated `web/lib/generated/settingsPages.ts` (empty for now — the hub still renders it, so Task 4 needs no hub edit).

- [ ] **Step 1: Write the failing component test** — the hub renders a card per cluster with its description and a link to each sub-page; the layout's nav lists the same destinations; links resolve against the real generated route table (mirror `ProvidersPanel.test.tsx`'s router setup).
- [ ] **Step 2: Run red** — `pnpm --dir web test SettingsHub`.
- [ ] **Step 3: Implement.** `SettingsLayout`: cluster nav (its own two clusters + every `settingsPages` row) and `<Outlet/>`. The hub is today's page content reduced to cards; `LanguagePage` wraps the reused `LanguageSwitcher`, `ProviderPage` wraps `ProvidersPanel`. New keys: `settings.clusterLanguage`, `settings.clusterProvider` (+ one-line descriptions each) in all three catalogs. The gear's `to="/settings"` is unchanged — it now lands on the hub.
- [ ] **Step 4: Run green** (component test; `just generate`; `just check`). Update the settings E2E paths and run it green.
- [ ] **Step 5: Commit** — `feat(settings): the settings area — a hub with clustered sub-pages`

```
User-visible: /settings is now an area: a hub listing Sprache and Provider,
each a page of its own; contributed pages join the hub as they appear.
```

---

### Task 4: the prompts page moves into the settings area

Closes #400.

**Files:**
- Modify: `app/capabilities/prompts/web/routes.tsx` (top-level route → `settingsRoutes` factory row)
- Modify: `app/capabilities/prompts/capability.yaml` (`path: /settings/prompts`, `nav: false`)
- Modify: `app/capabilities/prompts/web/PromptsPage.tsx` + `PromptsPage.test.tsx` (#400 only)
- Modify: `i18n/en.json`, `i18n/de.json`, `i18n/fr.json`
- Modify: `app/capabilities/prompts/e2e/test_prompts_e2e.py` (the three `/prompts` pins: `page.goto`/`to_have_url` around lines 190, 262, 324; the top-bar Prompts-link assertion)

**Interfaces:**
- Consumes: Task 2's `settingsRoutes` contract; Task 3's hub (the contributed row appears via `settingsPages` with no hub edit).
- Produces: `/settings/prompts` as the prompts page's only address; `prompts.settingsTitle` key in all three catalogs.

- [ ] **Step 1: Write the failing tests** — component: the hub lists the Prompts cluster (from the generated registry, not a hand row); PromptsPage: a failed list load offers a page-level retry (not a dead loading state) and a failed novels read gets its own message (not the list's). E2E: adjust the three URL pins to `/settings/prompts`; drop or replace the top-bar Prompts-link assertion (the link is gone with `nav: false`).
- [ ] **Step 2: Run red.**
- [ ] **Step 3: Implement** — `export const settingsRoutes = [<Parent extends AnyRoute>(parent: Parent) => createRoute({ getParentRoute: () => parent, path: "prompts", component: PromptsPage })] as const;` replacing the top-level route export; `capability.yaml` as above; `just generate` (registry row + routes wiring) committed together; #400: page-level retry on the list error, distinct copy keyed `prompts.errorLoadNovels` for the novels read.
- [ ] **Step 4: Run green** — component tests, prompts E2E, `just check`.
- [ ] **Step 5: Commit** — `feat(prompts): the prompts page lives in the settings area`

```
User-visible: Prompts is a cluster in the settings area at /settings/prompts;
its top-bar link is gone (the hub and the palette are the doors), a failed
list load has a way back, and the novels failure says what failed. Closes #400.
```

---

### Task 5: the workspace reads through Query

Closes #336, #318; folds the §11 NovelsPage first-paint row.

**Files:**
- Modify: `web/lib/query.ts` (+ `query.test.ts`): `useNovelQuery`, `useChaptersQuery`
- Modify: `app/capabilities/writing/web/NovelPage.tsx`
- Modify: `app/capabilities/writing/web/NovelsPage.tsx` (skeleton first paint)
- Modify: `i18n/en.json`, `i18n/de.json`, `i18n/fr.json`
- Test: `app/capabilities/writing/web/NovelPage.test.tsx` (new; router-wrapped, mirror `__root.test.tsx`'s setup)

**Interfaces:**
- Produces: `useNovelQuery(novelId: string): UseQueryResult<Novel>` (key `["novels", novelId]`), `useChaptersQuery(novelId: string): UseQueryResult<Chapter[]>` (key `["chapters", novelId]`); both throw on `!response.ok` so a 404/500 is `isError`, mirroring the existing hooks' `queryFn` style.
- Consumes: `useAutosave`'s `onSaved(chapterId, body)` (fires only on success) and `unsavedStatus`.

The state contract (spec §"Workspace on Query"):

| Cache state | UI |
|---|---|
| no data, fetching | `chapters.loading` |
| no data, error | `chapters.errorLoad` + retry (`refetch`) |
| data, error | new key `chapters.refreshFailed`, quiet note, editor and rail stay, retry |
| data | today's loaded workbench |

- [ ] **Step 1: Write the failing tests.** Hooks (mirror `query.test.ts`'s client mock): 200 → data; 404 → `isError`, no data. Component: (a) data + `isError` renders the editor *and* the quiet note, not `errorLoad`; (b) `onSaved` invalidates `["chapters", id]` and `["novels", id]` (spy on `queryClient.invalidateQueries`); (c) a failed save path never calls invalidate (the hook's contract already gates this — the test pins the wiring); (d) NovelsPage shows skeletons while `isPending`, never a white first paint.
- [ ] **Step 2: Run red** — `pnpm --dir web test query NovelPage NovelsPage`.
- [ ] **Step 3: Implement.** Delete `load`/`pending`/`failed` and the parallel `Promise.all`; derive the four states per the table; the leave guard stays keyed on `unsavedStatus` alone; chapter create invalidates `["chapters", novelId]`. While in `query.ts`, fix the comment #318 names (it contradicts the client it documents). The §11 hero note: the hub-hero keeps showing the latest novel (its repetition of row 1 *is* the continue affordance — say so in the commit body); the fix is the skeleton, not a redesign.
- [ ] **Step 4: Run green** — component + hook tests, `just check`, writing E2E (`test_chapters_e2e.py`, `test_novels_e2e.py`) unchanged and green. The ChapterEditor load flake (#353) is watched here of all places: if it recurs while load timing changes, capture the evidence in the task report — it stays an issue unless this task's work removes it, and then it closes with evidence.
- [ ] **Step 5: Commit** — `feat(writing): the workspace reads through Query, outages keep their names`

```
User-visible: a failed refresh no longer disguises itself as an unloaded book;
the shelf's first paint is a skeleton, not a white flash. Closes #336, #318.
```

---

### Task 6: the active chapter is URL state, every switch passes the flush gate

**Files:**
- Modify: `app/capabilities/writing/web/routes.tsx` (`validateSearch` gains `chapter`)
- Modify: `app/capabilities/writing/web/NovelPage.tsx`
- Modify: `app/capabilities/knowledge/web/ExtractionPanel.tsx` (reads the param)
- Delete: `web/lib/activeChapter.ts`
- Test: `app/capabilities/writing/e2e/test_chapters_e2e.py` (additions)

**Interfaces:**
- Produces: `/novels/$id?chapter=<uuid>` as the selection's address; `validateSearch` output type gains `chapter?: string`.
- Consumes: `useAutosave`'s `flush` (exposed return value) and `SaveStatus`; the delete removes `publishActiveChapter`/`subscribeActiveChapter`/`activeChapter` — `ExtractionPanel` switches to `useSearch({ from: "/novels/$id" })`.

- [ ] **Step 1: Write the failing E2E additions** — (1) select a chapter in the rail within the 800 ms debounce via the browser back button (select A → select B → `page.goBack()`): the body flushes, chapter A shows A's saved text (today's flush-on-switch, now through history); (2) `?chapter=<unknown-uuid>` degrades to the last-touched chapter and the param is cleaned (`replace`, URL assertions); (3) reload with no param still opens the last-touched chapter and writes nothing (the existing reload assertion keeps its meaning).
- [ ] **Step 2: Run red.**
- [ ] **Step 3: Implement.** Selection = `navigate({ to: ".", search: (prev) => ({ ...prev, chapter: id }) })` (push). `useBlocker` widened: block **any** navigation while `unsavedStatus(status)`, handler awaits `flush()`, `window.confirm(t("save.confirmLeave"))` only on a failed outcome — today's `leave()` semantics, absorbed by the blocker so rail links, history, and (later) palette jumps all pass it; delete `leave()`. Absent param → today's choice (latest by `updated_at`), nothing written; unknown id → same fallback plus a `replace` navigation cleaning the param. Delete `web/lib/activeChapter.ts` and its imports.
- [ ] **Step 4: Run green** — the additions, the full chapters E2E, `just check` (the deleted module must leave no import behind).
- [ ] **Step 5: Commit** — `feat(writing): the active chapter is URL state, every switch passes the flush gate`

```
User-visible: chapters have addresses — a chapter link survives reload and
sharing, the back button walks them, and no switch can drop unsaved text.
```

---

### Task 7: the Wissen dock's selected entity is URL state

**Files:**
- Modify: `app/capabilities/knowledge/web/routes.tsx` (the `dockRoutes` factory gains `validateSearch`)
- Modify: `app/capabilities/knowledge/web/EntitiesPanel.tsx` (selection from the param)
- Test: `app/capabilities/knowledge/e2e/test_knowledge_dock_e2e.py` (addition)

**Interfaces:**
- Produces: `/novels/$id/wissen?entity=<uuid>` selecting the panel's entity; the palette (Task 9) deep-links through it.
- Consumes: the parent route's search context (`useSearch({ from: "/novels/$id" })`).

- [ ] **Step 1: Write the failing E2E addition** — goto the dock with `?entity=<id>` of a novel with ≥2 entities: the panel shows that entity's relations, not the default selection; an unknown id selects nothing and cleans the param.
- [ ] **Step 2: Run red.**
- [ ] **Step 3: Implement** — the factory's route gains `validateSearch` accepting `entity` (tolerant, like `rail`); the panel initializes from it and writes with `replace` on selection.
- [ ] **Step 4: Run green** — the addition, the dock E2E, `just check`.
- [ ] **Step 5: Commit** — `feat(knowledge): the dock's selected entity is URL state`

```
User-visible: an entity in the Wissen dock has an address; a link opens the
dock with that entity selected.
```

---

### Task 8: commands are capability contributions

**Files:**
- Create: `web/lib/commands.ts` (types + the all-locale matcher)
- Modify: `scripts/generate_capabilities.py` (+ `app/api/test_capability_views.py`): the commands scan and view
- Create: `app/capabilities/settings/web/commands.ts`, `app/capabilities/prompts/web/commands.ts`, `app/capabilities/knowledge/web/commands.ts`
- Modify: `i18n/en.json`, `i18n/de.json`, `i18n/fr.json`
- Test: `web/lib/commands.test.tsx`

**Interfaces:**
- Produces:
  ```ts
  export type CommandContext = {
    navigate: NavigateFunction;               // @tanstack/react-router
    novelId: string | null;                   // from the active route, else null
    openModal: (load: () => Promise<{ default: ComponentType }>) => void;
  };
  export type Command = {
    id: string; titleKey: MessageKey;
    run: (ctx: CommandContext) => void;
    enabled?: (ctx: CommandContext) => boolean;
    shortcut?: string;
  };
  export function matchesAllLocales(titleKey: MessageKey, query: string): boolean;
  ```
  and the generated `web/lib/generated/commands.ts`: one import per capability owning `web/commands.ts` (`commands as {capability}Commands`), `export const commands = […writing, …settings, …prompts, …knowledge] as const;`. Scan rule: the file's presence is the contract (like `web/routes.tsx`); `titleKey` is compiler-checked against the English catalog via `MessageKey`.
- Consumes: Task 4's `/settings/prompts`; the `docks.ts` path for the Wissen dock.

First rows: settings `open-settings` (navigate `/settings`), prompts `open-prompts` (navigate `/settings/prompts`), knowledge `open-wissen-dock` (navigate `/novels/$id/wissen`, `enabled` only with a `novelId`). Keys `commands.openSettings`, `commands.openPrompts`, `commands.openWissenDock` in all three catalogs.

- [ ] **Step 1: Write the failing tests** — generator: a capability with `web/commands.ts` appears in the generated view, none → empty aggregation (golden, mirroring the docks tests). Web: parametrized over the generated `commands` — ids unique; every `titleKey` exists in **all three** catalogs (walk `catalogs`, never a hand list); `enabled` behaves at both `novelId` states per an expectation table in the test; each `run` navigates (router-wrapped render, location asserted). `matchesAllLocales("commands.openPrompts", "export")` is true in every active locale.
- [ ] **Step 2: Run red.**
- [ ] **Step 3: Implement** — types and matcher (`normalize = (s) => s.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase()` over every catalog's rendering); the generator's `scan_commands`/`typescript_commands` + write-dict entry; the three modules; `just generate` output committed with the contract.
- [ ] **Step 4: Run green** — `just test-file app/api/test_capability_views.py`, `pnpm --dir web test commands`, `just check`.
- [ ] **Step 5: Commit** — `feat(shell): commands are capability contributions, aggregated by the generator`

```
User-visible: none yet — the palette that renders these lands in the next
task; the aggregation and its tests are the deliverable.
```

---

### Task 9: the palette — targets, commands, shortcuts named

Folds the §11 shortcut-hints row.

**Files:**
- Create: `web/components/Palette.tsx` (+ `Palette.test.tsx`)
- Modify: `web/routes/__root.tsx` (mount + the ⌘K/Ctrl+K listener)
- Create: `app/capabilities/writing/web/commands.ts` (new chapter, export novel)
- Modify: `i18n/en.json`, `i18n/de.json`, `i18n/fr.json`

**Interfaces:**
- Consumes: `commands` and `matchesAllLocales` (Task 8), `useChaptersQuery`/`useEntitiesQuery`/`useNovelsQuery`, `docks`, `nav`, the `?entity=` deep link (Task 7), the flush gate (Task 6 — palette jumps are navigations, the blocker catches them).
- Produces: the palette as the app's keyboard surface; `commands.newChapter`, `commands.exportNovel` rows.

- [ ] **Step 1: Write the failing component tests** — ⌘K opens, Esc closes, focus returns to the opener; groups render (Chapters/Entities/Docks & pages/Commands with a novel in the route; Novels replaces the first two without one); typing filters via `matchesAllLocales` and the switch-locale case (filter → `applyLocale` → filter again finds the other language's word); an entity result navigates to the dock with `?entity=`; a command with `openModal` renders the lazily imported dialog (export), `new-chapter` POSTs, invalidates `["chapters", id]`, navigates to the new `?chapter=`; the shortcut-hint row names F9/Esc/⌘K (`workspace.shortcutHints`).
- [ ] **Step 2: Run red** — `pnpm --dir web test Palette`.
- [ ] **Step 3: Implement** — React Aria dialog over `web/ui/` primitives; the modal host lives in the palette (Suspense boundary); writing's `commands.ts` stays data-light: `run` uses `client.POST` + `queryClient.invalidateQueries` + `navigate`, and `openModal(() => import("./InterchangeDialogs").then((m) => ({ default: m.ExportNovelDialog })))`. The new-chapter corner is accepted and named (spec): the POST precedes the gate, a declined navigation leaves an empty chapter in the rail.
- [ ] **Step 4: Run green** — component tests, `just check`.
- [ ] **Step 5: Commit** — `feat(shell): the ⌘K palette — targets, commands, and the shortcuts named`

```
User-visible: ⌘K reaches chapters, entities, docks, pages and commands from
anywhere; the focus shortcuts are named in one place at last.
```

---

### Task 10: below 1024 the panels overlay the editor; the viewport gate measures honestly

**Files:**
- Create: `app/kernel/testing/viewport.py`
- Modify: `app/capabilities/writing/web/NovelPage.tsx` (responsive mounting/classes), `web/globals.css` if tokens need it
- Test: `app/capabilities/writing/e2e/test_viewport_e2e.py`

**Interfaces:**
- Produces:
  ```python
  def assert_page_fits(page, *, prose_selector: str | None = None) -> None
  def assert_overlay(page, *, editor_selector: str, panel_selector: str) -> None
  ```
  `assert_page_fits`: `scrollWidth` ≤ viewport width, and with a `prose_selector` the **content box** (bounding rect minus computed paddings) ≥ 320 px. `assert_overlay`: the panel's rect intersects the editor's, and the editor's width is unchanged by the panel's presence.
- Consumes: the a11y helper's file neighbours and the stack fixtures.

- [ ] **Step 1: Write the failing E2E** — at 360, 768, 1024, 1280 px on `/`, `/novels/$id` (rail open; dock open), `/settings`, `/settings/prompts`: `assert_page_fits` with the editor's prose selector; below 1024 additionally `assert_overlay` for rail and dock. Run it: **red at 360 today** (`scrollWidth 384` measured 2026-10-25) — that red is the defect's baseline, recorded in the task report.
- [ ] **Step 2: Run red** (all four widths, the failures enumerated).
- [ ] **Step 3: Implement** — below 1024 the rail and the dock mount as overlays over the editor (absolute positioning on the existing collapse machinery; no new state — `rail`/`focus` params and dock child routes stay as they are); at 360 the editor's own padding yields a ≥320 px content box.
- [ ] **Step 4: Run green** — the viewport E2E at all four widths; the chapters and dock E2Es unchanged (desktop behaviour identical at ≥1024).
- [ ] **Step 5: Commit** — `fix(web): below 1024 the rail and dock overlay the editor, not squeeze it`

```
User-visible: a narrow window no longer overflows or starves the prose —
the panels cover, the text keeps at least 320 px.
```

---

### Task 11: the French pass

**Files:**
- Modify: `i18n/fr.json`

**Interfaces:** none.

- [ ] **Step 1: Enumerate** — every key whose `fr` value is byte-identical to `en` (`python3 -c` one-liner in the task report): the 14 pre-existing (`app.title`, `novels.genre`, `knowledge.fileLabel`, `chat.questionLabel`, `chat.sources`, …) plus every WP5 placeholder. Classify each: real French differs → translate; true cognate (e.g. `Genre`) → keep, named in the report.
- [ ] **Step 2: Translate** the classified set; `pnpm --dir web test i18n` (key parity, no empty strings) stays green.
- [ ] **Step 3: Verify** — the identical-count drops to the reviewed cognate list; `just check`.
- [ ] **Step 4: Commit** — `feat(i18n): French catches up with the new surfaces`

```
User-visible: the settings area, the palette and every new surface read as
French, not as marked English placeholders.
```

---

### Task 12: the coherence flow end to end (§8.6)

Closes #369 via the axe sweep.

**Files:**
- Create: `app/capabilities/writing/e2e/test_coherence_e2e.py`

**Interfaces:**
- Consumes: the writing E2E stack (`conftest.py`'s module `stack`), `assert_accessible`, the Task 10 viewport helpers, `LlmCall` reads (WP4's prompts E2E pattern), the merge flow (for #369).

- [ ] **Step 1: Write the failing E2E** — one flow, DB-asserted: setup (demo novel) → workspace → entity with a relation → merge two entities (covers #369: `assert_accessible` on the merge hero) → `/settings/provider` (fake profile) → `/settings/prompts` (override `writing.continuation` for the novel) → continuation in the editor: the latest `LlmCall.prompt_text` carries the override and the call used the profile → ⌘K: jump to an entity (dock opens, `?entity=`), run `new-chapter` (rail gains a chapter, `?chapter=` moves) with an unsaved body flushed first → language switch on each new surface (hub, prompts page, palette) renders the new language → `assert_accessible` on **every** page visited → `assert_page_fits` at 360/768/1024/1280 on the visited pages.
- [ ] **Step 2: Run red** (the flow is new; product gaps it exposes go back into the owning task as a new step with its own test — this task lands test code and fixes that belong to no earlier surface).
- [ ] **Step 3: Make it pass**; `just verify` and this E2E, outputs read.
- [ ] **Step 4: Commit** — `test(writing): the coherence flow end to end`

```
User-visible: none — the proof is the deliverable; the flow a writer actually
lives through is now pinned green. Closes #369.
```

---

## Close-out

- `just verify` green and every touched capability E2E green, outputs read, before the final review dispatch.
- Final whole-branch review on the review model; findings triaged; surviving findings become GitHub issues (label `follow-up`, hung under this wave's new index issue) before merge — nothing dropped for being minor.
- Open the wave's index issue, add the row to `docs/superpowers/follow-ups.md`, and close what landed: Task 1 `Closes #399`, Task 4 `Closes #400`, Task 5 `Closes #336, #318`, Task 12 `Closes #369`. The design's allocation names what stays open and why: #395, #396, #398 (PromptsPage polish — no WP5 task touches their lines), #353 unless Task 5's evidence closes it, and the halves of #309–#316 no task intersects; each is cited in the index body, not silently left.
- The build session moves this plan to `docs/superpowers/plans/2026-10-30-wp5-ui-coherence-plan.md` and the design to `docs/superpowers/specs/2026-10-30-wp5-ui-coherence-design.md`, and commits both — move, never copy.
