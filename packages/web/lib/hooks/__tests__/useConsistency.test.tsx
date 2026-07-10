/**
 * useConsistency hook tests — TanStack Query mutation hooks for CONS-001.
 *
 * Tests useConsistencyCheck and useConsistencyCheckChapter mutation hooks:
 * 1. useConsistencyCheck calls analysisApi.consistencyCheck on mutate
 * 2. useConsistencyCheck returns data on success
 * 3. useConsistencyCheck handles API errors
 * 4. useConsistencyCheckChapter calls analysisApi.consistencyCheckChapter on mutate
 * 5. useConsistencyCheckChapter returns data on success
 * 6. useConsistencyCheckChapter handles API errors
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Mock the API client module
vi.mock("@/lib/api/analysis", () => ({
  analysisApi: {
    consistencyCheck: vi.fn(),
    consistencyCheckChapter: vi.fn(),
  },
}));

import {
  analysisApi,
  type ConsistencyCheckType,
  type ConsistencyResponse,
} from "@/lib/api/analysis";
import { useConsistencyCheck, useConsistencyCheckChapter } from "@/lib/hooks/useConsistency";

const mockConsistencyCheck = vi.mocked(analysisApi.consistencyCheck);
const mockConsistencyCheckChapter = vi.mocked(analysisApi.consistencyCheckChapter);

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockConsistencyResponse: ConsistencyResponse = {
  novel_id: "novel-1",
  chapter_ids: ["ch-1", "ch-2"],
  check_types: ["character", "timeline"],
  issues: [
    {
      check_type: "character",
      severity: "error",
      description: "Character name mismatch",
      locations: ["Chapter 1", "Chapter 2"],
      conflicting_facts: ["Anna is 25", "Anna is 30"],
      suggestion: "Unify character age across chapters",
      confidence: 0.92,
    },
  ],
  error_count: 1,
  warning_count: 0,
  info_count: 0,
  total_issues: 1,
  overall_assessment: "Minor consistency issues found.",
  analyzed_at: "2026-06-01T10:00:00Z",
};

const mockRequest = {
  chapter_ids: ["ch-1", "ch-2"],
  check_types: ["character", "timeline"] as ConsistencyCheckType[],
  include_kb: true,
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
// Tests: useConsistencyCheck
// ---------------------------------------------------------------------------

describe("useConsistencyCheck", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("calls analysisApi.consistencyCheck on mutate", async () => {
    mockConsistencyCheck.mockResolvedValueOnce(mockConsistencyResponse);

    const { result } = renderHook(() => useConsistencyCheck("novel-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate(mockRequest);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockConsistencyCheck).toHaveBeenCalledWith("novel-1", mockRequest);
    expect(result.current.data).toEqual(mockConsistencyResponse);
  });

  it("returns data on success", async () => {
    mockConsistencyCheck.mockResolvedValueOnce(mockConsistencyResponse);

    const { result } = renderHook(() => useConsistencyCheck("novel-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate(mockRequest);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data?.total_issues).toBe(1);
    expect(result.current.data?.issues[0].severity).toBe("error");
  });

  it("handles API errors", async () => {
    mockConsistencyCheck.mockRejectedValueOnce(new Error("Consistency check failed"));

    const { result } = renderHook(() => useConsistencyCheck("novel-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate(mockRequest);

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error?.message).toBe("Consistency check failed");
  });
});

// ---------------------------------------------------------------------------
// Tests: useConsistencyCheckChapter
// ---------------------------------------------------------------------------

describe("useConsistencyCheckChapter", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("calls analysisApi.consistencyCheckChapter on mutate", async () => {
    mockConsistencyCheckChapter.mockResolvedValueOnce(mockConsistencyResponse);

    const { result } = renderHook(() => useConsistencyCheckChapter("novel-1", "ch-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate(mockRequest);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockConsistencyCheckChapter).toHaveBeenCalledWith("novel-1", "ch-1", mockRequest);
  });

  it("returns data on success", async () => {
    mockConsistencyCheckChapter.mockResolvedValueOnce(mockConsistencyResponse);

    const { result } = renderHook(() => useConsistencyCheckChapter("novel-1", "ch-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate(mockRequest);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data?.overall_assessment).toBe("Minor consistency issues found.");
  });

  it("handles API errors", async () => {
    mockConsistencyCheckChapter.mockRejectedValueOnce(new Error("Chapter check failed"));

    const { result } = renderHook(() => useConsistencyCheckChapter("novel-1", "ch-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate(mockRequest);

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error?.message).toBe("Chapter check failed");
  });
});
