"use client";

/**
 * useConsistencyStream — SSE streaming hook wrapping useAIOperation (CONS-001).
 *
 * Novel-scoped: `run(novelId, request)` takes a novel id and request body.
 * See {@link UseConsistencyStreamReturn} for the full API surface.
 *
 * The SSE transport/promise boundary lives in {@link consistency-stream-bridge};
 * public types live in {@link useConsistencyStream.types}.
 *
 * @module useConsistencyStream
 */

import { useCallback, useRef, useState } from "react";
import type { ConsistencyIssue } from "@/lib/api/analysis";
import type {
  ConsistencyCheckRequest,
  ConsistencyResultPayload,
} from "@/lib/api/consistency-stream";
import { bridgeConsistencyStream } from "@/lib/hooks/consistency-stream-bridge";
import { useAIOperation } from "@/lib/hooks/use-ai-operation";
import type {
  ConsistencyStagePayload,
  UseConsistencyStreamReturn,
} from "./useConsistencyStream.types";

export type { ConsistencyStagePayload, UseConsistencyStreamReturn };

// --- Hook ------------------------------------------------------------------

/** Bridge the SSE consistency stream to React state. @returns Lifecycle flags, progress/issue intermediates, and actions. */
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
    execute: (signal) => {
      const id = novelIdRef.current;
      const req = requestRef.current;
      if (!id) {
        return Promise.reject(new Error("No novel id provided for consistency check"));
      }
      return bridgeConsistencyStream({
        novelId: id,
        request: req ?? {},
        signal,
        onStage: (payload) => {
          notifyData();
          setProgress(payload);
        },
        onIssue: (issue) => {
          notifyData();
          setIssues((prev) => [...prev, issue]);
        },
      });
    },
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
