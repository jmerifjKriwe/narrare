/**
 * useKBImprove hook tests — TanStack Query hooks for KB entry improvement.
 *
 * Tests:
 * 1. useKBImproveAnalysis calls analyzeEntry and caches result
 * 2. useKBImproveAnalysis handles errors
 * 3. useKBImproveApply calls applyImprovements and invalidates caches
 * 4. useKBImproveApply handles errors
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Mock the API client module
vi.mock("@/lib/api/kb-improve", () => ({
  kbImproveApi: {
    analyzeEntry: vi.fn(),
    applyImprovements: vi.fn(),
  },
}));

import { kbImproveApi } from "@/lib/api/kb-improve";
import { useKBImproveAnalysis, useKBImproveApply } from "@/lib/hooks/useKBImprove";

// ---------------------------------------------------------------------------
// Mock helpers
// ---------------------------------------------------------------------------

const mockAnalyzeEntry = kbImproveApi.analyzeEntry as ReturnType<typeof vi.fn>;
const mockApplyImprovements = kbImproveApi.applyImprovements as ReturnType<typeof vi.fn>;

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockAnalysisResponse = {
  suggestions: [
    {
      type: "add_field" as const,
      target: "personality",
      description: "Add personality trait.",
      proposed_content: "Brave and impulsive.",
      related_entity_id: null,
      related_entity_name: null,
      confidence: 0.88,
      reasoning: "Adds depth.",
      suggestion_id: 1,
    },
  ],
  overall_assessment: "Entry needs more depth.",
  completeness_score: 0.55,
};

const mockApplyResponse = {
  success: true,
  entry_id: "entry-1",
  applied_count: 1,
  message: "Applied 1 suggestion.",
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

function createWrapperWithClient(queryClient: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useKBImproveAnalysis", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("calls kbImproveApi.analyzeEntry with novelId and entryId", async () => {
    mockAnalyzeEntry.mockResolvedValueOnce(mockAnalysisResponse);

    const { result } = renderHook(() => useKBImproveAnalysis("novel-1", "entry-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate(undefined);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockAnalyzeEntry).toHaveBeenCalledWith("novel-1", "entry-1", undefined);
    expect(result.current.data?.suggestions).toHaveLength(1);
    expect(result.current.data?.completeness_score).toBe(0.55);
  });

  it("passes abort signal to analyzeEntry", async () => {
    mockAnalyzeEntry.mockResolvedValueOnce(mockAnalysisResponse);

    const { result } = renderHook(() => useKBImproveAnalysis("novel-1", "entry-1"), {
      wrapper: createWrapper(),
    });

    const controller = new AbortController();
    result.current.mutate(controller.signal);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockAnalyzeEntry).toHaveBeenCalledWith("novel-1", "entry-1", controller.signal);
  });

  it("caches analysis result in query cache on success", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
    });
    const setSpy = vi.spyOn(queryClient, "setQueryData");

    mockAnalyzeEntry.mockResolvedValueOnce(mockAnalysisResponse);

    const { result } = renderHook(() => useKBImproveAnalysis("novel-1", "entry-1"), {
      wrapper: createWrapperWithClient(queryClient),
    });

    result.current.mutate(undefined);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(setSpy).toHaveBeenCalledWith(
      ["kb", "novel-1", "improve", "entry-1"],
      mockAnalysisResponse,
    );
  });

  it("handles API errors", async () => {
    mockAnalyzeEntry.mockRejectedValueOnce(new Error("Analysis failed"));

    const { result } = renderHook(() => useKBImproveAnalysis("novel-1", "entry-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate(undefined);

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error?.message).toBe("Analysis failed");
  });
});

describe("useKBImproveApply", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("calls kbImproveApi.applyImprovements with correct params", async () => {
    mockApplyImprovements.mockResolvedValueOnce(mockApplyResponse);

    const { result } = renderHook(() => useKBImproveApply("novel-1", "entry-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate([1, 2]);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockApplyImprovements).toHaveBeenCalledWith("novel-1", "entry-1", [1, 2]);
    expect(result.current.data?.applied_count).toBe(1);
  });

  it("invalidates entry caches on success", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
    });
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    mockApplyImprovements.mockResolvedValueOnce(mockApplyResponse);

    const { result } = renderHook(() => useKBImproveApply("novel-1", "entry-1"), {
      wrapper: createWrapperWithClient(queryClient),
    });

    result.current.mutate([1]);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    // Should invalidate entry list, entry detail, and analysis caches
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["kb", "novel-1", "entries"] });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: ["kb", "novel-1", "entries", "entry-1"],
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: ["kb", "novel-1", "improve", "entry-1"],
    });
  });

  it("handles API errors", async () => {
    mockApplyImprovements.mockRejectedValueOnce(new Error("Apply failed"));

    const { result } = renderHook(() => useKBImproveApply("novel-1", "entry-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate([1]);

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error?.message).toBe("Apply failed");
  });
});
