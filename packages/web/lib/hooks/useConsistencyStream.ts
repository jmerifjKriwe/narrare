"use client";

/**
 * useConsistencyStream — SSE streaming hook for the Consistency Checker
 * (CONS-001), following the staged pipeline pattern (ADR-044).
 *
 * Wraps {@link useAIOperation} with the consistency-check streaming logic,
 * mirroring how `useCharacterVoiceCheck` wraps `streamVoiceCheck`. The
 * callback-based SSE stream ({@link streamConsistencyCheck}) is bridged to the
 * hook's `execute(signal) => Promise<T>` contract:
 *
 *  - `onStage` refreshes the streaming liveness timer (`notifyData` → keeps
 *    the connection-loss watchdog from firing) AND surfaces the latest pipeline
 *    stage snapshot via {@link progress}.
 *  - each `onIssue` appends one progressive issue to the accumulated
 *    {@link issues} array.
 *  - `onComplete` resolves the promise with the terminal
 *    {@link ConsistencyResultPayload}.
 *  - `onError` rejects the promise.
 *  - abort is translated to an `AbortError` rejection (swallowed by
 *    `useAIOperation` on cancel).
 *
 * Consistency-check is **novel-scoped** (like character profiling):
 * `run(novelId, request)` takes a novel id and the request body that
 * selects chapters, check types, and KB inclusion.
 *
 * Enforces §16 AI-Interaction Standards / ADR-043: no manual AbortController —
 * the abort signal comes from `useAIOperation`.
 *
 * @module useConsistencyStream
 */

import { useCallback, useRef, useState } from "react";
import type { ConsistencyIssue } from "@/lib/api/analysis";
import {
  type ConsistencyCheckRequest,
  type ConsistencyResultPayload,
  type ConsistencyStageName,
  type ConsistencyStageStatus,
  streamConsistencyCheck,
} from "@/lib/api/consistency-stream";
import { useAIOperation } from "@/lib/hooks/use-ai-operation";
import type { AIErrorResponse } from "@/lib/hooks/use-ai-operation.types";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/**
 * Snapshot of the current pipeline stage for progressive UI rendering.
 * Captures all fields from the backend's `ConsistencyStageEvent`.
 */
export interface ConsistencyStagePayload {
  stage: ConsistencyStageName;
  status: ConsistencyStageStatus;
  progress: number;
  message: string;
  factsExtracted: number | null;
  issuesFound: number | null;
}

/**
 * Public API surface returned by {@link useConsistencyStream}.
 *
 * Mirrors `UseCharacterVoiceCheckReturn` — AI-operation lifecycle flags,
 * actions, plus consistency-specific progressive state.
 */
export interface UseConsistencyStreamReturn {
  /** Raw AI-operation state (status, result, error, attemptCount). */
  state: {
    status: string;
    result: ConsistencyResultPayload | null;
    error: AIErrorResponse | null;
    attemptCount: number;
  };
  /** Latest stage snapshot (null when idle / completed). */
  progress: ConsistencyStagePayload | null;
  /** Accumulated progressive issues emitted during the checking phase. */
  issues: ConsistencyIssue[];
  /** Terminal result payload (null until the run completes). */
  result: ConsistencyResultPayload | null;
  /** Terminal error (null unless an error occurred). */
  error: AIErrorResponse | null;
  /** Start a consistency check for the given novel and request. */
  run: (novelId: string, request: ConsistencyCheckRequest) => void;
  /** Cancel the in-flight stream (governed by useAIOperation). */
  cancel: () => void;
  /** Retry the last request. */
  retry: () => void;
  /** Reset to idle, clearing progress, issues, and any result/error. */
  reset: () => void;
  // -- Derived lifecycle flags --
  isIdle: boolean;
  isLoading: boolean;
  isStreaming: boolean;
  isComplete: boolean;
  isError: boolean;
  isConnectionLost: boolean;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Bridge the callback-based SSE consistency stream to React state.
 *
 * @returns AI-operation lifecycle, progress/issue intermediates, and
 *          actions to start / cancel / retry / reset the check.
 */
export function useConsistencyStream(): UseConsistencyStreamReturn {
  // Staged before each start() so execute() reads the current values via refs.
  const novelIdRef = useRef<string | null>(null);
  const requestRef = useRef<ConsistencyCheckRequest | null>(null);

  // Latest pipeline stage snapshot (display-only). Reset on each run.
  const [progress, setProgress] = useState<ConsistencyStagePayload | null>(null);
  // Progressive issues accumulated during the checking phase.
  const [issues, setIssues] = useState<ConsistencyIssue[]>([]);

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
  } = useAIOperation<ConsistencyResultPayload>({
    execute: (signal) =>
      new Promise<ConsistencyResultPayload>((resolve, reject) => {
        const id = novelIdRef.current;
        const req = requestRef.current;
        if (!id) {
          reject(new Error("No novel id provided for consistency check"));
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

        streamConsistencyCheck(
          id,
          req ?? {},
          {
            onStage: (stage, status, progressVal, message, factsExtracted, issuesFound) => {
              notifyData();
              setProgress({
                stage,
                status,
                progress: progressVal,
                message,
                factsExtracted,
                issuesFound,
              });
            },
            onIssue: (issue) => {
              notifyData();
              setIssues((prev) => [...prev, issue]);
            },
            onComplete: (result) => {
              if (!settled) {
                settled = true;
                signal.removeEventListener("abort", onAbort);
                resolve(result);
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

  /** Stage the novel id and request, then start the consistency check. */
  const run = useCallback(
    (novelId: string, request: ConsistencyCheckRequest) => {
      novelIdRef.current = novelId;
      requestRef.current = request;
      setProgress(null);
      setIssues([]);
      start();
    },
    [start],
  );

  /** Reset to idle, clearing progress, issues, error, and result. */
  const handleReset = useCallback(() => {
    setProgress(null);
    setIssues([]);
    reset();
  }, [reset]);

  return {
    state,
    progress,
    issues,
    result: state.result,
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
