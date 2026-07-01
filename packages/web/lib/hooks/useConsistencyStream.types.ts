/**
 * Public types for the useConsistencyStream SSE streaming hook (CONS-001).
 *
 * Encapsulates all type definitions consumed by useConsistencyStream callers
 * and render components. Extracted from useConsistencyStream for modularity
 * (RULE-04), following the precedent of use-ai-operation.types.ts.
 *
 * See ADR-044 for the staged pipeline specification.
 *
 * @module useConsistencyStream.types
 */

import type { ConsistencyIssue } from "@/lib/api/analysis";
import type {
  ConsistencyCheckRequest,
  ConsistencyResultPayload,
  ConsistencyStageName,
  ConsistencyStageStatus,
} from "@/lib/api/consistency-stream";
import type { AIErrorResponse } from "@/lib/hooks/use-ai-operation.types";

// ---------------------------------------------------------------------------
// Public Types
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
