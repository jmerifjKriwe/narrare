# UI Command-Fokus, Slice 1 — Norm + Beweis (Galerie + Gates) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the enforceable core of the C guide: a reconciled norm plus a living `/design` gallery with gates, without re-implementing the landed visual-identity wave.

**Architecture:** The gallery is one settings-owned route (`/design`, root-parented, absent from hub clusters and user docs) rendering the real `web/ui/` primitives; E2E and the screenshot script pin it in light and dark. No new capability, no new registry, no new primitive.

**Tech Stack:** Python 3.14 · FastAPI · Vite · React 19 · TanStack Router · Tailwind v4 (`@theme inline`) · Vitest · Playwright (E2E).

**Spec:** `docs/superpowers/specs/2026-11-06-narrare-ui-command-fokus-design.md`

## Global Constraints

- English in code, tests and developer documentation; user-visible text in en, de and fr through `i18n/*.json`. A missing key is a build error.
- One capability is one folder; a capability never imports another capability. Shared UI lives in `web/ui/` and `web/components/`.
- Tokens only from `web/globals.css`; capability folders carry utilities, never a palette.
- No new primitive, no second data store, no new gate beyond what this plan names.
- Every `feat`/`fix`/`docs` commit carries a real `User-visible:` line and the trailer `Assisted-by: OpenCode (<model>)` via `git commit --trailer`. Author and committer stay human.
- Nothing is committed before the task's review is green.
- Gates: `just check` · `just test-file <path>` · `just test-e2e <capability>` · frontend suite via `pnpm --dir web vitest run <path>`.
- E2E contexts use locale de-DE (hand-made contexts must repeat it).

## Review Focus

The spec implies these and no task's happy path covers them; each gets its test in the named task.

1. **A corrupt `narrare.theme` hint (`"sepia"`)** — the gallery still renders with the system theme, no crash, no stuck attribute. (Task 2, unit test.)
2. **A 120-character gallery cover title** — clamps to three lines, no overflow, eyebrow intact. (Task 2, unit test.)
3. **Chosen dark theme on `/design`** — dark token pairs resolve (body background differs from light). (Task 3, screenshot read + E2E value assert.)
4. **A missing gallery i18n key** — must fail the build, not render an empty heading. (Task 2; the `just check` typecheck is the test.)
5. **E2E browser locale other than de-DE** — German-name assertions would fail; the new E2E pins de-DE like its neighbours. (Task 2, E2E fixture pattern.)

---

## File Structure

| File | Responsibility |
| --- | --- |
| `docs/superpowers/specs/2026-11-06-narrare-ui-command-fokus-design.md` | the reconciled norm (Task 1 edits this) |
| `app/capabilities/settings/web/DesignGallery.tsx` | the gallery component: tokens, type, controls, surfaces from real primitives |
| `app/capabilities/settings/web/DesignGallery.test.tsx` | render pins: sections present, long title clamps, corrupt hint falls back |
| `app/capabilities/settings/web/routes.tsx` | mounts `designRoute` (`/design`, root-parented, not in any cluster list) |
| `i18n/{en,de,fr}.json` | `design.*` keys, translated in all three |
| `app/capabilities/settings/e2e/test_settings_e2e.py` | `/design` serves in light and dark |
| `scripts/screenshots.py` | two more shots (`design` light + chosen-dark); expected count grows by two |

---

### Task 1: Reconcile the norm with the landed wave

The design doc was written from screenshots predating the visual-identity wave (now on main: palette door, tri-state theme, expanding rail, area hues, typographic covers, single-context dock tabs, tokened `Select`, chapter-row accessible names). The norm must name what is landed law and keep only the true delta, or implementers will re-litigate decided work.

**Files:**
- Modify: `docs/superpowers/specs/2026-11-06-narrare-ui-command-fokus-design.md`
- Nothing else.

**Interfaces:**
- Produces: the reconciled §5 (what is law by file reference) and the dropped rules with their reason. Task 2 builds against it.

- [ ] **Step 1: Rename the branch to the convention**

Run: `git branch -m feat/ui-command-fokus-gallery`
Expected: `git branch --show-current` prints `feat/ui-command-fokus-gallery`.

- [ ] **Step 2: Edit the spec's §5 and §8.4**

Make exactly these changes, nothing else:
- §5.1: delete the `--diff-add/--diff-del/--diff-hunk` proposal; adopt the landed markers (`border-success` added, `border-danger` removed, `PromptsPage.tsx`, visual-identity §A4). Record the reason in one sentence.
- §5.2: soften the no-truncation absolute into the landed rule — the chapter row's accessible name is complete (`NovelPage.tsx:658`), the visual single line is density; wrap only where the rail geometry allows, as a follow-up, not here.
- §5.3/5.4: replace "no ⌘K" and "stacked docks" claims with file references to the landed state (`__root.tsx` palette + `Palette.tsx`, generated `docks.ts` single-active-context, `NovelPage.tsx:234-242`).
- §5.2 language control: note `LanguageSwitcher.tsx` already uses the tokened `Select`.
- Status line at the top: `Entwurf zur Freigabe` becomes `Norm (Slice 1), reconciled with the landed visual-identity wave`.

