"use client";

/**
 * useUnblockStream — SSE streaming hook for Writer's Unblock (WRITE-009).
 *
 * Wraps {@link useAIOperation} with the story-suggest streaming logic, the same
 * way `useContinueStream` wraps `streamExtend`. The callback-based SSE stream
 * ({@link streamStorySuggestions}, which emits a single `suggestions` event) is
 * bridged to the hook's `execute(signal) => Promise<T>` contract:
 *
 *  - `onSuggestions` stores the data and notifies the hook (loading → streaming)
 *  - `onComplete` resolves the promise with the collected suggestions
 *  - `onError` rejects the promise
 *  - abort is translated to an `AbortError` rejection
 *
 * Extracted from {@link UnblockPanel} for modularity (RULE-04) and single
 * responsibility (RULE-06): the panel renders, this hook owns the lifecycle.
 *
 * @module useUnblockStream
 */

import { useCallback, useRef } from "react";
import { type StorySuggestion, streamStorySuggestions } from "@/lib/api/story-suggest-stream";
import { useAIOperation } from "@/lib/hooks/use-ai-operation";

/**
 * @param novelId   Novel to generate suggestions for (SSE URL path parameter).
 * @param chapterId Optional chapter to scope the suggestions (request body).
 * @returns The AI-operation lifecycle (state, flags, cancel/retry/reset) plus
 *          {@link request}, which stages the author instructions and starts the
 *          operation.
 */
export function useUnblockStream(novelId: string, chapterId?: string) {
  // Latest author instructions, staged before each start() so execute() reads
  // the current value via the ref (same pattern as useContinueStream's requestRef).
  const instructionsRef = useRef("");

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
  } = useAIOperation<StorySuggestion[]>({
    execute: (signal) =>
      new Promise<StorySuggestion[]>((resolve, reject) => {
        let settled = false;
        let collected: StorySuggestion[] = [];

        const onAbort = () => {
          if (!settled) {
            settled = true;
            reject(new DOMException("Aborted", "AbortError"));
          }
        };
        signal.addEventListener("abort", onAbort, { once: true });

        streamStorySuggestions(
          novelId,
          {
            chapter_id: chapterId,
            author_instructions: instructionsRef.current.trim() || undefined,
          },
          {
            onSuggestions: (items) => {
              notifyData();
              collected = items;
            },
            onComplete: () => {
              if (!settled) {
                settled = true;
                signal.removeEventListener("abort", onAbort);
                resolve(collected);
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

  /** Stage the author instructions and start the suggestion stream. */
  const request = useCallback(
    (instructions: string) => {
      instructionsRef.current = instructions;
      start();
    },
    [start],
  );

  return {
    state,
    cancel,
    retry,
    reset,
    request,
    isIdle,
    isLoading,
    isStreaming,
    isComplete,
    isError,
    isConnectionLost,
  };
}
