# Shelf Fidelity Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The shelf and the shell's TopBar ship 1:1 against `screens/library/shelf` / `shelf-dark`, with layout-holding placeholders for missing data, an English gap doc, and the workspace band trimmed of the facts the bar now owns.

**Architecture:** Re-composition on the W0–W3 primitives: tokens in `web/globals.css`, shared `Cover`/`StatusPill`/`TopBar` primitives, shelf components re-skinned in place. Behaviour frozen; presentation only. Base branch `feat/literary-modernism-w3` (stacked on the open W3 PR).

**Tech Stack:** Tailwind v4 (`@theme inline`), React 19, TanStack Router, vitest, Playwright E2E.

**Spec:** `docs/superpowers/specs/2026-11-13-shelf-fidelity-design.md` — executors read both. Composition norm: `docs/design/stitch/screens/library/shelf.html` / `shelf.webp` / `shelf-dark.html`; values: `DESIGN.md`.

## Global Constraints

- Tokens only in `web/globals.css`, every value a `light-dark()` pair; capabilities carry utilities, never a palette.
- AA 4.5:1 text / 3:1 icons in both themes; measured ratios ship in the PR; a failing draft value goes to a Stitch round, never a quiet adjustment.
- Icons stay the hand-drawn 16 px / 1.5-stroke set (O-3); no icon font, no CDN.
- Copy through en/de/fr catalogs, same keys sorted; a missing key is a build error; draft labels inform `de`.
- Placeholders hold the draft's geometry: "—" for missing numbers, empty bar tracks, flat labeled sparkline; never an invented number; controls without an action render disabled with `aria-disabled` + explanatory title; interim comments end in their issue number.
- Behaviour frozen: search/filter/view/menus/dialogs/navigation and the focus-depth contract (F9 deepens, Esc releases; depth 2 hides the bar) keep their semantics.
- UI tasks: implementer `opencode/deepseek-v4.1-flash-free` (UI Agent), reviewer `zai-coding-plan/glm-5.3`; coordinator `zai-coding-plan/glm-5.3`. Every dispatch names both models.
- Gates: `just check` after each group; `just test-file` on touched tests; `just verify` + writing E2E + axe both themes before the PR; a gate counts only when its output was read.
- Commits: conventional; `feat`/`fix` carry a real `User-visible:` line; docs `chore(docs)`; agent commits end with `Assisted-by: OpenCode (<model>)` via `--trailer`; no `--no-verify`, no force push; nothing commits before the task's review is green. Push after every green task group.

## Review Focus

1. **No fake number ever flashes** — while queries load or refetch, placeholders stay neutral; pinned by Task 8/10/11 tests asserting "—"/empty track in pending and settled states.
2. **Long titles, authors, genres** — cover lettering, bar breadcrumb, hero title truncate with the full string in the accessible name; pinned by Tasks 4/5/8 tests.
3. **Keyboard through the new chrome** — Filter popover traps focus, Esc closes, button carries `aria-expanded`; skip link stays first; bar controls tab in order; pinned by Tasks 5/9 tests + axe.
4. **Dark AA of the new pill/accent pairs** on their own grounds; pinned by Task 3's value pins + the axe dark leg (Task 12).
5. **Focus-depth contract survives** — bar hidden at depth 2, band trim keeps F9/Esc stepping; pinned by Tasks 5/6 tests + the writing focus E2E leg re-run.

---

### Task 1: Wave opening — issues, gap doc, spec corrections (coordinator)

**Files:**
- Create: `docs/design/stitch/shelf-gaps.md`
- Modify: `docs/superpowers/follow-ups.md`, umbrella spec §5/§6.5/§6.9, W3 spec decisions, `docs/design/stitch/dark-tokens.md`

- [ ] **Step 1:** File the index issue (`follow-up-index`) "Shelf fidelity repair — missing-data follow-ups" and three children (`follow-up`, `area: web`, `severity: minor`): hero imprint field; book form/kind field; Filter panel states beyond the Stitch export. Bodies name trigger + interim logic.
- [ ] **Step 2:** Add the wave's row to `follow-ups.md`; write `shelf-gaps.md` (English) with the spec §6 table, real issue numbers for the new rows, #781–#786/#788 for the shared ones.
- [ ] **Step 3:** Spec corrections: umbrella §6.5 cover prose → the screen's composition (top title, author foot, motif); umbrella §5 + W3 spec: D-2 superseded by owner 2026-11-13 (bar owns shell facts; band trimmed, spec §5.8); `dark-tokens.md`: delta tolerance superseded (spec §5.9); deviation log: D-5/D-6 recorded as owner decisions.
- [ ] **Step 4:** `just check` — PASS. Commit `chore(docs): the shelf fidelity wave opens — issues, gap doc, spec corrections`.

### Task 2: Stitch round G-F1 — the Filter panel (coordinator)

**Files:**
- Create: `docs/design/stitch/screens/library/shelf-filter.html` / `.webp` (export)

