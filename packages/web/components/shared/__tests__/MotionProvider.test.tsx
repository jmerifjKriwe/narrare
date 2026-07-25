/**
 * Regression test for the global reduced-motion mechanism.
 *
 * Background — `docs/superpowers/specs/2026-07-24-motion-activation-design.md`
 * (Reduced Motion section) requires: "When active, ALL animations are reduced
 * to simple opacity changes (no Scale, no Translate, no Stagger)." The
 * originally shipped implementation only gated ONE component
 * (`panel-shell.tsx`) via the per-component `useReducedMotion()` hook, leaving
 * ~22 other animated components (modals with scale, lists with stagger, banners
 * with slide) fully animated regardless of the user's OS setting.
 *
 * The fix is motion's idiomatic, centralized `<MotionConfig reducedMotion="user">`
 * root wrapper: a single context provider that makes every descendant
 * `motion.*` component automatically strip transform/layout/scale animations
 * (keeping opacity only) when the OS reports `prefers-reduced-motion: reduce`.
 *
 * Why this asserts the context rather than a rendered transform:
 *  - happy-dom cannot run motion's rAF/WAAPI animation loop, so the *animated*
 *    end-state is never produced in the test DOM (consistent with the documented
 *    limitation in `adaptive-status-indicator-a11y.test.tsx`: "happy-dom cannot
 *    evaluate the prefers-reduced-motion media query").
 *  - motion caches the media-query result in a module-level singleton
 *    (`motion-dom`'s `prefersReducedMotion`) on first `useReducedMotion()` call,
 *    so per-test `window.matchMedia` mocks are unreliable across tests.
 *  - `reducedMotion="user"` is a *static context value* — the single source of
 *    truth that a real browser consumes to drive the reduction. Asserting that
 *    MotionProvider puts `reducedMotion="user"` on `MotionConfigContext`
 *    deterministically proves the global mechanism is wired, without depending
 *    on animation-timing or media-query-cache behaviour.
 */
import { render, screen } from "@testing-library/react";
import { MotionConfigContext } from "motion/react";
import { type ReactNode, useContext } from "react";
import { describe, expect, it } from "vitest";
import { MotionProvider } from "@/components/shared/MotionProvider";

/**
 * Probe that surfaces the MotionConfig context value resolved for a descendant.
 * A real `motion.*` component reads this same context to decide whether to
 * reduce its animations, so this is exactly the value motion consumes.
 */
function MotionConfigProbe() {
  const ctx = useContext(MotionConfigContext) as { reducedMotion?: string } | null;
  const reduced = ctx?.reducedMotion ?? "unset";
  return (
    <div data-testid="probe" data-reduced-motion={reduced}>
      child
    </div>
  );
}

describe("MotionProvider — global reduced-motion mechanism", () => {
  it("provides MotionConfig with reducedMotion='user' to all descendant motion components", () => {
    render(
      <MotionProvider>
        <MotionConfigProbe />
      </MotionProvider>,
    );

    // The context value every descendant motion.* reads. "user" = honor the
    // OS-level prefers-reduced-motion preference (the spec's centralized rule).
    // Without the provider this is "unset" (MotionConfigContext default is
    // undefined) — which is exactly the defect.
    const probe = screen.getByTestId("probe");
    expect(probe.getAttribute("data-reduced-motion")).toBe("user");
  });

  it("renders its children (no content swallowed by the provider)", () => {
    const children: ReactNode = <span>hello</span>;
    const { getByText } = render(<MotionProvider>{children}</MotionProvider>);
    expect(getByText("hello")).toBeDefined();
  });
});
