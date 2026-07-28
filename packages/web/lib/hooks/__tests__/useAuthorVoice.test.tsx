/**
 * useAuthorVoice hook tests — SSE streaming for ANAL-007 author voice.
 *
 * Mirrors the useAIOperation execution-test style: the real useAIOperation
 * lifecycle runs, and only the SSE transport boundary
 * (`@/lib/api/author-voice-stream`) is mocked. Each test drives the captured
 * stream handlers (onProgress / onResult / onComplete / onError) and observes
 * the resulting lifecycle state — verifying the SSE → state bridging that is
 * unique to this hook (single-result capture, progress liveness, and cancel
 * flowing through useAIOperation's signal with NO manual AbortController).
 *
 * @module useAuthorVoice.test
 */

import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Hoisted mock: streamAuthorVoice captures the handlers + signal passed by
// the hook so each test can drive the SSE event stream deterministically.
const handle = vi.hoisted(() => ({ stream: vi.fn() }));

vi.mock("@/lib/api/author-voice-stream", () => ({
  streamAuthorVoice: handle.stream,
}));

import type { AuthorVoiceResult } from "@/lib/api/author-voice-stream";
import { useAuthorVoice } from "@/lib/hooks/useAuthorVoice";

// ---------------------------------------------------------------------------
// Types for the captured streamAuthorVoice call signature.
// ---------------------------------------------------------------------------

interface StreamHandlers {
  onProgress?: (message: string) => void;
  onResult: (result: AuthorVoiceResult) => void;
  onComplete: () => void;
  onError?: (error: Error) => void;
}

type StreamCall = [string, { chapter_ids: string[] | null }, StreamHandlers, AbortSignal];

function lastCall(): StreamCall {
  expect(handle.stream.mock.calls.length).toBeGreaterThan(0);
  return handle.stream.mock.calls.at(-1) as StreamCall;
}

function handlersOf(): StreamHandlers {
  return lastCall()[2];
}

// ---------------------------------------------------------------------------
// Fixtures — a single author-voice profile result (one profile per novel).
// ---------------------------------------------------------------------------

const sampleResult: AuthorVoiceResult = {
  novel_id: "novel-1",
  profile: {
    voice_analysis: {
      formality: 0.62,
      vocabulary_level: "moderate",
      sentence_profile: "varied",
      emotional_range: "expressive",
      cultural_regional_markers: "nautical idioms",
      voice_examples: ["The harbour bell tolled."],
      voice_metrics: { avg_sentence_length: 14.2, type_token_ratio: 0.71 },
    },
    author_examples: ["The wind carried salt and memory."],
    author_metrics: {
      dialogue_ratio: 0.34,
      description_density: 0.18,
      action_introspection_ratio: 0.55,
      metaphor_density: 0.02,
    },
    updated_at: "2026-07-27T10:00:00Z",
    is_fresh: true,
  },
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useAuthorVoice", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    handle.stream.mockClear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("run stages novelId + chapterIds and calls the stream client", async () => {
    const { result } = renderHook(() => useAuthorVoice());

    await act(async () => {
      result.current.run("novel-42", ["ch-a", "ch-b"]);
    });

    expect(handle.stream).toHaveBeenCalledOnce();
    const [novelId, body] = lastCall();
    expect(novelId).toBe("novel-42");
    expect(body.chapter_ids).toEqual(["ch-a", "ch-b"]);
    expect(result.current.isLoading).toBe(true);
    expect(result.current.isIdle).toBe(false);
  });

  it("run with no chapterIds requests all chapters (chapter_ids = null)", async () => {
    const { result } = renderHook(() => useAuthorVoice());

    await act(async () => {
      result.current.run("novel-42");
    });

    expect(lastCall()[1].chapter_ids).toBeNull();
  });

  it("captures the single result event and completes", async () => {
    const { result } = renderHook(() => useAuthorVoice());

    await act(async () => {
      result.current.run("novel-1", ["ch-1"]);
    });

    const handlers = handlersOf();
    await act(async () => {
      handlers.onResult(sampleResult);
      handlers.onComplete();
    });

    expect(result.current.isComplete).toBe(true);
    expect(result.current.result).toEqual(sampleResult);
    // Author voice is ONE profile per novel — the hook surfaces the single
    // result, not an accumulated array.
    expect(result.current.result?.profile?.voice_analysis?.formality).toBe(0.62);
  });

  it("progress events keep the stream alive and do not set a result", async () => {
    const { result } = renderHook(() => useAuthorVoice());

    await act(async () => {
      result.current.run("novel-1");
    });

    const handlers = handlersOf();

    await act(async () => {
      handlers.onProgress?.("Analysing 4 chapters");
    });
    expect(result.current.isStreaming).toBe(true);
    expect(result.current.result).toBeNull();

    await act(async () => {
      handlers.onResult(sampleResult);
      handlers.onComplete();
    });

    expect(result.current.isComplete).toBe(true);
    expect(result.current.result).toEqual(sampleResult);
  });

  it("surfaces a terminal error event in the error state", async () => {
    const { result } = renderHook(() => useAuthorVoice());

    await act(async () => {
      result.current.run("novel-1");
    });

    await act(async () => {
      handlersOf().onError?.(new Error("Author-voice analysis failed."));
    });

    expect(result.current.isError).toBe(true);
    expect(result.current.error).not.toBeNull();
    expect(result.current.result).toBeNull();
  });

  it("does not overwrite error state when onComplete fires after onError", async () => {
    const { result } = renderHook(() => useAuthorVoice());

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
    const { result } = renderHook(() => useAuthorVoice());

    await act(async () => {
      result.current.run("novel-1");
    });

    const handlers = handlersOf();
    await act(async () => {
      handlers.onResult(sampleResult);
      handlers.onComplete();
      handlers.onError?.(new Error("late error"));
    });

    expect(result.current.isComplete).toBe(true);
    expect(result.current.isError).toBe(false);
    expect(result.current.result).toEqual(sampleResult);
  });

  it("cancel flows through useAIOperation (no manual AbortController) → idle + aborted signal", async () => {
    const { result } = renderHook(() => useAuthorVoice());

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

  it("reset clears the result and returns to idle", async () => {
    const { result } = renderHook(() => useAuthorVoice());

    await act(async () => {
      result.current.run("novel-1");
    });
    const handlers = handlersOf();
    await act(async () => {
      handlers.onResult(sampleResult);
      handlers.onComplete();
    });
    expect(result.current.result).toEqual(sampleResult);

    act(() => {
      result.current.reset();
    });

    expect(result.current.isIdle).toBe(true);
    expect(result.current.result).toBeNull();
    expect(result.current.error).toBeNull();
  });
});
