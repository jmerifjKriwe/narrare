/**
 * useCharacterVoice hook tests — SSE streaming for ANAL-008 character voice.
 *
 * Mirrors the useAIOperation execution-test style: the real useAIOperation
 * lifecycle runs, and only the SSE transport boundary
 * (`@/lib/api/character-voice-stream`) is mocked. Each test drives the captured
 * stream handlers (onProgress / onResult / onComplete / onError) and observes
 * the resulting lifecycle state — verifying the SSE → state bridging that is
 * unique to this hook (multi-character accumulation, progress liveness,
 * display-only distinctiveness_notes, and cancel flowing through
 * useAIOperation's signal with NO manual AbortController).
 *
 * @module useCharacterVoice.test
 */

import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Hoisted mock: streamCharacterVoice captures the handlers + signal passed by
// the hook so each test can drive the SSE event stream deterministically.
const handle = vi.hoisted(() => ({ stream: vi.fn() }));

vi.mock("@/lib/api/character-voice-stream", () => ({
  streamCharacterVoice: handle.stream,
}));

import type { CharacterVoiceResult } from "@/lib/api/character-voice-stream";
import { useCharacterVoice } from "@/lib/hooks/useCharacterVoice";

// ---------------------------------------------------------------------------
// Types for the captured streamCharacterVoice call signature.
// ---------------------------------------------------------------------------

// The hook ALWAYS passes onResult + onComplete (its contract); onProgress /
// onError are optional on the client interface, so they stay optional here and
// are invoked with optional chaining.
interface StreamHandlers {
  onProgress?: (message: string) => void;
  onResult: (result: CharacterVoiceResult) => void;
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
// Fixtures — two per-character results. distinctiveness_notes is the
// display-only, per-run comparison artifact (ADR-055 Decision 1): it is carried
// in the surfaced results for the panel but is NOT persisted profile data.
// ---------------------------------------------------------------------------

const resultElena: CharacterVoiceResult = {
  character_name: "Elena",
  voice_analysis: {
    formality: 0.62,
    vocabulary_level: "moderate",
    sentence_profile: "varied",
    emotional_range: "expressive",
    cultural_regional_markers: null,
    voice_examples: ['"You won\'t forget this."'],
    voice_metrics: { avg_sentence_length: 12.4, type_token_ratio: 0.71 },
  },
  // Display-only (ADR-055): relative to the other characters in THIS run only.
  distinctiveness_notes: "More formal register than Marek.",
  kb_entry_id: "kb-elena-1",
};

const resultMarek: CharacterVoiceResult = {
  character_name: "Marek",
  voice_analysis: {
    formality: 0.31,
    vocabulary_level: "simple",
    sentence_profile: "short",
    emotional_range: "restricted",
    cultural_regional_markers: "working-class urban idiom",
    voice_examples: ['"Yeah. Sure."'],
    voice_metrics: { avg_sentence_length: 6.1 },
  },
  distinctiveness_notes: "Clipped, terse — contrasts with Elena's fluency.",
  kb_entry_id: null,
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useCharacterVoice", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    handle.stream.mockClear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("run stages novelId + chapterIds and calls the stream client", async () => {
    const { result } = renderHook(() => useCharacterVoice());

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
    const { result } = renderHook(() => useCharacterVoice());

    await act(async () => {
      result.current.run("novel-42");
    });

    expect(lastCall()[1].chapter_ids).toBeNull();
  });

  it("accumulates per-character results through SSE events and completes", async () => {
    const { result } = renderHook(() => useCharacterVoice());

    await act(async () => {
      result.current.run("novel-1", ["ch-1"]);
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
    // distinctiveness_notes is carried display-only on the surfaced results.
    expect(result.current.results?.[0].distinctiveness_notes).toBe(
      resultElena.distinctiveness_notes,
    );
  });

  it("progress events keep the stream alive and add no results", async () => {
    const { result } = renderHook(() => useCharacterVoice());

    await act(async () => {
      result.current.run("novel-1");
    });

    const handlers = handlersOf();

    await act(async () => {
      handlers.onProgress?.("Found 2 speaking characters");
    });
    expect(result.current.isStreaming).toBe(true);

    await act(async () => {
      handlers.onResult(resultElena);
      handlers.onComplete();
    });

    expect(result.current.isComplete).toBe(true);
    expect(result.current.results).toHaveLength(1);
  });

  it("surfaces a terminal error event in the error state", async () => {
    const { result } = renderHook(() => useCharacterVoice());

    await act(async () => {
      result.current.run("novel-1");
    });

    await act(async () => {
      handlersOf().onError?.(new Error("Character-voice analysis failed."));
    });

    expect(result.current.isError).toBe(true);
    expect(result.current.error).not.toBeNull();
    expect(result.current.results).toBeNull();
  });

  it("cancel flows through useAIOperation (no manual AbortController) → idle + aborted signal", async () => {
    const { result } = renderHook(() => useCharacterVoice());

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

  it("reset clears results and returns to idle", async () => {
    const { result } = renderHook(() => useCharacterVoice());

    await act(async () => {
      result.current.run("novel-1");
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
  });
});
