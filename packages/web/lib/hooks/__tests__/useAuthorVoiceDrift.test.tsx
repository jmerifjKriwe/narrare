/**
 * useAuthorVoiceDrift hook tests — SSE streaming for ANAL-009 Phase 2B author
 * voice drift.
 *
 * Mirrors the useCharacterVoiceDrift execution-test style: the real
 * useAIOperation lifecycle runs, and only the SSE transport boundary
 * (`@/lib/api/author-voice-drift-stream`) is mocked. Each test drives the
 * captured stream handlers (onProgress / onResult / onNoProfile / onComplete /
 * onError) and observes the resulting lifecycle state.
 *
 * Author voice is ONE narrator per novel, so the hook captures a SINGLE result
 * (not a per-character array) OR a SINGLE graceful no-profile skip — never both
 * (distinct from Phase 1's accumulator). Verifies progress liveness, the
 * singular result/no-profile bridging, and cancel flowing through
 * useAIOperation's signal with NO manual AbortController (ADR-043).
 *
 * @module useAuthorVoiceDrift.test
 */

import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Hoisted mock: streamAuthorVoiceDrift captures the handlers + signal passed by
// the hook so each test can drive the SSE event stream deterministically.
const handle = vi.hoisted(() => ({ stream: vi.fn() }));

vi.mock("@/lib/api/author-voice-drift-stream", () => ({
  streamAuthorVoiceDrift: handle.stream,
}));

import type {
  AuthorVoiceDriftNoProfile,
  AuthorVoiceDriftRequest,
  AuthorVoiceDriftResult,
} from "@/lib/api/author-voice-drift-stream";
import { useAuthorVoiceDrift } from "@/lib/hooks/useAuthorVoiceDrift";

// ---------------------------------------------------------------------------
// Types for the captured streamAuthorVoiceDrift call signature.
// ---------------------------------------------------------------------------

interface StreamHandlers {
  onProgress?: (message: string) => void;
  onResult: (result: AuthorVoiceDriftResult) => void;
  onNoProfile?: (noProfile: AuthorVoiceDriftNoProfile) => void;
  onComplete: () => void;
  onError?: (error: Error) => void;
}

type StreamCall = [string, AuthorVoiceDriftRequest, StreamHandlers, AbortSignal];

function lastCall(): StreamCall {
  expect(handle.stream.mock.calls.length).toBeGreaterThan(0);
  return handle.stream.mock.calls.at(-1) as StreamCall;
}

function handlersOf(): StreamHandlers {
  return lastCall()[2];
}

// ---------------------------------------------------------------------------
// Fixtures — one narrator result + one graceful no-profile skip.
// ---------------------------------------------------------------------------

const narratorResult: AuthorVoiceDriftResult = {
  novel_id: "novel-1",
  trend: [
    { chapter_id: "ch-1", match_subscore: 94, per_metric_deltas: {}, band: "stable" },
    {
      chapter_id: "ch-2",
      match_subscore: 71,
      per_metric_deltas: { dialogue_ratio: 0.18 },
      band: "minor",
    },
  ],
  jumps: [
    {
      from_chapter_id: "ch-1",
      to_chapter_id: "ch-2",
      jumped_metrics: ["dialogue_ratio"],
      magnitude: 0.18,
    },
  ],
  overall_match_score: 82,
  overall_band: "minor",
  drift: {
    drift_type: "evolution",
    confidence: 0.72,
    longitudinal_reasons: ["The narrative voice grows more conversational."],
    per_chapter_notes: [{ chapter_id: "ch-2", note: "Shorter sentences." }],
    suggested_attention: ["ch-2"],
  },
};

