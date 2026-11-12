# Literary Modernism W3 — the writing workspace (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The writing workspace, its chapter rail, the editor paper, the floating prompt bar and zen focus ship 1:1 against `docs/design/stitch/screens/writing/workspace` and `zen-focus`, and the shell chrome the draft shows (book-switcher, sync dot, theme toggle, user block) completes with them.

**Architecture:** Re-composition on the hardened pilot primitives — tokens, fonts, buttons, fields, icons, covers and chrome from W0–W1 are already in `globals.css`/`web/ui`; W3 re-skins the writing capability's existing surfaces (`NovelPage`, `ChapterRail`, `ChapterEditor`, `WorkspaceToolbar`) and the shared `IconRail`, changing presentation, never behaviour. One branch, one PR; task groups pushed after each green group.

**Tech Stack:** Tailwind v4 (`@theme inline` tokens), React 19, TanStack Router, TipTap (MarkdownEditor, ghostText extension), vitest, Playwright E2E.

**Spec:** `docs/superpowers/specs/2026-11-12-literary-modernism-w3-design.md` — the plan argues from it; executors read both. Value norm: `docs/design/stitch/DESIGN.md`, composition norm: the exported screens under `docs/design/stitch/screens/writing/`.

## Global Constraints

- Tokens live only in `web/globals.css`; capabilities carry utilities, never a palette.
- Every new surface uses existing `light-dark()` pairs; AA 4.5:1 text / 3:1 icons measured in both themes.
- No new palette values, no CDN, no icon font; icons come from the hand-drawn set (`web/ui/icons.tsx`), extended per O-3 where a drafted concept is missing.
- Behaviour is frozen: focus-depth contract (F9 deepens 0→1→2, Esc releases 2→1→0; a pending ghost owns Esc first), autosave, ghost text, slash palette, leave guard, chapter CRUD/reorder, dock registry — W3 changes presentation only. A task that needs a behaviour change to look right stops and reports.
- Interim fields render from the least-invented honest source (derived where the app has truth, neutral "—" where it has none, never an invented number) and carry a code comment ending in their follow-up issue number (spec §6).
- Copy through i18n catalogs en/de/fr — same keys, sorted; a missing key is a build error. Draft labels inform `de`.
- English in code and comments; user-visible text only through catalogs.
- Commits: conventional; user-visible changes `feat(web)`/`feat(writing)` with a real `User-visible:` line; docs/archive `chore(docs)`; agent commits end with `Assisted-by: OpenCode (<model>)` via `--trailer`. Nothing commits before the task's gates are green.
- Gates: `just check` (fast), `just test-file <path>`, `just verify`, the writing E2E; a gate counts only when its output was read.
- UI tasks are implemented by the UI Agent (`zai-coding-plan/glm-5.3-flash`) and reviewed by the Reviewer (`zai-coding-plan/glm-5.3`); every dispatch names both models explicitly (AGENTS.md rev. 6).

## Review Focus

1. **Focus-depth contract survives the re-skin** — F9/Esc still step 0↔1↔2, a pending ghost still owns Esc before the workbench, and at depth 2 only the writing surface remains. Pinned by Task 10's test on the stepped classes and the existing focus/continuation E2E legs, run again after every task that touches the toolbar or editor frame.
2. **Keyboard path on the restyled rail** — rows stay operable by keyboard (walk, select, reorder keys, filter field), the drag affordance never becomes the only path. Pinned by Task 5's test and the writing E2E's rail legs.
3. **Long titles and names** — rail row titles, runhead input, breadcrumb and book-switcher truncate with the full string in `aria-label`/accessible name. Pinned by Tasks 2, 5, 7 tests.
4. **Interim fields never fake a number** — session stats show "—", story arc is a labeled placeholder, target pills stay hidden, status line is the draft default. Pinned by Task 6's test asserting the neutral render and the issue-number comment.
5. **Locale completeness including ordinals** — `chapterOrdinal` covers en/de/fr 1–99 with digit fallback ≥100; KAP-prefix and every new label exist in all three catalogs. Pinned by Task 1's test and the i18n build error.
6. **Dark-mode contrast of the new chips** — word-count chip, badges, keycap pill and session card meet AA on their dark grounds. Pinned by the axe E2E leg in both themes (Task 12) and each component test's class assertions against token names, not hexes.

