# WP5 — UI coherence: settings area, workspace server state, palette

**Date:** 2026-10-30 · **Status:** draft for owner review — decisions 1–4 below were
taken with the owner on 2026-10-29/30; the "My calls" section is mine to overturn.

**Fahrplan:** `docs/superpowers/plans/2026-10-25-v2-foundation.md` §8 (WP5), §2
(server state, palette, phone bar), §11 (two deferred rows), §12 (WP5 gates).
**Frontend spec:** `docs/superpowers/specs/2026-10-22-frontend-design.md` §5.1–5.3.
**State after WP4:** merged as PR #406 (`c85770dd`); follow-up index #375,
findings #376–#405.

## Intent and why

WP1–WP4 built depth; the surfaces still behave like separate apps. Settings is one
long page and WP4's prompts editor sits beside it at `/prompts` with its own top-bar
link. The workspace holds hand-rolled server state (`NovelPage`'s `load`/`pending`/
`failed`), and its chapter selection is component state — no link targets a chapter,
the back button does not walk them. Every navigation beyond the top bar needs the
mouse. And the workbench overflows below 1024 px (measured 2026-10-25: with a dock
open the editor gets 0 px at a 640 px viewport; the workbench alone overflows at
360 px).

WP5 makes the app one coherent surface: a settings area with clustered sub-pages,
Query as the one server-state path (a §2 decision already taken), URL-addressable
workspace selections, and the ⌘K palette as the keyboard path through all of it.

## Goals

- `/settings` becomes an area: a hub listing clusters, one sub-page per cluster.
- The workspace reads novel and chapters through Query, with failure states that
  keep their current honesty.
- The active chapter is URL state; the `activeChapter` bus is deleted.
- ⌘K opens a palette over entities, chapters, docks/pages and commands; the mouse
  is never required for navigation afterwards.
- The measured bar holds at 360/768/1024/1280 px: no horizontal overflow, a prose
  column of at least 320 px, rail and dock as overlays below 1024 px.
- Every new user-visible string ships in en, de and fr in the same commit; one
  translation pass for `fr` is its own commit.

## Non-goals

- No new product features: no entity-creation API, no chat changes, none of WP6's
  chapter/novel management (rename, delete, reorder — §8A, later).
- No mobile design (§2: the phone is not a target; the bar is about not breaking).
- No generic signal module and no global store (see Approaches 3).
- No second dock, no new `capability.yaml` fields.

## Anti-goals

- A command *plugin registry* beyond the capability convention — commands are rows
  in each capability's `web/commands.tsx`, nothing more.
- Business logic in the shell: a command navigates, opens a modal, or calls one
  shell hook; it never contains a capability's behaviour.
- A palette that duplicates editing surfaces — it jumps and triggers, it does not
  edit.

## Constraints

Standing rules (AGENTS.md, `docs/_shared/CONSTRAINTS.md`): one capability one
folder; capabilities never import capabilities — the shell is the only shared
point; en/de/fr for user-visible text; green E2E is the done gate; governance
budget. Two new skeleton points arrive in this WP — the settings host and the
commands view — producing three generated outputs between them; each point
carries its three statements below (owner approved in the design conversation).

WP4's E2E pins the current route at three places
(`app/capabilities/prompts/e2e/test_prompts_e2e.py:190,262,324`); the route move
updates them in the same task, not later.

## Current state (as built, 2026-10-30)

- `settings` capability: one page (`SettingsPage`: language section +
  `ProvidersPanel` inline), `path: /settings`, `nav: false`, the top bar's gear
  links it.
- `prompts` capability (WP4): page at `/prompts`, `nav: true`, component tests and
  E2E green; the E2E visits `/prompts` three times.
- `NovelPage`: two parallel GETs in a hand-rolled `load()`, `pending`/`failed`
  states with named copy ("an outage must not wear the empty book's clothes"),
  chapter selection in `useState`, panel state (`rail`, `focus`) already URL state;
  autosave via `useAutosave` (serialized writes, `SaveStatus`), leave guard keyed on
  `unsavedStatus`.
- Two buses in `web/lib/`: `activeChapter` (state: workspace publishes, the Wissen
  dock's extraction panel subscribes) and `proposal` (event: chat offers ghost
  text, the workspace subscribes; offers never survive navigation by contract).
