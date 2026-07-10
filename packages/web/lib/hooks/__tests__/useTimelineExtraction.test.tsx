/**
 * useTimelineExtraction hook tests — SSE extraction + timeline queries.
 *
 * Covers:
 *  - useSSEExtraction: start (onEvent/onComplete/onError), cancel, reset
 *  - useConfirmExtractedEvent: mutation + invalidation
 *  - useTimelineConsistency: query
 *  - useCharacterAges: query
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/ai-error-mapping", () => ({
  mapSSEError: (e: Error) => ({ userMessage: e.message, technicalMessage: e.message }),
}));

vi.mock("@/lib/api/timeline", () => ({
  extractExpressionsSSE: vi.fn(() => Promise.resolve()),
  confirmExtractedEvent: vi.fn(),
  timelineApi: {
    checkConsistency: vi.fn(),
    getCharacterAges: vi.fn(),
  },
}));

import { confirmExtractedEvent, extractExpressionsSSE, timelineApi } from "@/lib/api/timeline";
import {
  useCharacterAges,
  useConfirmExtractedEvent,
  useSSEExtraction,
  useTimelineConsistency,
} from "@/lib/hooks/useTimelineExtraction";
import type { ExtractedEvent } from "@/types/timeline";

const mockedExtract = vi.mocked(extractExpressionsSSE);
const mockedConfirm = vi.mocked(confirmExtractedEvent);
const mockedCheckConsistency = vi.mocked(timelineApi.checkConsistency);
const mockedGetCharacterAges = vi.mocked(timelineApi.getCharacterAges);

const extractedEvent: ExtractedEvent = {
  id: "x1",
  expression: "in 1999",
  event_name: "The turn",
  timestamp_raw: "1999",
  chapter_reference: "Chapter 1",
  character_names: ["Anna"],
  location_name: "Hall",
  confidence: 0.9,
  context: "She arrived in 1999.",
};

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
// useSSEExtraction
// ---------------------------------------------------------------------------

describe("useSSEExtraction", () => {
  it("accumulates events via onEvent and completes via onComplete (with invalidation)", async () => {
    const invalidateSpy = vi.spyOn(QueryClient.prototype, "invalidateQueries");

    const { result } = renderHook(() => useSSEExtraction("novel-1"), {
      wrapper: createWrapper(),
    });

    act(() => {
      result.current.startExtraction(["ch-1"]);
    });

    expect(result.current.isExtracting).toBe(true);
    expect(mockedExtract).toHaveBeenCalledTimes(1);

    // Grab the callbacks passed to extractExpressionsSSE.
    const callbacks = mockedExtract.mock.calls[0][2];

    act(() => callbacks.onEvent(extractedEvent));
    expect(result.current.extractedEvents).toHaveLength(1);

    act(() => callbacks.onComplete());
    expect(result.current.isExtracting).toBe(false);
    await waitFor(() => expect(invalidateSpy).toHaveBeenCalled());
    invalidateSpy.mockRestore();
  });

  it("maps and stores the error on stream error", () => {
    const { result } = renderHook(() => useSSEExtraction("novel-1"), {
      wrapper: createWrapper(),
    });

    act(() => result.current.startExtraction(["ch-1"]));
    const callbacks = mockedExtract.mock.calls[0][2];

    act(() => callbacks.onError(new Error("stream failed")));

    expect(result.current.isExtracting).toBe(false);
    expect(result.current.extractError?.userMessage).toBe("stream failed");
  });

  it("cancelExtraction aborts and stops extracting", () => {
    const { result } = renderHook(() => useSSEExtraction("novel-1"), {
      wrapper: createWrapper(),
    });

    act(() => result.current.startExtraction(["ch-1"]));
    expect(result.current.isExtracting).toBe(true);

    act(() => result.current.cancelExtraction());
    expect(result.current.isExtracting).toBe(false);
  });

  it("reset clears accumulated events and error", () => {
    const { result } = renderHook(() => useSSEExtraction("novel-1"), {
      wrapper: createWrapper(),
    });

    act(() => result.current.startExtraction(["ch-1"]));
    const callbacks = mockedExtract.mock.calls[0][2];
    act(() => {
      callbacks.onEvent(extractedEvent);
      callbacks.onError(new Error("boom"));
    });
    expect(result.current.extractedEvents).toHaveLength(1);
    expect(result.current.extractError).not.toBeNull();

    act(() => result.current.reset());
    expect(result.current.extractedEvents).toHaveLength(0);
    expect(result.current.extractError).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// useConfirmExtractedEvent
// ---------------------------------------------------------------------------

describe("useConfirmExtractedEvent", () => {
  it("confirms an extracted event and invalidates the events list", async () => {
    const persisted = { id: "evt-1" } as never;
    mockedConfirm.mockResolvedValueOnce(persisted);
    const invalidateSpy = vi.spyOn(QueryClient.prototype, "invalidateQueries");

    const { result } = renderHook(() => useConfirmExtractedEvent("novel-1"), {
      wrapper: createWrapper(),
    });

    result.current.mutate(extractedEvent);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockedConfirm).toHaveBeenCalledWith("novel-1", extractedEvent);
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["timeline", "novel-1", "events"] });
    invalidateSpy.mockRestore();
  });
});

// ---------------------------------------------------------------------------
// useTimelineConsistency
// ---------------------------------------------------------------------------

describe("useTimelineConsistency", () => {
  it("fetches temporal consistency for a novel", async () => {
    mockedCheckConsistency.mockResolvedValueOnce({
      issues: [],
      deterministic_pass: true,
      overall_assessment: "ok",
    });

    const { result } = renderHook(() => useTimelineConsistency("novel-1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockedCheckConsistency).toHaveBeenCalledWith("novel-1");
    expect(result.current.data?.deterministic_pass).toBe(true);
  });

  it("is disabled when novelId is empty", () => {
    const { result } = renderHook(() => useTimelineConsistency(""), {
      wrapper: createWrapper(),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(mockedCheckConsistency).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// useCharacterAges
// ---------------------------------------------------------------------------

describe("useCharacterAges", () => {
  it("fetches the character age report for a novel", async () => {
    mockedGetCharacterAges.mockResolvedValueOnce({
      characters: [],
      characters_with_age: 0,
      characters_without_age: 0,
    });

    const { result } = renderHook(() => useCharacterAges("novel-1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockedGetCharacterAges).toHaveBeenCalledWith("novel-1");
    expect(result.current.data?.characters_with_age).toBe(0);
  });
});
