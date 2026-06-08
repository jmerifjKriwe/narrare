/**
 * Unit tests for useAIOperation hook.
 *
 * Covers: state transitions, AbortController lifecycle, connection-loss timer,
 * retry logic, concurrent-start prevention, notifyData transitions, cleanup.
 *
 * @module useAIOperation.test
 */

import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { AIErrorResponse } from "@/lib/hooks/use-ai-operation";
import { useAIOperation } from "@/lib/hooks/use-ai-operation";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Create a mock execute function that can be controlled. */
function createMockExecute<T = string>(resolveValue?: T) {
  let resolveFn: (value: T) => void;
  let rejectFn: (error: unknown) => void;

  const promise = new Promise<T>((resolve, reject) => {
    resolveFn = resolve;
    rejectFn = reject;
  });

  const mockFn = vi.fn((_signal: AbortSignal) => promise);

  return {
    execute: mockFn,
    resolve: (value: T) => resolveFn!(value ?? resolveValue!),
    reject: (error: unknown) => rejectFn!(error),
    promise,
  };
}

/** Create an AbortError (DOMException-like). */
function createAbortError(): DOMException {
  return new DOMException("The operation was aborted.", "AbortError");
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useAIOperation", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  // -------------------------------------------------------------------------
  // Initial state
  // -------------------------------------------------------------------------

  it("starts in idle state", () => {
    const mock = createMockExecute("result");
    const { result } = renderHook(() => useAIOperation({ execute: mock.execute }));

    expect(result.current.state.status).toBe("idle");
    expect(result.current.state.result).toBeNull();
    expect(result.current.state.error).toBeNull();
    expect(result.current.state.attemptCount).toBe(0);
    expect(result.current.isIdle).toBe(true);
    expect(result.current.isLoading).toBe(false);
    expect(result.current.isStreaming).toBe(false);
    expect(result.current.isComplete).toBe(false);
    expect(result.current.isError).toBe(false);
    expect(result.current.isConnectionLost).toBe(false);
  });

  // -------------------------------------------------------------------------
  // State transitions: idle → loading → streaming → complete
  // -------------------------------------------------------------------------

  it("transitions idle → loading → streaming → complete", async () => {
    const mock = createMockExecute("done");
    const onSuccess = vi.fn();

    const { result } = renderHook(() =>
      useAIOperation({
        execute: mock.execute,
        connectionLossTimeout: 0,
        onSuccess,
      }),
    );

    // Start
    act(() => {
      result.current.start();
    });
    expect(result.current.state.status).toBe("loading");
    expect(result.current.state.attemptCount).toBe(1);
    expect(result.current.isLoading).toBe(true);

    // Notify data → streaming
    act(() => {
      result.current.notifyData();
    });
    expect(result.current.state.status).toBe("streaming");
    expect(result.current.isStreaming).toBe(true);

    // Resolve → complete
    await act(async () => {
      mock.resolve("done");
    });
    expect(result.current.state.status).toBe("complete");
    expect(result.current.state.result).toBe("done");
    expect(result.current.isComplete).toBe(true);
    expect(onSuccess).toHaveBeenCalledWith("done");
  });

  // -------------------------------------------------------------------------
  // State transitions: idle → loading → error
  // -------------------------------------------------------------------------

  it("transitions idle → loading → error on failure", async () => {
    const mock = createMockExecute();
    const onError = vi.fn();

    const { result } = renderHook(() =>
      useAIOperation({
        execute: mock.execute,
        connectionLossTimeout: 0,
        onError,
      }),
    );

    act(() => {
      result.current.start();
    });
    expect(result.current.state.status).toBe("loading");

    const networkError = new Error("Network failure");
    await act(async () => {
      mock.reject(networkError);
    });

    expect(result.current.state.status).toBe("error");
    expect(result.current.state.error).not.toBeNull();
    expect(result.current.state.error!.kind).toBe("network");
    expect(result.current.state.error!.i18nKey).toBe("aiActions.errorConnection");
    expect(result.current.isError).toBe(true);
    expect(onError).toHaveBeenCalled();
  });

  // -------------------------------------------------------------------------
  // Abort errors → swallowed (idle)
  // -------------------------------------------------------------------------

  it("swallows abort errors and returns to idle", async () => {
    const mock = createMockExecute();
    const { result } = renderHook(() =>
      useAIOperation({
        execute: mock.execute,
        connectionLossTimeout: 0,
      }),
    );

    act(() => {
      result.current.start();
    });

    await act(async () => {
      mock.reject(createAbortError());
    });

    expect(result.current.state.status).toBe("idle");
    expect(result.current.state.error).toBeNull();
  });

  // -------------------------------------------------------------------------
  // Cancel transitions: loading → cancel → idle
  // -------------------------------------------------------------------------

  it("transitions loading → idle on cancel", () => {
    const mock = createMockExecute();
    const { result } = renderHook(() =>
      useAIOperation({
        execute: mock.execute,
        connectionLossTimeout: 0,
      }),
    );

    act(() => {
      result.current.start();
    });
    expect(result.current.state.status).toBe("loading");

    act(() => {
      result.current.cancel();
    });
    expect(result.current.state.status).toBe("idle");
    expect(result.current.isIdle).toBe(true);
  });

  it("transitions streaming → idle on cancel", () => {
    const mock = createMockExecute();
    const { result } = renderHook(() =>
      useAIOperation({
        execute: mock.execute,
        connectionLossTimeout: 0,
      }),
    );

    act(() => {
      result.current.start();
    });
    act(() => {
      result.current.notifyData();
    });
    expect(result.current.state.status).toBe("streaming");

    act(() => {
      result.current.cancel();
    });
    expect(result.current.state.status).toBe("idle");
  });

  it("cancel is no-op when idle", () => {
    const mock = createMockExecute();
    const { result } = renderHook(() =>
      useAIOperation({
        execute: mock.execute,
        connectionLossTimeout: 0,
      }),
    );

    act(() => {
      result.current.cancel();
    });
    expect(result.current.state.status).toBe("idle");
  });

  // -------------------------------------------------------------------------
  // Concurrent start prevention
  // -------------------------------------------------------------------------

  it("start is no-op if already loading", () => {
    const mock = createMockExecute();
    const { result } = renderHook(() =>
      useAIOperation({
        execute: mock.execute,
        connectionLossTimeout: 0,
      }),
    );

    act(() => {
      result.current.start();
    });
    expect(result.current.state.status).toBe("loading");
    expect(result.current.state.attemptCount).toBe(1);

    // Second start should be a no-op
    act(() => {
      result.current.start();
    });
    expect(result.current.state.status).toBe("loading");
    expect(result.current.state.attemptCount).toBe(1);
  });

  // -------------------------------------------------------------------------
  // notifyData transitions
  // -------------------------------------------------------------------------

  it("notifyData transitions loading → streaming", () => {
    const mock = createMockExecute();
    const { result } = renderHook(() =>
      useAIOperation({
        execute: mock.execute,
        connectionLossTimeout: 0,
      }),
    );

    act(() => {
      result.current.start();
    });
    expect(result.current.state.status).toBe("loading");

    act(() => {
      result.current.notifyData();
    });
    expect(result.current.state.status).toBe("streaming");
  });

  it("notifyData is no-op when idle", () => {
    const mock = createMockExecute();
    const { result } = renderHook(() =>
      useAIOperation({
        execute: mock.execute,
        connectionLossTimeout: 0,
      }),
    );

    act(() => {
      result.current.notifyData();
    });
    expect(result.current.state.status).toBe("idle");
  });

  // -------------------------------------------------------------------------
  // Retry
  // -------------------------------------------------------------------------

  it("retry re-invokes execute after error", async () => {
    let callCount = 0;
    const execute = vi.fn((_signal: AbortSignal) => {
      callCount += 1;
      if (callCount === 1) {
        return Promise.reject(new Error("fail"));
      }
      return Promise.resolve("recovered");
    });

    const { result } = renderHook(() =>
      useAIOperation({
        execute,
        connectionLossTimeout: 0,
      }),
    );

    act(() => {
      result.current.start();
    });

    // Flush the microtask
    await act(async () => {
      vi.advanceTimersByTime(0);
    });
    expect(result.current.state.status).toBe("error");
    expect(execute).toHaveBeenCalledTimes(1);

    // Retry
    act(() => {
      result.current.retry();
    });

    // Flush microtask
    await act(async () => {
      vi.advanceTimersByTime(0);
    });
    expect(result.current.state.status).toBe("complete");
    expect(result.current.state.result).toBe("recovered");
    expect(execute).toHaveBeenCalledTimes(2);
  });

  it("retry is no-op when idle", () => {
    const mock = createMockExecute();
    const { result } = renderHook(() =>
      useAIOperation({
        execute: mock.execute,
        connectionLossTimeout: 0,
      }),
    );

    act(() => {
      result.current.retry();
    });
    expect(result.current.state.status).toBe("idle");
  });

  // -------------------------------------------------------------------------
  // Connection-loss timer
  // -------------------------------------------------------------------------

  it("transitions to connection_lost when timer fires", async () => {
    const mock = createMockExecute();
    const { result } = renderHook(() =>
      useAIOperation({
        execute: mock.execute,
        connectionLossTimeout: 5000,
      }),
    );

    act(() => {
      result.current.start();
    });

    // Flush the queueMicrotask that starts the timer
    await act(async () => {
      await vi.runAllTimersAsync();
    });

    expect(result.current.state.status).toBe("connection_lost");
    expect(result.current.isConnectionLost).toBe(true);
  });

  it("resets connection-loss timer on notifyData", async () => {
    const mock = createMockExecute();
    const { result } = renderHook(() =>
      useAIOperation({
        execute: mock.execute,
        connectionLossTimeout: 5000,
      }),
    );

    act(() => {
      result.current.start();
    });

    // Flush microtask, then advance 3s and notifyData
    await act(async () => {
      // Let microtask execute to start timer
      vi.advanceTimersByTime(0);
    });

    act(() => {
      vi.advanceTimersByTime(3000);
    });
    act(() => {
      result.current.notifyData();
    });

    // After another 3s (6s total, but timer was reset at 3s), still streaming
    act(() => {
      vi.advanceTimersByTime(3000);
    });
    expect(result.current.state.status).toBe("streaming");

    // After full 5s from last notifyData, connection_lost fires
    act(() => {
      vi.advanceTimersByTime(2000);
    });
    expect(result.current.state.status).toBe("connection_lost");
  });

  it("does not fire connection-loss timer when disabled (timeout=0)", () => {
    const mock = createMockExecute();
    const { result } = renderHook(() =>
      useAIOperation({
        execute: mock.execute,
        connectionLossTimeout: 0,
      }),
    );

    act(() => {
      result.current.start();
    });

    act(() => {
      vi.advanceTimersByTime(60_000);
    });

    expect(result.current.state.status).toBe("loading");
  });

  // -------------------------------------------------------------------------
  // Reset
  // -------------------------------------------------------------------------

  it("reset clears all state", async () => {
    const mock = createMockExecute();
    const { result } = renderHook(() =>
      useAIOperation({
        execute: mock.execute,
        connectionLossTimeout: 0,
      }),
    );

    act(() => {
      result.current.start();
    });

    await act(async () => {
      mock.reject(new Error("fail"));
    });
    expect(result.current.state.status).toBe("error");
    expect(result.current.state.attemptCount).toBe(1);

    act(() => {
      result.current.reset();
    });
    expect(result.current.state.status).toBe("idle");
    expect(result.current.state.result).toBeNull();
    expect(result.current.state.error).toBeNull();
    expect(result.current.state.attemptCount).toBe(0);
  });

  // -------------------------------------------------------------------------
  // Connection_lost → retry → complete
  // -------------------------------------------------------------------------

  it("supports retry from connection_lost state", async () => {
    let callCount = 0;
    const execute = vi.fn((_signal: AbortSignal) => {
      callCount += 1;
      // Never resolves on first call (simulates hanging connection)
      if (callCount === 1) {
        return new Promise<string>(() => {});
      }
      return Promise.resolve("recovered");
    });

    const { result } = renderHook(() =>
      useAIOperation({
        execute,
        connectionLossTimeout: 5000,
      }),
    );

    act(() => {
      result.current.start();
    });

    // Flush microtask and advance timer to trigger connection_lost
    await act(async () => {
      await vi.runAllTimersAsync();
    });
    expect(result.current.state.status).toBe("connection_lost");

    // User clicks retry
    act(() => {
      result.current.retry();
    });

    // Flush microtask
    await act(async () => {
      vi.advanceTimersByTime(0);
    });
    expect(result.current.state.status).toBe("complete");
    expect(result.current.state.result).toBe("recovered");
    expect(result.current.state.attemptCount).toBe(2);
  });

  // -------------------------------------------------------------------------
  // Custom error mapper
  // -------------------------------------------------------------------------

  it("uses custom error mapper when provided", async () => {
    const mock = createMockExecute();
    const customError: AIErrorResponse = {
      kind: "http",
      status: 418,
      i18nKey: "aiActions.errorDefault",
      userMessage: "I'm a teapot",
      retryable: false,
      cause: new Error("teapot"),
    };

    const { result } = renderHook(() =>
      useAIOperation({
        execute: mock.execute,
        connectionLossTimeout: 0,
        errorMapper: () => customError,
      }),
    );

    act(() => {
      result.current.start();
    });

    await act(async () => {
      mock.reject(new Error("fail"));
    });

    expect(result.current.state.status).toBe("error");
    expect(result.current.state.error).toBe(customError);
  });

  // -------------------------------------------------------------------------
  // SSEStreamError mapping (integration with ai-error-mapping)
  // -------------------------------------------------------------------------

  it("maps SSEStreamError with http kind to structured error", async () => {
    const mock = createMockExecute();

    // Create an SSEStreamError-like object
    const sseError = new Error("HTTP 401");
    Object.assign(sseError, { kind: "http", status: 401, name: "SSEStreamError" });

    const { result } = renderHook(() =>
      useAIOperation({
        execute: mock.execute,
        connectionLossTimeout: 0,
      }),
    );

    act(() => {
      result.current.start();
    });

    await act(async () => {
      mock.reject(sseError);
    });

    expect(result.current.state.status).toBe("error");
    expect(result.current.state.error!.kind).toBe("http");
    expect(result.current.state.error!.status).toBe(401);
    expect(result.current.state.error!.i18nKey).toBe("aiActions.errorApiKey");
    expect(result.current.state.error!.retryable).toBe(false);
  });

  // -------------------------------------------------------------------------
  // attemptCount tracking
  // -------------------------------------------------------------------------

  it("increments attemptCount on each start", () => {
    const mock = createMockExecute();
    const { result } = renderHook(() =>
      useAIOperation({
        execute: mock.execute,
        connectionLossTimeout: 0,
      }),
    );

    expect(result.current.state.attemptCount).toBe(0);

    act(() => {
      result.current.start();
    });
    expect(result.current.state.attemptCount).toBe(1);

    // Cancel and start again
    act(() => {
      result.current.cancel();
    });
    act(() => {
      result.current.start();
    });
    expect(result.current.state.attemptCount).toBe(2);
  });
});
