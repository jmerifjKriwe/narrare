/**
 * Internal execution logic for AI operations.
 *
 * Contains the OperationContext interface and the invokeExecute helper
 * that manages the async operation lifecycle. Extracted from use-ai-operation
 * for modularity (RULE-04).
 *
 * @module ai-operation-execute
 */

import type { AIErrorResponse, AIOperationState } from "./use-ai-operation.types";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Default connection-loss timeout in milliseconds (§16.4). */
const DEFAULT_CONNECTION_LOSS_TIMEOUT = 15_000;

/** Default maximum auto-retry attempts on connection loss. */
const DEFAULT_MAX_RETRIES = 0;

export { DEFAULT_CONNECTION_LOSS_TIMEOUT, DEFAULT_MAX_RETRIES };

// ---------------------------------------------------------------------------
// Internal Types
// ---------------------------------------------------------------------------

/** Mutable context shared across hook callbacks to avoid circular deps. */
export interface OperationContext<T> {
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
// Internal helpers
// ---------------------------------------------------------------------------

/**
 * Execute the async operation with proper lifecycle management.
 *
 * Extracted as a standalone function to avoid useCallback circular deps.
 * All mutable state is passed via the ops context object.
 */
export function invokeExecute<T>(ctx: OperationContext<T>, operationId: number): void {
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
