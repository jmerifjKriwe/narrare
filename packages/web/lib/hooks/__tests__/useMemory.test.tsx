/**
 * useMemory hook tests — TanStack Query hooks for memory/feedback/learning.
 *
 * Tests:
 * 1. usePreferences fetches preference profile
 * 2. usePreferences is disabled when projectId is null
 * 3. useRecordFeedback records feedback and invalidates cache
 * 4. useResetPreferences resets preferences and invalidates cache
 * 5. useTriggerAnalysis triggers analysis and invalidates cache
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Mock the API client module
vi.mock("@/lib/api/memory", () => ({
  memoryApi: {
    recordFeedback: vi.fn(),
    getPreferences: vi.fn(),
    resetPreferences: vi.fn(),
    triggerAnalysis: vi.fn(),
  },
}));

import { memoryApi } from "@/lib/api/memory";
import {
  usePreferences,
  useRecordFeedback,
  useResetPreferences,
  useTriggerAnalysis,
} from "@/lib/hooks/useMemory";

// ---------------------------------------------------------------------------
// Mock helpers
// ---------------------------------------------------------------------------

const mockRecordFeedback = memoryApi.recordFeedback as ReturnType<typeof vi.fn>;
const mockGetPreferences = memoryApi.getPreferences as ReturnType<typeof vi.fn>;
const mockResetPreferences = memoryApi.resetPreferences as ReturnType<typeof vi.fn>;
const mockTriggerAnalysis = memoryApi.triggerAnalysis as ReturnType<typeof vi.fn>;

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockProfile = {
  user_id: "user-1",
  project_id: "proj-1",
  event_count: 42,
  confidence: 0.85,
  style: { tone: "dramatic" },
  content: { genre: "fantasy" },
  constraints: [],
  last_updated: "2026-05-27T00:00:00Z",
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

describe("usePreferences", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("fetches preference profile for a project", async () => {
    mockGetPreferences.mockResolvedValueOnce(mockProfile);

    const { result } = renderHook(() => usePreferences("proj-1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockGetPreferences).toHaveBeenCalledWith("proj-1");
    expect(result.current.data?.event_count).toBe(42);
    expect(result.current.data?.confidence).toBe(0.85);
  });

  it("is disabled when projectId is null", () => {
    const { result } = renderHook(() => usePreferences(null), {
      wrapper: createWrapper(),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(mockGetPreferences).not.toHaveBeenCalled();
  });
});

describe("useRecordFeedback", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("calls memoryApi.recordFeedback with data", async () => {
    mockRecordFeedback.mockResolvedValueOnce({ id: "fb-1", action: "accept", created_at: "" });

    const { result } = renderHook(() => useRecordFeedback("proj-1"), {
      wrapper: createWrapper(),
    });

    const feedbackData = {
      action: "accept" as const,
      suggestion_id: "sug-1",
      intent: "generation",
      suggestion_text: "test",
      project_id: "proj-1",
    };

    result.current.mutate(feedbackData);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockRecordFeedback).toHaveBeenCalledWith(feedbackData, expect.anything());
  });

  it("invalidates memory cache on success", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
    });
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    mockRecordFeedback.mockResolvedValueOnce({ id: "fb-1", action: "accept", created_at: "" });

    const { result } = renderHook(() => useRecordFeedback("proj-1"), {
      wrapper: createWrapperWithClient(queryClient),
    });

    result.current.mutate({
      action: "accept",
      suggestion_id: "sug-1",
      intent: "generation",
      suggestion_text: "test",
      project_id: "proj-1",
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["memory", "proj-1"] });
  });
});

describe("useResetPreferences", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("calls memoryApi.resetPreferences for project", async () => {
    mockResetPreferences.mockResolvedValueOnce({ message: "Reset OK", deleted_count: 42 });

    const { result } = renderHook(() => useResetPreferences("proj-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate();

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockResetPreferences).toHaveBeenCalledWith("proj-1");
  });

  it("invalidates memory cache on success", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
    });
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    mockResetPreferences.mockResolvedValueOnce({ message: "Reset OK", deleted_count: 42 });

    const { result } = renderHook(() => useResetPreferences("proj-1"), {
      wrapper: createWrapperWithClient(queryClient),
    });

    result.current.mutate();

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["memory", "proj-1"] });
  });
});

describe("useTriggerAnalysis", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("calls memoryApi.triggerAnalysis with project_id", async () => {
    mockTriggerAnalysis.mockResolvedValueOnce({
      id: "a-1",
      user_id: "u-1",
      project_id: "proj-1",
      confidence: 0.9,
      summary: "Test",
      style_patterns: [],
      content_patterns: [],
      avoidance_patterns: [],
      event_count_at_analysis: 42,
      created_at: "",
      updated_at: "",
    });

    const { result } = renderHook(() => useTriggerAnalysis("proj-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate();

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockTriggerAnalysis).toHaveBeenCalledWith({ project_id: "proj-1" });
  });

  it("handles API errors", async () => {
    mockTriggerAnalysis.mockRejectedValueOnce(new Error("Analysis failed"));

    const { result } = renderHook(() => useTriggerAnalysis("proj-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate();

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error?.message).toBe("Analysis failed");
  });
});
