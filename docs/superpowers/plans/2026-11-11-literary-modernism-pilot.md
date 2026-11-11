# Literary Modernism pilot (S0, W0–W2) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The Stitch norm becomes the app: tokens, fonts and chrome move to Literary Modernism, and the Shelf ships 1:1 against its draft as the pilot proof.

**Architecture:** Vertical slice on the existing shell — the token file is rewritten in place (mechanism unchanged: `light-dark()` + `color-scheme`), the shell primitives (`web/ui`, `web/components`) take the drafted geometry, and the writing capability's shelf page (`NovelsPage.tsx`) is recomposed against `docs/design/stitch/screens/library/shelf`. One branch, one PR; a blocking Stitch round (S0) completes the norm first.

**Tech Stack:** Tailwind v4 (`@theme inline` tokens), React 19, TanStack Router, self-hosted woff2 (EB Garamond + Plus Jakarta Sans), vitest, Playwright E2E, Stitch MCP for design gaps.

**Spec:** `docs/superpowers/specs/2026-11-11-literary-modernism-frontend-design.md` — the plan argues from it; executors read both. Norm for values: `docs/design/stitch/DESIGN.md` + the exported screens.

## Global Constraints

- Tokens live only in `web/globals.css`; capabilities carry utilities, never a palette.
- Every colour is a `light-dark()` pair; AA 4.5:1 text / 3:1 icons, measured in **both** themes, values in the PR.
- No CDN, no icon font, no native unstyled widget; fonts self-hosted under `web/public/fonts/` (OFL notice kept).
- Copy through i18n catalogs en/de/fr — same keys, sorted; a missing key is a build error. Draft labels inform `de`.
- 100 % fidelity to the drafts; every departure lands in the spec's deviation log (§6.9) with the owner's approval.
- English in code and comments; user-visible text only through catalogs.
- Commits: conventional; user-visible changes are `feat(web): …` with a real `User-visible:` line; docs/archive work is `chore(docs): …`; agent commits end with `Assisted-by: OpenCode (<model>)` via `--trailer`. Nothing commits before the task's gates are green.
- Gates: `just check` (fast), `just test-file <path>`, `just verify`, the capability E2E; a gate counts only when its output was read.

## Review Focus

1. **Dark contrast of the parchment pairs** — muted/amber/state text on card and soft grounds in dark mode; expect AA 4.5:1. Pinned by Task 3's contrast table test and the axe E2E leg.
2. **forced-colors fallback** — covers, keycaps and the new buttons must survive forced-colors (no information by colour alone). Pinned in Task 8's Cover test and Task 5's buttonClasses test comment + E2E axe leg.
3. **Long titles** — hero and card titles truncate (density, not data loss; `aria-label` carries the full string). Pinned in Task 10's NovelsPage test.
4. **Keyboard path on the new shelf** — search, filter, view toggle and `more_horiz` menu reachable and operable by keyboard with the amber ring visible. Pinned in Task 10's test and the E2E.
5. **Locale completeness** — eyebrow uppercase/tracking with French accents; all three catalogs carry every new key. Pinned by the i18n build error and Task 10's catalog step.

---

### Task 1: S0 — the Stitch round completes the norm

**Files:**
- Create: `docs/design/stitch/screens/library/shelf-dark.html` + `.webp`, `screens/library/shelf-states.*` (as produced)
- Create: `docs/design/stitch/dark-tokens.md` — the extracted dark values with provenance
- Modify: `docs/design/stitch/README.md` (index rows), spec §7 (gaps marked answered)

**Interfaces:**
- Produces: the dark values Task 3 writes into `globals.css` — `area-*` and `state-*` dark pairs, dark cover grounds/inks, the dark shelf as G-2's answer.

- [ ] **Step 1: Run the round** — via Stitch MCP on project `15314899202287259920`: generate the dark Shelf (G-2) and the Shelf's undrafted states — loading, error, empty, >12 books (G-4); ask for the Midnight-Ink values of the five area hues and three state colours (G-1) on those screens. One batched round; if a value fails AA (check G-3's `#D39562`/`#1D140D`), ask for the adjusted pair in the same round.
- [ ] **Step 2: Export into the archive** — the same download path the README documents; slugs `shelf-dark`, `shelf-empty`, `shelf-many-books` (and `shelf-loading`/`shelf-error` if produced); index rows added.
- [ ] **Step 3: Write `dark-tokens.md`** — one table per gap: token, light (from DESIGN.md), dark (from the round's screens, named by screen), the measured contrast.
- [ ] **Step 4: Mark the spec's gaps answered** (G-1 … G-4 get their answer's file name).
- [ ] **Step 5: Commit** — `chore(docs): the S0 Stitch round completes the design norm`

