/**
 * Public types for the shared AI interaction lifecycle hook.
 *
 * Encapsulates all type definitions consumed by useAIOperation callers
 * and internal helper modules. Extracted from use-ai-operation for
 * modularity (RULE-04).
 *
 * See ADR-043 for the full state machine specification.
 *
 * @module use-ai-operation.types
 */

// ---------------------------------------------------------------------------
// Public Types
// ---------------------------------------------------------------------------

/** Lifecycle states for an AI operation (§16.3). */
export type AIOperationStatus =
  | "idle"
  | "loading"
  | "streaming"
  | "complete"
  | "error"
  | "connection_lost";

/** Categorised error kinds for AI operations. */
export type AIErrorKind =
  | "abort"
  | "http"
  | "network"
  | "parse"
  | "stream"
  | "timeout"
  | "connection_lost";

/** Structured, i18n-ready error response (§16.5). */
export interface AIErrorResponse {
  /** Error category for programmatic handling. */
  readonly kind: AIErrorKind;
  /** HTTP status code (for kind="http"). */
  readonly status?: number;
  /** i18n key from studio.aiActions.* namespace. */
  readonly i18nKey: string;
  /** Resolved user-facing message (locale-dependent). */
  readonly userMessage: string;
  /** Whether retry is available. */
  readonly retryable: boolean;
  /** Original error for logging. */
  readonly cause: Error;
}

/** Immutable state snapshot for an AI operation. */
export interface AIOperationState<T> {
  /** Current lifecycle status. */
  readonly status: AIOperationStatus;
  /** Result on successful completion. */
  readonly result: T | null;
  /** Structured error on failure. */
  readonly error: AIErrorResponse | null;
  /** Number of attempts (including retries). */
  readonly attemptCount: number;
}

/** Configuration for useAIOperation. */
export interface UseAIOperationOptions<T> {
  /**
   * The async operation to execute. Receives an AbortSignal.
   *
   * Must return a Promise that resolves with the final result.
   * For streaming operations, chunk handling happens inside this function
   * via the domain-specific API (e.g., streamRewrite's onChunk callback).
   *
   * The hook does NOT wrap the SSE transport — it wraps the async operation.
   */
  readonly execute: (signal: AbortSignal) => Promise<T>;

  /**
   * Connection-loss detection timeout in milliseconds.
   * If no notifyData() call within this window during loading/streaming,
   * transitions to "connection_lost" state. Default: 15000. Set to 0 to disable.
   */
  readonly connectionLossTimeout?: number;

  /**
   * Maximum automatic retry attempts on connection loss.
   * Default: 0 (no auto-retry; user must click retry).
   */
  readonly maxConnectionRetries?: number;

  /**
   * Custom error mapper. Receives the raw error and returns a structured
   * AIErrorResponse. If not provided, uses the default mapper which maps
   * SSEStreamError kinds and HTTP status codes to studio.aiActions.* i18n keys.
   */
  readonly errorMapper?: (error: unknown) => AIErrorResponse | null;

  /** Called on successful completion. */
  readonly onSuccess?: (result: T) => void;

  /** Called on failure (after all retries exhausted). */
  readonly onError?: (error: AIErrorResponse) => void;
}

/** Return value of useAIOperation. */
export interface UseAIOperationReturn<T> {
  /** Current immutable state snapshot. */
  readonly state: AIOperationState<T>;

  // -- Lifecycle actions --

  /** Start the operation. Creates a new AbortController. No-op if in progress. */
  readonly start: () => void;

  /** Cancel the in-progress operation. Transitions to idle. No-op if not in progress. */
  readonly cancel: () => void;

  /** Retry the last operation. Only valid in "error" or "connection_lost" state. */
  readonly retry: () => void;

  /** Reset to idle state. Cancels any in-progress operation. */
  readonly reset: () => void;

  /**
   * Notify the hook that streaming data has arrived.
   * Transitions "loading" → "streaming". Resets the connection-loss timer.
   */
  readonly notifyData: () => void;

  // -- Convenience flags --

  readonly isIdle: boolean;
  readonly isLoading: boolean;
  readonly isStreaming: boolean;
  readonly isComplete: boolean;
  readonly isError: boolean;
  readonly isConnectionLost: boolean;
}
