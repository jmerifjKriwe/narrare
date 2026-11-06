# Visual identity and shell chrome — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the eleven points of the #587 review as one wave: the mechanical fixes, the type scale, typographic covers, area hues, a readable rail and a user-owned theme.

**Architecture:** Tokens stay in `web/globals.css` (one design surface); covers stay deterministic and file-free; the rail's expansion is CSS-only in a fixed slot; the theme is one nullable column on the user row with `light-dark()` tokens and a `localStorage` paint hint that is never a source. No new primitive, no new store, no new component other than one settings page.

**Tech Stack:** Python 3.14 · FastAPI · SQLAlchemy async · Alembic · Postgres · Vite · React 19 · TanStack Router · Tailwind v4 (`@theme inline`) · React Aria · Vitest · Playwright.

**Spec:** `docs/superpowers/specs/2026-11-06-visual-identity-and-shell-design.md`

## Global Constraints

- English in code, tests and developer documentation; user-visible text in en, de and fr through `i18n/*.json`. A missing key is a build error.
- One capability is one folder; a capability never imports another capability. Shared UI lives in `web/ui/` and `web/components/`.
- Tokens only from `web/globals.css`; capability folders carry utilities, never a palette.
- No new primitive, no second data store, no new gate beyond the one approved scale test.
- No follow-up issues are filed for this work. #544, #573 and #555 close from their commits; #450 is already closed.
- Every `feat`/`fix` commit carries a real `User-visible:` line and the trailer `Assisted-by: OpenCode (<model>)` via `git commit --trailer`. Author and committer stay human.
- Nothing is committed before the task's review is green.
- The migration is additive and nullable.
- Gates: `just check` · `just test-file <path>` · `just test-e2e <capability>` · `just verify all` before the merge.
- Frontend single file: `pnpm --dir web vitest run <path-relative-to-web>`.
- One branch, eleven commits, one PR, one merge commit.

## Review Focus

The spec implies these and no task's happy path covers them; each gets its test in the named task.

1. **A 120-character title with no genre** (the setup demo) — the cover clamps to three lines and the eyebrow falls back to the language, with no overflow and no empty line. (Task 6.)
2. **The rail at its two breakpoints** — hovering at 1024 moves neither the page nor the dock, and the workspace at 1280 keeps its own rail timing. (Task 8.)
3. **The OS flips dark/light at runtime** — "System" follows live; a forced value does not move. (Task 10.)
4. **A pristine form** — the prompt and provider forms ask nothing until something actually changed, and a dirty one asks at all three doors. (Task 4.)
5. **The palette chip while a dialog is open** — it refuses exactly like ⌘K; no second focus trap. (Task 3.)

---

## File Structure

| File | Responsibility |
| --- | --- |
| `web/ui/typeScale.test.ts` | the scale's two pins: token values and the off-scale sweep |
| `web/lib/platform.ts` | `isMac()` for the palette key label |
| `web/lib/dirty.ts` | `dirtyFields(current, snapshot)` — the one dirty predicate |
| `web/lib/theme.ts` | `applyTheme`, `adoptServerTheme`, the paint-hint key |
| `web/ui/Cover.tsx` | tone, composition, eyebrow; no longer borrows action tokens |
| `web/components/IconRail.tsx` | sizes, area hue, the hover/focus expansion |
| `app/capabilities/settings/web/AppearancePage.tsx` | the theme control |
| `app/capabilities/settings/{schemas,service,router}.py` | `theme` read plus its own write endpoint |
| `scripts/screenshots.py` | five light images plus two chosen-dark ones |

---

### Task 1: The scale gate and its three strays (A1)

Closes #544 and #573's scale half.

**Files:**
- Create: `web/ui/typeScale.test.ts`
- Modify: `web/lib/save.tsx:162,169`, `web/ui/Dialog.tsx:35`, `app/capabilities/prompts/web/PromptsPage.tsx:565`

**Interfaces:**
- Produces: `typeScale.test.ts` — Task 2 adds the token-value pin to the same file; Task 7 adds the area-hue sweep.

- [ ] **Step 1: Write the failing sweep test**

```ts
// @vitest-environment node
/**
 * The scale's gate. The census in spec §11 is a command a human runs; this is
 * the same measurement in the suite, so a `text-lg` cannot ride in unnoticed
 * (#544, #573). Only `className="…"` literals are read — the shape §11
 * measures; `className={…}` templates are outside it on purpose.
 */
import { readFileSync, readdirSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

const WEB = new URL("..", import.meta.url).pathname;
const REPO = new URL("../..", import.meta.url).pathname;
const OFF_SCALE = /^text-(sm|base|lg|xl|2xl|3xl)$/;
const CLASS = /className="([^"]*)"/g;

function sources(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return entry.name === "node_modules" ? [] : sources(path);
    return /\.tsx?$/.test(entry.name) && !/\.test\.tsx?$/.test(entry.name) ? [path] : [];
  });
}

const scanned = [
  ...sources(join(REPO, "app/capabilities")).filter((path) => path.includes("/web/")),
  ...sources(join(WEB, "lib")),
  ...sources(join(WEB, "components")),
];

describe("the type scale's census", () => {
  it("carries no off-scale text utility in capability, lib or component sources", () => {
    const offences: string[] = [];
    let seen = 0;
    for (const file of scanned) {
      for (const [, value] of readFileSync(file, "utf8").matchAll(CLASS)) {
        seen += 1;
        for (const token of value.split(/\s+/)) {
          if (OFF_SCALE.test(token)) offences.push(`${relative(REPO, file)}: ${token}`);
        }
      }
    }
    // A gate that walks an empty set passes vacuously; the source tree is not empty.
    expect(seen).toBeGreaterThan(250);
    expect(offences).toEqual([]);
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pnpm --dir web vitest run ui/typeScale.test.ts`
Expected: FAIL, `offences` containing `web/lib/save.tsx: text-sm` and `app/capabilities/prompts/web/PromptsPage.tsx: text-lg`.

- [ ] **Step 3: Fix the three sites**