### Task 2: Plus Jakarta Sans, self-hosted

**Files:**
- Create: `web/public/fonts/plus-jakarta-sans-{latin,latext}-{400,500,600,700}.woff2`, `web/public/fonts/PJS-OFL.txt`
- Modify: `web/globals.css` (after the EB Garamond block), `web/index.html` (root font stack if it names a family)
- Test: `web/ui/typeScale.test.ts` stays green; new assertion in `web/globals.css`-adjacent test is not needed — the font-family is a token change verified visually and by the E2E screenshots.

**Interfaces:**
- Produces: `--font-ui: "Plus Jakarta Sans", <current system stack>` consumed by `body` and every `text-*` utility via the theme.

- [ ] **Step 1: Fetch and subset** the six static instances (latin + latin-ext, weights 400/500/600/700) the way the EB Garamond pipeline did; commit with the OFL notice.
- [ ] **Step 2: `@font-face` ×4 weights ×2 subsets** in `globals.css`, `font-display: swap`; set the UI family on `body`.
- [ ] **Step 3: Verify** — `just check`; the dev app renders UI text in PJS, prose untouched (`.ProseMirror` keeps EB Garamond).
- [ ] **Step 4: Commit** — `feat(web): the UI voice is Plus Jakarta Sans, self-hosted` + `User-visible:` line.

### Task 3: The token rewrite — parchment, surface ladder, radii, shadows, dock

**Files:**
- Modify: `web/globals.css:18-91` (token block), `:125-170` (`@theme inline`), dock width consumers in `app/capabilities/writing/web/NovelPage.tsx` (`w-88` → `w-84`/`21rem`)
- Test: `web/ui/typeScale.test.ts` (allowlist), new `web/ui/tokens.test.ts`

**Interfaces:**
- Consumes: Task 1's `dark-tokens.md`, Task 2's font token.
- Produces: the full ladder — `--surface-container-lowest/low/(default)/high/highest`, `--outline`, `--outline-variant`, `--secondary`, `--secondary-foreground`, `--inverse-surface/foreground`, `--cover-slate(-ink)`; `--radius-sm/-control/-surface` = 4/8/12 px; `--shadow-card`; dock `21rem`.

- [ ] **Step 1: Write the failing test** — `tokens.test.ts` parses `globals.css` and asserts each §6.2 pair resolves to the spec's values (light first, dark from `dark-tokens.md`), and that the radius/shadow/dock tokens exist.
- [ ] **Step 2: Run** `just test-file web/ui/tokens.test.ts` — FAIL.
- [ ] **Step 3: Rewrite the token block** per spec §6.2/§6.4 — values verbatim, comments keep the AA measurements; `@theme inline` maps every new name; `--card` follows the screens (`#FFF8F2` family) per §6.2's screen-wins rule.
- [ ] **Step 4: Widen the `typeScale.test` allowlist** for the area-token accents (eyebrow, sparkline, progress, pill) and update its fixtures.
- [ ] **Step 5: Run** `just check` and the axe E2E leg in both themes — PASS, with the contrast table pasted into the PR.
- [ ] **Step 6: Commit** — `feat(web): the shell wears Literary Modernism tokens` + `User-visible:` line.

### Task 4: The type scale merge

**Files:**
- Modify: `web/globals.css` (`@theme inline` text tokens, `.ProseMirror` headings), `web/ui/typeScale.test.ts`
- Test: `web/ui/typeScale.test.ts`

**Interfaces:**
- Produces: `text-eyebrow` (11/16, 600, 0.08 em, uppercase), retuned `--text-meta--line-height` 1.42, `--text-label--line-height` 1.38, `--text-body--line-height` 1.57, `--text-emph--line-height` 1.47, `--text-hero--line-height` 1.14/700, prose headings 26/34 and 21/28 (600), `tabular-nums` utility (`font-variant-numeric`).

- [ ] **Step 1: Extend `typeScale.test`** — eyebrow joins the on-scale census; the line-height pairs assert from the token table.
- [ ] **Step 2: Run** — FAIL; **Step 3: apply the token changes**; **Step 4: run** `just test-file web/ui/typeScale.test.ts` + `just check` — PASS.
- [ ] **Step 5: Commit** — `feat(web): the drafted type scale, eyebrow to hero` + `User-visible:` line.

### Task 5: The button ladder