- [ ] **Step 1:** One round in the `narrare` Stitch project: the shelf Filter button's panel — filters offered (genre now; status when #784 lands), layout, open/empty states, light + dark. Export into the archive.
- [ ] **Step 2:** Commit `chore(docs): the Filter panel draft, G-F1 answered`. Blocks Task 9.

### Task 3: Status pills and dark accents — shell tokens (UI Agent)

**Files:**
- Modify: `web/globals.css`
- Create: `web/ui/StatusPill.tsx`, `web/ui/StatusPill.test.tsx`

**Interfaces:**
- Produces: `StatusPill({ kind }: { kind: "active" | "draft" | "planning" | "review" })` — span, eyebrow step, tokens `--pill-<kind>-ground/-ink/-rule`; labels from catalogs. Tokens: dark halves active `#1B3520/#66BB6A/#25502C`, draft `#192D3E/#64B5F6/#234561`, planning `#2C2C28/#E0E0E0/#3D3D37`, review `#3A2814/#FFB74D/#5A3C1C`; light halves extracted from `shelf.html`; `--area-writing` dark becomes `#E28659`.

- [ ] **Step 1: Failing test** — each kind renders its token classes and catalog label; a value pin asserts the four dark triplets and `#E28659` in `globals.css`; contrast ratios computed and recorded (AA both themes).
- [ ] **Step 2:** FAIL. **Step 3:** Implement tokens + pill. **Step 4:** `just test-file web/ui/StatusPill.test.tsx` + `just check` — PASS.
- [ ] **Step 5:** Commit `feat(web): status pills wear the screens' own hues in both themes` + `User-visible:`.

### Task 4: The cover rebuilt to the draft (UI Agent)

**Files:**
- Modify: `web/ui/Cover.tsx`, its test, `web/ui/icons.tsx` (motif glyphs)

**Interfaces:**
- Produces: `Cover({ title, size?, genre?, language?, author?, imprint? })` — `author?: string | null`, `imprint?: string | null`. One composition for all tones: spine; top eyebrow + italic serif title (grid `prose-heading-2`, hero `prose-heading-1`); middle genre motif (sci-fi target, mystery house, literary waves, historical cloud, else ring); foot author (`null` → "—"); sepia keeps the gold frame; hero renders the imprint row when `imprint !== undefined` (`null` → "—") + corner motif. Geometry: grid w-36 h-52, hero w-48 h-72.

- [ ] **Step 1: Failing test** — composition per tone (top title, motif, author foot); null author "—"; imprint row only when prop present, "— when null"; frame only sepia; `aria-hidden`; long title/author truncate; motif per genre incl. fallback.
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** `just test-file` + `just check` — PASS.
- [ ] **Step 5:** Commit `feat(web): the cover wears the draft's composition — title, motif, author` + `User-visible:`.

### Task 5: The drafted TopBar, every route (UI Agent)

**Files:**
- Create: `web/lib/activeNovel.ts`, `web/lib/activeNovel.test.ts`
- Modify: `web/components/TopBar.tsx` + test, `web/components/LanguageSwitcher.tsx`, `web/routes/__root.tsx`

**Interfaces:**
- Consumes: `useNovelsQuery(): UseQueryResult<Novel[]>` (`web/lib/query.ts:73`), `RailSync` (`IconRail`), `useSyncStatus` bridge (`__root.tsx:49`).
- Produces: `activeNovel(novels: Novel[] | undefined): Novel | undefined` (max `updated_at`); `TopBar({ onOpenPalette, sync, novels, showSettings })`; `LanguageSwitcher({ showFormality?, compact? })`. Bar: left book glyph + `Manuscripts / <active title>` (`text-emph`, truncate + full name) + save chip (`shell.sync*`, from `sync`); right search-styled palette door (placeholder + keycap inside, fires `onOpenPalette`), Σ-words chip (tabular), compact language chip; gear only when `showSettings`. Skip link, `data-focus="2"` gating, rail-axis arithmetic unchanged.

- [ ] **Step 1: Failing tests** — `activeNovel` picks max `updated_at`, undefined on empty; bar renders breadcrumb/save/words/language from props; long book title truncates with full accessible name; palette door fires; gear absent unless `showSettings`; depth-2 gating untouched.
- [ ] **Step 2:** FAIL. **Step 3:** Implement; `__root` passes `sync`, `novels`, `showSettings`. **Step 4:** `just test-file` both + `just check` — PASS.
- [ ] **Step 5:** Commit `feat(web): the shell bar wears the draft on every route` + `User-visible:`.

### Task 6: The workspace band loses the duplicated cluster (UI Agent)

**Files:**
- Modify: `app/capabilities/writing/web/novel/WorkspaceToolbar.tsx` + test, `NovelPage.tsx`

**Interfaces:**
- Consumes: Task 5's bar (owns breadcrumb/save/words/language).
- Produces: `WorkspaceToolbar` without `bookTitle`/`words`/`status`/`localeChip`; keeps chapter selector, focus (F9), history (disabled), export, dock tabs, rail toggle, rail filter.

