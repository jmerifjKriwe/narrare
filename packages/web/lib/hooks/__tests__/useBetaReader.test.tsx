/**
 * useBetaReader hook tests — TanStack Query hooks for beta reader analysis.
 *
 * Tests:
 * 1. useBetaReaderAnalyze calls analysisApi.analyze with correct params
 * 2. useBetaReaderAnalyze handles API errors
 * 3. useBetaReaderAnalyze caches result on success
 * 4. useBetaReaderDeepDive calls analysisApi.deepDive with correct params
 * 5. useBetaReaderDeepDive handles API errors
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Mock the API client module
vi.mock("@/lib/api/analysis", () => ({
  analysisApi: {
    analyze: vi.fn(),
    deepDive: vi.fn(),
  },
}));

import { analysisApi } from "@/lib/api/analysis";
import { useBetaReaderAnalyze, useBetaReaderDeepDive } from "@/lib/hooks/useBetaReader";

// ---------------------------------------------------------------------------
// Mock helpers
// ---------------------------------------------------------------------------

const mockAnalyze = analysisApi.analyze as ReturnType<typeof vi.fn>;
const mockDeepDive = analysisApi.deepDive as ReturnType<typeof vi.fn>;

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

describe("useBetaReaderAnalyze", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("calls analysisApi.analyze with novelId and request", async () => {
    mockAnalyze.mockResolvedValueOnce(mockAnalysisResponse);

    const { result } = renderHook(() => useBetaReaderAnalyze("novel-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate({
      chapter_ids: ["ch-1"],
      phase: "full",
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockAnalyze).toHaveBeenCalledWith(
      "novel-1",
      {
        chapter_ids: ["ch-1"],
        phase: "full",
      },
      expect.any(AbortSignal),
    );
    expect(result.current.data?.cache_key).toBe("cache-abc");
  });

  it("handles API errors", async () => {
    mockAnalyze.mockRejectedValueOnce(new Error("Analysis failed"));

    const { result } = renderHook(() => useBetaReaderAnalyze("novel-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate({ chapter_ids: ["ch-1"], phase: "full" });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error?.message).toBe("Analysis failed");
  });

  it("caches result in query cache on success", async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0 },
        mutations: { retry: false },
      },
    });
    const setQueryDataSpy = vi.spyOn(queryClient, "setQueryData");

    mockAnalyze.mockResolvedValueOnce(mockAnalysisResponse);

    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useBetaReaderAnalyze("novel-1"), { wrapper });

    result.current.mutate({ chapter_ids: ["ch-1"], phase: "full" });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(setQueryDataSpy).toHaveBeenCalledWith(
      ["analysis", "novel-1", "beta-reader", "ch-1"],
      mockAnalysisResponse,
    );
  });

  it("returns overall assessment on success", async () => {
    mockAnalyze.mockResolvedValueOnce(mockAnalysisResponse);

    const { result } = renderHook(() => useBetaReaderAnalyze("novel-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate({ chapter_ids: ["ch-1"], phase: "full" });

    await waitFor(() => {
      expect(result.current.data).toBeDefined();
    });

    expect(result.current.data?.overall.reader_engagement).toBe(7);
  });
});

describe("useBetaReaderDeepDive", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("calls analysisApi.deepDive with novelId and request", async () => {
    mockDeepDive.mockResolvedValueOnce(mockDeepDiveResponse);

    const { result } = renderHook(() => useBetaReaderDeepDive("novel-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate({
      chapter_ids: ["ch-1"],
      category: "pacing",
      cache_key: "cache-abc",
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockDeepDive).toHaveBeenCalledWith(
      "novel-1",
      {
        chapter_ids: ["ch-1"],
        category: "pacing",
        cache_key: "cache-abc",
      },
      expect.any(AbortSignal),
    );
    expect(result.current.data?.category_score).toBe(4.5);
  });

  it("handles API errors", async () => {
    mockDeepDive.mockRejectedValueOnce(new Error("Deep dive failed"));

    const { result } = renderHook(() => useBetaReaderDeepDive("novel-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate({
      chapter_ids: ["ch-1"],
      category: "pacing",
      cache_key: "cache-abc",
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error?.message).toBe("Deep dive failed");
  });
});
