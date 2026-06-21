/**
 * GhostText fetching-state tests (CR-AUFG-07-10).
 *
 * Verifies that the visible fetching status indicator toggles correctly:
 * `_isFetching` is set to true while a suggestion request is in-flight and
 * cleared when the request resolves, is aborted, or errors.
 *
 * The decoration rendering itself (ProseMirror plugin) is covered indirectly
 * — these tests assert the storage state that drives the decoration.
 */

import { describe, expect, it, vi } from "vitest";
import { fetchAndStreamSuggestion } from "../ghost-text-helpers";
import type { GhostTextOptions, GhostTextStorage } from "../ghost-text-types";

// ── Mock helpers ──────────────────────────────────────────────────────────────

/** Minimal editor mock satisfying the methods used by the helper. */
function makeEditor(head = 5) {
  const dispatch = vi.fn();
  const tr = {};
  return {
    isDestroyed: false,
    view: { dispatch },
    state: {
      tr,
      selection: { head },
    },
  } as unknown as Parameters<typeof fetchAndStreamSuggestion>[1];
}

function makeStorage(): GhostTextStorage {
  return {
    currentSuggestion: null,
    suggestionPos: null,
    _fullSuggestion: null,
    _abortController: null,
    _isFetching: false,
    _streamTimer: null,
    _pendingTimer: null,
    _enabled: true,
    _suggestionDelay: 0,
    _cache: new Map(),
    _cacheMaxAge: 30_000,
    _cacheMaxSize: 50,
    _analytics: { accepted: 0, rejected: 0, total: 0 },
    _errorStatusVisible: false,
    _errorTimer: null,
    setGhostText: vi.fn(),
    clearGhostText: vi.fn(),
    setEnabled: vi.fn(),
    setDelay: vi.fn(),
    getAnalytics: () => ({ accepted: 0, rejected: 0, total: 0 }),
  };
}

