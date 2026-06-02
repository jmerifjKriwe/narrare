/**
 * KB Interview Resume — persist interview state to localStorage so
 * cancelled interviews can be resumed later.
 *
 * Design decisions:
 * - localStorage (not sessionStorage): survives tab close — user can come back later
 * - Keyed by novelId: one pending interview per project
 * - Minimal state: sessionId + entityType — actual data lives on the backend
 * - Clean separation: this module only manages persistence, not UI
 */

const STORAGE_KEY_PREFIX = "narrare:kbInterview:";

export interface PendingInterview {
  sessionId: string;
  entityType: string;
  savedAt: number;
}

// ---------------------------------------------------------------------------
// Pure storage functions
// ---------------------------------------------------------------------------

/** Save interview state so it can be resumed later. */
export function savePendingInterview(novelId: string, sessionId: string, entityType: string): void {
  if (typeof window === "undefined") return;
  const data: PendingInterview = {
    sessionId,
    entityType,
    savedAt: Date.now(),
  };
  try {
    localStorage.setItem(`${STORAGE_KEY_PREFIX}${novelId}`, JSON.stringify(data));
  } catch {
    // localStorage full or unavailable — best effort
  }
}

/** Retrieve and keep (don't clear) a pending interview. Returns null if none. */
export function getPendingInterview(novelId: string): PendingInterview | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(`${STORAGE_KEY_PREFIX}${novelId}`);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as PendingInterview;
  } catch {
    return null;
  }
}

/** Clear the pending interview (after resume or discard). */
export function clearPendingInterview(novelId: string): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(`${STORAGE_KEY_PREFIX}${novelId}`);
}

/** Check whether a pending interview exists for this project. */
export function hasPendingInterview(novelId: string): boolean {
  if (typeof window === "undefined") return false;
  return localStorage.getItem(`${STORAGE_KEY_PREFIX}${novelId}`) !== null;
}
