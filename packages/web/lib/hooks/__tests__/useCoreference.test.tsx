/**
 * useCoreference hook tests — SSE coreference analysis via useAIOperation.
 *
 * Strategy (same as useChat): mock useAIOperation but capture the `execute`
 * option it receives, then drive it directly. streamCoreference is mocked so
 * we can control its onResult / onComplete / onError callbacks and the abort
 * signal.
 *
 * Covers:
 *  - run() stages the chapter id and calls start
 *  - execute rejects when no chapter is staged
 *  - execute resolves the streamed result (onResult + onComplete)
 *  - execute resolves an empty fallback when no payload arrived
 *  - execute rejects on stream error
 *  - execute rejects with AbortError when the signal aborts
 *  - cancel/retry/reset are surfaced from the primitive
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { AIOperationState, UseAIOperationReturn } from "@/lib/hooks/use-ai-operation";

const { createMockAiOp } = vi.hoisted(() => {
  function createMockAiOp<T>(
    overrides: Partial<UseAIOperationReturn<T>> = {},
  ): UseAIOperationReturn<T> {
    return {
      state: { status: "idle", result: null, error: null, attemptCount: 0 } as AIOperationState<T>,
      start: vi.fn(),
      cancel: vi.fn(),
      retry: vi.fn(),
      reset: vi.fn(),
      notifyData: vi.fn(),
      isIdle: true,
      isLoading: false,
      isStreaming: false,
      isComplete: false,
      isError: false,
      isConnectionLost: false,
      ...overrides,
    };
  }
  return { createMockAiOp };
});

vi.mock("@/lib/hooks/use-ai-operation", () => ({ useAIOperation: vi.fn() }));
vi.mock("@/lib/api/coreference-stream", () => ({ streamCoreference: vi.fn() }));

import type { CoreferenceResult } from "@/lib/api/coreference-stream";
import { streamCoreference } from "@/lib/api/coreference-stream";
import { useAIOperation } from "@/lib/hooks/use-ai-operation";
import { useCoreference } from "@/lib/hooks/useCoreference";

const mockedUseAIOperation = vi.mocked(useAIOperation);
const mockedStream = vi.mocked(streamCoreference);

type Execute = (signal: AbortSignal) => Promise<CoreferenceResult>;
let capturedExecute: Execute;
let mockAiOp: UseAIOperationReturn<unknown>;

function setup(overrides: Partial<UseAIOperationReturn<unknown>> = {}) {
  mockAiOp = createMockAiOp(overrides);
  mockedUseAIOperation.mockImplementation((opts) => {
    capturedExecute = opts.execute as Execute;
    return mockAiOp;
  });
}

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

const coreferenceResult: CoreferenceResult = {
  chapter_id: "ch-1",
  clarity_score: 0.9,
  summary: "Clear references.",
  resolutions: [],
  character_mentions: [],
};

beforeEach(() => {
  vi.clearAllMocks();
  setup();
});
afterEach(() => cleanup());

describe("useCoreference — run()", () => {
  it("stages the chapter id and starts the operation", () => {
    const { result } = renderHook(() => useCoreference(null), { wrapper: createWrapper() });

    act(() => {
      result.current.run("ch-2");
    });

    expect(mockAiOp.start).toHaveBeenCalledTimes(1);
  });
});

describe("useCoreference — execute", () => {
  it("rejects when no chapter is staged", async () => {
    renderHook(() => useCoreference(null), { wrapper: createWrapper() });

    await expect(capturedExecute(new AbortController().signal)).rejects.toThrow(
      "No chapter selected for coreference analysis",
    );
    expect(mockedStream).not.toHaveBeenCalled();
  });

  it("resolves the streamed result (onResult + onComplete)", async () => {
    const { result } = renderHook(() => useCoreference(null), { wrapper: createWrapper() });
    act(() => result.current.run("ch-1"));

    mockedStream.mockImplementationOnce(async (_id, cbs) => {
      cbs.onResult(coreferenceResult);
      cbs.onComplete?.();
    });

    const out = await capturedExecute(new AbortController().signal);

    expect(out).toBe(coreferenceResult);
    expect(mockAiOp.notifyData).toHaveBeenCalled();
  });

  it("resolves an empty fallback when the stream completed with no payload", async () => {
    const { result } = renderHook(() => useCoreference(null), { wrapper: createWrapper() });
    act(() => result.current.run("ch-7"));

    mockedStream.mockImplementationOnce(async (_id, cbs) => {
      cbs.onComplete?.();
    });

    const out = await capturedExecute(new AbortController().signal);

    expect(out.chapter_id).toBe("ch-7");
    expect(out.clarity_score).toBe(0);
    expect(out.resolutions).toEqual([]);
  });

  it("rejects on stream error", async () => {
    const { result } = renderHook(() => useCoreference(null), { wrapper: createWrapper() });
    act(() => result.current.run("ch-1"));

    mockedStream.mockImplementationOnce(async (_id, cbs) => {
      cbs.onError?.(new Error("stream down"));
    });

    await expect(capturedExecute(new AbortController().signal)).rejects.toThrow("stream down");
  });

  it("rejects with an AbortError when the signal aborts", async () => {
    const { result } = renderHook(() => useCoreference(null), { wrapper: createWrapper() });
    act(() => result.current.run("ch-1"));

    const controller = new AbortController();
    mockedStream.mockImplementationOnce(async () => {
      // Simulate an external abort mid-stream.
      controller.abort();
    });

    await expect(capturedExecute(controller.signal)).rejects.toThrow("Aborted");
  });

  it("does not settle again when onComplete fires after onError", async () => {
    const { result } = renderHook(() => useCoreference(null), { wrapper: createWrapper() });
    act(() => result.current.run("ch-1"));

    // onError fires first (rejects), then onComplete (should be no-op)
    mockedStream.mockImplementationOnce(async (_id, cbs) => {
      cbs.onError?.(new Error("stream error"));
      cbs.onComplete?.();
    });

    await expect(capturedExecute(new AbortController().signal)).rejects.toThrow("stream error");
  });

  it("does not settle again when onError fires after onComplete", async () => {
    const { result } = renderHook(() => useCoreference(null), { wrapper: createWrapper() });
    act(() => result.current.run("ch-1"));

    // onComplete fires first (resolves), then onError (should be no-op)
    mockedStream.mockImplementationOnce(async (_id, cbs) => {
      cbs.onResult(coreferenceResult);
      cbs.onComplete?.();
      cbs.onError?.(new Error("late error"));
    });

    const out = await capturedExecute(new AbortController().signal);
    expect(out).toBe(coreferenceResult);
  });
});

describe("useCoreference — surfaced primitive actions", () => {
  it("cancel, retry and reset are forwarded", () => {
    const { result } = renderHook(() => useCoreference("ch-1"), { wrapper: createWrapper() });

    result.current.cancel();
    result.current.retry();
    result.current.reset();

    expect(mockAiOp.cancel).toHaveBeenCalled();
    expect(mockAiOp.retry).toHaveBeenCalled();
    expect(mockAiOp.reset).toHaveBeenCalled();
  });
});
