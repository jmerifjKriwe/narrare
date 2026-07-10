/**
 * SSE-based suggestion fetcher for GhostText inline AI completions.
 *
 * Connects to the backend POST /api/v1/writing/chapters/{chapter_id}/suggest
 * SSE endpoint and accumulates streaming chunks into a final suggestion string.
 *
 * Architecture decision (Phase 3):
 * Uses connectSSE (from streaming.ts) which handles auth headers, URL prefixing,
 * and SSE line parsing. The factory pattern (createSseSuggestionFetcher) creates
 * a closure over chapterId so the caller doesn't need to pass it on every call,
 * matching the GhostText extension's fetchSuggestion signature.
 *
 * Bounded auto-retry (network-resilience):
 * Because this module runs inside TipTap extensions (outside the React
 * lifecycle) it cannot use useAIOperation() (which is §16-compliant and
 * already provides DEFAULT_MAX_RETRIES). To avoid leaving inline suggestions
 * without any auto-retry on flaky networks, a SINGLE bounded retry is applied
 * here on transient connection-loss errors (`kind === "network"` only).
 * Retry budget is fixed at 1 (2 total attempts) after a short, abortable
 * backoff. No exponential backoff, jitter, budgets, or configurable counts —
 * the scope is deliberately minimal. See fetchSuggestionWithRetry.
 *
 * LIMITATION (§20 documented):
 * This module runs inside TipTap extensions which operate outside React component
 * lifecycle. Full useAIOperation migration is NOT possible because hooks cannot
 * be called from extension code. Error mapping is applied at the transport level
 * using mapSSEError for structured, i18n-ready error classification. However,
 * the TipTap extension itself does not have access to i18n context, so error
 * messages are consumed by the extension's internal error handling (silent dismissal).
 */

import { mapSSEError } from "./ai-error-mapping";
// SSEStreamError is imported as a VALUE (not `type`-only) because the retry
// loop checks `error instanceof SSEStreamError` at runtime — a type-only
// import would be erased by the compiler and `instanceof` would throw
// ReferenceError at runtime.
import { connectSSE, SSEStreamError } from "./streaming";

export interface SuggestChunk {
  text: string;
  is_final: boolean;
}

/** Maximum attempts: 1 original + 1 retry on transient network errors. */
export const MAX_SUGGEST_ATTEMPTS = 2;

/** Fixed backoff (ms) before the single network-error retry. */
export const NETWORK_RETRY_BACKOFF_MS = 400;

/**
 * Connector function type — a thin callback wrapper around connectSSE.
 *
 * Exposed as a dependency-injection seam so `fetchSuggestionWithRetry` can be
 * unit-tested with a fake connector instead of real network I/O (ADR-030,
 * fake-based testing). Production uses `defaultConnect` (the real transport);
 * tests inject a fake that drives attempt outcomes deterministically.
 */
export type SuggestConnectFn = (options: {
  url: string;
  body: unknown;
  onChunk: (chunk: SuggestChunk) => void;
  onComplete: () => void;
  onError: (error: SSEStreamError) => void;
  signal: AbortSignal;
}) => void;

/** Default connector — delegates to the real connectSSE SSE transport. */
const defaultConnect: SuggestConnectFn = (options) => {
  // connectSSE is async but communicates solely via callbacks; the returned
  // promise is intentionally not awaited (callbacks drive settlement).
  void connectSSE<SuggestChunk>({
    url: options.url,
    body: options.body,
    onChunk: options.onChunk,
    onComplete: options.onComplete,
    onError: options.onError,
    signal: options.signal,
  });
};

/**
 * Creates a suggestion fetcher function bound to a specific chapterId.
 *
 * The returned function matches the GhostText extension's `fetchSuggestion` option
 * signature: `({ textBefore, textAfter, signal }) => Promise<string>`.
 *
 * `connect` is an optional DI seam (defaults to the real SSE transport) used by
 * tests to drive the bounded network-retry loop without network I/O (ADR-030).
 */
export function createSseSuggestionFetcher(
  chapterId: string,
  language: string = "en",
  connect: SuggestConnectFn = defaultConnect,
): (params: { textBefore: string; textAfter: string; signal: AbortSignal }) => Promise<string> {
  return ({ textBefore, textAfter, signal }): Promise<string> => {
    const url = `/writing/chapters/${chapterId}/suggest`;
    const body = {
      text_before: textBefore,
      text_after: textAfter || undefined,
      language,
    };
    return fetchSuggestionWithRetry(connect, url, body, signal);
  };
}

