/**
 * voice-drift-stream client unit tests — event discrimination (ANAL-009).
 *
 * The SSE transport (`./streaming`) is mocked; each test captures the
 * `connectSSE` options and drives `onChunk` with typed events to verify the
 * client translates the discriminated event stream into the correct handlers
 * (progress / per-character result / no-profile skip / completion / error) and
 * dedupes the terminal completion (`done` event + transport `[DONE]` sentinel).
 *
 * @module voice-drift-stream.test
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/streaming", () => ({
  connectSSE: vi.fn(),
}));

import { connectSSE, type SSEOptions } from "@/lib/api/streaming";
import {
  streamVoiceDrift,
  type VoiceDriftCharacterResult,
  type VoiceDriftEvent,
  type VoiceDriftNoProfile,
} from "@/lib/api/voice-drift-stream";

const mockedConnectSSE = vi.mocked(connectSSE);

interface Captured {
  options: SSEOptions<VoiceDriftEvent>;
  onChunk: (event: VoiceDriftEvent) => void;
}

function capture(): Captured {
  expect(mockedConnectSSE).toHaveBeenCalled();
  const options = mockedConnectSSE.mock.calls.at(-1)?.[0] as
    | SSEOptions<VoiceDriftEvent>
    | undefined;
  expect(options).toBeDefined();
  return { options: options!, onChunk: options!.onChunk };
}

const sampleResult: VoiceDriftCharacterResult = {
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

const sampleNoProfile: VoiceDriftNoProfile = {
  character_id: "",
  character_name: "Marek",
  reason: "no_stored_profile",
};

describe("streamVoiceDrift", () => {
  beforeEach(() => {
    mockedConnectSSE.mockClear();
  });

  it("POSTs to the voice-drift endpoint with the filter body", async () => {
    await streamVoiceDrift(
      "novel-1",
      { character_id: "kb-elena", chapter_ids: ["ch-1", "ch-2"] },
      { onResult: vi.fn() },
    );

    const { options } = capture();
    expect(options.url).toBe("/analysis/voice-drift/novel-1");
    expect(options.method).toBe("POST");
    expect(options.body).toEqual({ character_id: "kb-elena", chapter_ids: ["ch-1", "ch-2"] });
  });

  it("defaults to analysing all characters/chapters when the body is empty", async () => {
    await streamVoiceDrift("novel-1", {}, { onResult: vi.fn() });

    expect(capture().options.body).toEqual({});
  });

  it("forwards progress events to onProgress", async () => {
    const onProgress = vi.fn();
    await streamVoiceDrift("novel-1", { chapter_ids: null }, { onResult: vi.fn(), onProgress });

    capture().onChunk({ event: "progress", progress: "Profiling 3 characters" });
    expect(onProgress).toHaveBeenCalledWith("Profiling 3 characters");
  });

  it("forwards each per-character result event to onResult", async () => {
    const onResult = vi.fn();
    await streamVoiceDrift("novel-1", { chapter_ids: null }, { onResult });

    const onChunk = capture().onChunk;
    onChunk({ event: "character_result", result: sampleResult });
    onChunk({
      event: "character_result",
      result: { ...sampleResult, character_name: "Kara" },
    });

    expect(onResult).toHaveBeenCalledTimes(2);
    expect(onResult).toHaveBeenNthCalledWith(1, sampleResult);
  });

  it("ignores a character_result event that carries no payload", async () => {
    const onResult = vi.fn();
    await streamVoiceDrift("novel-1", { chapter_ids: null }, { onResult });

    capture().onChunk({ event: "character_result", result: null });
    expect(onResult).not.toHaveBeenCalled();
  });

  it("forwards no_profile events to onNoProfile (RULE-11 graceful skip)", async () => {
    const onNoProfile = vi.fn();
    await streamVoiceDrift("novel-1", { chapter_ids: null }, { onResult: vi.fn(), onNoProfile });

    capture().onChunk({ event: "no_profile", no_profile: sampleNoProfile });

    expect(onNoProfile).toHaveBeenCalledOnce();
    expect(onNoProfile).toHaveBeenCalledWith(sampleNoProfile);
  });

  it("ignores a no_profile event that carries no payload", async () => {
    const onNoProfile = vi.fn();
    await streamVoiceDrift("novel-1", { chapter_ids: null }, { onResult: vi.fn(), onNoProfile });

    capture().onChunk({ event: "no_profile", no_profile: null });
    expect(onNoProfile).not.toHaveBeenCalled();
  });

  it("completes once on the done event and does not double-fire on the [DONE] sentinel", async () => {
    const onComplete = vi.fn();
    await streamVoiceDrift("novel-1", { chapter_ids: null }, { onResult: vi.fn(), onComplete });

    const { options, onChunk } = capture();
    onChunk({ event: "done", is_final: true });
    // The transport invokes its own onComplete when it sees `data: [DONE]`.
    options.onComplete?.(undefined);

    expect(onComplete).toHaveBeenCalledOnce();
  });

  it("surfaces a terminal error event via onError", async () => {
    const onError = vi.fn();
    await streamVoiceDrift("novel-1", { chapter_ids: null }, { onResult: vi.fn(), onError });

    capture().onChunk({ event: "error", error: "Voice-drift analysis failed." });

    expect(onError).toHaveBeenCalledOnce();
    expect(onError.mock.calls[0]?.[0]).toBeInstanceOf(Error);
    expect((onError.mock.calls[0]?.[0] as Error).message).toBe("Voice-drift analysis failed.");
  });
});