- `web/lib/save.tsx:162`: `className="text-meta text-danger"`.
- `web/lib/save.tsx:169`: `className="text-meta text-muted"`.
- `web/ui/Dialog.tsx:35`: `className="text-emph font-semibold"`.
- `app/capabilities/prompts/web/PromptsPage.tsx:565`: `className="text-emph font-semibold"`.

`text-emph` (15, 600) is the scale's section title; `text-title` is the page title, one per page. `text-meta` is the runhead status's step, beside `text-body`.

- [ ] **Step 4: Run it to verify it passes**

Run: `pnpm --dir web vitest run ui/typeScale.test.ts`
Expected: PASS, 1 test.

- [ ] **Step 5: Commit**

```bash
git add web/ui/typeScale.test.ts web/lib/save.tsx web/ui/Dialog.tsx app/capabilities/prompts/web/PromptsPage.tsx
git commit --trailer "Assisted-by: OpenCode (<model>)" -m "fix(ui): the scale's strays and a test that finds them

User-visible: the dialog title, the prompts heading and the save status
now use the app's own type scale instead of Tailwind's defaults.

Closes #573"
```

---

### Task 2: The scale grows one step on text (B1)

**Files:**
- Modify: `web/globals.css:123-134`, `web/ui/typeScale.test.ts`, `app/capabilities/writing/e2e/test_novels_e2e.py`

**Interfaces:**
- Consumes: `typeScale.test.ts` from Task 1.
- Produces: `--text-meta: 0.75rem`, `--text-label: 0.8125rem`, `--text-body: 0.875rem`; every later task sizes against these.

- [ ] **Step 1: Add the failing pin**

Append to `web/ui/typeScale.test.ts`:

```ts
describe("the scale's steps", () => {
  it("reads 12 / 13 / 14 / 15 / 20 / 28", () => {
    const css = readFileSync(join(WEB, "globals.css"), "utf8");
    const step = (name: string) =>
      new RegExp(`--text-${name}: ([\\d.]+)rem;`).exec(css)?.[1] ?? null;
    expect(
      Object.fromEntries(
        ["meta", "label", "body", "emph", "title", "hero"].map((name) => [name, step(name)]),
      ),
    ).toEqual({
      meta: "0.75",
      label: "0.8125",
      body: "0.875",
      emph: "0.9375",
      title: "1.25",
      hero: "1.75",
    });
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pnpm --dir web vitest run ui/typeScale.test.ts`
Expected: FAIL, meta `0.6875`, label `0.75`, body `0.8125`.

- [ ] **Step 3: Change the three tokens**

`web/globals.css`, in `@theme inline`: `--text-meta: 0.75rem;`,
`--text-label: 0.8125rem;`, `--text-body: 0.875rem;`. Leading stays attached
(`1.45 / 1.45 / 1.55`). `--text-emph`, `--text-title`, `--text-hero` do not move.

- [ ] **Step 4: Run it to verify it passes**

Run: `pnpm --dir web vitest run ui/typeScale.test.ts`
Expected: PASS, 2 tests.

- [ ] **Step 5: Pin the rendered sizes**

In `app/capabilities/writing/e2e/test_novels_e2e.py`, after the existing
`sizes` assertion (around line 78), add:

```python
    # The text steps render at the scale, not just in the CSS: a token edit
    # that never reaches a surface fails here as a pixel. `text-label` is not
    # pinned here — its lines (genre, language) are conditional; the token pin
    # in typeScale.test.ts covers that step.
    steps = page.evaluate(
        """() => {
          const hero = document.querySelector('section[aria-labelledby="novels-continue"]');
          return {
            body: getComputedStyle(document.querySelector('header .truncate')).fontSize,
            meta: getComputedStyle(hero.querySelector('p.text-meta')).fontSize,
          };
        }"""
    )
    assert steps == {"body": "14px", "meta": "12px"}, steps
```

- [ ] **Step 6: Run the E2E**

Run: `uv run pytest app/capabilities/writing/e2e/test_novels_e2e.py -v -m e2e --timeout=60`
Expected: PASS (the stack must be up; `just test-e2e writing` runs the same file).

- [ ] **Step 7: Commit**

```bash
git add web/globals.css web/ui/typeScale.test.ts app/capabilities/writing/e2e/test_novels_e2e.py
git commit --trailer "Assisted-by: OpenCode (<model>)" -m "feat(ui): the UI text steps one rung up

User-visible: labels, body text and meta lines read one step larger
(12 / 13 / 14 px); headings and the prose keep their size.

The three smallest steps were the ones the review found hard to read; the
title steps were not, and leaving them untouched keeps the three pinned
E2E sizes and the prose/UI relationship where they are."
```

---

### Task 3: A door to the palette (A2 + #555 + A6)

Closes #555.

**Files:**
- Create: `web/lib/platform.ts`, `web/lib/platform.test.ts`
- Modify: `web/components/TopBar.tsx:65-70`, `web/routes/__root.tsx:76-100,137`, `web/components/Palette.tsx:519`, `web/components/Palette.test.tsx`, `i18n/en.json`, `i18n/de.json`, `i18n/fr.json`, `app/capabilities/writing/e2e/test_shell_chrome_e2e.py`

**Interfaces:**
- Produces: `isMac(): boolean`; catalog keys `shell.paletteOpen`, `shell.paletteKeyMac`, `shell.paletteKeyOther`; `workspace.shortcutHints` gains `{key}`; `TopBar` gains `onOpenPalette: () => void`.

- [ ] **Step 1: Write the failing platform test**

```ts
// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { isMac } from "./platform";

const original = navigator.userAgent;

afterEach(() => {
  Object.defineProperty(navigator, "userAgent", { value: original, configurable: true });
});

describe("isMac", () => {
  it("reads a Mac agent as a Mac", () => {
    Object.defineProperty(navigator, "userAgent", {
      value: "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36",
      configurable: true,
    });
    expect(isMac()).toBe(true);
  });

  it("reads a Linux agent as not a Mac", () => {
    Object.defineProperty(navigator, "userAgent", {
      value: "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
      configurable: true,
    });
    expect(isMac()).toBe(false);
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pnpm --dir web vitest run lib/platform.test.ts`
Expected: FAIL, cannot resolve `./platform`.

