/**
 * character-voice-stream client unit tests — event discrimination.
 *
 * The SSE transport (`./streaming`) is mocked; each test captures the
 * `connectSSE` options and drives `onChunk` with typed events to verify the
 * client translates the discriminated event stream into the correct handlers
 * (progress / per-character result / completion / error) and dedupes the
 * terminal completion (`done` event + transport `[DONE]` sentinel).
 *
 * @module character-voice-stream.test
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/streaming", () => ({
  connectSSE: vi.fn(),
}));

import {
  type CharacterVoiceResult,
  type CharacterVoiceStreamEvent,
  streamCharacterVoice,
} from "@/lib/api/character-voice-stream";
import { connectSSE, type SSEOptions } from "@/lib/api/streaming";

const mockedConnectSSE = vi.mocked(connectSSE);

interface Captured {
  options: SSEOptions<CharacterVoiceStreamEvent>;
  onChunk: (event: CharacterVoiceStreamEvent) => void;
}

function capture(): Captured {
  expect(mockedConnectSSE).toHaveBeenCalled();
  const options = mockedConnectSSE.mock.calls.at(-1)?.[0] as
    | SSEOptions<CharacterVoiceStreamEvent>
    | undefined;
  expect(options).toBeDefined();
  return { options: options!, onChunk: options!.onChunk };
}

const sampleResult: CharacterVoiceResult = {
  character_name: "Elena",
  voice_analysis: { formality: 0.6, vocabulary_level: "moderate" },
  distinctiveness_notes: "display-only",
  kb_entry_id: "kb-1",
};

describe("streamCharacterVoice", () => {
  beforeEach(() => {
    mockedConnectSSE.mockClear();
  });

  it("POSTs to the character-voice endpoint with the chapter_ids body", async () => {
    await streamCharacterVoice("novel-1", { chapter_ids: ["ch-1", "ch-2"] }, { onResult: vi.fn() });

    const { options } = capture();
    expect(options.url).toBe("/analysis/character-voice/novel-1");
    expect(options.method).toBe("POST");
    expect(options.body).toEqual({ chapter_ids: ["ch-1", "ch-2"] });
  });

  it("forwards progress events to onProgress", async () => {
    const onProgress = vi.fn();
    await streamCharacterVoice(
      "novel-1",
      { chapter_ids: null },
      {
        onResult: vi.fn(),
        onProgress,
      },
    );

    capture().onChunk({ event: "progress", progress: "Found 3 characters" });
    expect(onProgress).toHaveBeenCalledWith("Found 3 characters");
  });

  it("forwards each per-character result event to onResult", async () => {
    const onResult = vi.fn();
    await streamCharacterVoice("novel-1", { chapter_ids: null }, { onResult });

    const onChunk = capture().onChunk;
    onChunk({ event: "result", result: sampleResult });
    onChunk({ event: "result", result: { ...sampleResult, character_name: "Marek" } });

    expect(onResult).toHaveBeenCalledTimes(2);
    expect(onResult).toHaveBeenNthCalledWith(1, sampleResult);
  });

  it("ignores a result event that carries no payload", async () => {
    const onResult = vi.fn();
    await streamCharacterVoice("novel-1", { chapter_ids: null }, { onResult });

    capture().onChunk({ event: "result", result: null });
    expect(onResult).not.toHaveBeenCalled();
  });

  it("completes once on the done event and does not double-fire on the [DONE] sentinel", async () => {
    const onComplete = vi.fn();
    await streamCharacterVoice(
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
    await streamCharacterVoice(
      "novel-1",
      { chapter_ids: null },
      {
        onResult: vi.fn(),
        onError,
      },
    );

    capture().onChunk({ event: "error", error: "Character-voice analysis failed." });

    expect(onError).toHaveBeenCalledOnce();
    expect(onError.mock.calls[0]?.[0]).toBeInstanceOf(Error);
    expect((onError.mock.calls[0]?.[0] as Error).message).toBe("Character-voice analysis failed.");
  });
});
