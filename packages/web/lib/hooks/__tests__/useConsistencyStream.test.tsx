/**
 * useConsistencyStream hook tests — SSE streaming for CONS-001 consistency
 * check (ADR-044 staged pipeline).
 *
 * Mirrors the useCharacterVoiceCheck execution-test style: the real
 * useAIOperation lifecycle runs, and only the SSE transport boundary
 * (`@/lib/api/consistency-stream`) is mocked. Each test drives the captured
 * stream handlers (onStage / onIssue / onComplete / onError) and observes
 * the resulting lifecycle state — verifying the SSE → state bridging that is
 * unique to this hook (stage progression, progressive issue accumulation,
 * liveness via notifyData, and cancel flowing through useAIOperation's signal
 * with NO manual AbortController).
 *
 * Consistency-check is **novel-scoped**: `run(novelId, request)` takes a novel
 * id and a request body (unlike the chapter-scoped voice-check hook).
 *
 * @module useConsistencyStream.test
 */

import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// ---------------------------------------------------------------------------
// Hoisted mock: captures the streamConsistencyCheck call arguments so each
// test can drive the SSE event stream deterministically.
// ---------------------------------------------------------------------------
const handle = vi.hoisted(() => ({ stream: vi.fn() }));

vi.mock("@/lib/api/consistency-stream", () => ({
  streamConsistencyCheck: handle.stream,
}));

import type { ConsistencyIssue } from "@/lib/api/analysis";
import type {
  ConsistencyCheckRequest,
  ConsistencyResultPayload,
} from "@/lib/api/consistency-stream";
import { useConsistencyStream } from "@/lib/hooks/useConsistencyStream";

// ---------------------------------------------------------------------------
// Types for the captured streamConsistencyCheck call signature.
//
// streamConsistencyCheck(novelId, request, handlers, signal?)
//   → handlers is arg index 2 (novel-scoped, WITH request body)
// ---------------------------------------------------------------------------

interface StreamHandlers {
  onStage?: (
    stage: string,
    status: string,
    progress: number,
    message: string,
    factsExtracted: number | null,
    issuesFound: number | null,
  ) => void;
  onIssue?: (issue: ConsistencyIssue) => void;
  onComplete?: (result: ConsistencyResultPayload) => void;
  onError?: (error: Error) => void;
}

type StreamCall = [string, ConsistencyCheckRequest, StreamHandlers, AbortSignal];

function lastCall(): StreamCall {
  expect(handle.stream.mock.calls.length).toBeGreaterThan(0);
  return handle.stream.mock.calls.at(-1) as StreamCall;
}

function handlersOf(): StreamHandlers {
  return lastCall()[2];
}

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const sampleIssue: ConsistencyIssue = {
  check_type: "character",
  severity: "warning",
  description: "Character eye color inconsistency between chapters.",
  locations: ["Chapter 3", "Chapter 5"],
  conflicting_facts: ["blue eyes", "brown eyes"],
  suggestion: "Reconcile eye color across both chapters.",
  confidence: 0.85,
};

const sampleResult: ConsistencyResultPayload = {
  novel_id: "novel-1",
  chapter_ids: ["ch-1", "ch-2"],
  check_types: ["character", "timeline"],
  issues: [sampleIssue],
  error_count: 0,
  warning_count: 1,
  info_count: 0,
  total_issues: 1,
  overall_assessment: "Minor inconsistencies found.",
  analyzed_at: "2026-06-30T12:00:00Z",
};

