"use client";

import { MotionConfig } from "motion/react";
import type { ReactNode } from "react";

/**
 * Global motion configuration provider.
 *
 * Wraps the application tree in motion's idiomatic, centralized
 * `<MotionConfig reducedMotion="user">`. This makes EVERY descendant
 * `motion.*` component automatically honor the OS-level
 * `prefers-reduced-motion: reduce` preference: when the user has it enabled,
 * motion reduces all animations to opacity changes only (no scale, translate,
 * stagger, or layout animations).
 *
 * Why a centralized provider rather than per-component `useReducedMotion()`
 * hooks:
 *  - ONE mechanism per concern (architectural-discipline). The prior approach
 *    gated reduced-motion in only a single component (`panel-shell.tsx`) and
 *    missed ~22 others (modals, staggered lists, banners), which is the
 *    accessibility defect this provider fixes.
 *  - DRY: any new `motion.*` component added anywhere in the tree is covered
 *    automatically, with no per-component wiring to forget.
 *
 * This mirrors the other client providers (`QueryProvider`, `AuthProvider`,
 * `ThemeProvider`). It is a client component because `MotionConfig` relies on
 * React context that must hydrate on the client; the root `app/layout.tsx` is a
 * Server Component and cannot host it directly.
 *
 * Spec: `docs/superpowers/specs/2026-07-24-motion-activation-design.md`
 * (Reduced Motion section).
 */
export function MotionProvider({ children }: { children: ReactNode }) {
  return <MotionConfig reducedMotion="user">{children}</MotionConfig>;
}
