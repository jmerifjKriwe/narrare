"use client";

/**
 * Shared utilities for ConsistencyPanel.
 *
 * Extracts pure helper functions and a reusable elapsed-timer hook
 * from ConsistencyPanel for modularity (RULE-04).
 *
 * @module consistencyPanelUtils
 */

import { useEffect, useRef, useState } from "react";
import type { AIErrorResponse } from "@/lib/hooks/use-ai-operation";

// ---------------------------------------------------------------------------
// Scope helpers
// ---------------------------------------------------------------------------

/** Scope controls which chapters are included in the check. */
export type Scope = "current" | "selected" | "all";

/**
 * Resolve a Scope value to an explicit list of chapter IDs.
 *
 * - "current" → the active chapter (or the first available)
 * - "selected" → the full list passed by the parent
 * - "all" → empty array (server interprets as "all chapters")
 */
export function getChapterIdsForScope(
  scope: Scope,
  activeChapterId: string | null,
  chapterIds: string[],
): string[] {
  if (scope === "current") return activeChapterId ? [activeChapterId] : chapterIds.slice(0, 1);
  if (scope === "all") return [];
  return chapterIds;
}

// ---------------------------------------------------------------------------
// Error message helper
// ---------------------------------------------------------------------------

/**
 * Resolve a structured AIErrorResponse to a user-visible message string.
 *
 * Tries the i18n key from the structured error first (studio.aiActions.*
 * namespace), falling back to the raw userMessage or a generic error string.
 */
export function getConsistencyErrorMessage(
  error: AIErrorResponse | null,
  t: (key: string) => string,
  tStudio: (key: string) => string,
): string {
  if (!error) return t("error");
  // Try studio.aiActions.* key first (structured errors)
  try {
    return tStudio(error.i18nKey);
  } catch {
    return error.userMessage || t("error");
  }
}

// ---------------------------------------------------------------------------
// Elapsed timer hook
// ---------------------------------------------------------------------------

/**
 * Track elapsed seconds during a loading state.
 *
 * Resets the counter when `isActive` is false. Returns the current count
 * and a human-readable step label that progresses through four phases.
 */
export function useElapsedTimer(isActive: boolean): { elapsed: number; loadingStep: string } {
  const [elapsed, setElapsed] = useState(0);
  const elapsedRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!isActive) {
      setElapsed(0);
      return;
    }
    elapsedRef.current = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => {
      if (elapsedRef.current) clearInterval(elapsedRef.current);
    };
  }, [isActive]);

  const loadingStep =
    elapsed < 5
      ? "collecting"
      : elapsed < 15
        ? "loading"
        : elapsed < 35
          ? "analyzing"
          : "finishing";

  return { elapsed, loadingStep };
}
