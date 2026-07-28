/**
 * author-voice-drift-stream client unit tests — event discrimination (ANAL-009
 * Phase 2B).
 *
 * The SSE transport (`./streaming`) is mocked; each test captures the
 * `connectSSE` options and drives `onChunk` with typed events to verify the
 * client translates the discriminated event stream into the correct handlers
 * (progress / single result / graceful no-profile skip / completion / error)
 * and dedupes the terminal completion (`done` event + transport `[DONE]`
 * sentinel).
 *
 * Author voice is ONE narrator per novel, so the stream emits a SINGLE
 * `"result"` event (not per-character like Phase 1) OR a SINGLE `"no_profile"`
 * event — never both, never repeated (mirrors the backend
 * `AuthorVoiceDriftEvent` contract).
 *
 * @module author-voice-drift-stream.test
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/streaming", () => ({
  connectSSE: vi.fn(),
}));

import {
  type AuthorVoiceDriftEvent,
  type AuthorVoiceDriftNoProfile,
  type AuthorVoiceDriftResult,
  streamAuthorVoiceDrift,
} from "@/lib/api/author-voice-drift-stream";
import { connectSSE, type SSEOptions } from "@/lib/api/streaming";

const mockedConnectSSE = vi.mocked(connectSSE);

interface Captured {
  options: SSEOptions<AuthorVoiceDriftEvent>;
  onChunk: (event: AuthorVoiceDriftEvent) => void;
}

function capture(): Captured {
  expect(mockedConnectSSE).toHaveBeenCalled();
  const options = mockedConnectSSE.mock.calls.at(-1)?.[0] as
    | SSEOptions<AuthorVoiceDriftEvent>
    | undefined;
  expect(options).toBeDefined();
  return { options: options!, onChunk: options!.onChunk };
}

const sampleResult: AuthorVoiceDriftResult = {
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
    per_chapter_notes: [{ chapter_id: "ch-2", note: "Shorter sentences, more contractions." }],
    suggested_attention: ["ch-2"],
  },
};

const sampleNoProfile: AuthorVoiceDriftNoProfile = {
  reason: "no_stored_profile",
};

describe("streamAuthorVoiceDrift", () => {
  beforeEach(() => {
    mockedConnectSSE.mockClear();
  });

  it("POSTs to the author-voice-drift endpoint with the chapter filter body", async () => {
    await streamAuthorVoiceDrift(
      "novel-1",
      { chapter_ids: ["ch-1", "ch-2"] },
      { onResult: vi.fn() },
    );

    const { options } = capture();
    expect(options.url).toBe("/analysis/author-voice-drift/novel-1");
    expect(options.method).toBe("POST");
    expect(options.body).toEqual({ chapter_ids: ["ch-1", "ch-2"] });
  });

  it("defaults to analysing every chapter when the body is empty", async () => {
    await streamAuthorVoiceDrift("novel-1", {}, { onResult: vi.fn() });

    expect(capture().options.body).toEqual({});
  });

  it("forwards progress events to onProgress", async () => {
    const onProgress = vi.fn();
    await streamAuthorVoiceDrift(
      "novel-1",
      { chapter_ids: null },
      { onResult: vi.fn(), onProgress },
    );

    capture().onChunk({ event: "progress", progress: "Measuring 4 chapters" });
    expect(onProgress).toHaveBeenCalledWith("Measuring 4 chapters");
  });

  it("forwards the single result event to onResult", async () => {
    const onResult = vi.fn();
    await streamAuthorVoiceDrift("novel-1", { chapter_ids: null }, { onResult });

    capture().onChunk({ event: "result", result: sampleResult });

    expect(onResult).toHaveBeenCalledOnce();
    expect(onResult).toHaveBeenCalledWith(sampleResult);
  });

  it("ignores a result event that carries no payload", async () => {
    const onResult = vi.fn();
    await streamAuthorVoiceDrift("novel-1", { chapter_ids: null }, { onResult });

    capture().onChunk({ event: "result", result: null });
    expect(onResult).not.toHaveBeenCalled();
  });

  it("forwards the graceful no_profile event to onNoProfile (RULE-11)", async () => {
    const onNoProfile = vi.fn();
    await streamAuthorVoiceDrift(
      "novel-1",
      { chapter_ids: null },
      { onResult: vi.fn(), onNoProfile },
    );

    capture().onChunk({ event: "no_profile", no_profile: sampleNoProfile });

    expect(onNoProfile).toHaveBeenCalledOnce();
    expect(onNoProfile).toHaveBeenCalledWith(sampleNoProfile);
  });

  it("ignores a no_profile event that carries no payload", async () => {
    const onNoProfile = vi.fn();
    await streamAuthorVoiceDrift(
      "novel-1",
      { chapter_ids: null },
      { onResult: vi.fn(), onNoProfile },
    );

    capture().onChunk({ event: "no_profile", no_profile: null });
    expect(onNoProfile).not.toHaveBeenCalled();
  });

  it("completes once on the done event and does not double-fire on the [DONE] sentinel", async () => {
    const onComplete = vi.fn();
    await streamAuthorVoiceDrift(
      "novel-1",
      { chapter_ids: null },
      { onResult: vi.fn(), onComplete },
    );

    const { options, onChunk } = capture();
    onChunk({ event: "done", is_final: true });
    // The transport invokes its own onComplete when it sees `data: [DONE]`.
    options.onComplete?.(undefined);

    expect(onComplete).toHaveBeenCalledOnce();
  });

  it("surfaces a terminal error event via onError", async () => {
    const onError = vi.fn();
    await streamAuthorVoiceDrift("novel-1", { chapter_ids: null }, { onResult: vi.fn(), onError });

    capture().onChunk({ event: "error", error: "Author-voice-drift analysis failed." });

    expect(onError).toHaveBeenCalledOnce();
    expect(onError.mock.calls[0]?.[0]).toBeInstanceOf(Error);
    expect((onError.mock.calls[0]?.[0] as Error).message).toBe(
      "Author-voice-drift analysis failed.",
    );
  });
});