function makeOptions(
  fetchImpl: (params: {
    textBefore: string;
    textAfter: string;
    signal: AbortSignal;
  }) => Promise<string>,
): GhostTextOptions {
  return {
    fetchSuggestion: fetchImpl,
    suggestionDelay: 800,
    minChars: 5,
    enabled: true,
    fetchingStatusText: "AI is thinking...",
    errorStatusText: "Suggestion unavailable",
    errorStatusDurationMs: 4000,
  };
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("GhostText fetching status (CR-AUFG-07-10)", () => {
  it("sets _isFetching=true while a suggestion request is in-flight", async () => {
    const storage = makeStorage();
    const editor = makeEditor();
    let resolveFetch: ((value: string) => void) | undefined;
    const slowFetch = () =>
      new Promise<string>((resolve) => {
        resolveFetch = resolve;
      });

    const promise = fetchAndStreamSuggestion(
      storage,
      editor,
      makeOptions(slowFetch),
      "The old house",
      "",
    );

    // While the fetch is pending, the fetching flag must be set so the
    // decoration plugin can render the visible status indicator.
    expect(storage._isFetching).toBe(true);
    expect(storage.suggestionPos).toBe(5);

    // Let the fetch resolve
    resolveFetch?.(" stood at the end of the lane.");
    await promise;

    expect(storage._isFetching).toBe(false);
  });

  it("clears _isFetching when the fetch resolves successfully", async () => {
    const storage = makeStorage();
    const editor = makeEditor();
    const fastFetch = vi.fn().mockResolvedValue(" a suggestion");

    await fetchAndStreamSuggestion(storage, editor, makeOptions(fastFetch), "hello", "");

    expect(storage._isFetching).toBe(false);
  });

  it("clears _isFetching when the fetch is aborted", async () => {
    const storage = makeStorage();
    const editor = makeEditor();
    const abortingFetch = vi.fn((_params: { signal: AbortSignal }) => {
      return new Promise<string>((_resolve, reject) => {
        // Immediately reject with AbortError
        reject(new DOMException("Aborted", "AbortError"));
      });
    });

    await fetchAndStreamSuggestion(storage, editor, makeOptions(abortingFetch), "hello", "");

    expect(storage._isFetching).toBe(false);
  });

  it("does NOT set _isFetching on a cache hit (no network request)", async () => {
    const storage = makeStorage();
    // Pre-populate cache
    storage._cache.set("hello", { text: " cached text", timestamp: Date.now() });
    const editor = makeEditor();
    const fetchImpl = vi.fn();

    await fetchAndStreamSuggestion(storage, editor, makeOptions(fetchImpl), "hello", "");

    // Cache hit → fetchImpl never called, _isFetching stays false
    expect(fetchImpl).not.toHaveBeenCalled();
    expect(storage._isFetching).toBe(false);
  });

  it("dispatches a transaction so decorations re-evaluate on status change", async () => {
    const storage = makeStorage();
    const editor = makeEditor();
    const dispatch = editor.view.dispatch as unknown as ReturnType<typeof vi.fn>;
    let resolveFetch: ((value: string) => void) | undefined;
    const slowFetch = () =>
      new Promise<string>((resolve) => {
        resolveFetch = resolve;
      });

    const promise = fetchAndStreamSuggestion(
      storage,
      editor,
      makeOptions(slowFetch),
      "The old house",
      "",
    );

    // At least one dispatch when fetching starts
    expect(dispatch).toHaveBeenCalled();

    resolveFetch?.(" stood at the end of the lane.");
    await promise;

    // Dispatch called again when fetching ends (re-render to clear indicator)
    expect(dispatch.mock.calls.length).toBeGreaterThanOrEqual(2);
  });
});

// ── Error affordance tests (CR-AUFG-07-15) ────────────────────────────────────

describe("GhostText fetch error affordance (CR-AUFG-07-15)", () => {
  it("sets _errorStatusVisible=true when fetch rejects with non-AbortError", async () => {
    const storage = makeStorage();
    const editor = makeEditor();
    const failingFetch = vi.fn().mockRejectedValue(new Error("Network down"));

    await fetchAndStreamSuggestion(storage, editor, makeOptions(failingFetch), "hello", "");

    expect(storage._errorStatusVisible).toBe(true);
    expect(storage._errorTimer).not.toBeNull();
  });

  it("does NOT set _errorStatusVisible when fetch rejects with AbortError", async () => {
    const storage = makeStorage();
    const editor = makeEditor();
    const abortingFetch = vi.fn().mockRejectedValue(new DOMException("Aborted", "AbortError"));

    await fetchAndStreamSuggestion(storage, editor, makeOptions(abortingFetch), "hello", "");

    expect(storage._errorStatusVisible).toBe(false);
    expect(storage._errorTimer).toBeNull();
  });

  it("auto-clears _errorStatusVisible after errorStatusDurationMs", async () => {
    vi.useFakeTimers();
    try {
      const storage = makeStorage();
      const editor = makeEditor();
      const failingFetch = vi.fn().mockRejectedValue(new Error("Network down"));

      await fetchAndStreamSuggestion(storage, editor, makeOptions(failingFetch), "hello", "");

      expect(storage._errorStatusVisible).toBe(true);

      vi.advanceTimersByTime(4000);

      expect(storage._errorStatusVisible).toBe(false);
      expect(storage._errorTimer).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it("clears previous error status when a new fetch starts", async () => {
    const storage = makeStorage();
    const editor = makeEditor();
    const failingFetch = vi.fn().mockRejectedValue(new Error("Network down"));

    // First fetch fails → error status visible
    await fetchAndStreamSuggestion(storage, editor, makeOptions(failingFetch), "hello", "");
    expect(storage._errorStatusVisible).toBe(true);

    // Second fetch starts (never-resolving) → should clear error status
    let resolveSecondFetch: ((value: string) => void) | undefined;
    const slowFetch = () =>
      new Promise<string>((resolve) => {
        resolveSecondFetch = resolve;
      });

    const promise = fetchAndStreamSuggestion(storage, editor, makeOptions(slowFetch), "world", "");

    // Synchronous portion (including clearErrorStatus) runs before first await
    expect(storage._errorStatusVisible).toBe(false);
    expect(storage._errorTimer).toBeNull();

    // Cleanup: resolve the pending fetch
    resolveSecondFetch?.(" resolved text");
    await promise;
  });

  it("clears error status on cache hit", async () => {
    const storage = makeStorage();
    const editor = makeEditor();

    // First fetch fails → error state
    const failingFetch = vi.fn().mockRejectedValue(new Error("Network down"));
    await fetchAndStreamSuggestion(storage, editor, makeOptions(failingFetch), "hello", "");
    expect(storage._errorStatusVisible).toBe(true);

    // Pre-populate cache for a different prefix
    storage._cache.set("world", { text: " cached text", timestamp: Date.now() });
    const neverCalledFetch = vi.fn();

    await fetchAndStreamSuggestion(storage, editor, makeOptions(neverCalledFetch), "world", "");

    expect(storage._errorStatusVisible).toBe(false);
    expect(neverCalledFetch).not.toHaveBeenCalled();
  });
});
