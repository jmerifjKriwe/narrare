/**
 * useTimeline hook tests — TanStack Query hooks for Timeline events & analysis.
 *
 * Tests:
 * 1. useTimelineEvents fetches events (enabled by novelId)
 * 2. useTimelineEvents passes filters through to the API
 * 3. useTimelineEvents is disabled when novelId is empty
 * 4. useTimelineEvent fetches a single event
 * 5. useTimelineAnalysis fetches analysis
 * 6. useCreateTimelineEvent calls API and invalidates events list
 * 7. useUpdateTimelineEvent calls API and invalidates events + single event
 * 8. useDeleteTimelineEvent calls API and invalidates events list
 * 9. mutation hooks propagate API errors
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/timeline", () => ({
  timelineApi: {
    listEvents: vi.fn(),
    createEvent: vi.fn(),
    getEvent: vi.fn(),
    updateEvent: vi.fn(),
    deleteEvent: vi.fn(),
    getAnalysis: vi.fn(),
  },
}));

import { timelineApi } from "@/lib/api/timeline";
import {
  useCreateTimelineEvent,
  useDeleteTimelineEvent,
  useTimelineAnalysis,
  useTimelineEvent,
  useTimelineEvents,
  useUpdateTimelineEvent,
} from "@/lib/hooks/useTimeline";
import type { TimelineAnalysis, TimelineEvent } from "@/types/timeline";

const listEvents = vi.mocked(timelineApi.listEvents);
const getEvent = vi.mocked(timelineApi.getEvent);
const getAnalysis = vi.mocked(timelineApi.getAnalysis);
const createEvent = vi.mocked(timelineApi.createEvent);
const updateEvent = vi.mocked(timelineApi.updateEvent);
const deleteEvent = vi.mocked(timelineApi.deleteEvent);

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const eventFixture: TimelineEvent = {
  id: "evt-1",
  novel_id: "novel-1",
  event_name: "The Council",
  description: "The council convenes.",
  event_type: "plot_point",
  timestamp_raw: "Year 3, Spring",
  timestamp_normalized: "0003-03",
  temporal_order: 1,
  chapter_id: "ch-1",
  character_refs: [{ id: "char-1", name: "Anna" }],
  location_ref: { id: "loc-1", name: "Hall" },
  causes: "",
  consequences: "",
  source: "manual",
  confidence: null,
  is_confirmed: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const analysisFixture: TimelineAnalysis = {
  timeline_events: [],
  temporal_conflicts: [],
  coverage_gaps: [],
  overall_assessment: "Looks coherent.",
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

beforeEach(() => vi.clearAllMocks());
afterEach(() => cleanup());

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------

describe("useTimelineEvents", () => {
  it("fetches events for a novel", async () => {
    listEvents.mockResolvedValueOnce([eventFixture]);

    const { result } = renderHook(() => useTimelineEvents("novel-1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(listEvents).toHaveBeenCalledWith("novel-1", undefined);
    expect(result.current.data).toHaveLength(1);
    expect(result.current.data?.[0].event_name).toBe("The Council");
  });

  it("passes filters through to the API", async () => {
    listEvents.mockResolvedValueOnce([]);

    const filters = { event_type: "battle" as const, is_confirmed: true };
    const { result } = renderHook(() => useTimelineEvents("novel-1", filters), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(listEvents).toHaveBeenCalledWith("novel-1", filters);
  });

  it("is disabled when novelId is empty", () => {
    const { result } = renderHook(() => useTimelineEvents(""), { wrapper: createWrapper() });

    expect(result.current.fetchStatus).toBe("idle");
    expect(listEvents).not.toHaveBeenCalled();
  });
});

describe("useTimelineEvent", () => {
  it("fetches a single event by id", async () => {
    getEvent.mockResolvedValueOnce(eventFixture);

    const { result } = renderHook(() => useTimelineEvent("novel-1", "evt-1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(getEvent).toHaveBeenCalledWith("novel-1", "evt-1");
    expect(result.current.data?.id).toBe("evt-1");
  });
});

describe("useTimelineAnalysis", () => {
  it("fetches analysis for a novel", async () => {
    getAnalysis.mockResolvedValueOnce(analysisFixture);

    const { result } = renderHook(() => useTimelineAnalysis("novel-1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(getAnalysis).toHaveBeenCalledWith("novel-1");
    expect(result.current.data?.overall_assessment).toBe("Looks coherent.");
  });

  it("is disabled when novelId is empty", () => {
    const { result } = renderHook(() => useTimelineAnalysis(""), {
      wrapper: createWrapper(),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(getAnalysis).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// Mutations
// ---------------------------------------------------------------------------

describe("useCreateTimelineEvent", () => {
  it("creates an event and invalidates the events list", async () => {
    createEvent.mockResolvedValueOnce(eventFixture);
    const invalidateSpy = vi.spyOn(QueryClient.prototype, "invalidateQueries");

    const { result } = renderHook(() => useCreateTimelineEvent("novel-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate({ event_name: "The Council" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(createEvent).toHaveBeenCalledWith("novel-1", { event_name: "The Council" });
    // At least one invalidation for the events list key
    expect(invalidateSpy).toHaveBeenCalled();
    invalidateSpy.mockRestore();
  });

  it("propagates API errors", async () => {
    createEvent.mockRejectedValueOnce(new Error("Create failed"));

    const { result } = renderHook(() => useCreateTimelineEvent("novel-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate({ event_name: "X" });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.message).toBe("Create failed");
  });
});

describe("useUpdateTimelineEvent", () => {
  it("updates an event and invalidates events + single event", async () => {
    updateEvent.mockResolvedValueOnce(eventFixture);
    const invalidateSpy = vi.spyOn(QueryClient.prototype, "invalidateQueries");

    const { result } = renderHook(() => useUpdateTimelineEvent("novel-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate({ eventId: "evt-1", data: { event_name: "Renamed" } });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(updateEvent).toHaveBeenCalledWith("novel-1", "evt-1", { event_name: "Renamed" });
    // onSuccess invalidates twice (events list + single event)
    expect(invalidateSpy.mock.calls.length).toBeGreaterThanOrEqual(2);
    invalidateSpy.mockRestore();
  });
});

describe("useDeleteTimelineEvent", () => {
  it("deletes an event and invalidates the events list", async () => {
    deleteEvent.mockResolvedValueOnce(undefined);
    const invalidateSpy = vi.spyOn(QueryClient.prototype, "invalidateQueries");

    const { result } = renderHook(() => useDeleteTimelineEvent("novel-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate("evt-1");

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(deleteEvent).toHaveBeenCalledWith("novel-1", "evt-1");
    expect(invalidateSpy).toHaveBeenCalled();
    invalidateSpy.mockRestore();
  });
});
