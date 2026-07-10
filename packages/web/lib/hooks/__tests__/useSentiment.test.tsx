/**
 * useSentiment hook tests — TanStack Query mutation hook for ANAL-002.
 *
 * Tests useSentimentAnalyze mutation hook:
 * 1. Calls analysisApi.sentiment on mutate
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
    sentiment: vi.fn(),
  },
}));

import { analysisApi, type SentimentOverview } from "@/lib/api/analysis";
import { useSentimentAnalyze } from "@/lib/hooks/useSentiment";

const mockSentiment = vi.mocked(analysisApi.sentiment);

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockSentimentOverview: SentimentOverview[] = [
  {
    sentence_count: 50,
    average_vad: { valence: 0.6, arousal: 0.3, dominance: 0.7 },
    overall_emotions: {
      anger: 0.05,
      anticipation: 0.2,
      disgust: 0.02,
      fear: 0.1,
      joy: 0.4,
      sadness: 0.08,
      surprise: 0.05,
      trust: 0.3,
      positive: 0.6,
      negative: 0.15,
    },
    narrative_arc: {
      arc_type: "rise",
      confidence: 0.78,
      segments: [{ start: 0, end: 0.5, phase: "rising" }],
      explanation: "Positive arc with increasing tension",
    },
    sentences: [
      {
        sentence: "She smiled at the memory.",
        sentence_index: 0,
        vad: { valence: 0.8, arousal: 0.3, dominance: 0.7 },
        emotions: {
          anger: 0.01,
          anticipation: 0.1,
          disgust: 0.01,
          fear: 0.01,
          joy: 0.7,
          sadness: 0.02,
          surprise: 0.05,
          trust: 0.3,
          positive: 0.8,
          negative: 0.03,
        },
        word_count: 5,
        is_dialogue: false,
        dominant_emotion: "joy",
      },
    ],
    dominant_emotions: ["joy", "trust"],
  },
];

const mockRequest = { chapter_ids: ["ch-1"], detect_arc: true };

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

describe("useSentimentAnalyze", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("calls analysisApi.sentiment on mutate", async () => {
    mockSentiment.mockResolvedValueOnce(mockSentimentOverview);

    const { result } = renderHook(() => useSentimentAnalyze("novel-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate(mockRequest);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockSentiment).toHaveBeenCalledWith("novel-1", mockRequest);
    expect(result.current.data).toEqual(mockSentimentOverview);
  });

  it("returns sentiment data on success", async () => {
    mockSentiment.mockResolvedValueOnce(mockSentimentOverview);

    const { result } = renderHook(() => useSentimentAnalyze("novel-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate(mockRequest);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toHaveLength(1);
    expect(result.current.data?.[0].dominant_emotions).toContain("joy");
    expect(result.current.data?.[0].average_vad.valence).toBe(0.6);
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
    mockSentiment.mockResolvedValueOnce(mockSentimentOverview);

    const { result } = renderHook(() => useSentimentAnalyze("novel-1"), {
      wrapper: ({ children }: { children: ReactNode }) => (
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      ),
    });

    result.current.mutate(mockRequest);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    const cached = queryClient.getQueryData(["analysis", "novel-1", "sentiment", "ch-1"]);
    expect(cached).toEqual(mockSentimentOverview);
  });

  it("handles API errors", async () => {
    mockSentiment.mockRejectedValueOnce(new Error("Sentiment analysis failed"));

    const { result } = renderHook(() => useSentimentAnalyze("novel-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate(mockRequest);

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error?.message).toBe("Sentiment analysis failed");
  });
});
