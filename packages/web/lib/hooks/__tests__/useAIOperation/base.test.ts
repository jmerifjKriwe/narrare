/**
 * Base tests for useAIOperation hook.
 *
 * Covers: initial state, state transitions (idle → loading → streaming → complete),
 * idle → loading → error, abort error swallowing.
 */

import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAIOperation } from "@/lib/hooks/use-ai-operation";
import { createAbortError, createMockExecute } from "./setup";

describe("useAIOperation — base", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  // ---------------------------------------------------------------------------
  // Initial state
  // ---------------------------------------------------------------------------

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

  // ---------------------------------------------------------------------------
  // State transitions: idle → loading → streaming → complete
  // ---------------------------------------------------------------------------

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

  // ---------------------------------------------------------------------------
  // State transitions: idle → loading → error
  // ---------------------------------------------------------------------------

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

  // ---------------------------------------------------------------------------
  // Abort errors → swallowed (idle)
  // ---------------------------------------------------------------------------

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
});
