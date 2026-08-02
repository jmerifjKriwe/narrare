/**
 * streamCoreference tests — SSE event discrimination for ANAL-005 coreference.
 *
 * The SSE transport (`./streaming`) is mocked; each test captures the
 * `connectSSE` options and drives `onChunk` with typed coreference events to
 * verify the client translates the result/done/error discriminated stream into
 * the correct handlers, including the terminal dedupe (done event + transport
 * [DONE] sentinel) and the optional-callback guards.
 *
 * @module coreference-stream.test
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/streaming", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/streaming")>();
  return {
    ...actual,
    connectSSE: vi.fn(),
  };
});

import {
  type CoreferenceResult,
  type CoreferenceStreamEvent,
  streamCoreference,
} from "@/lib/api/coreference-stream";
import { connectSSE, type SSEOptions, SSEStreamError } from "@/lib/api/streaming";

const mockedConnectSSE = vi.mocked(connectSSE);

interface Captured {
  options: SSEOptions<CoreferenceStreamEvent>;
  onChunk: (event: CoreferenceStreamEvent) => void;
}

function capture(): Captured {
  expect(mockedConnectSSE).toHaveBeenCalled();
  const options = mockedConnectSSE.mock.calls.at(-1)?.[0] as Captured["options"] | undefined;
  expect(options).toBeDefined();
  return { options: options!, onChunk: options!.onChunk };
}

const sampleResult: CoreferenceResult = {
  chapter_id: "ch-1",
  clarity_score: 82,
  summary: "Referents are mostly clear.",
  resolutions: [
    { pronoun: "she", position: 12, referent: "Anna", confidence: 0.94, is_ambiguous: false },
  ],
  character_mentions: [{ character_name: "Anna", mentions: [12], is_pov: true }],
};

describe("streamCoreference", () => {
  beforeEach(() => {
    mockedConnectSSE.mockClear();
  });

  it("POSTs to the coreference endpoint and forwards the abort signal", async () => {
    const controller = new AbortController();
    await streamCoreference(
      "ch-1",
      { onResult: vi.fn(), onComplete: vi.fn(), onError: vi.fn() },
      controller.signal,
    );

    const { options } = capture();
    expect(options.url).toBe("/analysis/coreference/ch-1");
    expect(options.method).toBe("POST");
    expect(options.signal).toBe(controller.signal);
  });

  it("calls onResult with the full analysis on a result event", async () => {
    const onResult = vi.fn();
    const onComplete = vi.fn();
    await streamCoreference("ch-1", { onResult, onComplete, onError: vi.fn() });

    capture().onChunk({ event: "result", result: sampleResult });

    expect(onResult).toHaveBeenCalledTimes(1);
    expect(onResult).toHaveBeenCalledWith(sampleResult);
    expect(onComplete).not.toHaveBeenCalled();
  });

  it("ignores a result event whose result payload is null", async () => {
    const onResult = vi.fn();
    await streamCoreference("ch-1", { onResult, onComplete: vi.fn(), onError: vi.fn() });

    capture().onChunk({ event: "result", result: null });

    expect(onResult).not.toHaveBeenCalled();
  });

  it("calls onComplete on the terminal done event", async () => {
    const onComplete = vi.fn();
    await streamCoreference("ch-1", { onResult: vi.fn(), onComplete, onError: vi.fn() });

    capture().onChunk({ event: "done", is_final: true });

    expect(onComplete).toHaveBeenCalledTimes(1);
  });

  it("calls onComplete when is_final is set without the done discriminator", async () => {
    const onComplete = vi.fn();
    await streamCoreference("ch-1", { onResult: vi.fn(), onComplete, onError: vi.fn() });

    capture().onChunk({ is_final: true });

    expect(onComplete).toHaveBeenCalledTimes(1);
  });

  it("surfaces a terminal error event with its message", async () => {
    const onError = vi.fn();
    const onComplete = vi.fn();
    await streamCoreference("ch-1", { onResult: vi.fn(), onComplete, onError });

    capture().onChunk({ event: "error", error: "model unavailable", is_final: true });

    expect(onError).toHaveBeenCalledTimes(1);
    expect((onError.mock.calls[0]?.[0] as Error).message).toBe("model unavailable");
    expect(onComplete).not.toHaveBeenCalled();
  });

  it("surfaces an error when event.error is set without the error discriminator", async () => {
    const onError = vi.fn();
    await streamCoreference("ch-1", { onResult: vi.fn(), onComplete: vi.fn(), onError });

    capture().onChunk({ event: "done", error: "late failure", is_final: true });

    expect(onError).toHaveBeenCalledTimes(1);
    expect((onError.mock.calls[0]?.[0] as Error).message).toBe("late failure");
  });

  it("uses a generic message when an error event omits the message", async () => {
    const onError = vi.fn();
    await streamCoreference("ch-1", { onResult: vi.fn(), onComplete: vi.fn(), onError });

    capture().onChunk({ event: "error" });

    expect(onError).toHaveBeenCalledTimes(1);
    expect((onError.mock.calls[0]?.[0] as Error).message).toBe("Coreference analysis failed");
  });

  it("completes once when both the done event and the transport [DONE] sentinel arrive", async () => {
    const onComplete = vi.fn();
    await streamCoreference("ch-1", { onResult: vi.fn(), onComplete, onError: vi.fn() });

    const { options, onChunk } = capture();
    onChunk({ event: "done", is_final: true });
    options.onComplete?.(undefined);

    expect(onComplete).toHaveBeenCalledTimes(1);
  });

  it("does not complete after a terminal error event", async () => {
    const onComplete = vi.fn();
    const onError = vi.fn();
    await streamCoreference("ch-1", { onResult: vi.fn(), onComplete, onError });

    const { onChunk, options } = capture();
    onChunk({ event: "error", error: "boom" });
    options.onComplete?.(undefined);

    expect(onError).toHaveBeenCalledTimes(1);
    expect(onComplete).not.toHaveBeenCalled();
  });

  it("forwards transport errors via onError", async () => {
    const onError = vi.fn();
    await streamCoreference("ch-1", { onResult: vi.fn(), onComplete: vi.fn(), onError });

    capture().options.onError?.(new SSEStreamError("HTTP 500", "http", 500));

    expect(onError).toHaveBeenCalledTimes(1);
    expect(onError.mock.calls[0]?.[0]).toBeInstanceOf(SSEStreamError);
  });

  it("does not throw when onComplete and onError callbacks are omitted", async () => {
    await streamCoreference("ch-1", { onResult: vi.fn() });

    const { options, onChunk } = capture();
    onChunk({ event: "done", is_final: true });
    onChunk({ event: "error", error: "boom" });
    options.onError?.(new SSEStreamError("HTTP 500", "http", 500));
    options.onComplete?.(undefined);
  });
});
