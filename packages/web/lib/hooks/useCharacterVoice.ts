"use client";

/**
 * useCharacterVoice — SSE streaming hook for Character Voice analysis (ANAL-008).
 *
 * Wraps {@link useAIOperation} with the character-voice streaming logic, the
 * same way `useCoreference` wraps `streamCoreference`. The callback-based SSE
 * stream ({@link streamCharacterVoice}) is bridged to the hook's
 * `execute(signal) => Promise<T>` contract:
 *
 *  - `onProgress` / `onResult` refresh the streaming liveness timer
 *    (`notifyData` → keeps the connection-loss watchdog from firing)
 *  - each `onResult` appends one character to the run's collected array
 *  - `onComplete` resolves the promise with the collected per-character array
 *  - `onError` rejects the promise
 *  - abort is translated to an `AbortError` rejection (swallowed by
 *    `useAIOperation` on cancel)
 *
 * Results are collected across the whole run and surfaced once on completion
 * (mirrors the coreference hook's single-result-at-completion pattern, but for
 * an array of per-character results).
 *
 * NOTE — `distinctiveness_notes` is a per-run, DISPLAY-ONLY comparison artifact
 * (ADR-055 Decision 1): it is carried on each surfaced `CharacterVoiceResult`
 * for the UI panel, but is NOT persisted profile data and is recomputed on
 * every run. Treat it as transient review aid, never as stored state.
 *
 * Enforces §16 AI-Interaction Standards / ADR-043: no manual AbortController —
 * the abort signal comes from `useAIOperation`.
 *
 * @module useCharacterVoice
 */

import { useCallback, useRef } from "react";
import { type CharacterVoiceResult, streamCharacterVoice } from "@/lib/api/character-voice-stream";
import { useAIOperation } from "@/lib/hooks/use-ai-operation";

/**
 * @returns The AI-operation lifecycle (state, flags, cancel/retry/reset) plus
 *          {@link run}, which starts the analysis for a given novel/chapters,
 *          and {@link results} — the accumulated per-character array (null
 *          until the run completes).
 */
export function useCharacterVoice() {
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
  } = useAIOperation<CharacterVoiceResult[]>({
    execute: (signal) =>
      new Promise<CharacterVoiceResult[]>((resolve, reject) => {
        const id = novelIdRef.current;
        if (!id) {
          reject(new Error("No novel id provided for character-voice analysis"));
          return;
        }

        let settled = false;
        const collected: CharacterVoiceResult[] = [];

        const onAbort = () => {
          if (!settled) {
            settled = true;
            reject(new DOMException("Aborted", "AbortError"));
          }
        };
        signal.addEventListener("abort", onAbort, { once: true });

        streamCharacterVoice(
          id,
          { chapter_ids: chapterIdsRef.current },
          {
            onProgress: () => notifyData(),
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

  /** Stage the novel/chapters and start the character-voice analysis. */
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
    results: state.result,
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
