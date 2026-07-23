"use client";

/**
 * useDialogueCoach — SSE streaming hook for the Dialogue Coach (ASSIST-004).
 *
 * Wraps {@link useAIOperation} (ADR-043) with the dialogue-coach streaming
 * logic, the same way `useCharacterVoice` wraps `streamCharacterVoice`. Unlike
 * character-voice (multiple per-character results), the coach emits a SINGLE
 * `result` event carrying the full DialogueCoachResponse — so `run()` resolves
 * with that one result rather than an array.
 *
 * The callback-based SSE stream ({@link streamDialogueCoach}) is bridged to the
 * hook's `execute(signal) => Promise<T>` contract:
 *
 *  - `onProgress` updates the surfaced `progress` string and refreshes the
 *    streaming liveness timer (`notifyData` → keeps the connection-loss
 *    watchdog from firing)
 *  - `onResult` resolves the promise with the single result
 *  - `onComplete` is a no-op (the stream ends after the single result)
 *  - `onError` rejects the promise
 *  - abort is translated to an `AbortError` rejection (swallowed by
 *    `useAIOperation` on cancel)
 *
 * Run parameters are staged in a ref before `start()` so `execute()` reads the
 * current values via the ref (mirrors `useCharacterVoice`). This keeps `run`
 * a stable callback (no per-run closure capturing the params).
 *
 * Enforces §16 AI-Interaction Standards / ADR-043: no manual AbortController —
 * the abort signal comes from `useAIOperation`.
 *
 * @module useDialogueCoach
 */
import { useCallback, useRef, useState } from "react";
import { streamDialogueCoach } from "@/lib/api/dialogue-coach-stream";
import { useAIOperation } from "@/lib/hooks/use-ai-operation";
import type { DialogueCoachMode, DialogueCoachResponse } from "@/types";

export interface DialogueCoachRunParams {
  chapterId: string;
  selectionText: string;
  mode: DialogueCoachMode;
}

export function useDialogueCoach() {
  // Staged before start() so execute() reads the current values via refs.
  const paramsRef = useRef<DialogueCoachRunParams | null>(null);
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
  } = useAIOperation<DialogueCoachResponse>({
    execute: (signal) =>
      new Promise<DialogueCoachResponse>((resolve, reject) => {
        const params = paramsRef.current;
        if (!params) {
          reject(new Error("No run params provided for dialogue coach"));
          return;
        }
        let settled = false;
        const onAbort = () => {
          if (!settled) {
            settled = true;
            reject(new DOMException("Aborted", "AbortError"));
          }
        };
        signal.addEventListener("abort", onAbort, { once: true });

        streamDialogueCoach(
          params.chapterId,
          { selection_text: params.selectionText, mode: params.mode },
          {
            onProgress: (msg) => {
              setProgress(msg);
              notifyData();
            },
            onResult: (result) => {
              notifyData();
              if (!settled) {
                settled = true;
                signal.removeEventListener("abort", onAbort);
                resolve(result);
              }
            },
            onComplete: () => {
              // Stream ends after the single result; nothing more to resolve.
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

  /** Stage the run params and start the dialogue-coach analysis. */
  const run = useCallback(
    (params: DialogueCoachRunParams) => {
      paramsRef.current = params;
      setProgress(null);
      start();
    },
    [start],
  );

  /** Clear progress on reset. */
  const resetAll = useCallback(() => {
    reset();
    setProgress(null);
  }, [reset]);

  return {
    state,
    result: state.result,
    error: state.error,
    progress,
    run,
    cancel,
    retry,
    reset: resetAll,
    isIdle,
    isLoading,
    isStreaming,
    isComplete,
    isError,
    isConnectionLost,
  };
}
