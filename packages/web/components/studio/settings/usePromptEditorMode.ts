"use client";

import { useCallback, useEffect, useState } from "react";

/** Prompt editor expertise mode: "simple" hides advanced features. */
export type PromptEditorMode = "simple" | "expert";

const STORAGE_KEY = "narrare.prompt-editor.mode";
const DEFAULT_MODE: PromptEditorMode = "simple";

/**
 * usePromptEditorMode — simple/expert toggle for the :component:`PromptEditor`.
 *
 * Persists the user's choice in ``localStorage`` so the preference survives
 * reloads. The default is "simple" so non-developers see a reduced UI.
 *
 * The persisted value is read in a ``useEffect`` (not a lazy initializer) to
 * avoid SSR/hydration mismatches: the server and the first client render
 * always use the default, then the client syncs from storage. This follows
 * the standard Next.js client-component localStorage pattern.
 *
 * RULE-06: keeps :component:`PromptEditor` presentation-only by encapsulating
 * the persistence logic here.
 *
 * @returns the active mode, an ``isExpert`` convenience flag, and a ``setMode``
 *          setter that also persists the choice.
 */
export function usePromptEditorMode(): {
  readonly mode: PromptEditorMode;
  readonly isExpert: boolean;
  readonly setMode: (mode: PromptEditorMode) => void;
} {
  const [mode, setModeState] = useState<PromptEditorMode>(DEFAULT_MODE);

  // Sync from localStorage on mount (SSR-safe — only runs in the browser).
  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (stored === "simple" || stored === "expert") {
        setModeState(stored);
      }
    } catch {
      // localStorage unavailable (private mode / disabled) — keep default.
    }
  }, []);

  const setMode = useCallback((next: PromptEditorMode): void => {
    setModeState(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Ignore persistence failures — in-memory state still updates.
    }
  }, []);

  return { mode, isExpert: mode === "expert", setMode };
}
