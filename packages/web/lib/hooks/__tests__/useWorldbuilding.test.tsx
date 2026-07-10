/**
 * useWorldbuilding hook tests — useAIOperation wrapper for worldbuilding analysis.
 *
 * Tests the wrapper API mapping (mutate, data, error, isSuccess, isError, abort).
 * useAIOperation is mocked — these tests verify the hook correctly maps
 * the primitive's state to the backward-compatible interface.
 *
 * Tests:
 * 1. useWorldbuildingAnalyze.mutate stores options and calls aiOp.start
 * 2. useWorldbuildingAnalyze.data reflects state.result when complete
 * 3. useWorldbuildingAnalyze.error wraps state.error.userMessage
 * 4. useWorldbuildingApply.mutate stores body and calls aiOp.start
 * 5. useWorldbuildingApply.data reflects state.result when complete
 * 6. useWorldbuildingApply.error wraps state.error.userMessage
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { AIOperationState, UseAIOperationReturn } from "@/lib/hooks/use-ai-operation";

// ---------------------------------------------------------------------------
// Hoisted mock data factory
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
import { useWorldbuildingAnalyze, useWorldbuildingApply } from "@/lib/hooks/useWorldbuilding";

const mockedUseAIOperation = vi.mocked(useAIOperation);

interface CapturedConfig {
  execute: (signal: AbortSignal) => Promise<unknown>;
}

let capturedConfig: CapturedConfig | null = null;

function setupWithCapture(overrides: Partial<UseAIOperationReturn<unknown>> = {}) {
  const mockAiOp = createDefaultMockAiOp(overrides);
  mockedUseAIOperation.mockImplementation((config: any) => {
    capturedConfig = { execute: config.execute };
    return mockAiOp;
  });
  return mockAiOp;
}

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockAnalysisResponse = {
  novel_id: "novel-1",
  entity_count: 10,
  gap_findings: [
    {
      entity_id: null,
      entity_name: null,
      entity_type: null,
      gap_type: "missing_entity" as const,
      field_key: null,
      description: "No antagonist.",
      related_entity_type: "character",
      story_relevance: 9,
      severity: "critical" as const,
    },
  ],
  connection_suggestions: [],
  consistency_issues: [],
  worldbuilding_score: 0.5,
  overall_assessment: "Needs work.",
  summary: { missing_entity: 1 },
  analyzed_at: "2026-05-27T12:00:00Z",
};

const mockApplyResponse = {
  success: true,
  created_count: 2,
  failed_count: 0,
  errors: [],
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
// Tests: useWorldbuildingAnalyze
// ---------------------------------------------------------------------------

describe("useWorldbuildingAnalyze", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("stores options and calls aiOp.start when mutate is called", () => {
    const mockAiOp = createDefaultMockAiOp();
    mockedUseAIOperation.mockReturnValue(mockAiOp);

    const { result } = renderHook(() => useWorldbuildingAnalyze("novel-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate({ include_gaps: true });

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

    const { result } = renderHook(() => useWorldbuildingAnalyze("novel-1"), {
      wrapper: createWrapper(),
    });

    expect(result.current.isSuccess).toBe(true);
    expect(result.current.data?.worldbuilding_score).toBe(0.5);
    expect(result.current.data?.gap_findings).toHaveLength(1);
    expect(result.current.data?.gap_findings[0].severity).toBe("critical");
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

    const { result } = renderHook(() => useWorldbuildingAnalyze("novel-1"), {
      wrapper: createWrapper(),
    });

    expect(result.current.isError).toBe(true);
    expect(result.current.error?.message).toBe("Analysis failed");
  });
});

// ---------------------------------------------------------------------------
// Tests: useWorldbuildingApply
// ---------------------------------------------------------------------------

describe("useWorldbuildingApply", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("calls aiOp.start when mutate is called", () => {
    const mockAiOp = createDefaultMockAiOp();
    mockedUseAIOperation.mockReturnValue(mockAiOp);

    const { result } = renderHook(() => useWorldbuildingApply("novel-1"), {
      wrapper: createWrapper(),
    });

    const body = { finding_indices: [0], analysis: mockAnalysisResponse };
    result.current.mutate(body);

    expect(mockAiOp.start).toHaveBeenCalledOnce();
  });

  it("returns data when state is complete", () => {
    const mockAiOp = createDefaultMockAiOp({
      state: {
        status: "complete",
        result: mockApplyResponse,
        error: null,
        attemptCount: 1,
      },
      isComplete: true,
      isIdle: false,
    });
    mockedUseAIOperation.mockReturnValue(mockAiOp);

    const { result } = renderHook(() => useWorldbuildingApply("novel-1"), {
      wrapper: createWrapper(),
    });

    expect(result.current.isSuccess).toBe(true);
    expect(result.current.data?.created_count).toBe(2);
  });

  it("returns error when state is error", () => {
    const applyError = {
      ...mockError,
      userMessage: "Apply failed",
      cause: new Error("Apply failed"),
    };
    const mockAiOp = createDefaultMockAiOp({
      state: {
        status: "error",
        result: null,
        error: applyError,
        attemptCount: 1,
      },
      isError: true,
      isIdle: false,
    });
    mockedUseAIOperation.mockReturnValue(mockAiOp);

    const { result } = renderHook(() => useWorldbuildingApply("novel-1"), {
      wrapper: createWrapper(),
    });

    expect(result.current.isError).toBe(true);
    expect(result.current.error?.message).toBe("Apply failed");
  });

  it("throws on execute when no request body was provided", async () => {
    setupWithCapture();
    renderHook(() => useWorldbuildingApply("novel-1"), {
      wrapper: createWrapper(),
    });

    await expect(capturedConfig!.execute(new AbortController().signal)).rejects.toThrow(
      "No request body provided",
    );
  });

  it("proceeds past guard on execute when request body is set via mutate", async () => {
    setupWithCapture();
    const { result } = renderHook(() => useWorldbuildingApply("novel-1"), {
      wrapper: createWrapper(),
    });

    const body = { finding_indices: [0], analysis: mockAnalysisResponse };
    result.current.mutate(body);

    // Should not throw "No request body" — instead throws network error
    let err: unknown = null;
    try {
      await capturedConfig!.execute(new AbortController().signal);
    } catch (e) {
      err = e;
    }
    expect(err).not.toEqual(new Error("No request body provided"));
    expect(err).not.toBeNull();
  });
});