**Files:**
- Modify: `web/ui/Button.tsx`, `web/ui/buttonClasses.test.ts`
- Test: `web/ui/buttonClasses.test.ts`

**Interfaces:**
- Produces: `BUTTON_SIZES = ["sm","md","lg"]` → `h-7` (28, dense floor) / `h-9` (36) / `h-10` (40); all controls `rounded-[var(--radius-control)]` (8 px); `focus-visible:ring-2 ring-focus ring-offset-1`; primary `bg-cover-sepia text-[#FAF8F5] shadow-sm hover:opacity-95`; secondary on card/panel grounds with `bg-soft` hover; icon variant `p-1.5`.

- [ ] **Step 1: Update `buttonClasses.test`** to the new matrix (sizes, radius token, ring offset, variant paints).
- [ ] **Step 2: Run** — FAIL. **Step 3: rewrite the matrices in `Button.tsx`**; audit call sites for the size they should now carry (shelf waits for Task 10).
- [ ] **Step 4: Run** `just test-file web/ui/buttonClasses.test.ts` + `just check` — PASS.
- [ ] **Step 5: Commit** — `feat(web): the drafted button ladder` + `User-visible:` line.

### Task 6: Field shells and the custom select

**Files:**
- Modify: `web/ui/field.tsx` (`controlClass`, `Input`, `Select`, `Textarea`), `web/ui/fieldAria.test.ts` (unchanged behaviour), select chevron in `web/ui/icons.tsx`
- Test: `web/ui/fieldAria.test.ts`, manual E2E axe leg

**Interfaces:**
- Produces: `controlClass` → `h-9` default (`h-8` compact), 8 px radius, amber focus ring; `Select` renders the custom chevron (SVG background), native popup stays native (color-scheme follows).

- [ ] **Step 1–4:** chevron glyph in `icons.tsx` (+ its test), `controlClass` retune, `just test-file web/ui/icons.test.tsx web/ui/fieldAria.test.ts`, `just check` — PASS.
- [ ] **Step 5: Commit** — `feat(web): drafted field shells with the custom chevron` + `User-visible:` line.

### Task 7: The icon set grows the drafted concepts

**Files:**
- Modify: `web/ui/icons.tsx`, `web/ui/icons.test.tsx`
- Test: `web/ui/icons.test.tsx`

**Interfaces:**
- Produces: new 16 px / 1.5-stroke glyphs for the drafted concepts, named by concept: `IconBookmarkCollection`, `IconEditNote`, `IconHub`, `IconSchema`, `IconRadar`, `IconWaves`, `IconFoggy`, `IconInkHighlighter`, `IconAutoStories`, `IconHistoryEdu`, `IconInsights`, `IconTune`, `IconGridView`, `IconViewList`, `IconMoreHoriz`, `IconLocalFire`, `IconMenuBook`, `IconCheckCircle`, `IconPerson` (skip any that exist).

- [ ] **Step 1: Extend the test** with the new names and their `aria-hidden` contract. **Step 2:** FAIL. **Step 3: draw the glyphs** in the set's stroke language; deviation #1 covers the style. **Step 4:** `just test-file web/ui/icons.test.tsx` — PASS.
- [ ] **Step 5: Commit** — `feat(web): the icon set learns the drafted concepts` + `User-visible:` line.

### Task 8: Cover composition and the slate tone

**Files:**
- Modify: `web/ui/Cover.tsx`, `web/ui/Cover.test.tsx`
- Test: `web/ui/Cover.test.tsx`

**Interfaces:**
- Produces: `CoverTone = "pale" | "sepia" | "ink" | "slate"`; spine strip 5 px left (tone-darkened), sepia's 1 px gold inset frame at 5 px offset, pale's eyebrow top-left, title bottom-aligned EB Garamond; 3:4 aspect; hash assigns across four tones; forced-colors keeps the title readable (contrast by structure, not colour).

- [ ] **Step 1: Extend `Cover.test`** — four tones hash-assigned, spine/frame/eyebrow classes per tone, `aria-label` keeps title + word count. **Step 2:** FAIL. **Step 3: implement**. **Step 4:** `just test-file web/ui/Cover.test.tsx` — PASS.
- [ ] **Step 5: Commit** — `feat(web): covers as book objects, four tones` + `User-visible:` line.

### Task 9: Keycaps, finding cards, rail and top bar chrome

**Files:**
- Create: `web/ui/Keycap.tsx` (+ test)
- Modify: `web/ui/Notice.tsx` (+ `noticeClasses.test.ts`), `web/components/IconRail.tsx`, `web/components/TopBar.tsx`
- Test: the components' test files

