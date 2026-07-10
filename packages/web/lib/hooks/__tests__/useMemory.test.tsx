/**
 * useMemory hook tests — TanStack Query hooks for memory/feedback/learning.
 *
 * Covers: usePreferences, useMemoryStatus (derived fields + hasProfile),
 * useRecordFeedback, useResetPreferences, useTriggerAnalysis.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/memory", () => ({
  memoryApi: {
    getPreferences: vi.fn(),
    recordFeedback: vi.fn(),
    resetPreferences: vi.fn(),
    triggerAnalysis: vi.fn(),
  },
}));

import { memoryApi } from "@/lib/api/memory";
import {
  useMemoryStatus,
  usePreferences,
  useRecordFeedback,
  useResetPreferences,
  useTriggerAnalysis,
} from "@/lib/hooks/useMemory";

const getPreferences = vi.mocked(memoryApi.getPreferences);
const recordFeedback = vi.mocked(memoryApi.recordFeedback);
const resetPreferences = vi.mocked(memoryApi.resetPreferences);
const triggerAnalysis = vi.mocked(memoryApi.triggerAnalysis);

function profileFixture(overrides: Record<string, unknown> = {}) {
  return { event_count: 5, confidence: 0.8, ...overrides } as never;
}

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

beforeEach(() => vi.clearAllMocks());
afterEach(() => cleanup());

describe("usePreferences", () => {
  it("fetches the preference profile for a project", async () => {
    getPreferences.mockResolvedValueOnce(profileFixture());

    const { result } = renderHook(() => usePreferences("proj-1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(getPreferences).toHaveBeenCalledWith("proj-1");
  });

  it("is disabled when projectId is null", () => {
    const { result } = renderHook(() => usePreferences(null), { wrapper: createWrapper() });

    expect(result.current.fetchStatus).toBe("idle");
    expect(getPreferences).not.toHaveBeenCalled();
  });
});

describe("useMemoryStatus", () => {
  it("derives eventCount, confidence, and hasProfile from the profile", async () => {
    getPreferences.mockResolvedValueOnce(profileFixture({ event_count: 12, confidence: 0.9 }));

    const { result } = renderHook(() => useMemoryStatus("proj-1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.hasProfile).toBe(true));

    expect(result.current.eventCount).toBe(12);
    expect(result.current.confidence).toBe(0.9);
  });

  it("reports no profile when event_count is 0", async () => {
    getPreferences.mockResolvedValueOnce(profileFixture({ event_count: 0, confidence: 0 }));

    const { result } = renderHook(() => useMemoryStatus("proj-1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.eventCount).toBe(0);
    expect(result.current.confidence).toBe(0);
    expect(result.current.hasProfile).toBe(false);
  });

  it("defaults eventCount/confidence to 0 when data is absent", () => {
    const { result } = renderHook(() => useMemoryStatus(null), { wrapper: createWrapper() });

    expect(result.current.eventCount).toBe(0);
    expect(result.current.confidence).toBe(0);
    expect(result.current.hasProfile).toBe(false);
  });
});

describe("useRecordFeedback", () => {
  it("records feedback and invalidates the memory cache", async () => {
    recordFeedback.mockResolvedValueOnce({} as never);
    const invalidateSpy = vi.spyOn(QueryClient.prototype, "invalidateQueries");

    const { result } = renderHook(() => useRecordFeedback("proj-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate({ project_id: "proj-1" } as never);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(recordFeedback).toHaveBeenCalled();
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["memory", "proj-1"] });
    invalidateSpy.mockRestore();
  });
});

describe("useResetPreferences", () => {
  it("resets preferences and invalidates the memory cache", async () => {
    resetPreferences.mockResolvedValueOnce({} as never);
    const invalidateSpy = vi.spyOn(QueryClient.prototype, "invalidateQueries");

    const { result } = renderHook(() => useResetPreferences("proj-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate();

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(resetPreferences).toHaveBeenCalledWith("proj-1");
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["memory", "proj-1"] });
    invalidateSpy.mockRestore();
  });
});

describe("useTriggerAnalysis", () => {
  it("triggers analysis and invalidates the memory cache", async () => {
    triggerAnalysis.mockResolvedValueOnce({} as never);
    const invalidateSpy = vi.spyOn(QueryClient.prototype, "invalidateQueries");

    const { result } = renderHook(() => useTriggerAnalysis("proj-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate();

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(triggerAnalysis).toHaveBeenCalledWith({ project_id: "proj-1" });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["memory", "proj-1"] });
    invalidateSpy.mockRestore();
  });
});
