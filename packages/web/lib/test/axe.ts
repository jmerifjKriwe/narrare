/**
 * Shared axe-core runner for component a11y tests (ADR-069 §28; Task 12).
 *
 * Why a wrapper rather than the bare `vitest-axe` `axe`? Two axe rules are
 * *page-level* concerns that cannot be meaningfully evaluated against an
 * isolated component rendered in happy-dom:
 *
 *  - `color-contrast` resolves the full CSS cascade + `getComputedStyle` to a
 *    concrete contrast ratio. The happy-dom test environment injects no
 *    Tailwind stylesheet, so every element resolves to the default and would
 *    produce systematic false positives. Colour-not-alone is instead verified
 *    structurally (e.g. severity badges render text + a variant class).
 *  - `region` flags content not contained in a landmark (`<main>`/`<nav>` …).
 *    Component tests render in isolation by design, so the rendered fragment
 *    is expectedly outside a landmark. This is asserted at the page level via
 *    the Playwright VRT suite (Task 13).
 *
 * Both exclusions are the documented, minimal set — no rule is disabled to
 * hide a genuine component-level defect. Call sites pass a rendered container
 * (or HTML string) and assert `expect(await runAxe(container)).toHaveNoViolations()`.
 *
 * @module lib/test/axe
 */
import { configureAxe } from "vitest-axe";

/** axe runner with the two page-level rules disabled (see module docs). */
export const runAxe = configureAxe({
  rules: {
    "color-contrast": { enabled: false },
    region: { enabled: false },
  },
});