const sampleRequest: ConsistencyCheckRequest = {
  chapter_ids: ["ch-1", "ch-2"],
  check_types: ["character", "timeline"],
  include_kb: true,
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useConsistencyStream", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    handle.stream.mockClear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  // -----------------------------------------------------------------------
  // Smoke: run stages params and calls stream client
  // -----------------------------------------------------------------------

  it("run stages novelId + request and calls the stream client", async () => {
    const { result } = renderHook(() => useConsistencyStream());

    await act(async () => {
      result.current.run("novel-1", sampleRequest);
    });

    expect(handle.stream).toHaveBeenCalledOnce();
    const [novelId, request, , signal] = lastCall();
    expect(novelId).toBe("novel-1");
    expect(request).toEqual(sampleRequest);
    expect(signal).toBeInstanceOf(AbortSignal);
    expect(result.current.isLoading).toBe(true);
    expect(result.current.isIdle).toBe(false);
  });

  // -----------------------------------------------------------------------
  // Progressive issues accumulate through SSE events
  // -----------------------------------------------------------------------

  it("accumulates progressive issues through onIssue and completes", async () => {
    const { result } = renderHook(() => useConsistencyStream());

    await act(async () => {
      result.current.run("novel-1", sampleRequest);
    });

    const secondIssue: ConsistencyIssue = {
      check_type: "timeline",
      severity: "error",
      description: "Event order contradiction.",
      locations: ["Chapter 2", "Chapter 4"],
      conflicting_facts: ["occurred before sunrise", "occurred at noon"],
      suggestion: "Adjust the timeline reference.",
      confidence: 0.92,
    };

    const handlers = handlersOf();
    await act(async () => {
      handlers.onIssue?.(sampleIssue);
      handlers.onIssue?.(secondIssue);
      handlers.onComplete?.(sampleResult);
    });

    expect(result.current.isComplete).toBe(true);
    expect(result.current.issues).toEqual([sampleIssue, secondIssue]);
    expect(result.current.issues).toHaveLength(2);
    // Terminal result carries the full issues array from the backend.
    expect(result.current.result).toEqual(sampleResult);
    expect(result.current.result?.issues).toHaveLength(1);
  });

  // -----------------------------------------------------------------------
  // Stage events update progress and keep the stream alive
  // -----------------------------------------------------------------------

  it("stage events update progress and surface the latest snapshot", async () => {
    const { result } = renderHook(() => useConsistencyStream());

    await act(async () => {
      result.current.run("novel-1", sampleRequest);
    });

    const handlers = handlersOf();
    expect(result.current.progress).toBeNull();

    await act(async () => {
      handlers.onStage?.("extracting_facts", "start", 0, "Extracting facts...", null, null);
    });
    expect(result.current.isStreaming).toBe(true);
    expect(result.current.progress).toEqual({
      stage: "extracting_facts",
      status: "start",
      progress: 0,
      message: "Extracting facts...",
      factsExtracted: null,
      issuesFound: null,
    });

    await act(async () => {
      handlers.onStage?.("extracting_facts", "progress", 0.5, "Extracted 10 facts", 10, null);
    });
    expect(result.current.progress?.progress).toBeCloseTo(0.5);
    expect(result.current.progress?.factsExtracted).toBe(10);

    await act(async () => {
      handlers.onStage?.("checking_consistency", "progress", 0.75, "Checking timeline...", 10, 2);
    });
    expect(result.current.progress?.stage).toBe("checking_consistency");
    expect(result.current.progress?.issuesFound).toBe(2);

    await act(async () => {
      handlers.onComplete?.(sampleResult);
    });

    expect(result.current.isComplete).toBe(true);
    // Progress persists until reset (same pattern as useCharacterVoiceCheck).
  });

  // -----------------------------------------------------------------------
  // Terminal error
  // -----------------------------------------------------------------------

  it("surfaces a terminal error event in the error state", async () => {
    const { result } = renderHook(() => useConsistencyStream());

    await act(async () => {
      result.current.run("novel-1", sampleRequest);
    });

    await act(async () => {
      handlersOf().onError?.(new Error("Consistency check failed."));
    });

    expect(result.current.isError).toBe(true);
    expect(result.current.error).not.toBeNull();
    expect(result.current.result).toBeNull();
    expect(result.current.issues).toHaveLength(0);
  });

  // -----------------------------------------------------------------------
  // Cancel flows through useAIOperation (no manual AbortController)
  // -----------------------------------------------------------------------

  it("cancel flows through useAIOperation → idle + aborted signal", async () => {
    const { result } = renderHook(() => useConsistencyStream());

    await act(async () => {
      result.current.run("novel-1", sampleRequest);
    });

    // The signal handed to the stream client IS useAIOperation's controller
    // signal — the hook never constructs its own AbortController (ADR-043).
    const signal = lastCall()[3];
    expect(signal.aborted).toBe(false);
    expect(result.current.isLoading).toBe(true);

    await act(async () => {
      result.current.cancel();
    });

    expect(result.current.isIdle).toBe(true);
    // Aborting this signal is what cancels the in-flight stream — proving the
    // cancel went through useAIOperation, not a hook-local controller.
    expect(signal.aborted).toBe(true);
  });

  // -----------------------------------------------------------------------
  // Reset clears everything
  // -----------------------------------------------------------------------

  it("reset clears progress, issues, and returns to idle", async () => {
    const { result } = renderHook(() => useConsistencyStream());

    await act(async () => {
      result.current.run("novel-1", sampleRequest);
    });
    const handlers = handlersOf();
    await act(async () => {
      handlers.onIssue?.(sampleIssue);
      handlers.onComplete?.(sampleResult);
    });
    expect(result.current.result).not.toBeNull();
    expect(result.current.issues).toHaveLength(1);

    act(() => {
      result.current.reset();
    });

    expect(result.current.isIdle).toBe(true);
    expect(result.current.result).toBeNull();
    expect(result.current.error).toBeNull();
    expect(result.current.progress).toBeNull();
    expect(result.current.issues).toHaveLength(0);
  });

  // -----------------------------------------------------------------------
  // Retry re-invokes the stream with the same params
  // -----------------------------------------------------------------------

  it("retry re-invokes the stream with the same novelId and request", async () => {
    const { result } = renderHook(() => useConsistencyStream());

    await act(async () => {
      result.current.run("novel-1", sampleRequest);
    });
    // Initial stream call
    expect(handle.stream).toHaveBeenCalledTimes(1);

    // Complete the first run so retry is valid
    await act(async () => {
      handlersOf().onComplete?.(sampleResult);
    });
    expect(result.current.isComplete).toBe(true);

    // Retry
    await act(async () => {
      result.current.retry();
    });
    expect(handle.stream).toHaveBeenCalledTimes(2);

    const [novelId, request] = lastCall();
    expect(novelId).toBe("novel-1");
    expect(request).toEqual(sampleRequest);
  });
});