- [ ] **Step 3: Implement the helper and wire the chip**

`web/lib/platform.ts`:

```ts
/** True on Apple platforms, where the command key is the keyboard's ⌘. */
export function isMac(): boolean {
  return /Mac|iPhone|iPad|iPod/.test(navigator.userAgent);
}
```

`web/routes/__root.tsx`: extract the refusal into one handler and pass it down.

```tsx
  /** A dialog owns the stage; the palette refuses exactly as the key does. */
  function openPalette(): void {
    if (document.querySelector('[role="dialog"]') !== null) return;
    setPaletteOpen(true);
  }
  // …
  {chromeless ? null : <TopBar onOpenPalette={openPalette} />}
```

`web/components/TopBar.tsx`: the prop and the chip become a button:

```tsx
export function TopBar({ onOpenPalette }: { onOpenPalette: () => void }) {
  // …
  const key = t(isMac() ? "shell.paletteKeyMac" : "shell.paletteKeyOther");
  // …
  <button
    type="button"
    onClick={onOpenPalette}
    aria-label={t("shell.paletteOpen")}
    className="rounded-[var(--radius)] border border-border bg-card px-1.5 py-0.5 font-mono text-meta leading-none text-muted hover:bg-soft focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus"
  >
    {key}
  </button>
```

`web/components/Palette.tsx:519`: `{t("workspace.shortcutHints", { key })}` with
the same `isMac()` choice.

- [ ] **Step 4: Catalog edits (en / de / fr)**

Add, translated in all three:
`shell.paletteOpen` — "Open the command palette" / "Befehlspalette öffnen" /
"Ouvrir la palette de commandes";
`shell.paletteKeyMac` — `"⌘K"` in all three;
`shell.paletteKeyOther` — "Ctrl K" / "Strg K" / "Ctrl K".
Change `workspace.shortcutHints` to end `{key} palette` (de: `· {key} Palette`),
and `palette.searchLabel` to end with `…` (de `… suchen`, fr `…`).

- [ ] **Step 5: Update the palette footer test**

