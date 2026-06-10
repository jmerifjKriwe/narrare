/**
 * Error-handling tests for useAIOperation hook.
 *
 * Covers: connection-loss timer, timer reset on notifyData,
 * custom error mapper, SSEStreamError mapping, retry from connection_lost.
 */

import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { AIErrorResponse } from "@/lib/hooks/use-ai-operation";
import { useAIOperation } from "@/lib/hooks/use-ai-operation";
import { createMockExecute } from "./setup";

describe("useAIOperation — error handling", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  // ---------------------------------------------------------------------------
  // Connection-loss timer
  // ---------------------------------------------------------------------------

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

    // Flush microtask (starts the connection-loss timer) then fire it
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

  // ---------------------------------------------------------------------------
  // Connection_lost → retry → complete
  // ---------------------------------------------------------------------------

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

    // Flush microtask (starts the connection-loss timer) then fire it
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

  // ---------------------------------------------------------------------------
  // Custom error mapper
  // ---------------------------------------------------------------------------

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

  // ---------------------------------------------------------------------------
  // SSEStreamError mapping (integration with ai-error-mapping)
  // ---------------------------------------------------------------------------

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
});
