# ADR-059 — Visual Regression Testing & Design System Documentation Strategy

> **Status:** ✅ Accepted
> **Date:** 2026-06-30
> **Deciders:** Architecture Agent
> **Supersedes:** —

---

## Context

Narrare's frontend (`packages/web/`) runs Next.js 16.2.6 + React 19.2.6 + TipTap v3 + Tailwind v4 + shadcn "base-nova" style. The frontend includes ~100+ bespoke app components that are deeply stateful (zustand, react-query, WebSockets, TipTap/ProseMirror). Two themes exist: `:root` (default warm custom palette) and `[data-theme="narrare"]` (shadcn default with `.dark` variant).

Root cause chain:

1. **Symptom:** UI regressions are caught late — during manual review or by users — because there is no automated visual checking in CI.
2. **Why (1):** No visual regression testing (VRT) infrastructure exists. Only functional tests (Vitest + Testing Library for logic, Playwright E2E for flows) verify the UI, none of which detect visual drift (color shifts, layout breaks, spacing regressions, theme inconsistencies).
3. **Why (2):** Design system decisions (color tokens, radii, typography scale) are documented only implicitly in CSS variable files. There is no centralized reference that shows all tokens, their theme variants, or their mapping to Tailwind utilities — making it difficult for developers to use the design system consistently and to detect visual regressions manually.
4. **Design:** Two-pronged approach: (a) add visual regression tests via Playwright's built-in `toHaveScreenshot()`, and (b) build a lightweight dev-only `/dev/design-tokens` route that documents all design tokens as a single source of reference.

The existing test infrastructure is already mature:
- Vitest + Testing Library: ~100+ component tests (functional logic)
- Playwright E2E: 16 tests at `tests/e2e/` (user-flow coverage)
- `playwright.config.ts`: fully configured with chromium, web server, retries, and CI settings

Storybook was evaluated and rejected as the vehicle for both VRT and design documentation (see Options).

---

## Decision Drivers

- **Minimize new tooling overhead** — avoid adding tools that require dedicated infrastructure, maintenance, or CI integration beyond what already exists.
- **Leverage existing infrastructure** — Playwright is already set up, configured, and used in CI. Use it for VRT rather than introducing a separate tool.
- **Avoid compatibility risk** — Next.js 16 + React 19 are bleeding-edge. Storybook's compatibility with these versions is not guaranteed and would create ongoing maintenance burden.
- **Cover critical UI surfaces** — snapshots should target high-value, stable pages that represent the core user experience (settings, analysis, editor).
- **Document the custom theme system** — two themes, each with light + dark variants, create a combinatorial surface that is hard to reason about without a centralized reference.
- **Dev-only by default** — design documentation must not ship to production. Both VRT snapshots and the dev-route are development concerns.
- **Must be accessible in development** — documentation should be viewable without leaving the editor or starting a separate tool.

---

## Options Considered

### Option A — Storybook + Chromatic (rejected)

Full component catalog with interaction tests, visual regression via Chromatic cloud service, a11y addon.

**Pros:**
- Complete solution: interactive component playground, visual regression, a11y audits
- Cross-browser VRT via Chromatic cloud rendering
- Rich addon ecosystem (controls, actions, a11y, viewports)
- Industry standard for component-driven UI documentation

**Cons:**
- Heavy configuration overhead — each component requires a story, which for stateful app components means elaborate mocking (duplicating existing MSW/Test-Library work)
- TipTap/ProseMirror is notoriously fragile in Storybook isolation — the editor relies on DOM layout, contenteditable, and extension registration that are hard to reproduce outside Next.js
- Next.js 16 + React 19 compatibility is uncertain — Storybook may lag behind, creating ongoing upgrade blockers
- Monthly cost for Chromatic (team tier required for parallel review)
- Duplicates behavior coverage already provided by Vitest component tests — the same assertions would need to be rewritten as Storybook interaction tests
- Single product (not a reusable library) reduces Storybook's catalog value — the audience is the internal dev team, not external consumers
- Separate CI pipeline (Chromatic upload + snapshot comparison) adds complexity

### Option B — Playwright `toHaveScreenshot()` + `/dev/design-tokens` (chosen)

