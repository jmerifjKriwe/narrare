"use client";

import { useCallback, useMemo } from "react";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STORAGE_KEY = "narrare_seen_tooltips";

// ---------------------------------------------------------------------------
// Storage helpers
// ---------------------------------------------------------------------------

function readSeen(): Set<string> {
  if (typeof window === "undefined") return new Set();
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return new Set();
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return new Set();
    return new Set(parsed.filter((v): v is string => typeof v === "string"));
  } catch {
    return new Set();
  }
}

function writeSeen(set: Set<string>): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEY, JSON.stringify([...set]));
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * useSeenTooltips — Track once-shown AI feature tooltips.
 *
 * Pattern follows GhostTextOnboarding localStorage approach.
 * Persisted across sessions via localStorage key "narrare_seen_tooltips".
 */
export function useSeenTooltips(): {
  isSeen: (tooltipId: string) => boolean;
  markSeen: (tooltipId: string) => void;
  resetAll: () => void;
} {
  const isSeen = useCallback((tooltipId: string): boolean => {
    return readSeen().has(tooltipId);
  }, []);

  const markSeen = useCallback((tooltipId: string): void => {
    const set = readSeen();
    set.add(tooltipId);
    writeSeen(set);
  }, []);

  const resetAll = useCallback((): void => {
    writeSeen(new Set());
  }, []);

  return useMemo(() => ({ isSeen, markSeen, resetAll }), [isSeen, markSeen, resetAll]);
}
