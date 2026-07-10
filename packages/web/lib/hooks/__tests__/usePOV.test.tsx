/**
 * usePOV hook tests — TanStack Query mutation hook for ANAL-004.
 *
 * Tests usePOVAnalysis mutation hook:
 * 1. Calls analysisApi.analyzePOV on mutate
 * 2. Returns data on success
 * 3. Stores result in query cache on success
 * 4. Handles API errors
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Mock the API client module
vi.mock("@/lib/api/analysis", () => ({
  analysisApi: {
    analyzePOV: vi.fn(),
  },
}));

import { analysisApi, type POVResult } from "@/lib/api/analysis";
import { usePOVAnalysis } from "@/lib/hooks/usePOV";

const mockAnalyzePOV = vi.mocked(analysisApi.analyzePOV);

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockPOVResult: POVResult = {
  scenes: [
    {
      scene_index: 0,
      start_position: 0,
      end_position: 100,
      pov_character: "Anna",
      confidence: 0.95,
    },
    {
      scene_index: 1,
      start_position: 101,
      end_position: 200,
      pov_character: "Ben",
      confidence: 0.88,
    },
  ],
  issues: [
    {
      type: "head_hop",
      location: "Chapter 1, paragraph 3",
      text: "Suddenly she felt tired...",
      explanation: "POV shifted from Anna to Ben without break",
      suggestion: "Add a scene break or stay in one POV",
      severity: "warning",
    },
  ],
  pov_distribution: { Anna: 50, Ben: 50 },
  switch_count: 1,
  analysis_type: "comprehensive",
};

const mockRequest = { chapter_ids: ["ch-1", "ch-2"] };

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
// Tests
// ---------------------------------------------------------------------------

describe("usePOVAnalysis", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("calls analysisApi.analyzePOV on mutate", async () => {
    mockAnalyzePOV.mockResolvedValueOnce(mockPOVResult);

    const { result } = renderHook(() => usePOVAnalysis("novel-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate(mockRequest);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockAnalyzePOV).toHaveBeenCalledWith("novel-1", mockRequest);
    expect(result.current.data).toEqual(mockPOVResult);
  });

  it("returns data on success", async () => {
    mockAnalyzePOV.mockResolvedValueOnce(mockPOVResult);

    const { result } = renderHook(() => usePOVAnalysis("novel-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate(mockRequest);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data?.scenes).toHaveLength(2);
    expect(result.current.data?.issues).toHaveLength(1);
    expect(result.current.data?.switch_count).toBe(1);
  });

  it("stores result in query cache on success", async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        // gcTime > 0: the hook writes a query with no observer via setQueryData.
        // gcTime: 0 would garbage-collect it before getQueryData can read it.
        queries: { retry: false, gcTime: 60_000 },
        mutations: { retry: false },
      },
    });
    mockAnalyzePOV.mockResolvedValueOnce(mockPOVResult);

    const { result } = renderHook(() => usePOVAnalysis("novel-1"), {
      wrapper: ({ children }: { children: ReactNode }) => (
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      ),
    });

    result.current.mutate(mockRequest);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    const cached = queryClient.getQueryData(["analysis", "novel-1", "pov", "ch-1", "ch-2"]);
    expect(cached).toEqual(mockPOVResult);
  });

  it("handles API errors", async () => {
    mockAnalyzePOV.mockRejectedValueOnce(new Error("POV analysis failed"));

    const { result } = renderHook(() => usePOVAnalysis("novel-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate(mockRequest);

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error?.message).toBe("POV analysis failed");
  });
});