- [ ] **Step 3: Verify by reading the diff**

Run: `git diff --stat && git diff docs/superpowers/specs/2026-11-06-narrare-ui-command-fokus-design.md | head -80`
Expected: exactly one file changed; every hunk is one of the five items above.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-11-06-narrare-ui-command-fokus-design.md
git commit --trailer "Assisted-by: OpenCode (<model>)" -m "docs(ui): reconcile the command-fokus guide with the landed wave
```

```text
User-visible: none; the design record no longer asks for work that already shipped.
"
```

---

### Task 2: The `/design` gallery route

**Files:**
- Create: `app/capabilities/settings/web/DesignGallery.tsx`, `app/capabilities/settings/web/DesignGallery.test.tsx`
- Modify: `app/capabilities/settings/web/routes.tsx`, `i18n/en.json`, `i18n/de.json`, `i18n/fr.json`, `app/capabilities/settings/e2e/test_settings_e2e.py`
- Test: `DesignGallery.test.tsx`, the new E2E node.

**Interfaces:**
- Consumes: Task 1's reconciled norm (which primitives and tokens the gallery must show).
- Produces: `designRoute` (`/design`, root-parented); catalog keys `design.heading`, `design.tokens`, `design.type`, `design.controls`, `design.surfaces`; the gallery renders Button, Field+Select, Notice (quiet/info/success/warning/danger), Cover (three tones), Row (current/selected), the six text steps and the token swatches.

- [ ] **Step 1: Add the catalog keys (en/de/fr)**

`design.heading` — "Design gallery" / "Design-Galerie" / "Galerie de design"; `design.tokens`, `design.type`, `design.controls`, `design.surfaces` translated likewise. No other keys.

- [ ] **Step 2: Write the failing component test**

```tsx
// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { DesignGallery } from "./DesignGallery";

describe("DesignGallery", () => {
  it("names its four sections", () => {
    render(<DesignGallery />);
    for (const name of ["Tokens", "Type", "Controls", "Surfaces"]) {
      expect(screen.getByRole("heading", { name })).toBeTruthy();
    }
  });

  it("clamps a 120-character cover title", () => {
    const { container } = render(<DesignGallery />);
    const tile = container.querySelector('[data-cover-tone][data-long-title]');
    expect(tile).not.toBeNull();
    expect(getComputedStyle(tile as Element).overflow).toBe("hidden");
  });

  it("survives a corrupt theme hint", () => {
    localStorage.setItem("narrare.theme", "sepia");
    render(<DesignGallery />);
    expect(document.documentElement.dataset.theme).not.toBe("sepia");
    localStorage.clear();
  });
});
```

(The gallery renders one fixed long-title cover tile carrying `data-long-title` so the clamp has a pin.)

- [ ] **Step 3: Run it to verify it fails**

Run: `pnpm --dir web vitest run ../app/capabilities/settings/web/DesignGallery.test.tsx`
Expected: FAIL, cannot resolve `./DesignGallery`.

- [ ] **Step 4: Implement the component**

`DesignGallery.tsx`: one `main`-landed page (h1 `design.heading`, `text-title`), four `section`s with h2s from the catalog. Content uses only the real primitives (`Button`, `Field`+`Select`, `Notice`, `Cover`, `Row`, `Panel`) and token classes (`bg-background`, `text-foreground`, `text-muted`, `bg-card`, `bg-panel`, `bg-soft`, `border-border`, `bg-primary text-primary-foreground`, `text-success/warning/danger`, `bg-cover-*`, `text-area-*` on rail-icon-sized swatches only). No new CSS, no new token, no new component. Long-title tile: `title={"A".repeat(120)}` with `data-long-title`.

- [ ] **Step 5: Mount the route**

In `routes.tsx`, lazy-import `DesignGallery` like the other pages and add:

```tsx
const designRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/design",
  component: DesignGallery,
});
```

Append `designRoute` to the `routes` array. Do NOT add it to `SettingsLayout` clusters, the hub, or any nav: it is reachable by URL for gates and humans, invisible in the product.

- [ ] **Step 6: Typecheck (the i18n gate)**

Run: `pnpm --dir web typecheck`
Expected: PASS — a missing `design.*` key in any locale fails here (Review Focus 4).

- [ ] **Step 7: Add the E2E node**

In `test_settings_e2e.py`, following the file's existing locale pattern (de-DE):

```python
def test_the_design_gallery_serves_its_four_sections(page: Page, stack: Stack) -> None:
    page.goto(f"{WEB}/design")
    expect(page.get_by_role("heading", name="Design-Galerie")).to_be_visible()
    for name in ["Tokens", "Type", "Controls", "Surfaces"]:
        expect(page.get_by_role("heading", name=name)).to_be_visible()