/**
 * Fetch a suggestion with a single bounded retry on transient network errors.
 *
 * Retry policy (minimal, deliberately scoped):
 *   - Retries ONLY when an attempt rejects with an `SSEStreamError` whose
 *     `kind === "network"` (connection loss). HTTP, parse, stream, and abort
 *     errors are never retried (server/parse errors are not transient loss).
 *   - At most ONE retry (2 total attempts) after a fixed ~400ms backoff.
 *
 * Abort contract (§20 — no regression): the caller's `signal` is honored at
 * every stage — before each attempt, during the attempt (via the attempt's own
 * abort listener), and during the backoff (abortableDelay). If the signal
 * aborts at any point, the promise rejects with `AbortError` immediately and no
 * further attempts are made.
 *
 * Error mapping: the final rejection is the raw `SSEStreamError` the attempt
 * produced (mapSSEError is applied inside attemptSuggestion, as before), so the
 * extension receives the same structured error class it always has.
 *
 * `connect` is the DI seam for tests (ADR-030).
 */
export async function fetchSuggestionWithRetry(
  connect: SuggestConnectFn,
  url: string,
  body: unknown,
  signal: AbortSignal,
): Promise<string> {
  let lastError: unknown;

  for (let attempt = 0; attempt < MAX_SUGGEST_ATTEMPTS; attempt++) {
    // Defensive: never start an attempt on an already-aborted signal.
    if (signal.aborted) {
      throw new DOMException("Aborted", "AbortError");
    }

    try {
      return await attemptSuggestion(connect, url, body, signal);
    } catch (error) {
      lastError = error;

      // Abort errors propagate immediately and are never retried.
      if (error instanceof DOMException && error.name === "AbortError") {
        throw error;
      }

      const isTransientNetwork = error instanceof SSEStreamError && error.kind === "network";
      const hasRetryLeft = attempt < MAX_SUGGEST_ATTEMPTS - 1;

      if (isTransientNetwork && hasRetryLeft) {
        // Abortable backoff before the single retry. If the signal aborts
        // during the wait, abortableDelay rejects with AbortError which
        // propagates out of this catch (no further attempt).
        await abortableDelay(NETWORK_RETRY_BACKOFF_MS, signal);
        continue;
      }

      // Non-retryable error, or retry budget exhausted — reject as today.
      throw error;
    }
  }

  // Unreachable: the loop always returns or throws on every path.
  // Guarded re-throw keeps the exhaustiveness check satisfied.
  throw lastError;
}

/**
 * A single SSE suggestion attempt.
 *
 * Returns a promise that resolves with the accumulated suggestion text, or
 * rejects with an `SSEStreamError` (http/network/parse/stream) or an
 * `AbortError` (DOMException).
 *
 * Handles the abort signal explicitly because connectSSE catches AbortError
 * internally and returns without calling any callbacks — without this listener,
 * the returned Promise would never settle on abort.
 *
 * Extracted from the original monolithic fetcher so the retry loop can call it
 * once per attempt. `connect` is the DI seam for tests (ADR-030).
 */
function attemptSuggestion(
  connect: SuggestConnectFn,
  url: string,
  body: unknown,
  signal: AbortSignal,
): Promise<string> {
  return new Promise<string>((resolve, reject) => {
    let settled = false;

    const onAbort = () => {
      if (!settled) {
        settled = true;
        reject(new DOMException("Aborted", "AbortError"));
      }
    };

    // If signal is already aborted, reject immediately.
    if (signal.aborted) {
      onAbort();
      return;
    }

    signal.addEventListener("abort", onAbort, { once: true });

    let accumulated = "";

    connect({
      url,
      body,
      onChunk: (chunk) => {
        accumulated += chunk.text;
      },
      onComplete: () => {
        if (!settled) {
          settled = true;
          signal.removeEventListener("abort", onAbort);
          resolve(accumulated);
        }
      },
      onError: (error: SSEStreamError) => {
        if (!settled) {
          settled = true;
          signal.removeEventListener("abort", onAbort);
          // Map through structured error mapper (§11 no silent failures).
          // The mapped error provides i18n keys for any component that
          // catches this error, even though the GhostText extension itself
          // handles errors internally.
          const mapped = mapSSEError(error);
          if (mapped === null) {
            // Abort — treat same as onAbort
            reject(new DOMException("Aborted", "AbortError"));
          } else {
            reject(error);
          }
        }
      },
      signal,
    });
  });
}

/**
 * Resolve after `ms`, or reject with `AbortError` if `signal` aborts first.
 *
 * Checks the signal immediately (before scheduling) and listens for abort
 * during the wait, so an abort during backoff stops the retry immediately.
 */
function abortableDelay(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise<void>((resolve, reject) => {
    if (signal.aborted) {
      reject(new DOMException("Aborted", "AbortError"));
      return;
    }
    const onAbort = () => {
      clearTimeout(timer);
      reject(new DOMException("Aborted", "AbortError"));
    };
    const timer = setTimeout(() => {
      signal.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    signal.addEventListener("abort", onAbort, { once: true });
  });
}
