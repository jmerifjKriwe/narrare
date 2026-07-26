"use client";

/**
 * useCharacterVoiceDrift — SSE streaming hook for Character Voice Drift
 * (ANAL-009 Phase 1).
 *
 * Wraps {@link useAIOperation} with the voice-drift streaming logic, the same
 * way `useCharacterVoice` wraps `streamCharacterVoice`. The callback-based SSE
 * stream ({@link streamVoiceDrift}) is bridged to the hook's
 * `execute(signal) => Promise<T>` contract:
 *  - `onProgress` refreshes the streaming liveness timer (`notifyData`) AND
 *    surfaces the latest pipeline status message via {@link progress}.
 *  - `onResult` appends one analysable character to `results`; `onNoProfile`
 *    appends one graceful RULE-11 skip to `noProfile` (surfaced separately so
 *    the panel can list un-analysable characters without confusion).
 *  - `onComplete` resolves with `{ results, noProfile }`; `onError` rejects;
 *    abort → `AbortError` rejection (swallowed on cancel).
 *
 * Voice-drift is **novel-scoped** (like character-voice profiling):
 * `run(novelId)` analyses the whole novel; optional `character_id` /
 * `chapter_ids` filters may be staged. Enforces ADR-043: no manual
 * AbortController — the abort signal comes from `useAIOperation`.
 */

import { useCallback, useRef, useState } from "react";
import {
  streamVoiceDrift,
  type VoiceDriftCharacterResult,
  type VoiceDriftNoProfile,
  type VoiceDriftRequest,
  type VoiceDriftRunResult,
} from "@/lib/api/voice-drift-stream";
import { useAIOperation } from "@/lib/hooks/use-ai-operation";

/** @returns lifecycle (state/flags/cancel/retry/reset), `run`, `results`, `noProfile`, `progress`. */
export function useCharacterVoiceDrift() {
  // Staged before each start() so execute() reads the current values via refs.
  const novelIdRef = useRef<string | null>(null);
  const bodyRef = useRef<VoiceDriftRequest>({});
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
  } = useAIOperation<VoiceDriftRunResult>({
    execute: (signal) =>
      new Promise<VoiceDriftRunResult>((resolve, reject) => {
        const id = novelIdRef.current;
        if (!id) {
          reject(new Error("No novel id provided for voice-drift analysis"));
          return;
        }

        let settled = false;
        const collectedResults: VoiceDriftCharacterResult[] = [];
        const collectedNoProfile: VoiceDriftNoProfile[] = [];

        const onAbort = () => {
          if (!settled) {
            settled = true;
            reject(new DOMException("Aborted", "AbortError"));
          }
        };
        signal.addEventListener("abort", onAbort, { once: true });

        streamVoiceDrift(
          id,
          bodyRef.current,
          {
            onProgress: (message) => {
              notifyData();
              setProgress(message);
            },
            onResult: (result) => {
              notifyData();
              collectedResults.push(result);
            },
            onNoProfile: (noProfile) => {
              notifyData();
              collectedNoProfile.push(noProfile);
            },
            onComplete: () => {
              if (!settled) {
                settled = true;
                signal.removeEventListener("abort", onAbort);
                resolve({ results: collectedResults, noProfile: collectedNoProfile });
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

  /** Stage the novel + optional filters and start the voice-drift analysis. */
  const run = useCallback(
    (novelId: string, body?: VoiceDriftRequest) => {
      novelIdRef.current = novelId;
      bodyRef.current = body ?? {};
      setProgress(null);
      start();
    },
    [start],
  );

  /** Reset to idle, clearing results, no-profile, error, and progress. */
  const handleReset = useCallback(() => {
    setProgress(null);
    reset();
  }, [reset]);

  const runResult = state.result;

  return {
    state,
    results: runResult?.results ?? null,
    noProfile: runResult?.noProfile ?? null,
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
