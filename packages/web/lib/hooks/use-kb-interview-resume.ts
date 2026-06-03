/**
 * KB Interview Resume — persist minimized interview state to localStorage so
 * cancelled interviews can be resumed later when the user allows it.
 *
 * Design decisions:
 * - localStorage (not sessionStorage): survives tab close for a short TTL
 * - Keyed by novelId: one pending interview per project
 * - Minimal state: sessionId + entityType — actual data lives on the backend
 * - Privacy: TTL expiry and user-controlled disabled mode
 * - Clean separation: this module only manages persistence, not UI
 */

const STORAGE_KEY_PREFIX = "narrare:kbInterview:";
const PERSISTENCE_DISABLED_KEY = "narrare:kbInterview:persistenceDisabled";
const DEFAULT_TTL_MS = 24 * 60 * 60 * 1000;

export interface PendingInterview {
  sessionId: string;
  entityType: string;
  savedAt: number;
  expiresAt: number;
}

// ---------------------------------------------------------------------------
// Pure storage functions
// ---------------------------------------------------------------------------

/** Save interview state so it can be resumed later. */
export function savePendingInterview(
  novelId: string,
  sessionId: string,
  entityType: string,
  ttlMs = DEFAULT_TTL_MS,
): void {
  if (typeof window === "undefined") return;
  if (isInterviewResumePersistenceDisabled()) {
    clearPendingInterview(novelId);
    return;
  }
  const now = Date.now();
  const data: PendingInterview = {
    sessionId,
    entityType,
    savedAt: now,
    expiresAt: now + ttlMs,
  };
  try {
    localStorage.setItem(`${STORAGE_KEY_PREFIX}${novelId}`, JSON.stringify(data));
  } catch (error) {
    console.warn("Unable to save pending KB interview", error);
  }
}

/** Retrieve and keep (don't clear) a pending interview. Returns null if none. */
export function getPendingInterview(novelId: string): PendingInterview | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(`${STORAGE_KEY_PREFIX}${novelId}`);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as Partial<PendingInterview>;
    if (!parsed.sessionId || !parsed.entityType || !parsed.savedAt || !parsed.expiresAt) {
      clearPendingInterview(novelId);
      return null;
    }
    if (parsed.expiresAt <= Date.now()) {
      clearPendingInterview(novelId);
      return null;
    }
    return parsed as PendingInterview;
  } catch (error) {
    console.warn("Unable to read pending KB interview", error);
    clearPendingInterview(novelId);
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
  return getPendingInterview(novelId) !== null;
}

export function isInterviewResumePersistenceDisabled(): boolean {
  if (typeof window === "undefined") return false;
  return localStorage.getItem(PERSISTENCE_DISABLED_KEY) === "true";
}

export function setInterviewResumePersistenceDisabled(disabled: boolean): void {
  if (typeof window === "undefined") return;
  if (disabled) {
    localStorage.setItem(PERSISTENCE_DISABLED_KEY, "true");
    return;
  }
  localStorage.removeItem(PERSISTENCE_DISABLED_KEY);
}
