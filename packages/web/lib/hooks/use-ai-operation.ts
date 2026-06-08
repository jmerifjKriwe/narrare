"use client";

/**
 * Shared AI interaction lifecycle hook.
 *
 * Encapsulates: state machine, AbortController management, error-to-i18n
 * mapping, connection-loss detection with partial output preservation, and
 * retry logic. Enforces §16 AI-Interaction Standards at the hook level.
 *
 * All AI operations MUST use this hook — no manual AbortController patterns.
 * See ADR-043.
 *
 * @module use-ai-operation
 */

import { useCallback, useRef, useState } from "react";

import { mapSSEError } from "@/lib/api/ai-error-mapping";

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

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_CONNECTION_LOSS_TIMEOUT = 15_000;
const DEFAULT_MAX_RETRIES = 0;

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/**
 * Execute the async operation with proper lifecycle management.
 *
 * Extracted as a standalone function to avoid useCallback circular deps.
 * All mutable state is passed via the ops context object.
 */
function invokeExecute<T>(ctx: OperationContext<T>, operationId: number): void {
  const controller = new AbortController();
  ctx.abortRef.current = controller;

  ctx.executeRef
    .current(controller.signal)
    .then((result) => {
      // Ignore stale operations
      if (operationId !== ctx.operationIdRef.current) return;

      ctx.clearConnectionLossTimer();

      if (ctx.mountedRef.current) {
        ctx.setState((prev) => ({
          ...prev,
          status: "complete",
          result,
          error: null,
        }));
        ctx.onSuccessRef.current?.(result);
      }
      ctx.abortRef.current = null;
    })
    .catch((error: unknown) => {
      if (operationId !== ctx.operationIdRef.current) return;

      ctx.clearConnectionLossTimer();

      const mappedError = ctx.errorMapperRef.current(error);

      // Abort errors are swallowed — user intentionally cancelled
      if (mappedError === null) {
        if (ctx.mountedRef.current) {
          ctx.setState((prev) => ({
            ...prev,
            status: "idle",
            error: null,
          }));
        }
        ctx.abortRef.current = null;
        return;
      }

      if (ctx.mountedRef.current) {
        ctx.setState((prev) => ({
          ...prev,
          status: "error",
          error: mappedError,
        }));
        ctx.onErrorRef.current?.(mappedError);
      }
      ctx.abortRef.current = null;
    });
}

/** Mutable context shared across hook callbacks to avoid circular deps. */
interface OperationContext<T> {
  abortRef: React.MutableRefObject<AbortController | null>;
  mountedRef: React.MutableRefObject<boolean>;
  operationIdRef: React.MutableRefObject<number>;
  retryCountRef: React.MutableRefObject<number>;
  executeRef: React.MutableRefObject<(signal: AbortSignal) => Promise<T>>;
  errorMapperRef: React.MutableRefObject<(error: unknown) => AIErrorResponse | null>;
  onSuccessRef: React.MutableRefObject<((result: T) => void) | undefined>;
  onErrorRef: React.MutableRefObject<((error: AIErrorResponse) => void) | undefined>;
  setState: React.Dispatch<React.SetStateAction<AIOperationState<T>>>;
  clearConnectionLossTimer: () => void;
  startConnectionLossTimer: () => void;
  connectionLossTimeout: number;
  maxConnectionRetries: number;
}

// ---------------------------------------------------------------------------
// Hook Implementation
// ---------------------------------------------------------------------------

/**
 * Shared AI interaction lifecycle hook.
 *
 * @template T The result type of the async operation.
 */
