/**
 * useReadability hook tests — TanStack Query mutation hook for ANAL-003.
 *
 * Tests useReadabilityAnalysis mutation hook:
 * 1. Calls analysisApi.readability on mutate
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
    readability: vi.fn(),
  },
}));

import { analysisApi, type ReadabilityResult } from "@/lib/api/analysis";
import { useReadabilityAnalysis } from "@/lib/hooks/useReadability";

const mockReadability = vi.mocked(analysisApi.readability);

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockReadabilityResult: ReadabilityResult[] = [
  {
    metrics: {
      flesch_reading_ease: 65.2,
      flesch_kincaid_grade: 8.5,
      gunning_fog: 10.2,
      avg_sentence_length: 15.3,
      avg_syllables_per_word: 1.5,
      complex_word_ratio: 0.12,
      word_count: 1500,
      sentence_count: 98,
    },
    sentence_analyses: [
      {
        sentence: "The old house stood silent.",
        sentence_index: 0,
        issues: [],
        readability_score: 85,
        suggestions: [],
      },
    ],
    genre_benchmarks: {
      literary: {
        flesch_reading_ease: 70,
        flesch_kincaid_grade: 7.5,
        gunning_fog: 9.0,
        avg_sentence_length: 14.0,
        avg_syllables_per_word: 1.4,
        complex_word_ratio: 0.1,
        word_count: 0,
        sentence_count: 0,
      },
    },
    overall_assessment: "Good readability for literary fiction.",
  },
];

const mockRequest = { chapter_ids: ["ch-1"] };

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

describe("useReadabilityAnalysis", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("calls analysisApi.readability on mutate", async () => {
    mockReadability.mockResolvedValueOnce(mockReadabilityResult);

    const { result } = renderHook(() => useReadabilityAnalysis("novel-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate(mockRequest);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockReadability).toHaveBeenCalledWith("novel-1", mockRequest);
    expect(result.current.data).toEqual(mockReadabilityResult);
  });

  it("returns readability metrics on success", async () => {
    mockReadability.mockResolvedValueOnce(mockReadabilityResult);

    const { result } = renderHook(() => useReadabilityAnalysis("novel-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate(mockRequest);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toHaveLength(1);
    expect(result.current.data?.[0].metrics.flesch_reading_ease).toBe(65.2);
    expect(result.current.data?.[0].overall_assessment).toBe(
      "Good readability for literary fiction.",
    );
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
    mockReadability.mockResolvedValueOnce(mockReadabilityResult);

    const { result } = renderHook(() => useReadabilityAnalysis("novel-1"), {
      wrapper: ({ children }: { children: ReactNode }) => (
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      ),
    });

    result.current.mutate(mockRequest);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    const cached = queryClient.getQueryData(["analysis", "novel-1", "readability", "ch-1"]);
    expect(cached).toEqual(mockReadabilityResult);
  });

  it("handles API errors", async () => {
    mockReadability.mockRejectedValueOnce(new Error("Readability analysis failed"));

    const { result } = renderHook(() => useReadabilityAnalysis("novel-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate(mockRequest);

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error?.message).toBe("Readability analysis failed");
  });
});
