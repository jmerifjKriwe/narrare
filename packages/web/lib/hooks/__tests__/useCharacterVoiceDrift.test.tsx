/**
 * useCharacterVoiceDrift hook tests — SSE streaming for ANAL-009 voice drift.
 *
 * Mirrors the useCharacterVoice execution-test style: the real useAIOperation
 * lifecycle runs, and only the SSE transport boundary
 * (`@/lib/api/voice-drift-stream`) is mocked. Each test drives the captured
 * stream handlers (onProgress / onResult / onNoProfile / onComplete / onError)
 * and observes the resulting lifecycle state — verifying the SSE → state
 * bridging that is unique to this hook (multi-character accumulation of BOTH
 * analysable results AND graceful no-profile skips, progress liveness + the
 * progress message, and cancel flowing through useAIOperation's signal with NO
 * manual AbortController).
 *
 * Voice-drift is novel-scoped (like character-voice profiling), so `run(novelId)`
 * takes a novel id and the stream client is called WITH a request body.
 *
 * @module useCharacterVoiceDrift.test
 */

import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Hoisted mock: streamVoiceDrift captures the handlers + signal passed by the
// hook so each test can drive the SSE event stream deterministically.
const handle = vi.hoisted(() => ({ stream: vi.fn() }));

vi.mock("@/lib/api/voice-drift-stream", () => ({
  streamVoiceDrift: handle.stream,
}));

import type {
  VoiceDriftCharacterResult,
  VoiceDriftNoProfile,
  VoiceDriftRequest,
} from "@/lib/api/voice-drift-stream";
import { useCharacterVoiceDrift } from "@/lib/hooks/useCharacterVoiceDrift";

// ---------------------------------------------------------------------------
// Types for the captured streamVoiceDrift call signature.
// ---------------------------------------------------------------------------

interface StreamHandlers {
  onProgress?: (message: string) => void;
  onResult: (result: VoiceDriftCharacterResult) => void;
  onNoProfile?: (noProfile: VoiceDriftNoProfile) => void;
  onComplete: () => void;
  onError?: (error: Error) => void;
}

type StreamCall = [string, VoiceDriftRequest, StreamHandlers, AbortSignal];

function lastCall(): StreamCall {
  expect(handle.stream.mock.calls.length).toBeGreaterThan(0);
  return handle.stream.mock.calls.at(-1) as StreamCall;
}

function handlersOf(): StreamHandlers {
  return lastCall()[2];
}

// ---------------------------------------------------------------------------
// Fixtures — one analysable result + one graceful no-profile skip.
// ---------------------------------------------------------------------------

const resultElena: VoiceDriftCharacterResult = {
  character_id: "kb-elena",
  character_name: "Elena",
  trend: [
    { chapter_id: "ch-1", match_subscore: 96, per_metric_deltas: {}, band: "stable" },
    {
      chapter_id: "ch-2",
      match_subscore: 78,
      per_metric_deltas: { formality: 0.2 },
      band: "minor",
    },
  ],
  jumps: [
    {
      from_chapter_id: "ch-1",
      to_chapter_id: "ch-2",
      jumped_metrics: ["formality"],
      magnitude: 0.2,
    },
  ],
  overall_match_score: 87,
  overall_band: "minor",
  drift: {
    drift_type: "context",
    confidence: 0.8,
    longitudinal_reasons: ["Scene-dependent variation."],
    per_chapter_notes: [{ chapter_id: "ch-2", note: "Faster pacing." }],
    suggested_attention: [],
  },
};

