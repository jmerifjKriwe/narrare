/**
 * useBetaReader hook tests — useAIOperation wrapper for beta reader analysis.
 *
 * Tests the wrapper API mapping (mutate, data, error, isSuccess, isError, abort).
 * useAIOperation is mocked — these tests verify the hook correctly maps
 * the primitive's state to the backward-compatible interface.
 *
 * Tests:
 * 1. useBetaReaderAnalyze.mutate stores request and calls aiOp.start
 * 2. useBetaReaderAnalyze.data reflects state.result when complete
 * 3. useBetaReaderAnalyze.error wraps state.error.userMessage
 * 4. useBetaReaderDeepDive.mutate stores request and calls aiOp.start
 * 5. useBetaReaderDeepDive.data reflects state.result when complete
 * 6. useBetaReaderDeepDive.error wraps state.error.userMessage
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  AIErrorResponse,
  AIOperationState,
  UseAIOperationOptions,
  UseAIOperationReturn,
} from "@/lib/hooks/use-ai-operation";

// ---------------------------------------------------------------------------
// Hoisted mock data factory (needed in vi.mock, which is hoisted)
// ---------------------------------------------------------------------------

const { createDefaultMockAiOp } = vi.hoisted(() => {
  function createDefaultMockAiOp<T>(
    overrides: Partial<UseAIOperationReturn<T>> = {},
  ): UseAIOperationReturn<T> {
    const start = vi.fn();
    const cancel = vi.fn();
    return {
      state: {
        status: "idle",
        result: null,
        error: null,
        attemptCount: 0,
      } as AIOperationState<T>,
      start,
      cancel,
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
  return { createDefaultMockAiOp };
});

// Mock useAIOperation at module level
vi.mock("@/lib/hooks/use-ai-operation", () => ({
  useAIOperation: vi.fn(),
}));

// Mock the analysis API so the captured `execute` (which calls the real
// analysisApi.analyze / analysisApi.deepDive) does not fire a live fetch()
// against localhost:3000 — Next.js dev is not running in the vitest step, so
// unmocked calls fail with ECONNREFUSED. The "executes API call" tests only
// assert that the guard error is NOT thrown (analyze) / that execute runs
// past the guard (deepDive); controlled rejections satisfy both
// deterministically without touching the network. See ADR-059 Mock Contract.
vi.mock("@/lib/api/analysis", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/analysis")>();
  return {
    ...actual,
    analysisApi: {
      ...actual.analysisApi,
      analyze: vi.fn().mockRejectedValue(new Error("Mocked analyze failure")),
      deepDive: vi.fn().mockRejectedValue(new Error("Mocked deepDive failure")),
    },
  };
});

import { useAIOperation } from "@/lib/hooks/use-ai-operation";
import { useBetaReaderAnalyze, useBetaReaderDeepDive } from "@/lib/hooks/useBetaReader";

const mockedUseAIOperation = vi.mocked(useAIOperation);

// Capture the config passed to useAIOperation for testing internal callbacks.
// Each test using setupWithCapture() must call this BEFORE renderHook.
interface CapturedConfig {
  execute: (signal: AbortSignal) => Promise<unknown>;
  onSuccess?: (data: unknown) => void;
  onError?: (error: AIErrorResponse) => void;
}

let capturedConfig: CapturedConfig | null = null;

function setupWithCapture<T>(
  overrides: Partial<UseAIOperationReturn<T>> = {},
): UseAIOperationReturn<T> {
  const mockAiOp = createDefaultMockAiOp(overrides);
  mockedUseAIOperation.mockImplementation((config: UseAIOperationOptions<unknown>) => {
    capturedConfig = {
      execute: config.execute,
      onSuccess: config.onSuccess,
      onError: config.onError,
    };
    return mockAiOp;
  });
  return mockAiOp;
}

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockAnalysisResponse = {
  novel_id: "novel-1",
  chapter_ids: ["ch-1"],
  total_word_count: 3000,
  strengths: [],
  feedback: [],
  questions: [],
  overall: {
    summary: "Solid opening.",
    reader_engagement: 7,
    emotional_impact: 6,
    pacing_score: 5,
    prose_quality: 8,
    plot_progression: 7,
    character_development: 8,
  },
  analyzed_at: "2026-05-27T10:00:00Z",
  cache_key: "cache-abc",
};

const mockDeepDiveResponse = {
  novel_id: "novel-1",
  category: "pacing" as const,
  detailed_feedback: [],
  revision_suggestions: [],
  category_score: 4.5,
  analyzed_at: "2026-05-27T10:05:00Z",
};

const mockError = {
  kind: "http" as const,
  i18nKey: "aiActions.errorDefault",
  userMessage: "Analysis failed",
  retryable: true,
  cause: new Error("Analysis failed"),
};

// ---------------------------------------------------------------------------
// Test wrapper
// ---------------------------------------------------------------------------

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

// ---------------------------------------------------------------------------
// Tests: useBetaReaderAnalyze
// ---------------------------------------------------------------------------

describe("useBetaReaderAnalyze", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("calls aiOp.start when mutate is called", () => {
    const mockAiOp = createDefaultMockAiOp();
    mockedUseAIOperation.mockReturnValue(mockAiOp);

    const { result } = renderHook(() => useBetaReaderAnalyze("novel-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate({ chapter_ids: ["ch-1"], phase: "full" });

    expect(mockAiOp.start).toHaveBeenCalledOnce();
  });

  it("returns data when state is complete", () => {
    const mockAiOp = createDefaultMockAiOp({
      state: {
        status: "complete",
        result: mockAnalysisResponse,
        error: null,
        attemptCount: 1,
      },
      isComplete: true,
      isIdle: false,
    });
    mockedUseAIOperation.mockReturnValue(mockAiOp);

    const { result } = renderHook(() => useBetaReaderAnalyze("novel-1"), {
      wrapper: createWrapper(),
    });

    expect(result.current.isSuccess).toBe(true);
    expect(result.current.data).toEqual(mockAnalysisResponse);
    expect(result.current.data?.overall.reader_engagement).toBe(7);
  });

  it("returns error when state is error", () => {
    const mockAiOp = createDefaultMockAiOp({
      state: {
        status: "error",
        result: null,
        error: mockError,
        attemptCount: 1,
      },
      isError: true,
      isIdle: false,
    });
    mockedUseAIOperation.mockReturnValue(mockAiOp);

    const { result } = renderHook(() => useBetaReaderAnalyze("novel-1"), {
      wrapper: createWrapper(),
    });

    expect(result.current.isError).toBe(true);
    expect(result.current.error?.message).toBe("Analysis failed");
  });

  it("cancels via abort and calls aiOp.cancel", () => {
    const mockAiOp = createDefaultMockAiOp({
      state: {
        status: "loading",
        result: null,
        error: null,
        attemptCount: 1,
      },
      isLoading: true,
      isIdle: false,
    });
    mockedUseAIOperation.mockReturnValue(mockAiOp);

    const { result } = renderHook(() => useBetaReaderAnalyze("novel-1"), {
      wrapper: createWrapper(),
    });

    result.current.abort();
    expect(mockAiOp.cancel).toHaveBeenCalledOnce();
  });

  it("caches data in queryClient on success when a request was provided via mutate", () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const setQueryDataSpy = vi.spyOn(queryClient, "setQueryData");
    const Wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    setupWithCapture<typeof mockAnalysisResponse>();
    const { result } = renderHook(() => useBetaReaderAnalyze("novel-1"), {
      wrapper: Wrapper,
    });

    result.current.mutate({ chapter_ids: ["ch-1"], phase: "full" });
    capturedConfig!.onSuccess!(mockAnalysisResponse);

    expect(setQueryDataSpy).toHaveBeenCalledWith(
      ["analysis", "novel-1", "beta-reader", "ch-1"],
      mockAnalysisResponse,
    );
  });

  it("skips cache on success when no request was provided before success", () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const setQueryDataSpy = vi.spyOn(queryClient, "setQueryData");
    const Wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    setupWithCapture<typeof mockAnalysisResponse>();
    renderHook(() => useBetaReaderAnalyze("novel-1"), {
      wrapper: Wrapper,
    });

    // Don't call mutate — requestRef.current stays null
    capturedConfig!.onSuccess!(mockAnalysisResponse);

    expect(setQueryDataSpy).not.toHaveBeenCalled();
  });

  it("throws on execute when no request parameters were provided", async () => {
    setupWithCapture();
    renderHook(() => useBetaReaderAnalyze("novel-1"), {
      wrapper: createWrapper(),
    });

    // Don't call mutate — requestRef.current stays null
    await expect(capturedConfig!.execute(new AbortController().signal)).rejects.toThrow(
      "No request parameters provided",
    );
  });

  it("executes API call when request is set and propagates network error", async () => {
    setupWithCapture<typeof mockAnalysisResponse>();
    renderHook(() => useBetaReaderAnalyze("novel-1"), {
      wrapper: createWrapper(),
    });

    // mutate sets requestRef.current
    await expect(capturedConfig!.execute(new AbortController().signal)).rejects.toThrow();
  });
});

// ---------------------------------------------------------------------------
// Tests: useBetaReaderDeepDive
// ---------------------------------------------------------------------------

describe("useBetaReaderDeepDive", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("calls aiOp.start when mutate is called", () => {
    const mockAiOp = createDefaultMockAiOp();
    mockedUseAIOperation.mockReturnValue(mockAiOp);

    const { result } = renderHook(() => useBetaReaderDeepDive("novel-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate({
      chapter_ids: ["ch-1"],
      category: "pacing",
      cache_key: "cache-abc",
    });

    expect(mockAiOp.start).toHaveBeenCalledOnce();
  });

  it("returns data when state is complete", () => {
    const mockAiOp = createDefaultMockAiOp({
      state: {
        status: "complete",
        result: mockDeepDiveResponse,
        error: null,
        attemptCount: 1,
      },
      isComplete: true,
      isIdle: false,
    });
    mockedUseAIOperation.mockReturnValue(mockAiOp);

    const { result } = renderHook(() => useBetaReaderDeepDive("novel-1"), {
      wrapper: createWrapper(),
    });

    expect(result.current.isSuccess).toBe(true);
    expect(result.current.data?.category_score).toBe(4.5);
  });

  it("returns error when state is error", () => {
    const deepDiveError = {
      ...mockError,
      userMessage: "Deep dive failed",
      cause: new Error("Deep dive failed"),
    };
    const mockAiOp = createDefaultMockAiOp({
      state: {
        status: "error",
        result: null,
        error: deepDiveError,
        attemptCount: 1,
      },
      isError: true,
      isIdle: false,
    });
    mockedUseAIOperation.mockReturnValue(mockAiOp);

    const { result } = renderHook(() => useBetaReaderDeepDive("novel-1"), {
      wrapper: createWrapper(),
    });

    expect(result.current.isError).toBe(true);
    expect(result.current.error?.message).toBe("Deep dive failed");
  });

  it("throws on execute when no request parameters were provided for deep dive", async () => {
    setupWithCapture();
    renderHook(() => useBetaReaderDeepDive("novel-1"), {
      wrapper: createWrapper(),
    });

    await expect(capturedConfig!.execute(new AbortController().signal)).rejects.toThrow(
      "No request parameters provided",
    );
  });

  it("executes the API call for deep dive when request is set", async () => {
    setupWithCapture<typeof mockDeepDiveResponse>();
    const { result } = renderHook(() => useBetaReaderDeepDive("novel-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate({
      chapter_ids: ["ch-1"],
      category: "pacing",
      cache_key: "cache-abc",
    });

    // Should not throw "No request parameters" because requestRef is set
    let error: unknown = null;
    try {
      await capturedConfig!.execute(new AbortController().signal);
    } catch (e) {
      error = e;
    }
    expect(error).not.toEqual(new Error("No request parameters provided"));
  });
});