export function useAIOperation<T>(options: UseAIOperationOptions<T>): UseAIOperationReturn<T> {
  const {
    execute,
    connectionLossTimeout = DEFAULT_CONNECTION_LOSS_TIMEOUT,
    maxConnectionRetries = DEFAULT_MAX_RETRIES,
    errorMapper = mapSSEError,
    onSuccess,
    onError,
  } = options;

  const [state, setState] = useState<AIOperationState<T>>({
    status: "idle",
    result: null,
    error: null,
    attemptCount: 0,
  });

  // Refs for values that must not trigger re-renders and must be latest
  const abortRef = useRef<AbortController | null>(null);
  const connectionLossTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retryCountRef = useRef(0);
  const mountedRef = useRef(true);
  const operationIdRef = useRef(0);

  // Stable refs for callbacks
  const executeRef = useRef(execute);
  executeRef.current = execute;
  const errorMapperRef = useRef(errorMapper);
  errorMapperRef.current = errorMapper;
  const onSuccessRef = useRef(onSuccess);
  onSuccessRef.current = onSuccess;
  const onErrorRef = useRef(onError);
  onErrorRef.current = onError;

  // -- Timer management --

  const clearConnectionLossTimer = useCallback(() => {
    if (connectionLossTimerRef.current !== null) {
      clearTimeout(connectionLossTimerRef.current);
      connectionLossTimerRef.current = null;
    }
  }, []);

  // Build the context object that callbacks share.
  // startConnectionLossTimer needs the context, so we create it once
  // and mutate the timer-related fields.
  const ctxRef = useRef<OperationContext<T> | null>(null);

  if (ctxRef.current === null) {
    ctxRef.current = {
      abortRef,
      mountedRef,
      operationIdRef,
      retryCountRef,
      executeRef,
      errorMapperRef,
      onSuccessRef,
      onErrorRef,
      setState,
      clearConnectionLossTimer,
      // Placeholder — reassigned below after the function is created
      startConnectionLossTimer: () => {},
      connectionLossTimeout,
      maxConnectionRetries,
    };
  }

  // Update mutable context fields on every render
  const ctx = ctxRef.current;
  ctx.connectionLossTimeout = connectionLossTimeout;
  ctx.maxConnectionRetries = maxConnectionRetries;

  // biome-ignore lint/correctness/useExhaustiveDependencies: ADR-043 state machine needs stable deps
  const startConnectionLossTimer = useCallback(() => {
    if (ctx.connectionLossTimeout <= 0) return;
    ctx.clearConnectionLossTimer();
    connectionLossTimerRef.current = setTimeout(() => {
      // Only transition if still in an active state
      setState((prev) => {
        if (prev.status === "loading" || prev.status === "streaming") {
          return { ...prev, status: "connection_lost" };
        }
        return prev;
      });
      ctx.abortRef.current?.abort();
      ctx.abortRef.current = null;

      // Auto-retry if under the limit
      ctx.retryCountRef.current += 1;
      if (ctx.retryCountRef.current <= ctx.maxConnectionRetries) {
        const newOpId = ctx.operationIdRef.current + 1;
        ctx.operationIdRef.current = newOpId;
        queueMicrotask(() => {
          if (!ctx.mountedRef.current) return;
          setState((prev) => ({
            ...prev,
            status: "loading",
            attemptCount: prev.attemptCount + 1,
          }));
          invokeExecute(ctx, newOpId);
        });
      }
    }, ctx.connectionLossTimeout);
  }, [ctx, clearConnectionLossTimer, setState]);

  // Wire the timer function into the context
  ctx.startConnectionLossTimer = startConnectionLossTimer;

  // -- Lifecycle actions --

  // biome-ignore lint/correctness/useExhaustiveDependencies: ADR-043 state machine needs stable deps
  const start = useCallback(() => {
    setState((prev) => {
      // Prevent concurrent starts
      if (prev.status === "loading" || prev.status === "streaming") {
        return prev;
      }
      return {
        status: "loading",
        result: null,
        error: null,
        attemptCount: prev.attemptCount + 1,
      };
    });

    const newOpId = ctx.operationIdRef.current + 1;
    ctx.operationIdRef.current = newOpId;
    ctx.retryCountRef.current = 0;

    queueMicrotask(() => {
      if (!ctx.mountedRef.current) return;
      ctx.startConnectionLossTimer();
      invokeExecute(ctx, newOpId);
    });
  }, [ctx, setState]);

  // biome-ignore lint/correctness/useExhaustiveDependencies: ADR-043 state machine needs stable deps
  const cancel = useCallback(() => {
    ctx.abortRef.current?.abort();
    ctx.abortRef.current = null;
    ctx.clearConnectionLossTimer();
    ctx.operationIdRef.current += 1;

    setState((prev) => {
      if (prev.status === "loading" || prev.status === "streaming") {
        return { ...prev, status: "idle", error: null };
      }
      return prev;
    });
  }, [ctx, setState]);

  // biome-ignore lint/correctness/useExhaustiveDependencies: ADR-043 state machine needs stable deps
  const retry = useCallback(() => {
    setState((prev) => {
      if (prev.status !== "error" && prev.status !== "connection_lost") {
        return prev;
      }
      ctx.retryCountRef.current += 1;
      return {
        status: "loading",
        result: null,
        error: null,
        attemptCount: prev.attemptCount + 1,
      };
    });

    const newOpId = ctx.operationIdRef.current + 1;
    ctx.operationIdRef.current = newOpId;

    queueMicrotask(() => {
      if (!ctx.mountedRef.current) return;
      ctx.startConnectionLossTimer();
      invokeExecute(ctx, newOpId);
    });
  }, [ctx, setState]);

  // biome-ignore lint/correctness/useExhaustiveDependencies: ADR-043 state machine needs stable deps
  const reset = useCallback(() => {
    ctx.abortRef.current?.abort();
    ctx.abortRef.current = null;
    ctx.clearConnectionLossTimer();
    ctx.operationIdRef.current += 1;
    ctx.retryCountRef.current = 0;

    setState({
      status: "idle",
      result: null,
      error: null,
      attemptCount: 0,
    });
  }, [ctx, setState]);

  // biome-ignore lint/correctness/useExhaustiveDependencies: ADR-043 state machine needs stable deps
  const notifyData = useCallback(() => {
    ctx.clearConnectionLossTimer();

    setState((prev) => {
      if (prev.status === "loading") {
        ctx.startConnectionLossTimer();
        return { ...prev, status: "streaming" };
      }
      if (prev.status === "streaming") {
        ctx.startConnectionLossTimer();
        return prev; // No status change, just timer reset
      }
      return prev;
    });
  }, [ctx, setState]);

  // -- Derived flags --

  const status = state.status;

  return {
    state,
    start,
    cancel,
    retry,
    reset,
    notifyData,
    isIdle: status === "idle",
    isLoading: status === "loading",
    isStreaming: status === "streaming",
    isComplete: status === "complete",
    isError: status === "error",
    isConnectionLost: status === "connection_lost",
  };
}