Use Playwright's built-in `toHaveScreenshot()` for VRT; build a lightweight dev-only Next.js route for design-token documentation.

**Pros:**
- Zero new dependencies — everything is already installed (Playwright, Next.js pages router)
- Full compatibility — renders the real application in a real browser context, no reconciliation needed
- Tests render the actual app (not isolated stories) — snapshots catch regressions from cross-component interaction, layout shifts, and data flow
- VRT and documentation are addressed in a single ADR (cohesive strategy)
- Dev-route is trivial to build — a single Next.js page rendering token values from CSS-in-JS or imported CSS
- No ongoing cost (no Chromium, no Chromatic subscription)
- Existing Playwright CI pipeline is reused — snapshot comparison runs alongside E2E tests
- Theme combinations are systematically covered (light + dark × 2 themes = 4 combinations per page)

**Cons:**
- No interactive component playground — developers cannot experiment with props
- Page-level snapshots may flake on unrelated content changes (e.g., dynamic data, timestamps)
  - Mitigation: target stable pages with deterministic content; mock API responses for snapshot tests
- Chromium only — no cross-browser VRT (acceptable for a web-app targeting modern browsers)
- Snapshot updates require explicit developer action (`--update-snapshots`)
  - Mitigation: reviewing snapshot diffs is part of PR review; updates are intentional

### Option C — Storybook scoped to `ui/` components (deferred)

Wait until a genuine presentational component layer (`packages/web/components/ui/`) exists, then add Storybook only for those components.

**Pros:**
- Avoids premature investment in tooling for what is mostly app-stateful components
- Storybook would add value for a genuine reusable component library

**Cons:**
- No VRT today — all visual regression risk remains unaddressed
- No design documentation today — the existing custom theme has no reference
- Deferral has no timeline — no guarantee that a presentational layer will emerge
- Does not solve either problem in the foreseeable future

---

## Decision

**We choose Option B: Playwright `toHaveScreenshot()` for VRT + a `/dev/design-tokens` dev route for design system documentation.**

This approach leverages zero new dependencies (Playwright is already configured, Next.js routes are free), avoids Storybook's compatibility risk with Next.js 16 + React 19, and addresses both the VRT and documentation gaps with a cohesive, low-maintenance strategy. The dev-route provides a centralized reference for all design tokens (colors, radii, typography, editor tokens, theme comparison) that developers can access in their browser during development. VRT snapshots target stable, high-value pages and cover all theme combinations.

---

## Rationale

1. **Playwright is already invested.** The `playwright.config.ts`, browser cache (chromium-1217), CI integration, and 16 existing E2E tests mean the infrastructure cost is already sunk. Adding `toHaveScreenshot()` is a configuration change, not a new tool adoption.

2. **Real-app rendering is more valuable than isolated rendering for VRT.** A page-level screenshot in Playwright renders the actual Next.js app with real data flow, real WebSocket connections, and real TipTap instances. It catches regressions from cross-component interactions that Storybook's isolated rendering cannot. The ~100+ Vitest component tests already cover unit-level behavior — VRT should cover the integration surface.

3. **Storybook's compatibility risk with Next.js 16 + React 19 is not worth taking.** Narrare upgrades its stack actively. Storybook has historically lagged behind Next.js major releases, creating an ongoing maintenance tax. For a single-product frontend (not a reusable component library), this tax is not justified.

4. **The dev-route closes the documentation gap without a documentation tool.** No Docusaurus, no ZeroHeight, no dedicated design-token platform. A single Next.js page that renders CSS variable values is always in sync because it reads variables at runtime (or from the compiled CSS). It costs ~200 lines of React code and zero new infrastructure.

5. **Theme coverage is systematic.** 4 viewport screenshots per target page (light-default, dark-default, light-narrare, dark-narrare) ensure theme regressions are caught. Without VRT, a CSS change that breaks dark-mode contrast would go unnoticed until manual review.

6. **Option C (defer) solves nothing.** Both VRT and documentation are needs today. Deferring them creates a compounding risk — as the component surface grows, the undocumented visual surface grows with it.

---

## Consequences