```

- [ ] **Step 8: Run the tests**

Run: `pnpm --dir web vitest run ../app/capabilities/settings/web/DesignGallery.test.tsx` then `just test-e2e settings`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add app/capabilities/settings/web/DesignGallery.tsx app/capabilities/settings/web/DesignGallery.test.tsx app/capabilities/settings/web/routes.tsx i18n app/capabilities/settings/e2e/test_settings_e2e.py
git commit --trailer "Assisted-by: OpenCode (<model>)" -m "feat(settings): a living design gallery behind /design
```

```text
User-visible: none in the product; the gallery at /design shows every
shared primitive and token in one place for review and screenshots.
"
```

---

### Task 3: Screenshot coverage for the gallery

**Files:**
- Modify: `scripts/screenshots.py`, `assets/screenshots/*`
- Test: the script's own expected-output check; human read of the two images.

**Interfaces:**
- Consumes: Task 2's `/design` route.
- Produces: `design-light.png` + `design-dark.png` (names follow the script's existing scheme; adjust if the script names shots differently and record the real names in the report).

- [ ] **Step 1: Extend the script**

Read `scripts/screenshots.py` first. Add the gallery shot after the existing passes: `GET /design` with the default (light) stack, then `PATCH /api/settings/theme {"theme": "dark"}` and the same URL again for the dark shot; clear the theme at the end (the chosen-dark pattern from the visual-identity wave). Grow the script's expected-output count by exactly two so the "only N of M written" check stays honest.

- [ ] **Step 2: Re-shoot**

Run: the script's own documented command (it needs the dev stack's Postgres).
Expected: all shots written, including the two new ones.

- [ ] **Step 3: Read the images**

Open both and confirm: four sections present; dark shot's body background differs from light (Review Focus 3); no expanded rail over the gallery; German headings (the seeded locale).

- [ ] **Step 4: Run the affected E2E**

Run: `just test-e2e settings`
Expected: PASS (the gallery E2E from Task 2 plus neighbours).

- [ ] **Step 5: Commit**

```bash
git add scripts/screenshots.py assets/screenshots
git commit --trailer "Assisted-by: OpenCode (<model>)" -m "docs(screenshots): the gallery is pinned in light and dark
```

```text
User-visible: none in the product; reviewers see the design state in both themes.
"
```

---

### Task 4: The slice's gates

No new code. This task is the evidence the slice is done.

- [ ] **Step 1: Fast gate**

Run: `just check`
Expected: exit 0, "All checks passed!".

- [ ] **Step 2: Frontend suite**

Run: `pnpm --dir web vitest run`
Expected: PASS, zero failures (includes `typeScale.test.ts`, `DesignGallery.test.tsx`, `Cover.test.tsx`).

- [ ] **Step 3: Affected E2E**

Run: `just test-e2e settings`
Expected: PASS.

- [ ] **Step 4: Production build**

Run: `pnpm --dir web build` (or `just build`)
Expected: exit 0 — the lazy gallery chunk splits cleanly and no type error survives.

- [ ] **Step 5: Report, no commit**

Write the task report: the four gate outputs verbatim, the two new screenshot names, and the open remainder (dock/toolbar polish items become `follow-up` issues per AGENTS.md, one per finding with `area: web`, hung under the wave's index issue — they are NOT fixed in this slice).

---

## Self-Review

**Spec coverage.** Reconciliation→T1; gallery route→T2; census/screenshot gate (1+3, schlank)→T2+T3; dark/A11y ab Tag 1→T3 read + Review Focus 3; anti-goals (no Storybook, no new primitive/registry/token)→enforced in T2 Step 4 and the Global Constraints. Dock/Canvas/command-AI work stays in later slices by design.

**Step scan.** Every test step names its assertions; every code step names file, signature and values; verification steps name command and expected output. Fixed inline: the E2E locale is pinned by reference to the file's pattern rather than a new fixture.

**Type consistency.** `designRoute` parents at `rootRoute` like `settingsLayoutRoute`; lazy import matches the file's pattern; catalog keys follow `settings.*` naming; `data-long-title` is defined once in the component and read once in its test.

**Review Focus.** Five lines, each with its owning task and test: corrupt hint→T2 unit; long title→T2 unit; chosen dark→T3 read; missing key→T2 typecheck; locale→T2 E2E pattern.

**Proportion.** The plan decides interfaces, values and gates; bodies appear only where the shape is the decision (gallery content list, E2E node, screenshot pattern). No transcript of component internals.