const noProfileMarek: VoiceDriftNoProfile = {
  character_id: "",
  character_name: "Marek",
  reason: "no_stored_profile",
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useCharacterVoiceDrift", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    handle.stream.mockClear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("run stages novelId + body and calls the stream client", async () => {
    const { result } = renderHook(() => useCharacterVoiceDrift());

    await act(async () => {
      result.current.run("novel-42", { chapter_ids: ["ch-a", "ch-b"] });
    });

    expect(handle.stream).toHaveBeenCalledOnce();
    const [novelId, body, , signal] = lastCall();
    expect(novelId).toBe("novel-42");
    expect(body.chapter_ids).toEqual(["ch-a", "ch-b"]);
    expect(signal).toBeInstanceOf(AbortSignal);
    expect(result.current.isLoading).toBe(true);
    expect(result.current.isIdle).toBe(false);
  });

  it("run with no body analyses all characters/chapters (empty body)", async () => {
    const { result } = renderHook(() => useCharacterVoiceDrift());

    await act(async () => {
      result.current.run("novel-42");
    });

    expect(lastCall()[1]).toEqual({});
  });

  it("accumulates results AND no-profile skips through SSE events and completes", async () => {
    const { result } = renderHook(() => useCharacterVoiceDrift());

    await act(async () => {
      result.current.run("novel-1", { chapter_ids: ["ch-1"] });
    });

    const handlers = handlersOf();
    await act(async () => {
      handlers.onResult(resultElena);
      handlers.onNoProfile?.(noProfileMarek);
      handlers.onComplete();
    });

    expect(result.current.isComplete).toBe(true);
    expect(result.current.results).toEqual([resultElena]);
    expect(result.current.results).toHaveLength(1);
    expect(result.current.noProfile).toEqual([noProfileMarek]);
    expect(result.current.noProfile).toHaveLength(1);
  });

  it("progress events keep the stream alive and surface the latest progress message", async () => {
    const { result } = renderHook(() => useCharacterVoiceDrift());

    await act(async () => {
      result.current.run("novel-1");
    });

    const handlers = handlersOf();

    expect(result.current.progress).toBeNull();

    await act(async () => {
      handlers.onProgress?.("Profiling 2 characters");
    });
    expect(result.current.isStreaming).toBe(true);
    expect(result.current.progress).toBe("Profiling 2 characters");

    await act(async () => {
      handlers.onResult(resultElena);
      handlers.onComplete();
    });

    expect(result.current.isComplete).toBe(true);
    expect(result.current.results).toHaveLength(1);
  });

  it("surfaces a terminal error event in the error state", async () => {
    const { result } = renderHook(() => useCharacterVoiceDrift());

    await act(async () => {
      result.current.run("novel-1");
    });

    await act(async () => {
      handlersOf().onError?.(new Error("Voice-drift analysis failed."));
    });

    expect(result.current.isError).toBe(true);
    expect(result.current.error).not.toBeNull();
    expect(result.current.results).toBeNull();
    expect(result.current.noProfile).toBeNull();
  });

  it("does not overwrite error state when onComplete fires after onError", async () => {
    const { result } = renderHook(() => useCharacterVoiceDrift());

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
    const { result } = renderHook(() => useCharacterVoiceDrift());

    await act(async () => {
      result.current.run("novel-1");
    });

    const handlers = handlersOf();
    await act(async () => {
      handlers.onResult(resultElena);
      handlers.onComplete();
      handlers.onError?.(new Error("late error"));
    });

    expect(result.current.isComplete).toBe(true);
    expect(result.current.isError).toBe(false);
    expect(result.current.results).toHaveLength(1);
  });

  it("cancel flows through useAIOperation (no manual AbortController) → idle + aborted signal", async () => {
    const { result } = renderHook(() => useCharacterVoiceDrift());

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

  it("reset clears results, no-profile, and progress and returns to idle", async () => {
    const { result } = renderHook(() => useCharacterVoiceDrift());

    await act(async () => {
      result.current.run("novel-1");
    });
    const handlers = handlersOf();
    await act(async () => {
      handlers.onProgress?.("working");
      handlers.onResult(resultElena);
      handlers.onNoProfile?.(noProfileMarek);
      handlers.onComplete();
    });
    expect(result.current.results).toHaveLength(1);
    expect(result.current.noProfile).toHaveLength(1);

    act(() => {
      result.current.reset();
    });

    expect(result.current.isIdle).toBe(true);
    expect(result.current.results).toBeNull();
    expect(result.current.noProfile).toBeNull();
    expect(result.current.error).toBeNull();
    expect(result.current.progress).toBeNull();
  });
});
