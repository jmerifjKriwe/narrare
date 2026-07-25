"use client";

import { useReducedMotion as motionUseReducedMotion } from "motion/react";

/**
 * Wrapper around motion's useReducedMotion.
 * Returns true when the user prefers reduced motion.
 * Falls back to false (animations enabled) if the hook is unavailable.
 */
export function useReducedMotion(): boolean {
  const prefersReduced = motionUseReducedMotion();
  return prefersReduced ?? false;
}
