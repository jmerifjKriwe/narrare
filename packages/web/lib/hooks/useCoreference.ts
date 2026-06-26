"use client";

/**
 * useCoreference — SSE streaming hook for Coreference analysis (ANAL-005).
 *
 * Wraps {@link useAIOperation} with the coreference streaming logic, the same
 * way `useUnblockStream` wraps `streamStorySuggestions`. The callback-based
 * SSE stream ({@link streamCoreference}, which emits a single `result` event)
 * is bridged to the hook's `execute(signal) => Promise<T>` contract:
 *
 *  - `onResult` stores the data and notifies the hook (loading → streaming)
 *  - `onComplete` resolves the promise with the collected analysis
 *  - `onError` rejects the promise
 *  - abort is translated to an `AbortError` rejection
 *
 * Enforces §16 AI-Interaction Standards / ADR-043: no manual AbortController.
 *
 * @module useCoreference
 */

import { useCallback, useRef } from "react";
import { type CoreferenceResult, streamCoreference } from "@/lib/api/coreference-stream";
import { useAIOperation } from "@/lib/hooks/use-ai-operation";

/**
 * @param chapterId  Chapter to analyse (SSE URL path parameter).
 * @returns The AI-operation lifecycle (state, flags, cancel/retry/reset) plus
 *          {@link run}, which starts the analysis for the given chapter.
 */
export function useCoreference(chapterId: string | null) {
  // Latest chapter id, staged before each start() so execute() reads the
  // current value via the ref (same pattern as useUnblockStream's
  // instructionsRef).
  const chapterIdRef = useRef<string | null>(chapterId);

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
  } = useAIOperation<CoreferenceResult>({
    execute: (signal) =>
      new Promise<CoreferenceResult>((resolve, reject) => {
        const id = chapterIdRef.current;
        if (!id) {
          reject(new Error("No chapter selected for coreference analysis"));
          return;
        }

        let settled = false;
        let collected: CoreferenceResult | null = null;

        const onAbort = () => {
          if (!settled) {
            settled = true;
            reject(new DOMException("Aborted", "AbortError"));
          }
        };
        signal.addEventListener("abort", onAbort, { once: true });

        streamCoreference(
          id,
          {
            onResult: (result) => {
              notifyData();
              collected = result;
            },
            onComplete: () => {
              if (!settled) {
                settled = true;
                signal.removeEventListener("abort", onAbort);
                resolve(collected ?? emptyResult(id));
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

  /** Stage the chapter id and start the coreference analysis. */
  const run = useCallback(
    (id: string) => {
      chapterIdRef.current = id;
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

/** Fallback result if the stream completed without a payload (defensive). */
function emptyResult(chapterId: string): CoreferenceResult {
  return {
    chapter_id: chapterId,
    clarity_score: 0,
    summary: "",
    resolutions: [],
    character_mentions: [],
  };
}