**Positive:**
- No new dependencies — Playwright and Next.js are already in the stack
- VRT runs in existing CI pipeline (reuses `just test-e2e` or adds `just test-vrt`)
- Dev-route provides a centralized, always-current reference for design tokens
- Theme coverage is systematic (4 combinations × target pages)
- Snapshot review becomes part of PR workflow (visual diffs in CI artifacts)
- No ongoing cost (no Chromatic subscription, no cloud service)
- Easy to onboard — any developer familiar with Playwright can add snapshots
- Dev-route is always in sync — reads CSS variables at runtime rather than duplicating values

**Negative / Tradeoffs:**
- No interactive component playground — developers cannot experiment with component props in isolation
  - Acceptable: Vitest + Testing Library covers component behavior; TipTap live editing happens in the app itself
- Page-level snapshots may flake on dynamic content
  - Mitigation: mock API responses for snapshot tests; target stable pages (settings, saved analysis results)
- Chromium only — no Firefox/WebKit coverage
  - Acceptable: Narrare targets modern browsers; Cross-browser testing can be added later if needed
- Snapshot updates require explicit developer action (`--update-snapshots`)
  - Acceptable: this is intentional — snapshot changes should be reviewed as part of PR
- Dev-route is accessible in dev but not in production
  - Acceptable: the route is guarded by environment check; design docs are a dev concern

**Constraints introduced:**
- Target pages for VRT must have deterministic content (mocked API data) to minimize flakiness
- New CSS variable additions should be reflected in the dev-route (documented as part of the CSS variable definition)
- `/dev/` routes are production-excluded (guarded by `process.env.NODE_ENV === 'development'` or build-time exclusion)
- Snapshot test files live in `packages/web/tests/screenshots/` (or `tests/e2e/screenshots/`) — clearly separated from functional E2E tests
- Cross-OS font rendering differences are handled via `maxDiffPixelRatio: 0.02` in the vrt project config; dimension changes require baseline regeneration from CI artifacts

---

## Implementation Notes

### VRT Strategy

**Snapshot test location:**
```
packages/web/tests/screenshots/
├── settings.general.spec.ts
├── settings.ai.spec.ts
├── worldbuilding.spec.ts
├── analysis.spec.ts
└── editor.spec.ts
```

Alternatively, snapshots can live under `tests/e2e/screenshots/` to share the existing Playwright config. The chosen convention should be consistent: either all Playwright tests in `tests/e2e/` (with a `screenshots/` subdirectory or filename suffix) or a separate top-level `tests/screenshots/` directory with its own Playwright project definition.

**Recommended approach:** Add a VRT project in the existing `playwright.config.ts`:

```typescript
// In playwright.config.ts — add a VRT project alongside "chromium"
projects: [
  {
    name: "chromium",  // existing E2E
    use: { ...devices["Desktop Chrome"] },
  },
  {
    name: "vrt",  // new VRT project
    testDir: "./tests/screenshots",
    use: {
      ...devices["Desktop Chrome"],
      screenshot: "on",  // always take screenshots for comparison
    },
  },
],
```

This keeps E2E tests and VRT tests in separate directories with potentially different configurations (e.g., VRT may mock API responses while E2E tests run against a real backend).

**Target pages:**
| Page | Route | Theme variants | Priority |
|------|-------|---------------|----------|
| Settings — General | `/settings/general` | 4 (light+dark × default+narrare) | High — stable, deterministic content |
| Settings — AI | `/settings/ai` | 4 | High — stable, deterministic content |
| Worldbuilding | `/worldbuilding` | 4 | High — KB-heavy, layout-critical |
| Analysis | `/analysis` | 4 | Medium — data-dense charts |
| Editor (view + toolbar) | `/editor/[id]` | 4 | Medium — TipTap rendering, toolbar layout |

**Test pattern (per page):**
```typescript
import { test, expect } from "@playwright/test";

test.describe("Settings — General — Visual Regression", () => {
  for (const theme of ["default", "narrare"]) {
    for (const colorScheme of ["light", "dark"]) {
      test(`screenshot: ${theme} ${colorScheme}`, async ({ page }) => {
        await page.goto("/settings/general");
        await page.evaluate((t) => document.documentElement.setAttribute("data-theme", t), theme);
        await page.emulateMedia({ colorScheme });
        await page.waitForLoadState("networkidle");
        await expect(page).toHaveScreenshot(`settings-general-${theme}-${colorScheme}.png`);
      });
    }
  }
});
```

