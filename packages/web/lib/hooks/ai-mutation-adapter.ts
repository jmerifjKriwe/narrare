/**
 * Mutation adapter utilities for useAIOperation-based hooks.
 *
 * Shared logic for TanStack-compatible mutation interfaces on top of
 * useAIOperation. Extracted from individual hooks (RULE-04).
 *
 * @module ai-mutation-adapter
 */

import { useCallback } from "react";
import type { AIErrorResponse, UseAIOperationReturn } from "@/lib/hooks/use-ai-operation";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Minimal ref interface compatible with RefObject and MutableRefObject. */
interface PromiseRef<T> {
  current: ((value: T) => void) | null;
}

interface RejectRef {
  current: ((reason: unknown) => void) | null;
}

// ---------------------------------------------------------------------------
// Hook helpers
// ---------------------------------------------------------------------------

/** Abort callback: rejects pending promise and cancels AI operation. */
export function useAbortCallback<T>(
  resolveRef: PromiseRef<T>,
  rejectRef: RejectRef,
  aiOp: UseAIOperationReturn<T>,
) {
  return useCallback(() => {
    rejectRef.current?.(new DOMException("Aborted", "AbortError"));
    resolveRef.current = null;
    rejectRef.current = null;
    aiOp.cancel();
  }, [aiOp, resolveRef, rejectRef]);
}

/** Creates a mutateAsync bridging useAIOperation start() with Promise API. */
export function useMutateAsyncFactory<TArgs, TResult>(
  argsRef: React.MutableRefObject<TArgs>,
  resolveRef: PromiseRef<TResult>,
  rejectRef: RejectRef,
  aiOp: UseAIOperationReturn<TResult>,
) {
  return useCallback(
    (args: TArgs): Promise<TResult> => {
      return new Promise<TResult>((resolve, reject) => {
        resolveRef.current = resolve;
        rejectRef.current = reject;
        argsRef.current = args;
        aiOp.start();
      });
    },
    [aiOp, resolveRef, rejectRef, argsRef],
  );
}

// ---------------------------------------------------------------------------
// Callback factories
// ---------------------------------------------------------------------------

/** Error mapper: rejects on AbortError, delegates other errors to fallback. */
export function createAbortAwareErrorMapper<TResult>(
  resolveRef: PromiseRef<TResult>,
  rejectRef: RejectRef,
  fallbackMapper: (error: unknown) => AIErrorResponse | null,
) {
  return (error: unknown): AIErrorResponse | null => {
    if (
      (error instanceof DOMException && error.name === "AbortError") ||
      (error instanceof Error && error.name === "AbortError")
    ) {
      rejectRef.current?.(error);
      resolveRef.current = null;
      rejectRef.current = null;
      return null;
    }
    return fallbackMapper(error);
  };
}

/** onSuccess callback: resolves the pending mutateAsync promise. */
export function createOnSuccessCallback<TResult>(
  resolveRef: PromiseRef<TResult>,
  rejectRef: RejectRef,
) {
  return (data: TResult): void => {
    resolveRef.current?.(data);
    resolveRef.current = null;
    rejectRef.current = null;
  };
}

/** onError callback: rejects the pending mutateAsync promise. */
export function createOnErrorCallback<TResult = unknown>(
  resolveRef: PromiseRef<TResult>,
  rejectRef: RejectRef,
) {
  return (error: AIErrorResponse): void => {
    rejectRef.current?.(new Error(error.userMessage));
    resolveRef.current = null;
    rejectRef.current = null;
  };
}

/** Build the common return object for AI mutation hooks. */
export function buildMutationReturn<T, TArgs>(
  aiOp: UseAIOperationReturn<T>,
  mutate: (args: TArgs) => void,
  mutateAsync: (args: TArgs) => Promise<T>,
  abort: () => void,
  variables: TArgs | null | undefined,
) {
  return {
    state: aiOp.state,
    start: aiOp.start,
    cancel: aiOp.cancel,
    retry: aiOp.retry,
    reset: aiOp.reset,
    notifyData: aiOp.notifyData,
    isIdle: aiOp.isIdle,
    isLoading: aiOp.isLoading,
    isStreaming: aiOp.isStreaming,
    isComplete: aiOp.isComplete,
    isError: aiOp.isError,
    isConnectionLost: aiOp.isConnectionLost,
    mutate,
    mutateAsync,
    abort,
    isPending: aiOp.isLoading || aiOp.isStreaming,
    data: aiOp.state.result,
    error: aiOp.state.error ? new Error(aiOp.state.error.userMessage) : null,
    isSuccess: aiOp.state.status === "complete",
    variables,
  };
}
