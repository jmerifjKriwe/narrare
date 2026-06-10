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

import type { AIOperationState, UseAIOperationReturn } from "@/lib/hooks/use-ai-operation";

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

import { useAIOperation } from "@/lib/hooks/use-ai-operation";
import { useBetaReaderAnalyze, useBetaReaderDeepDive } from "@/lib/hooks/useBetaReader";

const mockedUseAIOperation = vi.mocked(useAIOperation);

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
});