---

### Task 1: The chapter ordinal — locale number words

**Files:**
- Create: `app/capabilities/writing/web/numberWords.ts`
- Test: `app/capabilities/writing/web/numberWords.test.ts`

**Interfaces:**
- Produces: `chapterOrdinal(n: number, locale: "en" | "de" | "fr"): string` — the written-out ordinal word for the chapter eyebrow ("Kapitel Eins" uses `chapterOrdinal(1, "de")` → "Eins"); 1–99 written out per locale, ≥100 falls back to `String(n)` (the bound is the util's documented contract, spec D-3).

- [ ] **Step 1: Write the failing test** — `numberWords.test.ts` asserts: 1/2/3/11/13/21/99 for de ("Eins","Zwei","Drei","Elf","Dreizehn","Einundzwanzig","Neunundneunzig"), en ("One"…"Ninety-Nine"), fr ("Un"…"Quatre-Vingt-Dix-Neuf", hyphenation per locale); 100 and 0 return `"100"`/`"0"` digits; negative input throws or clamps per the JSDoc the builder writes (one rule, tested).
- [ ] **Step 2:** `just test-file app/capabilities/writing/web/numberWords.test.ts` — FAIL.
- [ ] **Step 3: Implement** the util with per-locale ones/tens tables and a compound rule (de/fr: unit-und-tens; en: tens-unit); no dependencies.
- [ ] **Step 4:** PASS; `just check`.
- [ ] **Step 5: Commit** — `feat(writing): chapter eyebrows speak their ordinal in three locales` + `User-visible:` line.

### Task 2: The shell chrome completes — book-switcher, sync dot, theme, user

**Files:**
- Modify: `web/components/IconRail.tsx`, its test
- Test: `web/components/IconRail.test.tsx` (extend)

**Interfaces:**
- Consumes: `useNovelsQuery()` (`web/lib/query.ts:73`), the theme contract (`applyTheme` + `PATCH /api/settings/theme` + `useSettingsQuery`, as `AppearancePage` drives it), `web/ui/Cover.tsx`, `web/ui/Menu.tsx` (`ActionMenu`), `web/ui/icons.tsx`.
- Produces: the drafted rail blocks (spec §5.0); no exported interface changes.

- [ ] **Step 1: Catalogs + failing tests** — shell catalog keys for book-switcher label, sync states, theme labels, user block; tests assert: book-switcher renders the active novel's cover chip + truncated name and a menu of novels navigating on select; sync dot derives from the autosave state it is handed (prop `sync: "saved" | "pending" | "failed"` — add it, `IconRail` stays presentational); theme button cycles system→light→dark through the AppearancePage contract; user block names the user row and renders the fallback label when the author name is null. Long names truncate with full accessible names.
- [ ] **Step 2:** FAIL. **Step 3: Implement** the four blocks in the rail's drafted geometry (`DESIGN.md` spacing; eyebrow/meta type tokens); extend `IconRail`'s call site (`web/routes` shell layout) to pass `sync` and the novels data.
- [ ] **Step 4:** `just test-file web/components/IconRail.test.tsx` + `just check` — PASS; axe leg for the menu's focus contract.
- [ ] **Step 5: Commit** — `feat(web): the rail's drafted chrome — book-switcher, sync, theme, user` + `User-visible:` line.

### Task 3: The workspace ribbon — breadcrumb, chips, right cluster

**Files:**
- Modify: `app/capabilities/writing/web/novel/WorkspaceToolbar.tsx`, its test (in `NovelPage.test.tsx` or a new `WorkspaceToolbar.test.tsx` as fits the existing pattern)
- Test: same

**Interfaces:**
- Consumes: existing `WorkspaceToolbar` props; new props `bookTitle: string | undefined`, `words: number | undefined` (the book's Σ `word_count`, derived in `useNovelWorkspace`), `status: SaveStatus`, `localeChip` from the shell's language state.
- Produces: the drafted band: breadcrumb `Manuscripts / <book>` (`text-emph` on the book), save chip (from the one `status` owner), word-count chip (tabular), language chip, right cluster focus (F9) / history (**disabled**, comment + follow-up number) / export. Existing rail-toggle and dock tabs stay in the band, drafted geometry. Target-progress pill stays hidden (comment + #783).

- [ ] **Step 1: Catalogs + failing tests** — breadcrumb labels, chip labels, history tooltip; tests assert chip contents derive from props, history renders disabled with `aria-disabled`, breadcrumb truncates with full name, no fake target number renders.
- [ ] **Step 2:** FAIL. **Step 3: Implement**; wire `words`/`bookTitle`/`status` through `NovelPage`.
- [ ] **Step 4:** `just test-file` the touched suites + `just check` — PASS.
- [ ] **Step 5: Commit** — `feat(writing): the workspace band wears the drafted ribbon` + `User-visible:` line.

### Task 4: The rail's meta header and tabs

**Files:**
- Modify: `app/capabilities/writing/web/novel/ChapterRail.tsx`, test
- Test: same

**Interfaces:**
- Consumes: `visibleChapters`, `chapterCounts`, `chapterCount` (existing props).
- Produces: meta header card (eyebrow `workspace.railOutline` area-writing, "Entwurf" badge — neutral, comment + new issue, chapter count + Σ words derived), `Kapitel`/`Szenen & Plot` tabs (Kapitel active; Szenen renders an empty state linking to the active novel's planning surface with the novel param — comment + new issue).

- [ ] **Step 1: Catalogs + failing tests** — header labels, badge, tabs, empty state; tests assert derived counts, badge neutrality, tab switch renders the empty state with the correct link, keyboard tabs operable.
- [ ] **Step 2:** FAIL. **Step 3: Implement.**
- [ ] **Step 4:** `just test-file` + `just check` — PASS.
- [ ] **Step 5: Commit** — `feat(writing): the chapter rail's drafted header and tabs` + `User-visible:` line.

### Task 5: The rail's chapter rows and add-button

**Files:**
- Modify: `app/capabilities/writing/web/novel/ChapterRail.tsx`, `web/ui/Row.tsx` (only if the drafted row look belongs in the shared primitive — otherwise local classes), tests
- Test: same

**Interfaces:**
- Consumes: existing row machinery (`walkRail`, drag, filter) — untouched.
- Produces: drafted rows: drag handle, eyebrow `Kapitel 0N` (zero-padded, digits — the rail stays digits; only the editor eyebrow is written out), right-aligned tabular word count, title `text-emph` truncating with full `aria-label`, status dot + line (interim "Erster Entwurf" for all, comment + #784); full-width add-chapter button.

- [ ] **Step 1: Failing tests** — row composition per draft, word count from `chapterCounts`, truncation + `aria-label`, status interim + issue comment, add button present; keyboard walk/select/reorder unchanged.
- [ ] **Step 2:** FAIL. **Step 3: Implement.**
- [ ] **Step 4:** `just test-file` + `just check` — PASS; writing E2E rail legs green.
- [ ] **Step 5: Commit** — `feat(writing): chapter rows as the draft draws them` + `User-visible:` line.

### Task 6: Story arc and session stats — honest neutrals

**Files:**
- Create: `app/capabilities/writing/web/novel/StoryArc.tsx`, `app/capabilities/writing/web/novel/SessionStats.tsx`
- Modify: `ChapterRail.tsx` (mount both), `web/ui/icons.tsx` (missing glyphs only)
- Test: `StoryArc.test.tsx`, `SessionStats.test.tsx`

**Interfaces:**
- Consumes: `activeVisibleIndex`, `chapterCount` (arc marker position), nothing real for stats yet.
- Produces: `StoryArc({ position, total })` — the area-writing gradient curve with the current-chapter marker at `position/total`; a labeled placeholder until plot data exists (comment + new issue). `SessionStats()` — the drafted card with "—" values and hidden goal bar (comment + new issue). Never a number the app does not have.

- [ ] **Step 1: Failing tests** — arc renders the SVG with the marker derived from props and a catalog label; stats render neutral "—" and no bar/percent; both carry the issue-number comment.
- [ ] **Step 2:** FAIL. **Step 3: Implement** (SVG per the draft's path/gradient, tokens not hexes).
- [ ] **Step 4:** `just test-file` both + `just check` — PASS.
- [ ] **Step 5: Commit** — `feat(writing): the rail's arc and session card, honestly neutral` + `User-visible:` line.

### Task 7: The editor runhead and chapter headline

**Files:**
- Modify: `app/capabilities/writing/web/ChapterEditor.tsx`, test
- Test: `ChapterEditor.test.tsx` (extend)

**Interfaces:**
- Consumes: `chapterOrdinal` (Task 1), existing props (`bookTitle`, `title`, `chapterNumber`).
- Produces: runhead retuned to the drafted geometry (1 px rule, eyebrow spacing, `text-emph`); the card's chapter headline: eyebrow `Kapitel <ordinal>` (area-writing, tracked, written out per D-3), title in `prose-heading-1`, 1 px sepia rule beneath; mono chapter badge (`KAP-01` style: catalog prefix + zero-padded position) in the runhead line. Title input stays the runhead's input (behaviour unchanged).

- [ ] **Step 1: Catalogs + failing tests** — ordinal eyebrow per locale (1 → "Kapitel Eins"), badge prefix per catalog, rule/headline classes; input behaviour assertions unchanged.
- [ ] **Step 2:** FAIL. **Step 3: Implement.**
- [ ] **Step 4:** `just test-file app/capabilities/writing/web/ChapterEditor.test.tsx` + `just check` — PASS.
- [ ] **Step 5: Commit** — `feat(writing): the chapter headline speaks its ordinal` + `User-visible:` line.

### Task 8: The paper — running head, drop cap, foot, ghost keycap

**Files:**
- Modify: `app/capabilities/writing/web/ChapterEditor.tsx`, `web/ui/markdown-editor.tsx` (prose styles only), `web/globals.css` (drop-cap + running-head utilities in `@layer utilities`, values from tokens), `web/ui/Keycap.tsx` (only if the pill needs a variant), tests
- Test: `ChapterEditor.test.tsx`, `web/ui/typeScale.test.ts` (census if new named utilities)

**Interfaces:**
- Produces: paper running head (`book — author`, italic EB Garamond; book alone when author is null; folio omitted until pagination — comment + new issue); CSS drop cap on the prose's first paragraph (`first-letter`, drafted metrics); card foot: autosave state line (from the one `status` owner) + word count/position as today, page marker omitted (same issue); ghost text's `[Tab] Vorschlag übernehmen` keycap pill beside the ghost (Keycap reuse), ghost tint `area-writing/70 italic`.

- [ ] **Step 1: Failing tests** — running head render + null-author fallback, drop-cap utility applied to the prose root, ghost keycap pill rendered with the pending ghost, foot renders autosave line; no folio, no page count.
- [ ] **Step 2:** FAIL. **Step 3: Implement** (drop cap as a utility class so `.ProseMirror` content stays markdown-roundtrip-neutral — no stored markup).
- [ ] **Step 4:** `just test-file` the touched suites + `just check` — PASS; continuation E2E leg green (ghost accept/discard unchanged).
- [ ] **Step 5: Commit** — `feat(writing): the paper — running head, drop cap, ghost keycap` + `User-visible:` line.

### Task 9: The floating prompt bar

**Files:**
- Create: `app/capabilities/writing/web/novel/PromptBar.tsx`
- Modify: `app/capabilities/writing/web/novel/EditorColumn.tsx` (mount below the card), `web/ui/icons.tsx` (drafted concepts: spark, neurology as named concepts)
- Test: `PromptBar.test.tsx`

**Interfaces:**
- Consumes: `continueWriting` (pass as `onContinue: () => void`), `disabled` = streaming state.
- Produces: the drafted sticky bottom bar: context trigger chip (neutral "Stil: —", comment + new issue), inline prompt input (**disabled**, comment + the prompt-param issue), "Weiterschreiben" primary pill button (the working continuation trigger — the existing button above the card stays), three quick-prompt pills (**disabled**, same issue). All copy through catalogs.

- [ ] **Step 1: Catalogs + failing tests** — bar composition, input and pills `disabled` with `aria-disabled` and explanatory title, button fires `onContinue`, trigger neutral; keyboard order sane.
- [ ] **Step 2:** FAIL. **Step 3: Implement.**
- [ ] **Step 4:** `just test-file` + `just check` — PASS.
- [ ] **Step 5: Commit** — `feat(writing): the floating prompt bar, honest about what it can send` + `User-visible:` line.

### Task 10: Zen focus at depth 2

**Files:**
- Modify: `app/capabilities/writing/web/ChapterEditor.tsx`, `app/capabilities/writing/web/novel/EditorColumn.tsx`, tests
- Test: the touched suites + the writing E2E focus leg

**Interfaces:**
- Produces: depth-2 presentation per `zen-focus.webp`: centered paper on canvas, no band/runhead (already yielded at depth 2), the focus hint line stays, ghost keycap reachable. No state-machine change — classes only.

- [ ] **Step 1: Failing test** — depth 2 renders the centered paper classes and no band; Review Focus 1 re-run (focus E2E leg).
- [ ] **Step 2:** FAIL. **Step 3: Implement.** **Step 4:** `just test-file` + `just check` + the focus/continuation E2E legs — PASS.
- [ ] **Step 5: Commit** — `feat(writing): zen focus wears the draft` + `User-visible:` line.

### Task 11: The follow-up issues

**Files:** none in the tree — GitHub issues + `docs/superpowers/follow-ups.md`

- [ ] **Step 1:** File the index issue (label `follow-up-index`) for the W3 wave.
- [ ] **Step 2:** One child per spec §6 row marked "new issue" (draft version badge, story arc, session stats, Szenen tab, folio/page marker, prompt input+pills, history button) — labels `follow-up` + `area: writing`, body naming the trigger and the interim logic it replaces; the two shared rows reference #783/#784.
- [ ] **Step 3:** Add the wave's row to `docs/superpowers/follow-ups.md`; commit — `chore(docs): the W3 follow-up index`. Interim comments in code cite their issue numbers (fix-ups where the plan wrote "new issue").

### Task 12: The proof — master frames and side-by-side

**Files:**
- Modify: `scripts/screenshots.py` (workspace light + dark + focus-depth-2 frames), `assets/screenshots/`
- Test: the screenshot-updated E2E frames, axe legs

- [ ] **Step 1:** Re-shoot the workspace master frames (light, dark, zen) on the seeded demo book; commit per the naming convention.
- [ ] **Step 2:** The side-by-side artifacts — implemented route next to `workspace.webp` and `zen-focus.webp` — via the existing fidelity compositor (`22e85679`), attached to the PR.
- [ ] **Step 3:** `just verify` — PASS; axe AA both themes on `/novels/$id`.
- [ ] **Step 4: Commit** — `chore(docs): the W3 proof — frames and side-by-side`.

### Task 13: Whole-branch review

- [ ] Fresh reviewer (not the implementer's context, Reviewer model) reads the branch against the spec: fidelity of every surface, interim table complete with live issue numbers, deviation log untouched (D-3 needs no entry — the draft itself is written out), gates' outputs, Review Focus 1–6 each answered. Findings become issues or fixes before merge; the branch lands as a merge commit with a plain-language PR title.
