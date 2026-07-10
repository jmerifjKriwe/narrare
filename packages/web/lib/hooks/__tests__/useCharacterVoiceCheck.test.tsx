/**
 * useCharacterVoiceCheck hook tests — SSE streaming for WRITE-010 voice check.
 *
 * Mirrors the useCharacterVoice execution-test style: the real useAIOperation
 * lifecycle runs, and only the SSE transport boundary
 * (`@/lib/api/voice-check-stream`) is mocked. Each test drives the captured
 * stream handlers (onProgress / onResult / onComplete / onError) and observes
 * the resulting lifecycle state — verifying the SSE → state bridging that is
 * unique to this hook (multi-character accumulation, progress liveness + the
 * progress message, and cancel flowing through useAIOperation's signal with
 * NO manual AbortController).
 *
 * Voice-check is chapter-scoped (unlike the novel-scoped character-voice
 * profiling hook), so `run(chapterId)` takes a single chapter id and the stream
 * client is called with NO request body.
 *
 * @module useCharacterVoiceCheck.test
 */

import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Hoisted mock: streamVoiceCheck captures the handlers + signal passed by the
// hook so each test can drive the SSE event stream deterministically.
const handle = vi.hoisted(() => ({ stream: vi.fn() }));

vi.mock("@/lib/api/voice-check-stream", () => ({
  streamVoiceCheck: handle.stream,
}));

import type { VoiceCheckResult } from "@/lib/api/voice-check-stream";
import { useCharacterVoiceCheck } from "@/lib/hooks/useCharacterVoiceCheck";

// ---------------------------------------------------------------------------
// Types for the captured streamVoiceCheck call signature.
// ---------------------------------------------------------------------------

// The hook ALWAYS passes onResult + onComplete (its contract); onProgress /
// onError are optional on the client interface, so they stay optional here and
// are invoked with optional chaining.
interface StreamHandlers {
  onProgress?: (message: string) => void;
  onResult: (result: VoiceCheckResult) => void;
  onComplete: () => void;
  onError?: (error: Error) => void;
}

// streamVoiceCheck(chapterId, handlers, signal) — chapter-scoped, NO body.
type StreamCall = [string, StreamHandlers, AbortSignal];

function lastCall(): StreamCall {
  expect(handle.stream.mock.calls.length).toBeGreaterThan(0);
  return handle.stream.mock.calls.at(-1) as StreamCall;
}

// streamVoiceCheck(chapterId, handlers, signal) — handlers are arg index 1
// (no request body, unlike the novel-scoped character-voice client).
function handlersOf(): StreamHandlers {
  return lastCall()[1];
}

// ---------------------------------------------------------------------------
// Fixtures — two per-character results. One fully scored (green/consistent),
// one with no stored profile (graceful "no profile" signal — RULE-11).
// ---------------------------------------------------------------------------

const resultElena: VoiceCheckResult = {
  character_name: "Elena",
  match_score: 92,
  band: "green",
  match_judgment: "consistent",
  qualitative_sub_score: 90,
  metric_delta_subscore: 94,
  flagged_lines: [
    {
      quote: "\u201cYou won\u2019t forget this.\u201d",
      reason: "Slightly more formal than profile.",
    },
  ],
  has_profile: true,
  n_comparable_metrics: 6,
};

const resultMarek: VoiceCheckResult = {
  character_name: "Marek",
  match_score: null,
  band: null,
  match_judgment: null,
  qualitative_sub_score: null,
  metric_delta_subscore: null,
  flagged_lines: [],
  has_profile: false,
  n_comparable_metrics: 0,
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useCharacterVoiceCheck", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    handle.stream.mockClear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("run stages chapterId and calls the stream client (chapter-scoped, no body)", async () => {
    const { result } = renderHook(() => useCharacterVoiceCheck());

    await act(async () => {
      result.current.run("ch-1");
    });

    expect(handle.stream).toHaveBeenCalledOnce();
    const [chapterId, , signal] = lastCall();
    expect(chapterId).toBe("ch-1");
    expect(signal).toBeInstanceOf(AbortSignal);
    expect(result.current.isLoading).toBe(true);
    expect(result.current.isIdle).toBe(false);
  });

  it("accumulates per-character results through SSE events and completes", async () => {
    const { result } = renderHook(() => useCharacterVoiceCheck());

    await act(async () => {
      result.current.run("ch-1");
    });

    const handlers = handlersOf();
    await act(async () => {
      handlers.onResult(resultElena);
      handlers.onResult(resultMarek);
      handlers.onComplete();
    });

    expect(result.current.isComplete).toBe(true);
    expect(result.current.results).toEqual([resultElena, resultMarek]);
    expect(result.current.results).toHaveLength(2);
    // The graceful "no profile" character is carried through verbatim.
    expect(result.current.results?.[1].has_profile).toBe(false);
  });

  it("progress events keep the stream alive and surface the latest progress message", async () => {
    const { result } = renderHook(() => useCharacterVoiceCheck());

    await act(async () => {
      result.current.run("ch-1");
    });

    const handlers = handlersOf();

    expect(result.current.progress).toBeNull();

    await act(async () => {
      handlers.onProgress?.("Found 2 speaking characters");
    });
    expect(result.current.isStreaming).toBe(true);
    expect(result.current.progress).toBe("Found 2 speaking characters");

    await act(async () => {
      handlers.onResult(resultElena);
      handlers.onComplete();
    });

    expect(result.current.isComplete).toBe(true);
    expect(result.current.results).toHaveLength(1);
  });

  it("surfaces a terminal error event in the error state", async () => {
    const { result } = renderHook(() => useCharacterVoiceCheck());

    await act(async () => {
      result.current.run("ch-1");
    });

    await act(async () => {
      handlersOf().onError?.(new Error("Voice-check analysis failed."));
    });

    expect(result.current.isError).toBe(true);
    expect(result.current.error).not.toBeNull();
    expect(result.current.results).toBeNull();
  });

  it("does not overwrite error state when onComplete fires after onError", async () => {
    const { result } = renderHook(() => useCharacterVoiceCheck());

    await act(async () => {
      result.current.run("ch-1");
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
    const { result } = renderHook(() => useCharacterVoiceCheck());

    await act(async () => {
      result.current.run("ch-1");
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
    const { result } = renderHook(() => useCharacterVoiceCheck());

    await act(async () => {
      result.current.run("ch-1");
    });

    // The signal handed to the stream client IS useAIOperation's controller
    // signal — the hook never constructs its own AbortController (ADR-043).
    const signal = lastCall()[2];
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

  it("reset clears results and returns to idle", async () => {
    const { result } = renderHook(() => useCharacterVoiceCheck());

    await act(async () => {
      result.current.run("ch-1");
    });
    const handlers = handlersOf();
    await act(async () => {
      handlers.onResult(resultElena);
      handlers.onComplete();
    });
    expect(result.current.results).toHaveLength(1);

    act(() => {
      result.current.reset();
    });

    expect(result.current.isIdle).toBe(true);
    expect(result.current.results).toBeNull();
    expect(result.current.error).toBeNull();
    expect(result.current.progress).toBeNull();
  });
});