**Interfaces:**
- Produces: `Keycap({ children })` (1 px border, 4 px radius, meta type, `kbd` semantics); Notice gains the severity top rule (warning amber / danger rust) with actions row (primary/ghost pair); rail and top bar sit on `--panel` with hairline `--border`, area-hue icons, eyebrow section labels.

- [ ] **Step 1: Tests first** — Keycap renders `kbd` with the label; Notice severity rule; rail/top bar class fixtures. **Step 2:** FAIL. **Step 3: implement**; **Step 4:** `just test-file` the three + `just check` — PASS; axe leg for the rail's focus states.
- [ ] **Step 5: Commit** — `feat(web): drafted chrome — keycaps, severity rules, rail and top bar` + `User-visible:` line.

### Task 10: The Shelf, 1:1

**Files:**
- Modify: `app/capabilities/writing/web/NovelsPage.tsx` (recompose; split sections into `app/capabilities/writing/web/shelf/` files as it grows), `app/capabilities/writing/web/i18n/{en,de,fr}.json`
- Test: `app/capabilities/writing/web/NovelsPage.test.tsx`, the writing E2E

**Interfaces:**
- Consumes: Tasks 2–9 primitives; `useNovelsQuery`, `formatRelative`, `dirty`-derived save state.
- Produces: the drafted page — hero (cover, progress, tabular words, last-edited, "Weiterschreiben in Kapitel 3" CTA), metrics strip, search/filter/view-toggle row, book grid with status pills + targets + `more_horiz` menu, activity banner (Schreibziel, Wochenschnitt, sparkline), empty state per S0's export; interim logic per spec §6.6's table, each missing field's code comment naming its follow-up issue number.

- [ ] **Step 1: Catalogs first** — every new label in en/de/fr (de from the draft), sorted, same keys; the i18n build fails on a miss.
- [ ] **Step 2: Tests** — NovelsPage.test: hero derives from the active novel; metrics from the list; interim fields render their §6.6 neutral (streak "—", target bar hidden, pill "Entwurf"); search filters titles; toggle switches views; long title truncates with full `aria-label`; every drafted section present. **Step 3:** FAIL. **Step 4: implement** the composition.
- [ ] **Step 5: E2E** — writing E2E green, axe in both themes, keyboard path across search/filter/toggle/menu.
- [ ] **Step 6: Commit** — `feat(writing): the shelf in Literary Modernism, 1:1` + `User-visible:` line.

### Task 11: The follow-up issues

**Files:** none in the tree — GitHub issues + `docs/superpowers/follow-ups.md`

- [ ] **Step 1: File the index issue** (label `follow-up-index`) for the pilot wave.
- [ ] **Step 2: One child per "issue" row in spec §6.6** (streak, goal/week-sparkline, per-book target, status field, figure/tag search) — label `follow-up` + `area:` per row, body naming the trigger and the interim logic it replaces.
- [ ] **Step 3: Add the wave's row to `docs/superpowers/follow-ups.md`; commit** — `chore(docs): the pilot's follow-up index`.

### Task 12: The living proof — gallery, master frames, side-by-side

**Files:**
- Modify: `app/capabilities/settings/web/DesignGallery.tsx` (new pairs incl. slate cover and radius ladder), `scripts/screenshots.py` (re-shoot the shelf frame, add the dark shelf frame; follow the existing 01–19 pattern)
- Test: the settings E2E's `/design` leg, the screenshot-updated E2E frames

- [ ] **Step 1: DesignGallery on the new tokens** (+ its test if it has fixtures).
- [ ] **Step 2: Re-shoot** the shelf master frames (light + dark) via the screenshots script; commit them to `assets/screenshots/` following the naming convention.
- [ ] **Step 3: The side-by-side artifact** — one image per theme: the E2E screenshot next to `docs/design/stitch/screens/library/shelf.webp` (Task 1's dark export for dark), produced by a small script step, attached to the PR.
- [ ] **Step 4: `just verify`** — PASS; **Step 5: Commit** — `chore(docs): the pilot's proof — gallery, frames, side-by-side`.

### Task 13: Whole-branch review

- [ ] Fresh reviewer (not the implementer's context) reads the branch against the spec: fidelity of every surface, the deviation log complete, gates' outputs, follow-up issues real. Findings become issues or fixes before merge; the branch lands as a merge commit with a plain-language PR title (no conventional grammar — the commit subjects carry it).
