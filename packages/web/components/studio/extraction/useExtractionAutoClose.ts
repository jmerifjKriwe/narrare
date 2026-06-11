"use client";

/**
 * useExtractionAutoClose — Auto-close timer for extraction completion.
 *
 * Extracted from useExtractionPhase as a focused sub-hook (RULE-04, RULE-06).
 * Starts a 2-second countdown when the target phase is reached, then
 * fires onClose. Cancels on phase change or unmount.
 */

import { useEffect, useRef } from "react";

/** Delay in milliseconds before auto-closing after successful apply. */
const AUTO_CLOSE_DELAY_MS = 2000;

export function useExtractionAutoClose(
  phase: string,
  triggerPhase: string,
  onClose: () => void,
): void {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (phase === triggerPhase) {
      timerRef.current = setTimeout(onClose, AUTO_CLOSE_DELAY_MS);
    }
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [phase, triggerPhase, onClose]);
}
