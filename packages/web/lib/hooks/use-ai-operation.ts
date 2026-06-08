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

import { useRef, useState } from "react";

import { mapSSEError } from "@/lib/api/ai-error-mapping";
import type { OperationContext } from "./ai-operation-execute";
import { DEFAULT_CONNECTION_LOSS_TIMEOUT, DEFAULT_MAX_RETRIES } from "./ai-operation-execute";
import { createLifecycleActions } from "./ai-operation-lifecycle";
import type {
  AIOperationState,
  UseAIOperationOptions,
  UseAIOperationReturn,
} from "./use-ai-operation.types";

// Re-export types for backward compatibility
export type {
  AIErrorKind,
  AIErrorResponse,
  AIOperationState,
  AIOperationStatus,
  UseAIOperationOptions,
  UseAIOperationReturn,
} from "./use-ai-operation.types";

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

  // Build the context object that callbacks share.
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
      clearConnectionLossTimer: () => {},
      startConnectionLossTimer: () => {},
      connectionLossTimeout,
      maxConnectionRetries,
    };
  }

  // Update mutable context fields on every render
  const ctx = ctxRef.current;
  ctx.connectionLossTimeout = connectionLossTimeout;
  ctx.maxConnectionRetries = maxConnectionRetries;

  // Create lifecycle actions once (stable via ref)
  const lifecycleRef = useRef<ReturnType<typeof createLifecycleActions<T>> | null>(null);
  if (lifecycleRef.current === null) {
    lifecycleRef.current = createLifecycleActions(ctx, connectionLossTimerRef);
  }

  // Wire timer functions into context
  ctx.clearConnectionLossTimer = lifecycleRef.current.clearConnectionLossTimer;
  ctx.startConnectionLossTimer = lifecycleRef.current.startConnectionLossTimer;

  const { start, cancel, retry, reset, notifyData } = lifecycleRef.current;

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
