/**
 * streamStorySuggestions tests — SSE event translation for Writer's Unblock
 * (WRITE-009).
 *
 * The SSE transport (`./streaming`) is mocked; each test captures the
 * `connectSSE` options and drives `onChunk` with story-suggest events to
 * verify suggestions / done / error discrimination, the terminal dedupe
 * (done event + transport [DONE] sentinel), and the optional-callback guards.
 *
 * @module story-suggest-stream.test
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/streaming", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/streaming")>();
  return {
    ...actual,
    connectSSE: vi.fn(),
  };
});

import { type StorySuggestion, streamStorySuggestions } from "@/lib/api/story-suggest-stream";
import { connectSSE, type SSEOptions, SSEStreamError } from "@/lib/api/streaming";

const mockedConnectSSE = vi.mocked(connectSSE);

interface Captured {
  options: SSEOptions<{
    event?: "suggestions" | "done" | "error";
    suggestions?: StorySuggestion[] | null;
    error?: string | null;
    is_final?: boolean;
  }>;
  onChunk: (event: {
    event?: "suggestions" | "done" | "error";
    suggestions?: StorySuggestion[] | null;
    error?: string | null;
    is_final?: boolean;
  }) => void;
}

function capture(): Captured {
  expect(mockedConnectSSE).toHaveBeenCalled();
  const options = mockedConnectSSE.mock.calls.at(-1)?.[0] as Captured["options"] | undefined;
  expect(options).toBeDefined();
  return { options: options!, onChunk: options!.onChunk };
}

const sampleSuggestions: StorySuggestion[] = [
  {
    type: "plot_development",
    title: "Raise the stakes",
    description: "Introduce a rival who threatens the protagonist's goal.",
    connection: "Ties into chapter 3's cliffhanger.",
  },
];

describe("streamStorySuggestions", () => {
  beforeEach(() => {
    mockedConnectSSE.mockClear();
  });

  it("POSTs to the story-suggest endpoint with the body and forwards the signal", async () => {
    const controller = new AbortController();
    const body = { chapter_id: "ch-1", author_instructions: "Make it darker" };

    await streamStorySuggestions(
      "novel-1",
      body,
      { onSuggestions: vi.fn(), onComplete: vi.fn(), onError: vi.fn() },
      controller.signal,
    );

    const { options } = capture();
    expect(options.url).toBe("/writing/story-suggest/novel-1");
    expect(options.method).toBe("POST");
    expect(options.body).toEqual(body);
    expect(options.signal).toBe(controller.signal);
  });

  it("calls onSuggestions with the full list on a suggestions event", async () => {
    const onSuggestions = vi.fn();
    await streamStorySuggestions("novel-1", {}, { onSuggestions, onComplete: vi.fn() });

    capture().onChunk({ event: "suggestions", suggestions: sampleSuggestions });

    expect(onSuggestions).toHaveBeenCalledTimes(1);
    expect(onSuggestions).toHaveBeenCalledWith(sampleSuggestions);
  });

  it("ignores a suggestions event with a null payload", async () => {
    const onSuggestions = vi.fn();
    await streamStorySuggestions("novel-1", {}, { onSuggestions, onComplete: vi.fn() });

    capture().onChunk({ event: "suggestions", suggestions: null });

    expect(onSuggestions).not.toHaveBeenCalled();
  });

  it("calls onComplete on the terminal done event", async () => {
    const onComplete = vi.fn();
    await streamStorySuggestions("novel-1", {}, { onSuggestions: vi.fn(), onComplete });

    capture().onChunk({ event: "done", is_final: true });

    expect(onComplete).toHaveBeenCalledTimes(1);
  });

  it("calls onComplete when is_final is set without the done discriminator", async () => {
    const onComplete = vi.fn();
    await streamStorySuggestions("novel-1", {}, { onSuggestions: vi.fn(), onComplete });

    capture().onChunk({ is_final: true });

    expect(onComplete).toHaveBeenCalledTimes(1);
  });

  it("surfaces a terminal error event with its message", async () => {
    const onError = vi.fn();
    const onComplete = vi.fn();
    await streamStorySuggestions("novel-1", {}, { onSuggestions: vi.fn(), onComplete, onError });

    capture().onChunk({ event: "error", error: "model unavailable", is_final: true });

    expect(onError).toHaveBeenCalledTimes(1);
    expect((onError.mock.calls[0]?.[0] as Error).message).toBe("model unavailable");
    expect(onComplete).not.toHaveBeenCalled();
  });

  it("uses a generic message when an error event omits the message", async () => {
    const onError = vi.fn();
    await streamStorySuggestions("novel-1", {}, { onSuggestions: vi.fn(), onError });

    capture().onChunk({ event: "error" });

    expect(onError).toHaveBeenCalledTimes(1);
    expect((onError.mock.calls[0]?.[0] as Error).message).toBe("Story suggestion failed");
  });

  it("surfaces an error when event.error is set without the error discriminator", async () => {
    const onError = vi.fn();
    await streamStorySuggestions("novel-1", {}, { onSuggestions: vi.fn(), onError });

    capture().onChunk({ event: "done", error: "late failure", is_final: true });

    expect(onError).toHaveBeenCalledTimes(1);
    expect((onError.mock.calls[0]?.[0] as Error).message).toBe("late failure");
  });

  it("does not complete after a terminal error event", async () => {
    const onComplete = vi.fn();
    const onError = vi.fn();
    await streamStorySuggestions("novel-1", {}, { onSuggestions: vi.fn(), onComplete, onError });

    const { onChunk, options } = capture();
    onChunk({ event: "error", error: "boom" });
    options.onComplete?.(undefined);

    expect(onError).toHaveBeenCalledTimes(1);
    expect(onComplete).not.toHaveBeenCalled();
  });

  it("completes once when both the done event and the transport [DONE] sentinel arrive", async () => {
    const onComplete = vi.fn();
    await streamStorySuggestions("novel-1", {}, { onSuggestions: vi.fn(), onComplete });

    const { options, onChunk } = capture();
    onChunk({ event: "done", is_final: true });
    options.onComplete?.(undefined);

    expect(onComplete).toHaveBeenCalledTimes(1);
  });

  it("forwards transport errors via onError", async () => {
    const onError = vi.fn();
    await streamStorySuggestions("novel-1", {}, { onSuggestions: vi.fn(), onError });

    capture().options.onError?.(new SSEStreamError("HTTP 500", "http", 500));

    expect(onError).toHaveBeenCalledTimes(1);
    expect(onError.mock.calls[0]?.[0]).toBeInstanceOf(SSEStreamError);
  });

  it("does not throw when onComplete and onError callbacks are omitted", async () => {
    await streamStorySuggestions("novel-1", {}, { onSuggestions: vi.fn() });

    const { options, onChunk } = capture();
    onChunk({ event: "done", is_final: true });
    onChunk({ event: "error", error: "boom" });
    options.onError?.(new SSEStreamError("HTTP 500", "http", 500));
    options.onComplete?.(undefined);
  });
});
