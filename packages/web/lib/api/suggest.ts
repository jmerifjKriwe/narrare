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
 */

import { connectSSE } from "./streaming";

export interface SuggestChunk {
  text: string;
  is_final: boolean;
}

/**
 * Creates a suggestion fetcher function bound to a specific chapterId.
 *
 * The returned function matches the GhostText extension's `fetchSuggestion` option
 * signature: `({ textBefore, textAfter, signal }) => Promise<string>`.
 *
 * Handles the abort signal explicitly because connectSSE catches AbortError
 * internally and returns without calling any callbacks — without this listener,
 * the returned Promise would never settle on abort.
 */
export function createSseSuggestionFetcher(
  chapterId: string,
  language: string = "en",
): (params: { textBefore: string; textAfter: string; signal: AbortSignal }) => Promise<string> {
  return (params: {
    textBefore: string;
    textAfter: string;
    signal: AbortSignal;
  }): Promise<string> => {
    const { textBefore, textAfter, signal } = params;

    return new Promise<string>((resolve, reject) => {
      let settled = false;

      const onAbort = () => {
        if (!settled) {
          settled = true;
          reject(new DOMException("Aborted", "AbortError"));
        }
      };

      // If signal is already aborted, reject immediately
      if (signal.aborted) {
        onAbort();
        return;
      }

      signal.addEventListener("abort", onAbort, { once: true });

      let accumulated = "";

      connectSSE<SuggestChunk>({
        url: `/writing/chapters/${chapterId}/suggest`,
        body: {
          text_before: textBefore,
          text_after: textAfter || undefined,
          language,
        },
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
        onError: (error) => {
          if (!settled) {
            settled = true;
            signal.removeEventListener("abort", onAbort);
            reject(error);
          }
        },
        signal,
      });
    });
  };
}