`web/components/Palette.test.tsx` asserts the footer string; change it to the
interpolated form the component now renders
(`t("workspace.shortcutHints", { key: "⌘K" })` is not stable across platforms —
assert on the catalog's template parts or on `screen.getByText(/Palette/)`).

- [ ] **Step 6: Add the E2E**

In `app/capabilities/writing/e2e/test_shell_chrome_e2e.py`, two nodes:

```python
def test_the_palette_key_opens_it_by_pointer(page: Page, stack: Stack) -> None:
    page.goto(f"{WEB}/")
    page.get_by_role("button", name="Befehlspalette öffnen").click()
    expect(page.get_by_role("dialog", name="Befehlspalette")).to_be_visible()


def test_the_palette_key_refuses_while_a_dialog_owns_the_stage(page: Page, stack: Stack) -> None:
    page.goto(f"{WEB}/")
    page.get_by_role("button", name="Neues Buch").click()
    page.get_by_role("button", name="Befehlspalette öffnen").click()
    expect(page.get_by_role("dialog")).to_have_count(1)
```

Use the module's existing `WEB` constant and the real trigger label for the new
book dialog if it differs.

- [ ] **Step 7: Run the tests**

Run: `pnpm --dir web vitest run lib/platform.test.ts components/Palette.test.tsx`
then `just test-e2e writing`.
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add web/lib/platform.ts web/lib/platform.test.ts web/components/TopBar.tsx web/routes/__root.tsx web/components/Palette.tsx web/components/Palette.test.tsx i18n app/capabilities/writing/e2e/test_shell_chrome_e2e.py
git commit --trailer "Assisted-by: OpenCode (<model>)" -m "feat(shell): the palette gets a door and the key tells the truth

User-visible: the ⌘K chip in the bar opens the command palette with a
click, and on Linux and Windows it reads Strg K / Ctrl K instead of ⌘K.

Closes #555"
```

---

### Task 4: Leave guards on the two explicit-save forms (A3)

**Files:**
- Create: `web/lib/dirty.ts`, `web/lib/dirty.test.ts`
- Modify: `app/capabilities/prompts/web/PromptsPage.tsx`, `app/capabilities/settings/web/ProvidersPanel.tsx`, `i18n/*.json`
- Test: `app/capabilities/prompts/e2e/test_prompts_e2e.py`

**Interfaces:**
- Produces: `dirtyFields<T extends Record<string, unknown>>(current: T, snapshot: T): (keyof T)[]`; catalog key `dirty.confirmLeave`.

- [ ] **Step 1: Write the failing predicate test**

```ts
import { describe, expect, it } from "vitest";
import { dirtyFields } from "./dirty";

describe("dirtyFields", () => {
  it("finds nothing in an unchanged form", () => {
    expect(dirtyFields({ name: "a", key: "" }, { name: "a", key: "" })).toEqual([]);
  });

  it("names the field that changed", () => {
    expect(dirtyFields({ name: "a", key: "x" }, { name: "a", key: "" })).toEqual(["key"]);
  });

  it("compares shallowly and by value", () => {
    expect(dirtyFields({ a: 1, b: [1] }, { a: 1, b: [1] })).toEqual([]);
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pnpm --dir web vitest run lib/dirty.test.ts`
Expected: FAIL, cannot resolve `./dirty`.

- [ ] **Step 3: Implement**

```ts
/** The fields whose value differs from the form's load-time snapshot. */
export function dirtyFields<T extends Record<string, unknown>>(
  current: T,
  snapshot: T,
): (keyof T)[] {
  return (Object.keys(current) as (keyof T)[]).filter((key) => current[key] !== snapshot[key]);
}
```

- [ ] **Step 4: Wire the prompt editor**

- Snapshot `detail.effective_content` when the detail load lands; `dirty` is
  `content !== snapshot`.
- `useBlocker({ shouldBlockFn: () => askToLeave(), enableBeforeUnload: () => dirty })`
  in `PromptsPage`, where `askToLeave(): Promise<boolean>` opens the shell
  `Dialog` (`title={t("save.leaveTitle")}`, body `t("dirty.confirmLeave")`,
  buttons `t("save.leaveStay")` / `t("save.leaveGo")`) and resolves the answer.
- The same `askToLeave()` wraps the editor's close and each row's Edit button
  (`onEdit`) — a dirty editor asks at all three doors. A pristine one never asks.

Add `dirty.confirmLeave` in en/de/fr: "This form has changes that were not
saved. Leave anyway?" / "Dieses Formular hat ungespeicherte Änderungen.
Trotzdem wechseln?" / "Ce formulaire contient des modifications non
enregistrées. Quitter quand même ?"

- [ ] **Step 5: Wire the provider form**

`ProvidersPanel`: snapshot `form` when the form is opened (`startEditing` /
new); `dirty = dirtyFields(form, snapshot).length > 0`; the same three doors —
Cancel, another `startEditing`, and `useBlocker` for navigation.

- [ ] **Step 6: Add the E2E**

In `app/capabilities/prompts/e2e/test_prompts_e2e.py`: open an editor, type
into the textarea, click the editor's Cancel, expect the confirm dialog; choose
"Stay", expect the text still there; choose "Leave anyway", expect the editor
gone. A pristine open-and-cancel asks nothing.

- [ ] **Step 7: Run the tests**

Run: `pnpm --dir web vitest run lib/dirty.test.ts` then `just test-e2e prompts`.
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add web/lib/dirty.ts web/lib/dirty.test.ts app/capabilities/prompts/web/PromptsPage.tsx app/capabilities/settings/web/ProvidersPanel.tsx i18n app/capabilities/prompts/e2e/test_prompts_e2e.py
git commit --trailer "Assisted-by: OpenCode (<model>)" -m "feat(settings): a dirty form asks before it is thrown away

User-visible: closing, re-targeting or leaving a prompt or provider form
with unsaved text now asks first; an untouched form never asks."
```

---

### Task 5: The `text-danger` rule stops lying, the diff markers, and technical inputs (A4 + A5)

Closes #544.

**Files:**
- Modify: `docs/superpowers/specs/2026-10-31-narrare-ui-b-pur-design.md` (§11), `app/capabilities/prompts/web/PromptsPage.tsx`, `app/capabilities/settings/web/ProvidersPanel.tsx:478-514`, `app/capabilities/settings/e2e/test_profiles_e2e.py`

**Interfaces:**
- Produces: no new code; the spec's census target is narrowed to the folders it measured, and the diff view joins the named surfaces.

- [ ] **Step 1: Add the failing E2E assertions**

In `test_profiles_e2e.py`, when the profile form is open, assert:
`model` input `spellcheck="false"` and `autocomplete="off"`; the API key input
`autocomplete="new-password"` and `type="password"`.
Run: `just test-e2e settings` — expected FAIL on the missing attributes.

- [ ] **Step 2: Add the attributes**

Profile name, `baseUrl`, `model`: `spellCheck={false} autoComplete="off"`.
API key: `type="password" spellCheck={false} autoComplete="new-password"`.

- [ ] **Step 3: Give the diff view its own markers**

In `PromptsPage.tsx`, the diff render's `border-primary` becomes `border-success`
(an added line) and `border-danger` stays (a removed line). `--primary` keeps one
meaning: an action. No new token.

- [ ] **Step 4: Narrow the spec**

In §11, replace `text-danger = 0 outside Notice` with the measured statement:
the census scans `app/capabilities/*/web/*.tsx` and `web/components/*.tsx`, and
`text-danger` outside `Notice` there is 0; `web/ui/field.tsx` (a field's error
line), `web/ui/JobStatus.tsx` (a failed job row) and `web/lib/save.tsx` (the
save indicator) carry it outside the measured folders, each as
`role="alert"`/`role="status"`, none of them a notice surface. The prompts diff
view names its two markers as `border-success` / `border-danger`.

- [ ] **Step 5: Run the E2E**

Run: `just test-e2e settings` then `just test-e2e prompts`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add docs/superpowers/specs/2026-10-31-narrare-ui-b-pur-design.md app/capabilities/prompts/web/PromptsPage.tsx app/capabilities/settings/web/ProvidersPanel.tsx app/capabilities/settings/e2e/test_profiles_e2e.py
git commit --trailer "Assisted-by: OpenCode (<model>)" -m "fix(settings): technical inputs stop offering spellcheck and autofill

User-visible: the provider form no longer runs spellcheck over URLs,
model names or keys, and the API key field no longer invites a password
manager to store it; an added diff line no longer wears the primary
action's colour.

Closes #544"
```

---

### Task 6: Typographic covers (B2, closes #590)

**Files:**
- Modify: `web/globals.css` (cover tokens), `web/ui/Cover.tsx`, `app/capabilities/writing/web/NovelsPage.tsx:119,349`, `app/capabilities/setup/web/SetupPage.tsx:139`, `web/ui/Cover.test.tsx`, `app/capabilities/writing/e2e/test_novels_e2e.py`, `docs/superpowers/specs/2026-10-31-narrare-ui-b-pur-design.md` (§8.6, §11)

**Interfaces:**
- Produces: `Cover({ title, size, genre?, language? })`; `data-cover-tone="pale|sepia|ink"`; classes `bg-cover-pale|sepia|ink` and `text-cover-pale|sepia|ink`; `COVER_TONES` is gone.

- [ ] **Step 1: Write the failing component tests**

In `web/ui/Cover.test.tsx`:

```tsx
it("names its tone for the test and for the eye", () => {
  const { container } = render(<Cover title="Das Zählwerk" />);
  expect(container.querySelector("[data-cover-tone]")?.getAttribute("data-cover-tone")).toBe("pale");
});

it("wears the eyebrow's genre, or the language when there is none", () => {
  const withGenre = render(<Cover title="Der Sturm" genre="Roman" language="de" />);
  expect(withGenre.getByText("Roman")).toBeTruthy();
  const withoutGenre = render(<Cover title="Der Sturm" language="de" />);
  expect(withoutGenre.getByText("DE")).toBeTruthy();
});

it("draws its frame only on the sepia tone", () => {
  const titles = Array.from({ length: 20 }, (_, index) => `Buch ${index}`);
  const byTone = (tone: number) => titles.find((title) => coverTone(title) === tone);
  const sepia = byTone(1);
  const pale = byTone(0);
  expect(sepia).toBeDefined();
  expect(pale).toBeDefined();
  const sepiaTile = render(<Cover title={sepia!} />);
  expect(sepiaTile.container.querySelector("[data-cover-frame]")).not.toBeNull();
  cleanup();
  const paleTile = render(<Cover title={pale!} />);
  expect(paleTile.container.querySelector("[data-cover-frame]")).toBeNull();
});
```

All three render calls need `cleanup()` between them (`afterEach(cleanup)` is
already in the file).

- [ ] **Step 2: Run them to verify they fail**

Run: `pnpm --dir web vitest run ui/Cover.test.tsx`
Expected: FAIL, no `data-cover-tone`, no eyebrow, no frame.

- [ ] **Step 3: Add the tokens**

In `web/globals.css` (as `light-dark()` pairs — they take effect once Task 10
sets `color-scheme`, and need no second pass):

```css
  /* The book object's own grounds. Not action tokens: a cover is an object
   * surface, and in dark mode its sepia must stay quieter than the button. */
  --cover-pale-ground: light-dark(oklch(0.94 0.008 85), oklch(0.30 0.012 85));
  --cover-pale-ink: light-dark(oklch(0.25 0.01 85), oklch(0.90 0.005 85));
  --cover-sepia-ground: light-dark(oklch(0.42 0.09 45), oklch(0.44 0.06 45));
  --cover-sepia-ink: light-dark(oklch(0.98 0.005 85), oklch(0.96 0.01 85));
  --cover-ink-ground: light-dark(oklch(0.25 0.01 85), oklch(0.16 0.01 85));
  --cover-ink-ink: light-dark(oklch(0.98 0.005 85), oklch(0.90 0.005 85));
```

Map them in `@theme inline` (`--color-cover-pale: var(--cover-pale-ground)`, …)
so `bg-cover-pale` / `text-cover-pale` exist.

- [ ] **Step 4: Rewrite `Cover.tsx`**

```tsx
const TONES = [
  { tone: "pale", ground: "bg-cover-pale", ink: "text-cover-pale", frame: false },
  { tone: "sepia", ground: "bg-cover-sepia", ink: "text-cover-sepia", frame: true },
  { tone: "ink", ground: "bg-cover-ink", ink: "text-cover-ink", frame: false },
] as const;
```

Keep `coverTone(title)` byte-for-byte (its pins stay). Composition: frame +
spine only when `frame`; the eyebrow is `genre ?? language?.toUpperCase()`;
titles bottom-aligned except the ink tone, which stays centred. The tile keeps
`aria-hidden`.

- [ ] **Step 5: Pass the fields at the three call sites**

`NovelsPage.tsx:119` and `:349` pass `genre`/`language` from the novel;
`SetupPage.tsx:139` passes `language={entry.language}` (the demos have no genre).

- [ ] **Step 6: Update the E2E selector**

`test_novels_e2e.py:78` becomes:

```python
    expect(hero.locator("[data-cover-tone]").first).to_be_visible()
```

- [ ] **Step 7: Run the tests and measure the contrast**

Run: `pnpm --dir web vitest run ui/Cover.test.tsx` and
`just test-e2e writing`.
Then, in a browser at both themes, read the title's computed `color` and the
tile's `background-color` for all three tones and confirm ≥ 4.5:1; record the
six pairs in the task report. (The E2E's axe pass is a second check.)

- [ ] **Step 8: Commit**

```bash
git add web/globals.css web/ui/Cover.tsx web/ui/Cover.test.tsx app/capabilities/writing/web/NovelsPage.tsx app/capabilities/setup/web/SetupPage.tsx app/capabilities/writing/e2e/test_novels_e2e.py docs/superpowers/specs/2026-10-31-narrare-ui-b-pur-design.md
git commit --trailer "Assisted-by: OpenCode (<model>)" -m "feat(shelf): the covers become composed objects with their own inks

User-visible: a book's tile now carries a hairline frame, a spine and its
genre or language; in dark mode the sepia cover is no longer the same
fill as the one primary button.

Closes #590"
```

---

### Task 7: Area hues on the rail (B3)

**Files:**
- Modify: `web/globals.css` (area tokens), `web/components/IconRail.tsx`, `web/ui/typeScale.test.ts`, `app/capabilities/writing/e2e/test_shell_chrome_e2e.py`

**Interfaces:**
- Produces: `AREA_ICON = { writing: "text-area-writing", knowledge: "text-area-knowledge", chat: "text-area-chat", settings: "text-area-settings" }`; tokens `--area-*`.

- [ ] **Step 1: Write the failing E2E**

```python
def test_the_rail_tells_the_four_areas_apart(page: Page, stack: Stack) -> None:
    page.goto(f"{WEB}/")
    colours = page.evaluate(
        """() => ["Regal", "Wissen", "Chat", "Einstellungen"].map((name) => {
          const link = document.querySelector(`nav a[aria-label="${name}"] svg`);
          return getComputedStyle(link).stroke;
        })"""
    )
    assert len(set(colours)) == 4, colours
```

Run: `just test-e2e writing` — expected FAIL, four identical strokes.

- [ ] **Step 2: Add the tokens and the mapping**

`web/globals.css`, `light-dark()` pairs:

```css
  --area-writing: light-dark(oklch(0.50 0.10 45), oklch(0.78 0.08 45));
  --area-knowledge: light-dark(oklch(0.48 0.08 110), oklch(0.76 0.07 110));
  --area-chat: light-dark(oklch(0.48 0.06 235), oklch(0.76 0.05 235));
  --area-settings: light-dark(oklch(0.45 0.02 85), oklch(0.74 0.02 85));
```

Measure each against `--panel` in both themes and adjust lightness until each
clears 3:1 (icons are non-text); record the four values and their ratios in the
task report. Map them in `@theme inline` as `--color-area-*`.

`IconRail.tsx`: `RailLink` gains `area: "writing" | "knowledge" | "chat" |
"settings"` and applies `AREA_ICON[area]` to the `Icon` wrapper. Home is
`writing`, each `nav` entry uses `entry.id`, Settings is `settings`.

- [ ] **Step 3: Add the census to `typeScale.test.ts`**

```ts
it("keeps the area hues in the rail", () => {
  const offences = scanned
    .filter((file) => !file.endsWith("components/IconRail.tsx"))
    .flatMap((file) =>
      [...readFileSync(file, "utf8").matchAll(/\b(?:text|bg|border)-area-[a-z]+\b/g)].map(
        (match) => `${relative(REPO, file)}: ${match[0]}`,
      ),
    );
  expect(offences).toEqual([]);
});
```

- [ ] **Step 4: Run**

Run: `pnpm --dir web vitest run ui/typeScale.test.ts` and `just test-e2e writing`.
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/globals.css web/components/IconRail.tsx web/ui/typeScale.test.ts app/capabilities/writing/e2e/test_shell_chrome_e2e.py
git commit --trailer "Assisted-by: OpenCode (<model>)" -m "feat(shell): the rail names its four areas in colour

User-visible: the writing, knowledge, chat and settings icons each carry
their area's hue; no action, notice or cover takes one."
```

---

### Task 8: The rail expands over the page (C1)

**Files:**
- Modify: `web/components/IconRail.tsx`, `app/capabilities/writing/e2e/test_shell_chrome_e2e.py`
- Modify `web/globals.css` only if Tailwind's `pointer-coarse:` variant is unavailable (the fallback rule)

**Interfaces:**
- Produces: the rail's slot (`relative w-12`) and nav (`absolute inset-y-0 left-0 w-12 hover:w-[168px] focus-within:w-[168px]`); labels always in the DOM with opacity 0/1.

- [ ] **Step 1: Write the failing E2E**

```python
def test_the_rail_names_itself_on_hover_and_focus(page: Page, stack: Stack) -> None:
    page.goto(f"{WEB}/")
    rail = page.locator(ICON_RAIL)
    label = rail.get_by_text("Wissen")
    expect(rail).to_have_css("width", "48px")
    expect(label).to_have_css("opacity", "0")
    rail.hover()
    expect(rail).to_have_css("width", "168px")
    expect(label).to_have_css("opacity", "1")


def test_the_expanded_rail_moves_no_page_pixels(page: Page, stack: Stack) -> None:
    page.goto(f"{WEB}/")
    before = page.locator("main").bounding_box()
    page.locator(ICON_RAIL).hover()
    assert page.locator("main").bounding_box() == before


def test_a_touch_pointer_gets_permanent_labels(browser, stack: Stack) -> None:
    context = browser.new_context(has_touch=True, viewport={"width": 1280, "height": 900})
    page = context.new_page()
    page.goto(f"{WEB}/")
    expect(page.locator(ICON_RAIL)).to_have_css("width", "168px")
    expect(page.locator(ICON_RAIL).get_by_text("Wissen")).to_have_css("opacity", "1")
    context.close()
```

Add a keyboard case: `page.keyboard.press("Tab")` until the rail's first link is
focused, then the width is 168 (Tab order: skip link, bar controls, rail).

- [ ] **Step 2: Run it to verify it fails**

Run: `just test-e2e writing`
Expected: FAIL, width 48 and no labels.

- [ ] **Step 3: Implement**

Wrap the nav in a `relative w-12 shrink-0` slot; the nav becomes
`absolute inset-y-0 left-0 z-20 flex w-12 flex-col items-start justify-between overflow-hidden border-r border-border bg-panel p-1.5 transition-[width] duration-150 hover:w-[168px] focus-within:w-[168px] hover:shadow-overlay focus-within:shadow-overlay motion-reduce:transition-none`.
`RailLink` renders the icon and a
`<span className="whitespace-nowrap opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100 motion-reduce:transition-none">{label}</span>`
inside a `group`; the nav is the group.

For a coarse pointer, the same properties ride Tailwind's `pointer-coarse:`
variant: `pointer-coarse:w-[168px]`, `pointer-coarse:shadow-none`, and the label
`pointer-coarse:opacity-100`; no transition
(`pointer-coarse:transition-none`). If the installed Tailwind lacks the variant,
fall back to one `@media (hover: none)` rule keyed on `data-rail` (the nav's
attribute) in `globals.css` — either way the E2E's `has_touch` context is the
proof.

Keep `aria-label` per link; keep the `justify-between` bottom anchor.

- [ ] **Step 4: Run**

Run: `just test-e2e writing`. Expected: PASS.
Also rerun `just test-e2e knowledge` — the rail is shell chrome on every route.

- [ ] **Step 5: Commit**

```bash
git add web/components/IconRail.tsx web/globals.css app/capabilities/writing/e2e/test_shell_chrome_e2e.py
git commit --trailer "Assisted-by: OpenCode (<model>)" -m "feat(shell): the rail opens its names instead of hiding them

User-visible: hovering or tabbing into the icon rail shows each
destination's name over the page, without moving the page; touch screens
show the names permanently."
```

---

### Task 9: The theme on the user row (C2, backend)

**Files:**
- Modify: `app/kernel/contracts/models.py:44`, `app/capabilities/settings/schemas.py`, `service.py`, `router.py`, `app/capabilities/settings/tests/test_settings.py`
- Create: a migration under `app/kernel/db/migrations/versions/`

**Interfaces:**
- Produces: `User.theme: str | None`; `GET /api/settings` → `{locale, theme}`; `PATCH /api/settings/theme` with `{theme: "light" | "dark" | null}` → `{theme}`. `SettingsUpdate` and `PATCH /api/settings` do not change shape.

- [ ] **Step 1: Write the failing tests**

Add to `test_settings.py`:

```python
async def test_a_theme_who_never_chose_follows_the_system() -> None:
    async with _client() as client:
        assert (await client.get("/api/settings")).json() == {"locale": None, "theme": None}


async def test_a_chosen_theme_is_stored_on_the_user_row() -> None:
    async with _client() as client:
        written = await client.patch("/api/settings/theme", json={"theme": "dark"})
        assert written.status_code == 200
        assert written.json() == {"theme": "dark"}
        assert (await client.get("/api/settings")).json() == {"locale": None, "theme": "dark"}

    async with Session() as session:
        user = await session.get(User, LOCAL_USER_ID)
        assert user is not None
        assert user.theme == "dark"


async def test_an_unknown_theme_is_refused_and_changes_nothing() -> None:
    async with _client() as client:
        await client.patch("/api/settings/theme", json={"theme": "dark"})
        refused = await client.patch("/api/settings/theme", json={"theme": "sepia"})
        assert refused.status_code == 422
        assert (await client.get("/api/settings")).json()["theme"] == "dark"


async def test_an_omitted_theme_is_refused() -> None:
    async with _client() as client:
        await client.patch("/api/settings/theme", json={"theme": "dark"})
        refused = await client.patch("/api/settings/theme", json={})
        assert refused.status_code == 422


async def test_null_returns_the_theme_to_the_system() -> None:
    async with _client() as client:
        await client.patch("/api/settings/theme", json={"theme": "light"})
        cleared = await client.patch("/api/settings/theme", json={"theme": None})
        assert cleared.status_code == 200
        assert cleared.json() == {"theme": None}


async def test_a_theme_write_before_setup_is_refused() -> None:
    await _forget_the_user()
    async with _client() as client:
        refused = await client.patch("/api/settings/theme", json={"theme": "dark"})
        assert refused.status_code == 409
        assert (await client.get("/api/settings")).json() == {"locale": None, "theme": None}
```

Update the five existing assertions that read `{"locale": X}` to
`{"locale": X, "theme": None}` — the response grew one field, deliberately.

- [ ] **Step 2: Run them to verify they fail**

Run: `just test-file app/capabilities/settings/tests/test_settings.py`
Expected: FAIL, 404 on `/api/settings/theme`.

- [ ] **Step 3: Implement the model and the migration**

`models.py`: `theme: Mapped[str | None] = mapped_column(String(8))` beside
`locale`. Then `just db-revision "add users.theme"`; read the generated file and
confirm it only adds the nullable column.

- [ ] **Step 4: Implement the API**

`SettingsRead` gains `theme: str | None`. New `SettingsThemeUpdate` with
`theme: str | None` and a validator against `{"light", "dark"}`. `SettingsService`
gains `read_theme` / `write_theme` mirroring the locale methods. `router.py`:

```python
@router.patch("/theme", response_model=SettingsThemeRead)
async def update_theme(payload: SettingsThemeUpdate, service: ServiceDep) -> SettingsThemeRead:
    try:
        theme = await service.write_theme(payload.theme)
    except SetupRequiredError:
        raise HTTPException(status_code=409, detail="setup required") from None
    return SettingsThemeRead(theme=theme)
```

`GET /api/settings` and `PATCH /api/settings` both return `SettingsRead` with
both fields.

- [ ] **Step 5: Run the tests**

Run: `just test-file app/capabilities/settings/tests/test_settings.py`
Expected: PASS, including the unchanged locale tests.

- [ ] **Step 6: Commit**

```bash
git add app/kernel/contracts/models.py app/kernel/db/migrations/versions app/capabilities/settings
git commit --trailer "Assisted-by: OpenCode (<model>)" -m "feat(settings): the theme becomes user data

User-visible: none yet; the choice has a place to live.

The write gets its own endpoint so SettingsUpdate keeps its
present-and-nullable law: a form sending both fields would let a stale
read clobber the other setting."
```

---

### Task 10: The theme reaches the screen (C2, web)

**Files:**
- Modify: `web/globals.css`, `web/lib/theme.ts` (create), `web/lib/theme.test.ts` (create), `web/lib/query.ts`, `web/routes/__root.tsx`, `web/index.html`, `app/capabilities/settings/web/{SettingsLayout,routes}.tsx`, create `app/capabilities/settings/web/AppearancePage.tsx`, `i18n/*.json`, `app/capabilities/settings/e2e/test_settings_e2e.py`, generated API files
- Run: `just generate`

**Interfaces:**
- Consumes: Task 9's `GET /api/settings` → `{locale, theme}` and `PATCH /api/settings/theme`.
- Produces: `applyTheme(theme: "light" | "dark" | null): void`, `adoptServerTheme(theme)`, `THEME_HINT = "narrare.theme"`; `useSettingsQuery` → `{ locale, theme }`.

- [ ] **Step 1: Write the failing theme-module test**

```ts
// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { applyTheme, THEME_HINT } from "./theme";

afterEach(() => {
  document.documentElement.removeAttribute("data-theme");
  localStorage.clear();
});

describe("applyTheme", () => {
  it("marks the document and remembers the choice", () => {
    applyTheme("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(localStorage.getItem(THEME_HINT)).toBe("dark");
  });

  it("clears both when the system decides", () => {
    applyTheme("light");
    applyTheme(null);
    expect(document.documentElement.hasAttribute("data-theme")).toBe(false);
    expect(localStorage.getItem(THEME_HINT)).toBeNull();
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pnpm --dir web vitest run lib/theme.test.ts`
Expected: FAIL, cannot resolve `./theme`.

- [ ] **Step 3: Implement the module and the boot**

```ts
export type Theme = "light" | "dark";
export const THEME_HINT = "narrare.theme";

/** Set or clear the document's theme and the pre-paint hint. */
export function applyTheme(theme: Theme | null): void {
  if (theme === null) document.documentElement.removeAttribute("data-theme");
  else document.documentElement.dataset.theme = theme;
  try {
    if (theme === null) localStorage.removeItem(THEME_HINT);
    else localStorage.setItem(THEME_HINT, theme);
  } catch {
    /* A blocked store only costs the hint, never the choice. */
  }
}
```

`web/index.html`, before the module script:

```html
    <script>
      try {
        var t = localStorage.getItem("narrare.theme");
        if (t === "light" || t === "dark") document.documentElement.dataset.theme = t;
      } catch (e) {}
    </script>
```

`__root.tsx`: in the settings-success effect, call `applyTheme(settings.data.theme)`
beside `adoptServerLocale`.

`web/lib/query.ts`: `useSettingsQuery` returns `{ locale, theme }` (outage:
`{ locale: null, theme: null }`).

- [ ] **Step 4: Convert the tokens to `light-dark()`**

Every remaining colour token in `:root` becomes `light-dark(<light>, <dark>)` with
the dark values from the deleted media block; `:root { color-scheme: light dark }`;
`[data-theme="light"] { color-scheme: light }`; `[data-theme="dark"] { color-scheme: dark }`.
Delete `@media (prefers-color-scheme: dark)`. Keep `--scrim` and
`--overlay-shadow` constant. The cover and area tokens from Tasks 6 and 7 are
already `light-dark()` pairs and only start resolving here.

- [ ] **Step 5: The settings page**

`AppearancePage.tsx`: a `Field` with the label `t("settings.appearance.themeLabel")`
and a `Select` of three options (`system`, `light`, `dark`), value
`theme ?? "system"`; on change, `applyTheme(value === "system" ? null : value)`
first, then `PATCH /api/settings/theme`, restoring and showing a `Notice` on
refusal (the `LanguageSwitcher` pattern). Add the cluster to
`SettingsLayout.CLUSTERS` (`/settings/appearance`, `settings.clusterAppearance`)
and the route to `routes.tsx`.

Catalog keys: `settings.clusterAppearance`, `settings.appearance.themeLabel`,
`settings.appearance.system`, `settings.appearance.light`,
`settings.appearance.dark` (en/de/fr).

- [ ] **Step 6: Regenerate and typecheck**

Run: `just generate` then `just check`.
Expected: `schema.d.ts` carries `theme`; no type errors.

- [ ] **Step 7: The E2E**

In `test_settings_e2e.py`:

```python
def test_a_chosen_theme_survives_a_fresh_browser(page: Page, stack: Stack) -> None:
    page.goto(f"{WEB}/settings/appearance")
    page.get_by_label("Darstellung").select_option("dark")
    page.reload()
    assert page.evaluate("document.documentElement.dataset.theme") == "dark"
    dark = page.evaluate("getComputedStyle(document.body).backgroundColor")
    page.get_by_label("Darstellung").select_option("light")
    page.reload()
    light = page.evaluate("getComputedStyle(document.body).backgroundColor")
    assert dark != light


def test_an_unchosen_theme_follows_the_system(browser, stack: Stack) -> None:
    context = browser.new_context(color_scheme="dark")
    page = context.new_page()
    page.goto(f"{WEB}/")
    assert page.evaluate("document.documentElement.dataset.theme ?? null") is None
    assert page.evaluate("getComputedStyle(document.body).backgroundColor") != "rgb(255, 255, 255)"
    context.close()
```

- [ ] **Step 8: Run**

Run: `pnpm --dir web vitest run lib/theme.test.ts` and `just test-e2e settings`.
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add web/globals.css web/lib/theme.ts web/lib/theme.test.ts web/lib/query.ts web/routes/__root.tsx web/index.html app/capabilities/settings/web i18n app/capabilities/settings/e2e/test_settings_e2e.py web/lib/api
git commit --trailer "Assisted-by: OpenCode (<model>)" -m "feat(settings): the reader chooses the light

User-visible: a new Darstellung page offers System, Hell and Dunkel; the
choice follows the account and survives a reload without a flash.

Dark mode was system-only by decision, and the decision outlived the
readers who wanted the other way at night."
```

---

### Task 11: Screenshots and the full gate

**Files:**
- Modify: `scripts/screenshots.py`, `assets/screenshots/*`, `README.md`

- [ ] **Step 1: Add the chosen-dark pass**

After the five light shots, `PATCH /api/settings/theme {"theme": "dark"}` against
the running stack, then shoot `01-workspace-continuation-dark.png` and
`05-shelf-dark.png`; clear the theme at the end. Add both names to the script's
expected output so the "only N of M written" check stays honest.

- [ ] **Step 2: Re-shoot**

Run: `uv run python -m scripts.screenshots` (needs the dev stack's Postgres).
Expected: 7 files written.

- [ ] **Step 3: Read the images**

Open all seven and confirm: the light five show the new scale and covers, the
two dark ones show the chosen theme, the sepia cover is quieter than the
button, and the shelf's rail is not expanded.

- [ ] **Step 4: The README**

Add the dark shelf beside the light one in the gallery, with alt text naming
the theme.

- [ ] **Step 5: Full gate**

Run: `just verify all`
Expected: check, every suite, the frontend suite, the build and every E2E green.

- [ ] **Step 6: Commit**

```bash
git add scripts/screenshots.py assets/screenshots README.md
git commit --trailer "Assisted-by: OpenCode (<model>)" -m "docs(screenshots): the gallery shows the chosen dark

User-visible: the README's shelf now shows both themes."
```

---

## Self-Review

**Spec coverage.** A1→T1, A2/A6/#555→T3, A3→T4, A4/A5→T5, B1→T2, B2/#590→T6,
B3→T7, C1→T8, C2→T9+T10, screenshots→T11. The design's §12 approvals: the
scale gate is Task 1. The design's "my calls" (text-danger scope, eyebrow
fallback, rail-only hues, coarse-pointer labels, hint as cache, endpoint split,
three doors, browser floor, chosen-dark screenshots, title steps) each land in
their task. Nothing in the design lacks a task.

**Type consistency.** `dirtyFields` (T4) is used in T4 only; `applyTheme` /
`THEME_HINT` (T10) match the hint script's key; `Cover`'s props match its three
call sites; `data-cover-tone` is the same string in T6's test and the E2E;
`AREA_ICON` keys match `nav` ids and the Home/Settings literals; the
`PATCH /api/settings/theme` body matches T9's schema and T10's call.

**Proportion.** The plan names signatures, assertions and values; bodies appear
only where the shape is the decision (the dirty predicate, the sweep, the hint
script).

**Review Focus.** Five lines, each with its test: T6 (long title, no genre),
T8 (rail breakpoints, no page move), T10 (OS flips while System), T4 (pristine
vs dirty), T3 (chip refuses behind a dialog).
