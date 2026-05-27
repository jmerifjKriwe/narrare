/**
 * useWorldbuilding hook tests — TanStack Query hooks for worldbuilding analysis.
 *
 * Tests:
 * 1. useWorldbuildingAnalyze calls analyze and caches result
 * 2. useWorldbuildingAnalyze handles errors
 * 3. useWorldbuildingApply calls applyConnections and invalidates caches
 * 4. useWorldbuildingApply handles errors
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Mock the API client module
vi.mock("@/lib/api/worldbuilding", () => ({
  worldbuildingApi: {
    analyze: vi.fn(),
    applyConnections: vi.fn(),
  },
}));

import { worldbuildingApi } from "@/lib/api/worldbuilding";
import { useWorldbuildingAnalyze, useWorldbuildingApply } from "@/lib/hooks/useWorldbuilding";

// ---------------------------------------------------------------------------
// Mock helpers
// ---------------------------------------------------------------------------

const mockAnalyze = worldbuildingApi.analyze as ReturnType<typeof vi.fn>;
const mockApplyConnections = worldbuildingApi.applyConnections as ReturnType<typeof vi.fn>;

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

describe("useWorldbuildingAnalyze", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("calls worldbuildingApi.analyze with novelId and options", async () => {
    mockAnalyze.mockResolvedValueOnce(mockAnalysisResponse);

    const { result } = renderHook(() => useWorldbuildingAnalyze("novel-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate({ include_gaps: true });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockAnalyze).toHaveBeenCalledWith("novel-1", { include_gaps: true });
    expect(result.current.data?.worldbuilding_score).toBe(0.5);
  });

  it("caches analysis result on success", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
    });
    const setSpy = vi.spyOn(queryClient, "setQueryData");

    mockAnalyze.mockResolvedValueOnce(mockAnalysisResponse);

    const { result } = renderHook(() => useWorldbuildingAnalyze("novel-1"), {
      wrapper: createWrapperWithClient(queryClient),
    });

    result.current.mutate(undefined);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(setSpy).toHaveBeenCalledWith(
      ["worldbuilding", "novel-1", "analysis"],
      mockAnalysisResponse,
    );
  });

  it("handles API errors", async () => {
    mockAnalyze.mockRejectedValueOnce(new Error("Analysis failed"));

    const { result } = renderHook(() => useWorldbuildingAnalyze("novel-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate(undefined);

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error?.message).toBe("Analysis failed");
  });

  it("returns gap findings on success", async () => {
    mockAnalyze.mockResolvedValueOnce(mockAnalysisResponse);

    const { result } = renderHook(() => useWorldbuildingAnalyze("novel-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate(undefined);

    await waitFor(() => {
      expect(result.current.data).toBeDefined();
    });

    expect(result.current.data?.gap_findings).toHaveLength(1);
    expect(result.current.data?.gap_findings[0].severity).toBe("critical");
  });
});

describe("useWorldbuildingApply", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("calls worldbuildingApi.applyConnections with body", async () => {
    mockApplyConnections.mockResolvedValueOnce(mockApplyResponse);

    const { result } = renderHook(() => useWorldbuildingApply("novel-1"), {
      wrapper: createWrapper(),
    });

    const body = { finding_indices: [0], analysis: mockAnalysisResponse };

    result.current.mutate(body);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockApplyConnections).toHaveBeenCalledWith("novel-1", body);
    expect(result.current.data?.created_count).toBe(2);
  });

  it("invalidates KB and worldbuilding caches on success", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
    });
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    mockApplyConnections.mockResolvedValueOnce(mockApplyResponse);

    const { result } = renderHook(() => useWorldbuildingApply("novel-1"), {
      wrapper: createWrapperWithClient(queryClient),
    });

    result.current.mutate({ finding_indices: [0], analysis: mockAnalysisResponse });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["kb", "novel-1"] });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["worldbuilding", "novel-1"] });
  });

  it("handles API errors", async () => {
    mockApplyConnections.mockRejectedValueOnce(new Error("Apply failed"));

    const { result } = renderHook(() => useWorldbuildingApply("novel-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate({ finding_indices: [], analysis: mockAnalysisResponse });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error?.message).toBe("Apply failed");
  });
});
