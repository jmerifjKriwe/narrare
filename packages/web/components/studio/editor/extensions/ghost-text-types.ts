/**
 * ghost-text-types — Shared interfaces for the GhostText TipTap extension.
 *
 * Extracted from GhostText.ts to avoid circular imports between the main
 * extension module and its helper functions.
 */

// ── Interfaces ─────────────────────────────────────────────────────────────────

export interface GhostTextOptions {
  /** Called when a suggestion should be fetched.
   *  Phase 2: uses simulated local generator (built-in default).
   *  Phase 3: connects to real SSE endpoint. */
  fetchSuggestion?: (params: {
    textBefore: string;
    textAfter: string;
    signal: AbortSignal;
  }) => Promise<string>;
  /** Delay in ms before auto-triggering a suggestion after user pauses typing. */
  suggestionDelay?: number;
  /** Minimum characters before auto-triggering. */
  minChars?: number;
  /** Whether ghost text functionality is enabled. */
  enabled?: boolean;
  /** Localized keyboard shortcut hint text (e.g. "Tab accept · Esc dismiss · → word").
   *  Injected from React via Extension options. Falls back to English default. */
  hintText?: string;
  /** Localized status text shown while a suggestion is being fetched
   *  (e.g. "AI is thinking..."). Injected from React via Extension options so
   *  the non-React extension never hardcodes a visible locale string
   *  (CR-AUFG-07-10, ADR-043 Note 7). */
  fetchingStatusText?: string;
  /** Localized transient error text shown after a non-AbortError fetch failure
   *  (e.g. "Suggestion unavailable"). Injected from React via Extension options
   *  so no hardcoded English appears in ProseMirror DOM (CR-AUFG-07-15). */
  errorStatusText?: string;
  /** How long (ms) the transient error decoration stays visible before
   *  auto-clearing. Default: 4000. */
  errorStatusDurationMs?: number;
}

export interface GhostTextStorage {
  /** The currently displayed suggestion text (partial if still streaming), or null */
  currentSuggestion: string | null;
  /** The cursor position (doc-relative) where the suggestion was anchored */
  suggestionPos: number | null;
  /** The full suggestion text returned by fetchSuggestion (for Tab accept) */
  _fullSuggestion: string | null;
  /** AbortController for the pending fetchSuggestion call */
  _abortController: AbortController | null;
  /** Whether a suggestion fetch is currently in-flight (visible status indicator) */
  _isFetching: boolean;
  /** setInterval timer for character-by-character streaming */
  _streamTimer: ReturnType<typeof setInterval> | null;
  /** setTimeout timer for auto-trigger debounce */
  _pendingTimer: ReturnType<typeof setTimeout> | null;

  /** Whether ghost text is currently enabled (reactive, set via setEnabled) */
  _enabled: boolean;
  /** Current suggestion delay in ms (reactive, set via setDelay) */
  _suggestionDelay: number;

  /** Prefix-based suggestion cache to avoid redundant API calls */
  _cache: Map<string, { text: string; timestamp: number }>;
  /** Maximum age of a cache entry in ms (default: 30_000 = 30 seconds) */
  _cacheMaxAge: number;
  /** Maximum number of cache entries before LRU eviction (default: 50) */
  _cacheMaxSize: number;

  /** Minimal analytics counters for future use */
  _analytics: { accepted: number; rejected: number; total: number };

  /** Whether the transient fetch-error decoration is currently visible
   *  (CR-AUFG-07-15). Set by showErrorStatus, auto-cleared after
   *  errorStatusDurationMs or on new fetch / cache hit / success. */
  _errorStatusVisible: boolean;
  /** setTimeout handle for the auto-clear of the error decoration. */
  _errorTimer: ReturnType<typeof setTimeout> | null;

  /** Test hook — programmatically set ghost text at current cursor position */
  setGhostText: (suggestion: string) => void;
  /** Test hook — clear ghost text */
  clearGhostText: () => void;
  /** Enable or disable ghost text at runtime */
  setEnabled: (enabled: boolean) => void;
  /** Update the suggestion delay at runtime */
  setDelay: (delay: number) => void;
  /** Returns analytics counters */
  getAnalytics: () => { accepted: number; rejected: number; total: number };
}
