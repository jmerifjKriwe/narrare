/**
 * voice-check-stream client unit tests — event discrimination.
 *
 * The SSE transport (`./streaming`) is mocked; each test captures the
 * `connectSSE` options and drives `onChunk` with typed events to verify the
 * client translates the discriminated event stream into the correct handlers
 * (progress / per-character result / completion / error) and dedupes the
 * terminal completion (`done` event + transport `[DONE]` sentinel).
 *
 * Voice-check is chapter-scoped (like coreference) but emits MULTIPLE
 * per-character results (like character-voice), so the test covers both the
 * no-body transport and the multi-result fan-out.
 *
 * @module voice-check-stream.test
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/streaming", () => ({
  connectSSE: vi.fn(),
}));

import { connectSSE, type SSEOptions } from "@/lib/api/streaming";
import {
  streamVoiceCheck,
  type VoiceCheckResult,
  type VoiceCheckStreamEvent,
} from "@/lib/api/voice-check-stream";

const mockedConnectSSE = vi.mocked(connectSSE);

interface Captured {
  options: SSEOptions<VoiceCheckStreamEvent>;
  onChunk: (event: VoiceCheckStreamEvent) => void;
}

function capture(): Captured {
  expect(mockedConnectSSE).toHaveBeenCalled();
  const options = mockedConnectSSE.mock.calls.at(-1)?.[0] as
    | SSEOptions<VoiceCheckStreamEvent>
    | undefined;
  expect(options).toBeDefined();
  return { options: options!, onChunk: options!.onChunk };
}

const sampleResult: VoiceCheckResult = {
  character_name: "Elena",
  match_score: 92,
  band: "green",
  match_judgment: "consistent",
  qualitative_sub_score: 94,
  metric_delta_subscore: 90,
  flagged_lines: [],
  has_profile: true,
  n_comparable_metrics: 5,
};

describe("streamVoiceCheck", () => {
  beforeEach(() => {
    mockedConnectSSE.mockClear();
  });

  it("POSTs to the chapter-scoped voice-check endpoint with no body", async () => {
    await streamVoiceCheck("chapter-1", { onResult: vi.fn() });

    const { options } = capture();
    expect(options.url).toBe("/analysis/voice-check/chapter-1");
    expect(options.method).toBe("POST");
    expect(options.body).toBeUndefined();
  });

  it("forwards progress events to onProgress", async () => {
    const onProgress = vi.fn();
    await streamVoiceCheck("chapter-1", { onResult: vi.fn(), onProgress });

    capture().onChunk({ event: "progress", progress: "Extracting dialogue" });
    expect(onProgress).toHaveBeenCalledWith("Extracting dialogue");
  });

  it("forwards each per-character result event to onResult", async () => {
    const onResult = vi.fn();
    await streamVoiceCheck("chapter-1", { onResult });

    const onChunk = capture().onChunk;
    onChunk({ event: "result", result: sampleResult });
    onChunk({
      event: "result",
      result: { ...sampleResult, character_name: "Marek", match_score: 42, band: "red" },
    });

    expect(onResult).toHaveBeenCalledTimes(2);
    expect(onResult).toHaveBeenNthCalledWith(1, sampleResult);
    expect(onResult).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({ character_name: "Marek", match_score: 42, band: "red" }),
    );
  });

  it("ignores a result event that carries no payload", async () => {
    const onResult = vi.fn();
    await streamVoiceCheck("chapter-1", { onResult });

    capture().onChunk({ event: "result", result: null });
    expect(onResult).not.toHaveBeenCalled();
  });

  it("completes once on the done event and does not double-fire on the [DONE] sentinel", async () => {
    const onComplete = vi.fn();
    await streamVoiceCheck("chapter-1", { onResult: vi.fn(), onComplete });

    const { options, onChunk } = capture();
    onChunk({ event: "done", is_final: true });
    // The transport invokes its own onComplete when it sees `data: [DONE]`.
    options.onComplete?.(undefined);

    expect(onComplete).toHaveBeenCalledOnce();
  });

  it("surfaces a terminal error event via onError", async () => {
    const onError = vi.fn();
    await streamVoiceCheck("chapter-1", { onResult: vi.fn(), onError });

    capture().onChunk({ event: "error", error: "Voice-check analysis failed." });

    expect(onError).toHaveBeenCalledOnce();
    expect(onError.mock.calls[0]?.[0]).toBeInstanceOf(Error);
    expect((onError.mock.calls[0]?.[0] as Error).message).toBe("Voice-check analysis failed.");
  });

  it("does not fire onComplete after an error event", async () => {
    const onComplete = vi.fn();
    const onError = vi.fn();
    await streamVoiceCheck("chapter-1", { onResult: vi.fn(), onComplete, onError });

    const onChunk = capture().onChunk;
    onChunk({ event: "error", error: "Voice-check analysis failed." });
    // A subsequent done event must not fire onComplete after the error path ran.
    onChunk({ event: "done", is_final: true });

    expect(onError).toHaveBeenCalledOnce();
    expect(onComplete).not.toHaveBeenCalled();
  });
});
