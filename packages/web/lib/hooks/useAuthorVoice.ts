"use client";

/**
 * useAuthorVoice — SSE streaming hook for Author Voice analysis (ANAL-007).
 *
 * Wraps {@link useAIOperation} with the author-voice streaming logic, the
 * same way `useCharacterVoice` wraps `streamCharacterVoice`. The
 * callback-based SSE stream ({@link streamAuthorVoice}) is bridged to the
 * hook's `execute(signal) => Promise<T>` contract:
 *
 *  - `onProgress` / `onResult` refresh the streaming liveness timer
 *    (`notifyData` → keeps the connection-loss watchdog from firing)
 *  - the single `onResult` resolves with the assembled profile (author voice
 *    is ONE profile per novel — not per-character like ANAL-008)
 *  - `onComplete` resolves the promise with the captured result
 *  - `onError` rejects the promise
 *  - abort is translated to an `AbortError` rejection (swallowed by
 *    `useAIOperation` on cancel)
 *
 * The profile is captured across the run and surfaced once on completion
 * (mirrors the on-demand single-result pattern, distinct from the
 * character-voice array accumulator).
 *
 * Enforces §16 AI-Interaction Standards / ADR-043: no manual AbortController —
 * the abort signal comes from `useAIOperation`.
 *
 * @module useAuthorVoice
 */

import { useCallback, useRef } from "react";
import { type AuthorVoiceResult, streamAuthorVoice } from "@/lib/api/author-voice-stream";
import { useAIOperation } from "@/lib/hooks/use-ai-operation";

/**
 * @returns The AI-operation lifecycle (state, flags, cancel/retry/reset) plus
 *          {@link run}, which starts the analysis for a given novel/chapters,
 *          and {@link result} — the captured profile (null until the run
 *          completes).
 */
export function useAuthorVoice() {
  // Staged before each start() so execute() reads the current values via refs.
  const novelIdRef = useRef<string | null>(null);
  const chapterIdsRef = useRef<string[] | null>(null);

  const {
    state,
    start,
    cancel,
    retry,
    reset,
    notifyData,
    isIdle,
    isLoading,
    isStreaming,
    isComplete,
    isError,
    isConnectionLost,
  } = useAIOperation<AuthorVoiceResult>({
    execute: (signal) =>
      new Promise<AuthorVoiceResult>((resolve, reject) => {
        const id = novelIdRef.current;
        if (!id) {
          reject(new Error("No novel id provided for author-voice analysis"));
          return;
        }

        let settled = false;
        let captured: AuthorVoiceResult | null = null;

        const onAbort = () => {
          if (!settled) {
            settled = true;
            reject(new DOMException("Aborted", "AbortError"));
          }
        };
        signal.addEventListener("abort", onAbort, { once: true });

        streamAuthorVoice(
          id,
          { chapter_ids: chapterIdsRef.current },
          {
            onProgress: () => notifyData(),
            onResult: (result) => {
              notifyData();
              // Author voice is ONE profile per novel — capture the single
              // result event (the last one wins, defensively).
              captured = result;
            },
            onComplete: () => {
              if (!settled) {
                settled = true;
                signal.removeEventListener("abort", onAbort);
                resolve(captured ?? { novel_id: id, profile: null });
              }
            },
            onError: (err) => {
              if (!settled) {
                settled = true;
                signal.removeEventListener("abort", onAbort);
                reject(err);
              }
            },
          },
          signal,
        );
      }),
    connectionLossTimeout: 15_000,
  });

  /** Stage the novel/chapters and start the author-voice analysis. */
  const run = useCallback(
    (novelId: string, chapterIds?: string[] | null) => {
      novelIdRef.current = novelId;
      chapterIdsRef.current = chapterIds ?? null;
      start();
    },
    [start],
  );

  return {
    state,
    result: state.result,
    error: state.error,
    run,
    cancel,
    retry,
    reset,
    isIdle,
    isLoading,
    isStreaming,
    isComplete,
    isError,
    isConnectionLost,
  };
}
