/**
 * Execution tests for useAIOperation hook.
 *
 * Covers: cancel transitions, concurrent-start prevention,
 * notifyData transitions, retry, reset, attemptCount tracking.
 */

import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAIOperation } from "@/lib/hooks/use-ai-operation";
import { createMockExecute } from "./setup";

describe("useAIOperation — execution", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  // ---------------------------------------------------------------------------
  // Cancel transitions: loading → cancel → idle
  // ---------------------------------------------------------------------------

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

  // ---------------------------------------------------------------------------
  // Concurrent start prevention
  // ---------------------------------------------------------------------------

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

  // ---------------------------------------------------------------------------
  // notifyData transitions
  // ---------------------------------------------------------------------------

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

  // ---------------------------------------------------------------------------
  // Retry
  // ---------------------------------------------------------------------------

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

  // ---------------------------------------------------------------------------
  // Reset
  // ---------------------------------------------------------------------------

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

  // ---------------------------------------------------------------------------
  // attemptCount tracking
  // ---------------------------------------------------------------------------

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
