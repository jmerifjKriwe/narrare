"use client";

/**
 * useCharacterVoiceCheck — SSE streaming hook for the Voice Consistency
 * Checker (WRITE-010).
 *
 * Wraps {@link useAIOperation} with the voice-check streaming logic, mirroring
 * how `useCharacterVoice` wraps `streamCharacterVoice`. The callback-based SSE
 * stream ({@link streamVoiceCheck}) is bridged to the hook's
 * `execute(signal) => Promise<T>` contract:
 *
 *  - `onProgress` refreshes the streaming liveness timer (`notifyData` → keeps
 *    the connection-loss watchdog from firing) AND surfaces the latest pipeline
 *    status message via {@link progress}.
 *  - each `onResult` appends one character to the run's collected array.
 *  - `onComplete` resolves the promise with the collected per-character array.
 *  - `onError` rejects the promise.
 *  - abort is translated to an `AbortError` rejection (swallowed by
 *    `useAIOperation` on cancel).
 *
 * Voice-check is **chapter-scoped** (like coreference): `run(chapterId)` takes a
 * single chapter id and the stream client is called with NO request body, unlike
 * the novel-scoped `useCharacterVoice` profiling hook.
 *
 * Enforces §16 AI-Interaction Standards / ADR-043: no manual AbortController —
 * the abort signal comes from `useAIOperation`.
 *
 * @module useCharacterVoiceCheck
 */

import { useCallback, useRef, useState } from "react";
import { streamVoiceCheck, type VoiceCheckResult } from "@/lib/api/voice-check-stream";
import { useAIOperation } from "@/lib/hooks/use-ai-operation";

/**
 * @returns The AI-operation lifecycle (state, flags, cancel/retry/reset) plus
 *          {@link run}, which starts the check for a given chapter, and
 *          {@link results} — the accumulated per-character array (null until
 *          the run completes). {@link progress} carries the latest pipeline
 *          status message while analyzing (null at idle / after completion).
 */
export function useCharacterVoiceCheck() {
  // Staged before each start() so execute() reads the current value via ref.
  const chapterIdRef = useRef<string | null>(null);

  // Latest pipeline progress message (display-only). Reset on each run.
  const [progress, setProgress] = useState<string | null>(null);

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
  } = useAIOperation<VoiceCheckResult[]>({
    execute: (signal) =>
      new Promise<VoiceCheckResult[]>((resolve, reject) => {
        const id = chapterIdRef.current;
        if (!id) {
          reject(new Error("No chapter id provided for voice-check analysis"));
          return;
        }

        let settled = false;
        const collected: VoiceCheckResult[] = [];

        const onAbort = () => {
          if (!settled) {
            settled = true;
            reject(new DOMException("Aborted", "AbortError"));
          }
        };
        signal.addEventListener("abort", onAbort, { once: true });

        streamVoiceCheck(
          id,
          {
            onProgress: (message) => {
              notifyData();
              setProgress(message);
            },
            onResult: (result) => {
              notifyData();
              collected.push(result);
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

  /** Stage the chapter id and start the voice-check analysis. */
  const run = useCallback(
    (chapterId: string) => {
      chapterIdRef.current = chapterId;
      setProgress(null);
      start();
    },
    [start],
  );

  /** Reset to idle, clearing results, error, and progress. */
  const handleReset = useCallback(() => {
    setProgress(null);
    reset();
  }, [reset]);

  return {
    state,
    results: state.result,
    progress,
    error: state.error,
    run,
    cancel,
    retry,
    reset: handleReset,
    isIdle,
    isLoading,
    isStreaming,
    isComplete,
    isError,
    isConnectionLost,
  };
}
