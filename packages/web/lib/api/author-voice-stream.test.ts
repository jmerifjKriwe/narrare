/**
 * author-voice-stream client unit tests — event discrimination (ANAL-007).
 *
 * The SSE transport (`./streaming`) is mocked; each test captures the
 * `connectSSE` options and drives `onChunk` with typed events to verify the
 * client translates the discriminated event stream into the correct handlers
 * (progress / single result / completion / error) and dedupes the terminal
 * completion (`done` event + transport `[DONE]` sentinel).
 *
 * Mirrors `character-voice-stream.test.ts`, adapted to the SINGLE-result
 * author-voice contract (one profile per novel, not per-character).
 *
 * @module author-voice-stream.test
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/streaming", () => ({
  connectSSE: vi.fn(),
}));

import {
  type AuthorVoiceProfile,
  type AuthorVoiceResult,
  type AuthorVoiceStreamEvent,
  streamAuthorVoice,
} from "@/lib/api/author-voice-stream";
import { connectSSE, type SSEOptions } from "@/lib/api/streaming";

const mockedConnectSSE = vi.mocked(connectSSE);

interface Captured {
  options: SSEOptions<AuthorVoiceStreamEvent>;
  onChunk: (event: AuthorVoiceStreamEvent) => void;
}

function capture(): Captured {
  expect(mockedConnectSSE).toHaveBeenCalled();
  const options = mockedConnectSSE.mock.calls.at(-1)?.[0] as
    | SSEOptions<AuthorVoiceStreamEvent>
    | undefined;
  expect(options).toBeDefined();
  return { options: options!, onChunk: options!.onChunk };
}

const sampleProfile: AuthorVoiceProfile = {
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
};

const sampleResult: AuthorVoiceResult = {
  novel_id: "novel-1",
  profile: sampleProfile,
};

describe("streamAuthorVoice", () => {
  beforeEach(() => {
    mockedConnectSSE.mockClear();
  });

  it("POSTs to the author-voice endpoint with the chapter_ids body", async () => {
    await streamAuthorVoice(
      "novel-1",
      { chapter_ids: ["ch-1", "ch-2"] },
      {
        onResult: vi.fn(),
      },
    );

    const { options } = capture();
    expect(options.url).toBe("/analysis/author-voice/novel-1");
    expect(options.method).toBe("POST");
    expect(options.body).toEqual({ chapter_ids: ["ch-1", "ch-2"] });
  });

  it("forwards progress events to onProgress", async () => {
    const onProgress = vi.fn();
    await streamAuthorVoice(
      "novel-1",
      { chapter_ids: null },
      {
        onResult: vi.fn(),
        onProgress,
      },
    );

    capture().onChunk({ event: "progress", progress: "Analysing 4 chapters" });
    expect(onProgress).toHaveBeenCalledWith("Analysing 4 chapters");
  });

  it("forwards the single result event to onResult", async () => {
    const onResult = vi.fn();
    await streamAuthorVoice("novel-1", { chapter_ids: null }, { onResult });

    capture().onChunk({ event: "result", result: sampleResult });

    expect(onResult).toHaveBeenCalledOnce();
    expect(onResult).toHaveBeenCalledWith(sampleResult);
  });

  it("ignores a result event that carries no payload", async () => {
    const onResult = vi.fn();
    await streamAuthorVoice("novel-1", { chapter_ids: null }, { onResult });

    capture().onChunk({ event: "result", result: null });
    expect(onResult).not.toHaveBeenCalled();
  });

  it("completes once on the done event and does not double-fire on the [DONE] sentinel", async () => {
    const onComplete = vi.fn();
    await streamAuthorVoice(
      "novel-1",
      { chapter_ids: null },
      {
        onResult: vi.fn(),
        onComplete,
      },
    );

    const { options, onChunk } = capture();
    onChunk({ event: "done", is_final: true });
    // The transport invokes its own onComplete when it sees `data: [DONE]`.
    options.onComplete?.(undefined);

    expect(onComplete).toHaveBeenCalledOnce();
  });

  it("surfaces a terminal error event via onError", async () => {
    const onError = vi.fn();
    await streamAuthorVoice(
      "novel-1",
      { chapter_ids: null },
      {
        onResult: vi.fn(),
        onError,
      },
    );

    capture().onChunk({ event: "error", error: "Author-voice analysis failed." });

    expect(onError).toHaveBeenCalledOnce();
    expect(onError.mock.calls[0]?.[0]).toBeInstanceOf(Error);
    expect((onError.mock.calls[0]?.[0] as Error).message).toBe("Author-voice analysis failed.");
  });
});