- Query: one client (`retry: false`, `staleTime: 30_000`), hooks for novels,
  entities, relations, suggestions, findings, jobs; **no chapters hook**.
- No palette; `Dialog`, `ComboBox`, `GridList` (React Aria) exist in `web/ui/`.
- `fr` catalog: 290/304 keys differ from `en` (14 carry the English string).
- Open findings on surfaces this WP reopens: #336 (failed refetch reports the
  landed write as failed), #318 (`query.ts` comment), #400 (PromptsPage load has
  no page-level retry), #395/#396/#398 (PromptsPage polish), #369 (merge hero
  lacks axe), #353 (ChapterEditor load flake), and the WP1 UI/a11y batch
  #309–#316.

## Approaches (settled with the owner)

### 1. Settings area

- **A — move the prompts page into the settings capability.** One owner, no
  generator change. Rejected: the surface belongs to the capability whose API and
  E2E own it; WP4 chose an own capability deliberately ("settings would carry
  writing/chat/knowledge prompt text — the wrong owner").
- **B (chosen) — settings becomes a second route host.** `settings` exports
  `settingsRoute`; `prompts` exports `settingsRoutes` factories; the generator
  passes the settings route in, exactly as it passes `workspaceRoute` into
  `dockRoutes` today. Any capability can later add a settings page without a
  generator change.
- **C — sibling routes with a hub page linking out.** No machinery, but the URL
  never nests and the area stays cosmetic. Rejected by the owner: no intermediate
  shape that gets replaced later.

### 2. Commands

- **Shell table, closed list.** Cheapest; rejected — growth is the normal case,
  and capability-owned handlers cannot live in the shell.
- **URL parameters per command** (`/novels/$id?export=1`). Rejected by the owner:
  a throwaway vocabulary to be replaced by the real mechanism.
- **Chosen — capability contributions.** `app/capabilities/*/web/commands.ts(x)`
  exports a `commands` array; the generator aggregates it into
  `web/lib/generated/commands.ts` the way it aggregates `dockRoutes`; the modules
  stay data-light (handlers `import()` their dialogs on first use); the shell
  renders the palette and a modal host.

### 3. Signals

- **§8.4's typed signal module on `useSyncExternalStore`.** Rejected: once the
  chapter is URL state, *zero* channels remain for it — `activeChapter` dies with
  the bus, and `proposal` is an event, not state. `useSyncExternalStore` needs a
  snapshot a fresh mount can read; storing the last offer would resurrect a stale
  ghost across navigation, which `proposal.ts` explicitly forbids.
- **Chosen:** delete the `activeChapter` bus, read the search param; leave
  `proposal.ts` untouched. Trigger recorded: a channel gains a second producer or
  state that must survive navigation → a shell store (already §8.4's own rule).

### 4. Workspace failure states

Chosen rules (the whole of the §8.3 state contract):

1. The **first** load failing is today's named outage with a retry button —
   unchanged copy, unchanged honesty.
2. A failed **refresh with data on screen** is a quiet inline note; the editor and
   rail stay; retry offered. The page never claims the book could not be loaded
   while its text is on screen.
3. The leave guard asks about **unsaved writes only** (`unsavedStatus`), never
   about read errors; and **invalidation happens only after a successful save** —
   a refetch after a failed save would lay the server's old text over the body
   `useAutosave` is holding for retry.

## The design

### 1. Settings area (first task — the palette's command targets depend on it)

- `settings/web/routes.tsx`: `settingsRoute` at `/settings` becomes a layout
  rendering an `<Outlet/>` plus the cluster nav; an index child is the hub.
- Sub-pages, one cluster each: `/settings/language` (the bar's own
  `LanguageSwitcher`, reused), `/settings/provider` (`ProvidersPanel` moves),
  `/settings/prompts` (the prompts capability's page — WP4's `PromptsPage`
  unchanged in behaviour, its route factory now parents at `settingsRoute`).
- `prompts/capability.yaml`: `path: /settings/prompts`, `nav: false` — the hub and
  the palette are the doors; the top bar drops the Prompts link.
- Generator: the second host. Contract mirrors the dock scan — exactly one
  capability exports `settingsRoute` (settings); any capability may export
  `settingsRoutes`, an array of rows `{ path, titleKey, factory }`. The generator
  emits two outputs from that one export: the wiring in `routes.ts` (factories
  parented after the settings route, order guaranteed by construction) and
  `web/lib/generated/settingsPages.ts` — the hub's list of `{ id, path, titleKey }`,
  the same shape `docks.ts` gives the workspace. Without the registry the hub
  (settings) could not name another capability's page without importing it; with
  it, a new cluster appears with zero hub edits. Tests mirror the dock-scan
  tests. **Three statements** (NEEDS-APPROVAL, owner approved 2026-10-30):
  *failure prevented* — a capability's settings page would otherwise live in the
  wrong owner or behind a throwaway URL; *effort* — ~30 lines plus tests in
  `scripts/generate_capabilities.py` and one export per contributing capability;
  *cheaper alternative* — sibling routes linked from a hub page (rejected: the
  area stays cosmetic and is replaced later).
- WP4's E2E: the three `/prompts` pins become `/settings/prompts`; the top-bar
  assertion loses the Prompts link. Same task, same commit boundary as the move.
- The hub lists its own clusters (language, provider) plus every row of the
  generated `settingsPages` registry, so a new cluster appears without hub edits.

### 2. Workspace on Query

- New hooks in `web/lib/query.ts`: `useNovelQuery(id)` → `["novels", id]`,
  `useChaptersQuery(id)` → `["chapters", id]`. `NovelPage`'s `load`, `pending`,
  `failed` and the parallel `Promise.all` go away.
- State mapping (the copy stays the copy it is today):

| Cache state | UI |
|---|---|
| no data, fetching | `chapters.loading` |
| no data, error | `chapters.errorLoad` + retry (`refetch`) |
| data, error (refresh failed) | quiet note (new key), editor and rail stay, retry |
| data | today's loaded workbench |

- Leave guard: keyed on `unsavedStatus` of the autosave only.
- Invalidation: a successful save invalidates `["chapters", id]` and
  `["novels", id]`; a failed save invalidates nothing; chapter create invalidates
  `["chapters", id]`.
- Closes #336 and #318; #400's page-level retry rule is applied to PromptsPage in
  task 1, where its surface reopens.

### 3. Chapter as URL state

- `validateSearch` on `/novels/$id` gains `chapter`; the rail's selection
  navigates (history **push** — back walks chapters; my call).
- **Switching is a navigation, and every navigation passes the same gate.**
  Today `leave()` wraps the rail's selection: flush the debounced body, confirm
  only if the flush failed. Once selection is a `?chapter=` navigation, that gate
  moves into `useBlocker`, widened from "leaves the book subtree" to "any
  navigation while `unsavedStatus` — including search-only changes inside the
  book, the back/forward stack, and jumps the palette triggers": flush, then
  confirm only on failure, exactly today's semantics. The blocker is the
  workspace's own; the palette needs no hook, no bus and no store — it navigates,
  and the gate catches it. `test_chapters_e2e.py`'s "switch inside the debounce
  must flush" keeps its meaning and gains back-button and palette variants.
- **Absent param:** arrival without `?chapter=` opens the last-touched chapter,
  as today, and does **not** write the param — a reload still proves the server's
  `updated_at` choice (`test_chapters_e2e.py`'s reload assertion keeps testing
  something). Only an explicit selection writes.
- A param naming a chapter that no longer exists resolves as absent (last
  touched) and is cleaned from the URL — a dead link degrades, it does not error.
- `web/lib/activeChapter.ts` is deleted; the Wissen dock's extraction panel reads
  the param from its parent route context.
- `proposal.ts` unchanged.

### 4. Palette and commands

**Palette (shell):** `web/components/Palette.tsx`; ⌘K/Ctrl+K opens, Esc closes,
focus returns to the opener; built on the React Aria pieces `web/ui/` already
holds. It is available on **every route**; its groups fill from context, and
nothing is persisted: with a current novel — **Chapters** (`useChaptersQuery`),
**Entities** (`useEntitiesQuery`, matched over name + aliases + tags, normalized
case- and diacritics-insensitively), **Docks & pages** (`docks.ts` +
`capabilities.ts`), **Commands**; without one — **Novels** (`useNovelsQuery`)
replaces the first two, so ⌘K is the app-wide keyboard path, and "the mouse is
never required" holds everywhere, not only inside the workspace. No
last-visited-novel memory: that would be new persisted state, and §8.4's rule
stands.

- Entity results deep-link: the Wissen dock's selected entity becomes URL state
  (`?entity=` on the dock route) — the same principle as `?chapter=`; the palette
  navigates to the dock with the entity selected. (My call; the details of the
  dock's param plumbing are the builder's.)
- Search text for every row is built from **all three catalogs'** renderings of
  its label; the display shows the active locale. "export" finds "Export" in a
  German UI and "Exporter" in a French one; the index is locale-independent, so a
  mid-session language switch rebuilds nothing. The catalogs are already in the
  bundle (`web/lib/generated/catalogs.ts`).
- The palette is the one place shortcuts are named (§11): F9/Esc for the focus
  steps, ⌘K itself; depth 2's Esc exit stops being undocumented.

**Commands contract:** `app/capabilities/*/web/commands.ts(x)` exports

```ts
export const commands = [
  { id, titleKey, run(ctx), enabled?(ctx), shortcut? }, …
] as const;
```

- `ctx` from the shell: `{ navigate, novelId?, openModal }`. A command navigates,
  opens a modal, or calls one shell hook — nothing else.
- The module imports **no components statically**; `run` loads its dialog with
  `import()` on first use, so `React.lazy`'s bundle split survives and the shell
  can import every `commands.ts` eagerly.
- The shell's modal host renders what `openModal` is handed; the shell owns the
  slot, the capability owns the dialog.
- Generator view `web/lib/generated/commands.ts`: aggregates the arrays,
  `titleKey` checked against the English catalog exactly as docks are. **Three
  statements** (owner approved 2026-10-29): *failure prevented* — commands would
  either fossilize in a shell table or smuggle capability code into the shell
  bundle; *effort* — one scan + one aggregation view + tests, the `dockRoutes`
  pattern repeated; *cheaper alternative* — a hand-kept shell list (rejected:
  silently drifts as capabilities grow).
- Test discipline: parametrized over the generated table — every command has its
  keys in all three catalogs, is enabled exactly where its `enabled` says, and
  running it produces its effect. A new command cannot land uncovered.

**First set** (growth is additive; nothing here is a closed catalogue). Every
row lives in its owning capability's `commands.ts` — the shell owns the palette,
never a command:

| Command | Owner | Handler |
|---|---|---|
| Neues Kapitel / New chapter | writing | create-and-navigate: the existing chapter mutation (`title: ""`, server placeholder), then navigate to the new `?chapter=` |
| Roman exportieren / Export novel | writing | modal: `ExportNovelDialog` |
| Einstellungen öffnen / Open settings | settings | navigate `/settings` |
| Prompts öffnen / Open prompts | prompts | navigate `/settings/prompts` |
| Wissen-Dock öffnen / Open Wissen dock | knowledge | navigate `/novels/$id/wissen` |

Two of those rows are deliberately not dialogs. "Neues Kapitel" creates
immediately: no title dialog exists, and WP6 (§8A.3) has already decided the
title is edited in place in the editor header — a create dialog now would be
built to be deleted then. Named corner: the command's POST runs before the
navigation gate, so a user who declines the navigation after a failed flush
leaves an empty chapter in the rail — visible, honest, and WP6's delete cleans
it up; today's rail button flushes first, and that difference is accepted
knowingly.

Deferred with its trigger: **"create new in knowledge"** — no creation surface
exists today (entities are born from extraction acceptance or import; document
upload is a form on `/knowledge`, not a dialog). When knowledge gains an upload
dialog or a `POST /entities`, its command is one row in its `commands.ts` and one
modal — no generator change, no palette change.

### 5. Responsive bar

Below 1024 px the rail and the dock render as overlays over the editor, never as
columns beside it; at every width the prose column measures at least 320 px and no
page overflows horizontally at 360 px. This is CSS and mounting behaviour on the
existing collapse machinery (`rail`/`focus` params, dock child routes) — no new
state.

### 6. i18n

Every new key lands in en, de and fr in the same commit; `fr` may carry the
English string as a marked placeholder. One translation-pass commit at the end
covers the placeholders and the 14 existing en==fr keys (my call).

### 7. E2E (§8.6, the done gate)

- Full flow: setup (demo) → workspace → entity with relation → settings (provider,
  prompts) → continuation uses both → ⌘K reaches an entity and runs a command.
- Language switch renders all new surfaces; `assert_accessible` on every page the
  flow visits — the sweep also covers #369's merge hero.
- A viewport helper beside `a11y.py` in `kernel/testing` asserts the four widths.
  The measurements are defined, so the gate cannot pass on a technicality:
  - **No horizontal overflow:** `scrollWidth` ≤ viewport width on every page.
  - **Prose column ≥ 320 px:** the editor's *content box* — the box text wraps
    in, the editor's own padding excluded — because the plan's §2 warning is
    exactly about gates that measure the wrong box. At 360 px this forces the
    responsive padding work, not a re-read of the rule.
  - **Overlays below 1024 px:** opening the rail or the dock must not reduce the
    editor's bounding-box width — operationally "an overlay", whatever the CSS
    route; and the overlay must cover, not push (bounding-box intersection with
    the editor).
- #353's load flake is addressed where task 2 touches load timing; if it survives,
  it stays an issue with evidence.

### 8. Findings allocation (the rule, then the list)

Rule: a finding folds into WP5 when WP5 reopens its surface; everything else stays
an issue and is cited, not silently dropped.

- Fold: #336, #318 (task 2); #400 (task 1, same rule on PromptsPage); #369 (the
  axe sweep); the §11 rows (shortcut hints and the named Esc exit — task 4;
  NovelsPage hero duplication and the null first paint — task 2's Query work on
  the shelf's first paint).
- Ride task 1 where its diff touches the lines anyway: #395, #396, #398 — each
  only the half its lines intersect; the rest stays an issue.
- Stay open: #309–#316 except the halves task 1/4 intersect, #353 unless task 2
  removes it, #399 (pre-commit web filter — a repo gate gap, not UI; it deserves
  its own fix commit early in the WP so every later web commit is gated), and all
  other open findings.

## Verification

`just check` before every commit; `just verify` plus the capability E2Es (writing,
knowledge, prompts, settings) to close. §12's WP5 gates: ⌘K reaches an entity; the
settings area routes; the language switch renders every new surface; axe on each
page; 360/768/1024/1280 px with no overflow and a ≥320 px prose column.

## My calls (mine to overturn)

1. Hub layout: an index page listing clusters as cards with one-line descriptions;
   sub-pages carry the same list as a compact nav.
2. Chapter selection pushes history entries (back walks chapters) rather than
   replacing; an absent param opens the last-touched chapter and writes nothing.
3. The flush gate moves into `useBlocker` and covers every navigation —
   search-only switches, back/forward, palette jumps — with today's
   flush-then-confirm-only-on-failure semantics.
4. The palette is available on every route, with a Novels group when no novel is
   current; nothing persisted.
5. "Neues Kapitel" creates immediately (no title dialog — WP6 owns the title
   surface); the declined-navigation corner is accepted and named above.
6. The dock's selected entity becomes `?entity=` URL state so palette results
   deep-link.
7. Palette filtering is client-side over cached novels/chapters/entities — no new
   endpoints.
8. The 14 en==fr catalog keys get real French in the translation-pass commit.
9. Viewport assertions live in `kernel/testing` beside `a11y.py`, with the three
   measurement definitions above.
10. The first command set as tabled above; "create new in knowledge" deferred with
    its trigger.

## Left to the builder

- Hook shapes and query-key naming inside the §8.3 rules; the quiet
  refresh-failure note's copy.
- The palette's keyboard details beyond the open/close/focus-return contract.
- The overlay CSS approach below 1024 px.
- The async blocker mechanics inside TanStack Router (`useBlocker` awaiting the
  flush) — the rule is decided, the mechanism is not.
- Test file layout; which PromptsPage polish halves ride task 1.
- The exact scan rules for `settingsRoutes` and `commands.ts` in the generator,
  mirroring the dock scan's tests.