**CI integration:**
- Add a `just test-vrt` recipe: `playwright test --project=vrt`
- Run VRT alongside E2E in CI, or as a separate step for faster feedback
- On snapshot mismatch: CI fails with a diff image in the Playwright report artifact

**Updating snapshots:**
```bash
npx playwright test --project=vrt --update-snapshots
```

**Cross-OS tolerance:**
- Font anti-aliasing differs between Ubuntu minor versions (e.g., 24.04 vs 26.04), causing ~1-2% pixel drift
- VRT project config uses `maxDiffPixelRatio: 0.02` to tolerate this while still catching real visual regressions
- This is the industry-standard approach for cross-OS VRT
- The 2% threshold is set in `playwright.config.ts` in the `vrt` project's `expect.toHaveScreenshot` configuration

**Regenerating baselines from CI artifacts:**
- When screenshot dimensions differ between environments (not just pixel values), `maxDiffPixelRatio` does not help — Playwright requires matching image dimensions
- The canonical fix: run CI, download the failed test's `actual.png` render from the `vrt-test-results` artifact, and use it as the new baseline
- Workflow:
  1. Trigger CI run (push to main or PR branch)
  2. If VRT fails, download artifact: `gh run download <run-id> -n vrt-test-results`
  3. Find `actual.png` files in the downloaded artifact directory
  4. Copy each `actual.png` to the matching `*-vrt-linux.png` in `packages/web/tests/screenshots/design-tokens.spec.ts-snapshots/`
  5. Commit with message documenting the CI run ID and reason
- This ensures baselines match the exact CI rendering environment (Ubuntu 24.04, CI Playwright version, CI Chromium version)

**Flakiness mitigation:**
- Mock all API responses for snapshot test pages (`page.route()`)
- Use deterministic seed data (no random content, no real dates in snapshot view)
- Set `animations: "disabled"` in Playwright config for VRT project
- Set viewport to fixed dimensions (1280×720)

---

### Design-Tokens Route

**Route location:**
```
packages/web/app/dev/design-tokens/page.tsx
```

**Dev guard:**
```typescript
// packages/web/app/dev/design-tokens/page.tsx
import { notFound } from "next/navigation";

export default function DesignTokensPage() {
  if (process.env.NODE_ENV !== "development") {
    notFound();
  }
  return <TokenDisplay />;
}
```

Alternatively, the entire `/dev` route segment can be conditionally excluded at build time via Next.js config or middleware. The `notFound()` guard is the simplest approach.

**Sections to document:**

1. **Color palette** — all `--color-*` CSS variables rendered as colored swatches with hex/rgb values. Show all 4 theme combinations (`:root` light, `:root` dark, `[data-theme="narrare"]` light, `[data-theme="narrare"]` dark).

2. **Radii** — `--radius-{sm, md, lg, xl}` rendered as visual boxes with the radius value and a size label.

3. **Typography** — system font stack displayed as rendered text samples. Heading scale (`h1`–`h6`) with font-size, line-height, font-weight. Body text with the primary font stack.

4. **Editor tokens** — `--editor-*` CSS variables (TipTap/ProseMirror specific: editor background, caret color, selection highlight, gutter, active node indicator). Sampled from the TipTap editor's CSS variable output.

5. **Theme comparison** — side-by-side view of the same component (e.g., a card, button, input) rendered in `:root` vs `[data-theme="narrare"]`, in both light and dark mode. This gives developers an immediate visual sense of how the two themes differ.

6. **Tailwind utility mapping** — which CSS variable maps to which Tailwind utility class. Example:

   ```
   --color-brand-primary  →  bg-brand-primary, text-brand-primary, border-brand-primary
   --color-bg-primary     →  bg-primary
   --radius-md            →  rounded-md
   ```

