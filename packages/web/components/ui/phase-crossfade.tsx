"use client";

import { AnimatePresence, motion } from "motion/react";
import { crossfadeVariants } from "@/lib/motion-variants";

interface PhaseCrossfadeProps {
  /** Unique key for the current phase — triggers exit/enter animation on change. */
  readonly phase: string;
  readonly children: React.ReactNode;
}

/**
 * Wraps content with crossfade animation when `phase` changes.
 * Uses `AnimatePresence mode="wait"` so the exiting phase fades out before the
 * entering phase fades in — no overlap or layout shift.
 *
 * Usage:
 *   <PhaseCrossfade phase={currentPhase}>
 *     <div>Phase content here</div>
 *   </PhaseCrossfade>
 */
export function PhaseCrossfade({ phase, children }: PhaseCrossfadeProps) {
  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={phase}
        variants={crossfadeVariants}
        initial="hidden"
        animate="visible"
        exit="exit"
        className="h-full"
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
}
