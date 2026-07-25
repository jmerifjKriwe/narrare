/// <reference types="vitest/globals" />
import "@testing-library/jest-dom/vitest";
import type { ReactElement, ReactNode } from "react";
import { expect, vi } from "vitest";
import * as axeMatchers from "vitest-axe/matchers";
import { server } from "./mocks/server";

// axe-core a11y matchers (ADR-069 §28; Task 12). Registered globally so every
// test file can `expect(await axe(container)).toHaveNoViolations()` without
// re-extending. The matcher TYPE augmentation lives in `types/vitest-axe.d.ts`
// (vitest-axe's bundled `extend-expect.d.ts` targets the legacy `Vi` namespace
// and does not apply to vitest 4).
expect.extend(axeMatchers);

// Mock styled-jsx (Next.js CSS-in-JS) for test environment
vi.mock("styled-jsx", () => ({
  style: ({ children }: { children: React.ReactNode }) => children,
}));

// ---------------------------------------------------------------------------
// motion/react — neutralize the animation engine in the test environment
// ---------------------------------------------------------------------------
// ROOT CAUSE this addresses: components such as `PhaseCrossfade` wrap content
// in `<AnimatePresence mode="wait"><motion.div key={phase}>…</motion.div>`.
// With `mode="wait"` the entering phase is NOT mounted until the exiting
// phase's exit animation has completed. happy-dom cannot drive motion's
// rAF/WAAPI animation loop, so across rapid sequential phase transitions
// (idle → loading → results) the exit-completion callback never fires and the
// final phase's content never mounts within a test's `waitFor` window — every
// analysis-panel component test would otherwise time out.
//
// Component tests verify behaviour (state transitions, copy, a11y), NEVER
// animation timing. The industry-standard remedy is to replace the animation
// primitives with plain render pass-throughs so content is always mounted,
// leaving the real crossfade UX untouched for actual browsers (see spec
// `docs/superpowers/specs/2026-07-24-motion-activation-design.md`).
//
// `MotionConfig` and `MotionConfigContext` are intentionally kept REAL (via
// importActual) so the global reduced-motion wiring — asserted by
// `MotionProvider.test.tsx` — continues to verify the genuine context value
// (`reducedMotion === "user"`).
vi.mock("motion/react", async (importOriginal) => {
  const actual = await importOriginal<typeof import("motion/react")>();
  const { createElement, Fragment } = await import("react");

  // Props that exist only on motion components and have no DOM equivalent.
  // Stripped so React does not warn about unknown attributes on plain elements.
  const MOTION_ONLY_PROPS = new Set([
    "variants",
    "initial",
    "animate",
    "exit",
    "transition",
    "whileHover",
    "whileTap",
    "whileFocus",
    "whileDrag",
    "whileInView",
    "drag",
    "dragConstraints",
    "dragElastic",
    "dragMomentum",
    "layout",
    "layoutId",
    "onAnimationStart",
    "onAnimationComplete",
    "onUpdate",
    "onDrag",
    "onDragStart",
    "onDragEnd",
  ]);

  type MotionComponentProps = Record<string, unknown> & {
    readonly children?: ReactNode;
  };

  // `motion.div`, `motion.section`, `motion.li`, `motion.ul`, … → render as the
  // equivalent plain DOM element, forwarding DOM-valid props (className, style,
  // aria-*, data-*, …) while dropping animation-only props.
  //
  // The component function for each tag is CACHED: `motion.div` must return the
  // SAME function reference across renders, otherwise React sees a new component
  // type on every render and unmounts/remounts the whole subtree (which breaks
  // controlled inputs and click handlers in components like EditorView).
  const componentCache = new Map<string, (props: MotionComponentProps) => ReactElement>();
  const motion = new Proxy(
    {},
    {
      get: (_target: unknown, tag: string) => {
        let component = componentCache.get(tag);
        if (!component) {
          component = (props: MotionComponentProps) => {
            const clean: Record<string, unknown> = {};
            for (const [key, value] of Object.entries(props)) {
              if (!MOTION_ONLY_PROPS.has(key)) {
                clean[key] = value;
              }
            }
            return createElement(tag, clean);
          };
          componentCache.set(tag, component);
        }
        return component;
      },
    },
  );

  // `AnimatePresence` → render children directly. No exit/enter sequencing, so
  // the current phase's content mounts immediately (mode="wait" no longer gates).
  const AnimatePresence = ({ children }: { readonly children?: ReactNode }) =>
    createElement(Fragment, null, children);

  return {
    ...actual,
    AnimatePresence,
    motion,
  };
});

// ---------------------------------------------------------------------------
// Zustand Store Mocks - NOT IMPLEMENTED
// ---------------------------------------------------------------------------
// NOTE: Global zustand store mocks are NOT implemented because:
// 1. The stores (editorStore, wizardStore, themeStore, authStore) have no
//    problematic top-level code - they only define state via create().
// 2. Some tests need the real store (e.g., wizard.test.tsx uses setState).
// 3. The actual failure in tests is missing QueryClientProvider, not stores.
//
// If a specific component fails due to store access at module load time,
// add a targeted mock in that component's test file.
// See: docs/development/testing-standards.md for guidance.

// ---------------------------------------------------------------------------
// next-intl Mock (centralized)
// ---------------------------------------------------------------------------
// All tests use useTranslations() — this global mock ensures consistency.
// Individual test mocks can still override if needed.
vi.mock("next-intl", () => ({
  useTranslations: () => (key: string, params?: Record<string, unknown>) => {
    if (params) {
      return Object.entries(params).reduce((str, [k, v]) => str.replace(`{${k}}`, String(v)), key);
    }
    return key;
  },
  useLocale: () => "en",
  useNow: () => new Date("2024-01-01"),
  useTimeZone: () => "UTC",
}));

// Mock next/navigation globally (useRouter, useParams, useSearchParams, usePathname)
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
  }),
  useParams: () => ({ id: "novel-1" }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/",
}));

// Establish API mocking before all tests
// Start MSW before any test files are imported (must be top-level, not in beforeAll,
// because some modules make fetch calls during import which would bypass MSW).
// Using "bypass" for unhandled requests — MSW handlers exist for all API endpoints now.
server.listen({ onUnhandledRequest: "bypass" });

// Reset any request handlers that are declared during the tests
afterEach(() => server.resetHandlers());

// Clean up after the tests are finished
afterAll(() => server.close());
