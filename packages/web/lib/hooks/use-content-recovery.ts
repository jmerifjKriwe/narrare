/**
 * Content recovery — saves editor content to sessionStorage before 401 redirect.
 *
 * When the API client detects an expired session (401 + refresh failed),
 * it calls `saveBeforeRedirect()` synchronously to persist any unsaved
 * editor content. After re-login, the editor checks for recoverable content
 * and restores it with a toast notification.
 *
 * Design decisions:
 * - sessionStorage (not localStorage): cleared when tab closes — no stale data
 * - Synchronous save: no async gap where content could be lost
 * - Callback registration: avoids circular deps between client.ts and editor
 * - Timestamp comparison: only restore if newer than what's in the DB
 */

const STORAGE_KEY_PREFIX = "narrare:unsavedContent:";

export interface SavedContent {
  chapterId: string;
  content: string;
  timestamp: number;
}

// ---------------------------------------------------------------------------
// Pure storage functions (sync, no React dependency)
// ---------------------------------------------------------------------------

/** Save editor content to sessionStorage. Synchronous — no async gap. */
export function saveContent(chapterId: string, content: string): void {
  if (typeof window === "undefined") return;
  const data: SavedContent = { chapterId, content, timestamp: Date.now() };
  try {
    sessionStorage.setItem(`${STORAGE_KEY_PREFIX}${chapterId}`, JSON.stringify(data));
  } catch {
    // sessionStorage full or unavailable — best effort
  }
}

/** Retrieve and clear saved content. Returns null if nothing saved. */
export function recoverContent(chapterId: string): SavedContent | null {
  if (typeof window === "undefined") return null;
  const key = `${STORAGE_KEY_PREFIX}${chapterId}`;
  const raw = sessionStorage.getItem(key);
  if (!raw) return null;
  sessionStorage.removeItem(key);
  try {
    return JSON.parse(raw) as SavedContent;
  } catch {
    return null;
  }
}

/** Check whether recoverable content exists for a chapter. */
export function hasRecoverableContent(chapterId: string): boolean {
  if (typeof window === "undefined") return false;
  return sessionStorage.getItem(`${STORAGE_KEY_PREFIX}${chapterId}`) !== null;
}

/**
 * Recover content only if it's newer than the database version.
 * Compares the saved timestamp against the chapter's `updated_at`.
 */
export function recoverIfNewer(chapterId: string, dbUpdatedAt: string): SavedContent | null {
  const saved = recoverContent(chapterId);
  if (!saved) return null;
  const dbTimestamp = new Date(dbUpdatedAt).getTime();
  if (saved.timestamp > dbTimestamp) {
    return saved;
  }
  // Saved content is older than DB — discard
  return null;
}

// ---------------------------------------------------------------------------
// Pre-redirect callback registry (used by client.ts)
// ---------------------------------------------------------------------------

type SaveCallback = () => void;
let _saveCallback: SaveCallback | null = null;

/**
 * Register a callback that saves current editor content.
 * Called synchronously by `saveBeforeRedirect()` before redirecting to login.
 *
 * Returns an unregister function for cleanup.
 */
export function registerPreRedirectSave(cb: SaveCallback): () => void {
  _saveCallback = cb;
  return () => {
    if (_saveCallback === cb) {
      _saveCallback = null;
    }
  };
}

/**
 * Save content before redirect. Called by the API client's 401 handler.
 * Synchronous — no await, no gap.
 */
export function saveBeforeRedirect(): void {
  _saveCallback?.();
}
