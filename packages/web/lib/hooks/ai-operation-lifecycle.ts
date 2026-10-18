/**
 * Lifecycle action creators for AI operations.
 *
 * Factory function that creates all lifecycle actions (start, cancel, retry,
 * reset, notifyData) and connection-loss timer management. Extracted from
 * use-ai-operation for modularity (RULE-04).
 *
 * All functions close over the mutable OperationContext, so they remain
 * stable across renders despite changing timeout/retry configuration.
 *
 * @module ai-operation-lifecycle
 */

import type { OperationContext } from "./ai-operation-execute";
import { invokeExecute } from "./ai-operation-execute";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Lifecycle actions and timer management for an AI operation. */
export interface LifecycleActions {
  clearConnectionLossTimer: () => void;
  startConnectionLossTimer: () => void;
  start: () => void;
  cancel: () => void;
  retry: () => void;
  reset: () => void;
  notifyData: () => void;
}

// ---------------------------------------------------------------------------
// Factory
// ---------------------------------------------------------------------------

/**
 * Create lifecycle actions for an AI operation.
 *
 * Returns stable function references that close over the mutable
 * OperationContext. Must be stored in a ref (called once) to maintain
 * reference stability across renders.
 */
export function createLifecycleActions<T>(
  ctx: OperationContext<T>,
  connectionLossTimerRef: React.MutableRefObject<ReturnType<typeof setTimeout> | null>,
): LifecycleActions {
  // -- Timer management --

  function clearConnectionLossTimer() {
    if (connectionLossTimerRef.current !== null) {
      clearTimeout(connectionLossTimerRef.current);
      connectionLossTimerRef.current = null;
    }
  }

  function startConnectionLossTimer() {
    if (ctx.connectionLossTimeout <= 0) return;
    clearConnectionLossTimer();
    connectionLossTimerRef.current = setTimeout(() => {
      // Only transition if still in an active state
      ctx.setState((prev) => {
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
          // Fire-time re-validation: a newer operation superseded this one.
          if (ctx.operationIdRef.current !== newOpId) return;
          ctx.setState((prev) => ({
            ...prev,
            status: "loading",
            attemptCount: prev.attemptCount + 1,
          }));
          invokeExecute(ctx, newOpId);
        });
      }
    }, ctx.connectionLossTimeout);
  }

  // -- Lifecycle actions --

  function start() {
    ctx.setState((prev) => {
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
      // Fire-time re-validation: an intervening cancel()/reset() (e.g. a
      // StrictMode cleanup between setup #1's queue and this microtask)
      // superseded this operation — it must not fire a duplicate request.
      if (ctx.operationIdRef.current !== newOpId) return;
      ctx.startConnectionLossTimer();
      invokeExecute(ctx, newOpId);
    });
  }

  function cancel() {
    ctx.abortRef.current?.abort();
    ctx.abortRef.current = null;
    clearConnectionLossTimer();

    // Invalidate the current operation HERE — synchronously, exactly once per
    // call, outside any setState updater. Updaters must be pure: React may
    // invoke them multiple times (guaranteed under StrictMode dev) and at any
    // later time (updater replay). Bumping inside the updater invalidated
    // operations started AFTER this cancel — a StrictMode double-mount's
    // cleanup #1 then killed setup #2's fresh operation, and the stale guard
    // dropped every result (F9-3). Matches start()/retry()/reset(), which all
    // bump the id synchronously as well.
    ctx.operationIdRef.current += 1;

    ctx.setState((prev) => {
      if (prev.status === "loading" || prev.status === "streaming") {
        return { ...prev, status: "idle", error: null };
      }
      return prev;
    });
  }

  function retry() {
    ctx.setState((prev) => {
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
      // Fire-time re-validation: a newer operation superseded this one.
      if (ctx.operationIdRef.current !== newOpId) return;
      ctx.startConnectionLossTimer();
      invokeExecute(ctx, newOpId);
    });
  }

  function reset() {
    ctx.abortRef.current?.abort();
    ctx.abortRef.current = null;
    clearConnectionLossTimer();
    ctx.operationIdRef.current += 1;
    ctx.retryCountRef.current = 0;

    ctx.setState({
      status: "idle",
      result: null,
      error: null,
      attemptCount: 0,
    });
  }

  function notifyData() {
    clearConnectionLossTimer();

    ctx.setState((prev) => {
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
  }

  return {
    clearConnectionLossTimer,
    startConnectionLossTimer,
    start,
    cancel,
    retry,
    reset,
    notifyData,
  };
}
