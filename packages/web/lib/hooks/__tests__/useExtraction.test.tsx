/**
 * useExtraction hook tests — useAIOperation wrapper for KB extraction.
 *
 * Tests the wrapper API mapping (mutate, data, error, isSuccess, isError, abort).
 * useAIOperation is mocked — these tests verify the hook correctly maps
 * the primitive's state to the backward-compatible interface.
 *
 * Tests:
 * 1. useExtractChapter.mutate calls aiOp.start
 * 2. useExtractChapter.data reflects state.result when complete
 * 3. useExtractChapter.error wraps state.error.userMessage
 * 4. useApplyExtraction.mutate stores items and calls aiOp.start
 * 5. useApplyExtraction.data reflects state.result when complete
 * 6. useApplyExtraction.error wraps state.error.userMessage
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
import { useApplyExtraction, useExtractChapter } from "@/lib/hooks/useExtraction";

const mockedUseAIOperation = vi.mocked(useAIOperation);

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockExtractionOutput = {
  results: [
    {
      item_type: "new_entity" as const,
      entity_type: "character",
      name: "Anna Schmidt",
      confidence: 0.92,
      source_text: "She walked through the old archive.",
      proposed_content: { role: "Protagonist" },
      target_entity_id: null,
      conflict_description: null,
      relationship_type: null,
      related_entity_name: null,
    },
  ],
  analysis_notes: "Found 1 new entity.",
};

const mockApplyResponse = {
  created_entries: [{ id: "entry-1", name: "Anna Schmidt", entity_type: "character" }],
  updated_entries: [],
};

const mockError = {
  kind: "http" as const,
  i18nKey: "aiActions.errorDefault",
  userMessage: "Extraction failed",
  retryable: true,
  cause: new Error("Extraction failed"),
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
// Tests: useExtractChapter
// ---------------------------------------------------------------------------

describe("useExtractChapter", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("calls aiOp.start when mutate is called", () => {
    const mockAiOp = createDefaultMockAiOp();
    mockedUseAIOperation.mockReturnValue(mockAiOp);

    const { result } = renderHook(() => useExtractChapter("novel-1", "chapter-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate(undefined);

    expect(mockAiOp.start).toHaveBeenCalledOnce();
  });

  it("returns data when state is complete", () => {
    const mockAiOp = createDefaultMockAiOp({
      state: {
        status: "complete",
        result: mockExtractionOutput,
        error: null,
        attemptCount: 1,
      },
      isComplete: true,
      isIdle: false,
    });
    mockedUseAIOperation.mockReturnValue(mockAiOp);

    const { result } = renderHook(() => useExtractChapter("novel-1", "chapter-1"), {
      wrapper: createWrapper(),
    });

    expect(result.current.isSuccess).toBe(true);
    expect(result.current.data).toEqual(mockExtractionOutput);
    expect(result.current.data?.results).toHaveLength(1);
    expect(result.current.data?.results[0].name).toBe("Anna Schmidt");
    expect(result.current.data?.analysis_notes).toBe("Found 1 new entity.");
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

    const { result } = renderHook(() => useExtractChapter("novel-1", "chapter-1"), {
      wrapper: createWrapper(),
    });

    expect(result.current.isError).toBe(true);
    expect(result.current.error?.message).toBe("Extraction failed");
  });
});

// ---------------------------------------------------------------------------
// Tests: useApplyExtraction
// ---------------------------------------------------------------------------

describe("useApplyExtraction", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("calls aiOp.start when mutate is called", () => {
    const mockAiOp = createDefaultMockAiOp();
    mockedUseAIOperation.mockReturnValue(mockAiOp);

    const mockApplyItems = [
      {
        item_type: "new_entity" as const,
        name: "Anna Schmidt",
        entity_type: "character",
        proposed_content: { role: "Protagonist" },
        target_entity_id: null,
        relationship_type: null,
        related_entity_name: null,
        source_text: "She walked through the old archive.",
      },
    ];

    const { result } = renderHook(() => useApplyExtraction("novel-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate(mockApplyItems);

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

    const { result } = renderHook(() => useApplyExtraction("novel-1"), {
      wrapper: createWrapper(),
    });

    expect(result.current.isSuccess).toBe(true);
    expect(result.current.data).toEqual(mockApplyResponse);
    expect(result.current.data?.created_entries).toHaveLength(1);
    expect(result.current.data?.created_entries[0].name).toBe("Anna Schmidt");
    expect(result.current.data?.updated_entries).toHaveLength(0);
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

    const { result } = renderHook(() => useApplyExtraction("novel-1"), {
      wrapper: createWrapper(),
    });

    expect(result.current.isError).toBe(true);
    expect(result.current.error?.message).toBe("Apply failed");
  });
});
