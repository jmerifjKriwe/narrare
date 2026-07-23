/**
 * Type augmentation for the `vitest-axe` `toHaveNoViolations` matcher.
 *
 * `vitest-axe@0.1.0` ships its own `extend-expect.d.ts`, but that file targets
 * vitest <1 and augments the legacy `declare global { namespace Vi }` shape,
 * which vitest 4 no longer exposes — so the matcher type never reaches
 * `expect(...)`. This file mirrors the pattern used by
 * `@testing-library/jest-dom/vitest` (a `declare module "vitest"` interface
 * merge) so `expect(await runAxe(container)).toHaveNoViolations()` is typed in
 * every test file.
 *
 * Runtime registration lives in `setupTests.ts` (`expect.extend(matchers)`).
 */
import "vitest";
import type { AxeMatchers } from "vitest-axe/matchers";

declare module "vitest" {
  interface Assertion<T = unknown> extends AxeMatchers {}
  interface AsymmetricMatchersContaining extends AxeMatchers {}
}