const noProfile: AuthorVoiceDriftNoProfile = {
  reason: "no_stored_profile",
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useAuthorVoiceDrift", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    handle.stream.mockClear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("run stages novelId + body and calls the stream client", async () => {
    const { result } = renderHook(() => useAuthorVoiceDrift());

    await act(async () => {
      result.current.run("novel-42", ["ch-a", "ch-b"]);
    });

    expect(handle.stream).toHaveBeenCalledOnce();
    const [novelId, body, , signal] = lastCall();
    expect(novelId).toBe("novel-42");
    expect(body.chapter_ids).toEqual(["ch-a", "ch-b"]);
    expect(signal).toBeInstanceOf(AbortSignal);
    expect(result.current.isLoading).toBe(true);
    expect(result.current.isIdle).toBe(false);
  });

  it("run with no chapters analyses every chapter (null body)", async () => {
    const { result } = renderHook(() => useAuthorVoiceDrift());

    await act(async () => {
      result.current.run("novel-42");
    });

    expect(lastCall()[1].chapter_ids).toBeNull();
  });

  it("captures the single narrator result through the result event and completes", async () => {
    const { result } = renderHook(() => useAuthorVoiceDrift());

    await act(async () => {
      result.current.run("novel-1", ["ch-1"]);
    });

    const handlers = handlersOf();
    await act(async () => {
      handlers.onResult(narratorResult);
      handlers.onComplete();
    });

    expect(result.current.isComplete).toBe(true);
    expect(result.current.result).toEqual(narratorResult);
    expect(result.current.noProfile).toBeNull();
  });

  it("captures the graceful no-profile skip when no result is analysable", async () => {
    const { result } = renderHook(() => useAuthorVoiceDrift());

    await act(async () => {
      result.current.run("novel-1");
    });

    const handlers = handlersOf();
    await act(async () => {
      handlers.onNoProfile?.(noProfile);
      handlers.onComplete();
    });

    expect(result.current.isComplete).toBe(true);
    expect(result.current.noProfile).toEqual(noProfile);
    expect(result.current.result).toBeNull();
  });

  it("progress events keep the stream alive and surface the latest progress message", async () => {
    const { result } = renderHook(() => useAuthorVoiceDrift());

    await act(async () => {
      result.current.run("novel-1");
    });

    const handlers = handlersOf();

    expect(result.current.progress).toBeNull();

    await act(async () => {
      handlers.onProgress?.("Measuring 4 chapters");
    });
    expect(result.current.isStreaming).toBe(true);
    expect(result.current.progress).toBe("Measuring 4 chapters");

    await act(async () => {
      handlers.onResult(narratorResult);
      handlers.onComplete();
    });

    expect(result.current.isComplete).toBe(true);
    expect(result.current.result).not.toBeNull();
  });

  it("surfaces a terminal error event in the error state", async () => {
    const { result } = renderHook(() => useAuthorVoiceDrift());

    await act(async () => {
      result.current.run("novel-1");
    });

    await act(async () => {
      handlersOf().onError?.(new Error("Author-voice-drift analysis failed."));
    });

    expect(result.current.isError).toBe(true);
    expect(result.current.error).not.toBeNull();
    expect(result.current.result).toBeNull();
    expect(result.current.noProfile).toBeNull();
  });

  it("does not overwrite error state when onComplete fires after onError", async () => {
    const { result } = renderHook(() => useAuthorVoiceDrift());

    await act(async () => {
      result.current.run("novel-1");
    });

    const handlers = handlersOf();
    await act(async () => {
      handlers.onError?.(new Error("stream error"));
      handlers.onComplete();
    });

    expect(result.current.isError).toBe(true);
    expect(result.current.isComplete).toBe(false);
  });

  it("does not overwrite complete state when onError fires after onComplete", async () => {
    const { result } = renderHook(() => useAuthorVoiceDrift());

    await act(async () => {
      result.current.run("novel-1");
    });

    const handlers = handlersOf();
    await act(async () => {
      handlers.onResult(narratorResult);
      handlers.onComplete();
      handlers.onError?.(new Error("late error"));
    });

    expect(result.current.isComplete).toBe(true);
    expect(result.current.isError).toBe(false);
    expect(result.current.result).not.toBeNull();
  });

  it("cancel flows through useAIOperation (no manual AbortController) → idle + aborted signal", async () => {
    const { result } = renderHook(() => useAuthorVoiceDrift());

    await act(async () => {
      result.current.run("novel-1");
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

  it("reset clears the result, no-profile, and progress and returns to idle", async () => {
    const { result } = renderHook(() => useAuthorVoiceDrift());

    await act(async () => {
      result.current.run("novel-1");
    });
    const handlers = handlersOf();
    await act(async () => {
      handlers.onProgress?.("working");
      handlers.onResult(narratorResult);
      handlers.onComplete();
    });
    expect(result.current.result).not.toBeNull();

    act(() => {
      result.current.reset();
    });

    expect(result.current.isIdle).toBe(true);
    expect(result.current.result).toBeNull();
    expect(result.current.noProfile).toBeNull();
    expect(result.current.error).toBeNull();
    expect(result.current.progress).toBeNull();
  });
});