- [ ] **Step 1: Failing test** — band renders no breadcrumb/save/language/word chip; workbench controls intact; ribbon assertions that moved to the bar live in TopBar's test.
- [ ] **Step 2:** FAIL. **Step 3:** Implement + rewire `NovelPage`. **Step 4:** `just test-file` + `just check` + the writing focus/continuation E2E legs — PASS.
- [ ] **Step 5:** Commit `feat(writing): the band keeps the workbench, the bar keeps the facts` + `User-visible:`.

### Task 7: Shelf header and metrics strip (UI Agent)

**Files:**
- Modify: `app/capabilities/writing/web/shelf/ShelfHeader.tsx` + test

- [ ] **Step 1: Failing test** — h1 at `prose-heading-1`/text-3xl `text-primary`; eyebrow + session line; metrics: count and Σ words derived, streak "—" with #781 comment; Import + New book on the metrics row, right.
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** `just test-file` + `just check` — PASS.
- [ ] **Step 5:** Commit `feat(writing): the shelf header stands at the draft's scale` + `User-visible:`.

### Task 8: The hero card (UI Agent)

**Files:**
- Modify: `app/capabilities/writing/web/shelf/HeroCard.tsx` + test, `NovelsPage.tsx` (share `activeNovel`)

- [ ] **Step 1: Failing test** — `StatusPill kind="active"` + real sync line; title + series slot "—" (#786 comment); blurb = description, no added quotes, clamp-3; words real + "/ —" + empty track (#783); chapters + last-edited real; Cover gets `author`/`imprint` (imprint "—", Task 1 issue); CTAs real; pending query renders neutrals, never numbers.
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** `just test-file` + `just check` — PASS.
- [ ] **Step 5:** Commit `feat(writing): the hero card reads like the draft's, honestly` + `User-visible:`.

### Task 9: Search / Filter / view row (UI Agent, after Task 2)

**Files:**
- Modify: `app/capabilities/writing/web/shelf/ShelfToolbar.tsx` + test
- Create: `app/capabilities/writing/web/shelf/FilterPopover.tsx` + test

**Interfaces:**
- Consumes: the G-F1 export (`shelf-filter.html`); existing genre filter state.
- Produces: `FilterPopover({ open, onClose, genres, selected, onSelect })` — focus trap, Esc closes, `aria-expanded` on the button; composition per the export.

- [ ] **Step 1: Failing test** — Filter button (tune) replaces the genre select; popover per export, genre filter real; trap/Esc/aria; search placeholder copy as drafted; view toggle unchanged.
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** `just test-file` both + `just check` — PASS.
- [ ] **Step 5:** Commit `feat(writing): the shelf's filter door opens the drafted panel` + `User-visible:`.

### Task 10: Book grid and list (UI Agent)

**Files:**
- Modify: `app/capabilities/writing/web/shelf/BookCard.tsx`, `BookList.tsx` + tests

- [ ] **Step 1: Failing test** — cover on drafted pad + `more_horiz` menu; title + `StatusPill kind="draft"` interim (#784); blurb clamp-2; "N / —" + "—" % + empty track (#783); foot chapters + relative time real; hover lift; list view re-tokened, behaviour unchanged; long titles truncate with full name.
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** `just test-file` + `just check` — PASS.
- [ ] **Step 5:** Commit `feat(writing): the shelf cards wear the draft's faces` + `User-visible:`.

### Task 11: The activity banner, honestly neutral (UI Agent)

**Files:**
- Modify: `app/capabilities/writing/web/shelf/ActivityBanner.tsx` + test

- [ ] **Step 1: Failing test** — goal "—", subline neutral, WOCHENSCHNITT "—", flat labeled sparkline (#782 comments); "Statistiken öffnen" disabled + `aria-disabled` + title (#788); geometry as drafted; no number while pending.
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** `just test-file` + `just check` — PASS.
- [ ] **Step 5:** Commit `feat(writing): the activity banner holds the draft's foot, neutrally` + `User-visible:`.

### Task 12: The proof — frames and side-by-sides (Coding Agent `zai-coding-plan/glm-5.3-flash`)

**Files:**
- Modify: `scripts/screenshots.py`, `assets/screenshots/05-shelf.png`, `06-shelf-dark.png`
- Create: `docs/design/stitch/comparisons/2026-11-13-shelf-light.png`, `-shelf-dark.png`, workspace spot-check pair

- [ ] **Step 1:** Re-shoot shelf light + dark on the seeded showcase; compose the pairs via the fidelity compositor; workspace spot-check shows one bar + trimmed ribbon.
- [ ] **Step 2:** `just verify` — PASS; axe AA both themes on the shelf route; writing E2E green.
- [ ] **Step 3:** Commit `chore(docs): the shelf proof — frames and side-by-sides`.

### Task 13: Whole-branch review and the PR (Reviewer `zai-coding-plan/glm-5.3`)

- [ ] Fresh reviewer reads the branch against the spec: fidelity of every surface, gap doc current with live issue numbers, interim comments complete, Review Focus 1–5 answered, gates' outputs read. Findings become issues or fixes before merge.
- [ ] Owner approves the shelf pairs (light + dark) and the workspace spot-check.
- [ ] Push; open the PR with a plain-language title (no conventional grammar, no wave names); plan + spec referenced in the body.