**Implementation approach:**
- Read CSS variables from `document.documentElement` using `getComputedStyle()` at runtime (client component)
- Use a React Server Component for the page layout, with a client component for the live variable reader
- Organize variables into the sections above using a declarative config (array of variable names per section)
- Allow theme toggling via buttons (light/dark, default/narrare) — the variable reader re-reads on theme change

**Excluded from production:**
- The entire `packages/web/app/dev/` directory should not be deployed to production. Ensure either:
  - `next.config.js` excludes it during `next build`, or
  - The runtime guard (`notFound()`) prevents access
  - A build-time check verifies no `/dev` routes exist in the production bundle

---

### What is NOT in scope

- **Storybook**: explicitly rejected (see Options). No Storybook adoption is planned.
- **Dedicated design-token platform** (ZeroHeight, Specify, Figma Tokens): explicitly rejected. The dev-route is sufficient for a single-product team.
- **Accessibility audit tooling** (axe-core, Lighthouse CI): not part of this decision. Could be added as a separate ADR if needed.
- **Interaction tests in VRT**: not needed. Vitest + Testing Library covers component interactions. VRT is purely visual.
- **Mobile viewport snapshots**: deferred. Initial VRT targets desktop (1280×720) only. Mobile viewports can be added when mobile-responsive pages are a priority.
- **Automatic CSS variable documentation generation**: the dev-route manually lists variable names. Automated extraction from CSS files is a future enhancement.

---

## Review Trigger

- [ ] After 3 months — evaluate if snapshot flakiness is a significant burden; if so, consider mocking improvements or reducing snapshot count
- [ ] When Next.js 17 or React 20 is adopted — re-evaluate if Storybook compatibility has improved enough to warrant a migration
- [ ] When a genuine `ui/` presentational component layer emerges (>10 reusable components) — reconsider Option C (Storybook scoped to ui/)
- [ ] When cross-browser visual issues are reported — evaluate adding Firefox/WebKit Playwright projects for VRT
- [ ] When the team grows beyond 3 frontend developers — reconsider if a richer design documentation tool (ZeroHeight, Figma Tokens) adds value
- [ ] When GitHub Actions runner image updates to a new Ubuntu LTS (e.g., 26.04) — regenerate all VRT baselines in CI to match the new rendering environment

---

## Sustainability Check

1. **Correct in 3 months?** Yes. Playwright is stable, well-maintained, and already in use. The dev-route is trivially maintainable (a single page with static variable lists).
2. **Hard-to-undo coupling?** None. VRT is a Playwright project — removing it means deleting the test directory and one project entry in the config. The dev-route is a single page behind a dev guard — removing it means deleting the file.
3. **Simplest correct solution?** Yes. Zero new dependencies, ~200 lines of new code for the dev-route, ~50 lines per snapshot test file.
4. **Design intent clear?** Yes. "VRT via Playwright, design tokens via dev route" is self-explanatory from the file names and directory structure.

---

## RULE-XX Compliance

| Rule | Status | Nachweis |
|------|--------|----------|
| RULE-03 | ✅ | This ADR is the contract — defines the VRT and documentation strategy before implementation |
| RULE-04 | ✅ | No file-size impact — new files are small (dev-route ~200 lines, snapshot tests ~50 lines each) |
| RULE-05 | ✅ | Changes stay in their module boundaries: VRT in `packages/web/tests/screenshots/`, dev-route in `packages/web/app/dev/` |
| RULE-06 | ✅ | Each file has one responsibility: one snapshot spec per page, one dev-route page |
| RULE-07 | ✅ | No cross-layer dependencies — frontend-only changes |
| RULE-09 | ✅ | All new test code is fully typed (TypeScript strict) |
| RULE-10 | ✅ | Test plan defined (8+ snapshot specs, 4 theme combinations each) |
| RULE-11 | ✅ | No silent failures — snapshot diffs are visible in Playwright report artifacts |
| RULE-13 | ✅ | Not applicable (no streaming/interface change) |
| RULE-15 | ✅ | No new middleware — dev-route uses standard Next.js page with runtime guard |
| RULE-17 | ✅ | No API contract changes — frontend-only |
| RULE-20 | ✅ | Full implementation — no half-implementations, no deferrals within scope |
| RULE-22 | ✅ | Single-feature concern (VRT + documentation) — no cross-feature impact |
