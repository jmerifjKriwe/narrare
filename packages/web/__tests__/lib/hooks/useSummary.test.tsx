/**
 * Unit tests for useSummarizeChapter hook.
 *
 * Verifies that the mutation calls the API and invalidates
 * the chapter query cache on success.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Mock the summary API client module
vi.mock("@/lib/api/summary", () => ({
  summaryApi: {
    summarizeChapter: vi.fn(),
  },
}));

import { summaryApi } from "@/lib/api/summary";
import { useSummarizeChapter } from "@/lib/hooks/useSummary";

const mockSummarizeChapter = summaryApi.summarizeChapter as ReturnType<typeof vi.fn>;

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

describe("useSummarizeChapter", () => {
  const chapterId = "chapter-123";
  const novelId = "novel-456";

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("calls summaryApi.summarizeChapter with correct arguments", async () => {
    const mockResponse = {
      summary: "A test summary.",
      word_count: 4,
      key_points: ["Key point"],
    };
    mockSummarizeChapter.mockResolvedValueOnce(mockResponse);

    const { result } = renderHook(() => useSummarizeChapter(chapterId, novelId), {
      wrapper: createWrapper(),
    });

    // Trigger the mutation
    result.current.mutate({ max_sentences: 3, language: "fr" });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockSummarizeChapter).toHaveBeenCalledWith(chapterId, novelId, {
      max_sentences: 3,
      language: "fr",
    });
    expect(result.current.data).toEqual(mockResponse);
  });

  it("calls the API with default options when none provided", async () => {
    mockSummarizeChapter.mockResolvedValueOnce({
      summary: "Default summary.",
      word_count: 2,
      key_points: [],
    });

    const { result } = renderHook(() => useSummarizeChapter(chapterId, novelId), {
      wrapper: createWrapper(),
    });

    result.current.mutate(undefined);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockSummarizeChapter).toHaveBeenCalledWith(chapterId, novelId, undefined);
  });

  it("invalidates chapter queries on success", async () => {
    mockSummarizeChapter.mockResolvedValueOnce({
      summary: "S.",
      word_count: 1,
      key_points: [],
    });

    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });
    // Spy on invalidateQueries
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useSummarizeChapter(chapterId, novelId), {
      wrapper: ({ children }: { children: ReactNode }) => (
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      ),
    });

    result.current.mutate(undefined);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    // Should have invalidated the chapter query for this chapter
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: ["chapters", chapterId],
    });
  });

  it("handles API errors gracefully", async () => {
    const errorMessage = "Failed to summarize";
    mockSummarizeChapter.mockRejectedValueOnce(new Error(errorMessage));

    const { result } = renderHook(() => useSummarizeChapter(chapterId, novelId), {
      wrapper: createWrapper(),
    });

    result.current.mutate(undefined);

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error).toBeDefined();
    expect(result.current.error!.message).toBe(errorMessage);
  });
});
