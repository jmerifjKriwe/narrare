import { HttpResponse, http } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { server } from "@/mocks/server";
import { setAccessToken } from "./client";
import { SSEStreamError } from "./streaming";
import {
  createSseSuggestionFetcher,
  NETWORK_RETRY_BACKOFF_MS,
  type SuggestConnectFn,
} from "./suggest";

describe("createSseSuggestionFetcher", () => {
  const CHAPTER_ID = "chapter-42";

  beforeEach(() => {
    setAccessToken("");
  });

  // --- 1. Happy path: accumulates SSE chunks into final suggestion ----------

  it("should accumulate SSE chunks into final suggestion", async () => {
    // Arrange — capture request body and stream 3 SSE chunks
    let capturedBody: Record<string, unknown> | null = null;

    server.use(
      http.post("*/api/v1/writing/chapters/:id/suggest", async ({ request }) => {
        capturedBody = (await request.json()) as Record<string, unknown>;

        const stream = new ReadableStream({
          start(controller) {
            controller.enqueue(
              new TextEncoder().encode('data: {"text":"The ","is_final":false}\n'),
            );
            controller.enqueue(
              new TextEncoder().encode('data: {"text":"old ","is_final":false}\n'),
            );
            controller.enqueue(
              new TextEncoder().encode('data: {"text":"house","is_final":true}\n'),
            );
            controller.enqueue(new TextEncoder().encode("data: [DONE]\n"));
            controller.close();
          },
        });

        return new HttpResponse(stream, {
          headers: {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
          },
        });
      }),
    );

    const fetcher = createSseSuggestionFetcher(CHAPTER_ID);

    // Act
    const result = await fetcher({
      textBefore: "Once upon a time, ",
      textAfter: " stood on the hill.",
      signal: new AbortController().signal,
    });

    // Assert — accumulated text matches concatenated chunks
    expect(result).toBe("The old house");

    // Assert — request body contains required fields
    expect(capturedBody).not.toBeNull();
    expect(capturedBody!.text_before).toBe("Once upon a time, ");
    expect(capturedBody!.text_after).toBe(" stood on the hill.");
    expect(capturedBody!.language).toBe("en");
  });

  // --- 2. Pre-aborted signal: rejects immediately ----------------------------

  it("should reject immediately when signal is already aborted", async () => {
    const controller = new AbortController();
    controller.abort(); // Pre-abort the signal before calling fetcher

    const fetcher = createSseSuggestionFetcher(CHAPTER_ID);

    await expect(
      fetcher({
        textBefore: "test",
        textAfter: "",
        signal: controller.signal,
      }),
    ).rejects.toThrow("Aborted");
  });

  // --- 3. Abort signal during stream: rejects with AbortError -----------------

  it("should reject with DOMException AbortError when signal is aborted", async () => {
    // Arrange — slow SSE stream that would run for ~100ms
    const abortController = new AbortController();

    server.use(
      http.post("*/api/v1/writing/chapters/:id/suggest", async () => {
        const stream = new ReadableStream({
          start(controller) {
            let count = 0;
            const interval = setInterval(() => {
              if (count >= 10) {
                clearInterval(interval);
                controller.close();
                return;
              }
              controller.enqueue(
                new TextEncoder().encode(`data: {"text":"chunk${count}","is_final":false}\n`),
              );
              count++;
            }, 10);
          },
        });

        return new HttpResponse(stream, {
          headers: { "Content-Type": "text/event-stream" },
        });
      }),
    );

    const fetcher = createSseSuggestionFetcher(CHAPTER_ID);

    // Act — abort after 50ms, before stream completes
    setTimeout(() => abortController.abort(), 50);

    let caughtError: unknown;
    try {
      await fetcher({
        textBefore: "test",
        textAfter: "",
        signal: abortController.signal,
      });
    } catch (error) {
      caughtError = error;
    }

    // Assert — rejected with DOMException named AbortError
    expect(caughtError).toBeInstanceOf(DOMException);
    expect((caughtError as DOMException).name).toBe("AbortError");
    expect((caughtError as DOMException).message).toBe("Aborted");
  });

  // --- 4. HTTP error: rejects with error -------------------------------------

  it("should reject with error containing status on HTTP error", async () => {
    // Arrange — server returns 500
    server.use(
      http.post("*/api/v1/writing/chapters/:id/suggest", async () => {
        return HttpResponse.json({ detail: "Internal Server Error" }, { status: 500 });
      }),
    );

    const fetcher = createSseSuggestionFetcher(CHAPTER_ID);

    // Act & Assert
    await expect(
      fetcher({
        textBefore: "test",
        textAfter: "",
        signal: new AbortController().signal,
      }),
    ).rejects.toThrow("HTTP 500");
  });

  // --- 5. Empty response: resolves with empty string -------------------------

  it("should resolve with empty string when SSE sends [DONE] immediately", async () => {
    // Arrange — stream with [DONE] and no text chunks
    server.use(
      http.post("*/api/v1/writing/chapters/:id/suggest", async () => {
        const stream = new ReadableStream({
          start(controller) {
            controller.enqueue(new TextEncoder().encode("data: [DONE]\n"));
            controller.close();
          },
        });

        return new HttpResponse(stream, {
          headers: { "Content-Type": "text/event-stream" },
        });
      }),
    );

    const fetcher = createSseSuggestionFetcher(CHAPTER_ID);

    // Act
    const result = await fetcher({
      textBefore: "test",
      textAfter: "",
      signal: new AbortController().signal,
    });

    // Assert
    expect(result).toBe("");
  });

  // --- 6. Language parameter: passed in request body -------------------------

  it("should pass custom language parameter in request body", async () => {
    // Arrange
    let capturedBody: Record<string, unknown> | null = null;

    server.use(
      http.post("*/api/v1/writing/chapters/:id/suggest", async ({ request }) => {
        capturedBody = (await request.json()) as Record<string, unknown>;

        const stream = new ReadableStream({
          start(controller) {
            controller.enqueue(new TextEncoder().encode("data: [DONE]\n"));
            controller.close();
          },
        });

        return new HttpResponse(stream, {
          headers: { "Content-Type": "text/event-stream" },
        });
      }),
    );

    // Create fetcher with German language
    const fetcher = createSseSuggestionFetcher(CHAPTER_ID, "de");

    // Act
    await fetcher({
      textBefore: "Es war einmal ",
      textAfter: "",
      signal: new AbortController().signal,
    });

    // Assert — language field is "de"
    expect(capturedBody).not.toBeNull();
    expect(capturedBody!.language).toBe("de");
  });

  // --- 6. Missing text_after: not sent when empty ----------------------------

  it("should omit text_after from request body when textAfter is empty", async () => {
    // Arrange
    let capturedBody: Record<string, unknown> | null = null;

    server.use(
      http.post("*/api/v1/writing/chapters/:id/suggest", async ({ request }) => {
        capturedBody = (await request.json()) as Record<string, unknown>;

        const stream = new ReadableStream({
          start(controller) {
            controller.enqueue(new TextEncoder().encode("data: [DONE]\n"));
            controller.close();
          },
        });

        return new HttpResponse(stream, {
          headers: { "Content-Type": "text/event-stream" },
        });
      }),
    );

    const fetcher = createSseSuggestionFetcher(CHAPTER_ID);

    // Act — textAfter is empty string
    await fetcher({
      textBefore: "Hello",
      textAfter: "",
      signal: new AbortController().signal,
    });

    // Assert — text_after is undefined (not in JSON body)
    expect(capturedBody).not.toBeNull();
    expect(capturedBody!.text_after).toBeUndefined();
  });
});

// =============================================================================
// Bounded network-retry (DI seam: fake connector, no real network I/O)
//
// The fetcher retries ONCE on transient connection-loss errors
// (`SSEStreamError.kind === "network"`) after a short abortable backoff, and
// never retries abort / http / parse / stream errors. These tests inject a fake
// connector via the `connect` DI seam (ADR-030) and drive attempt outcomes
// deterministically with fake timers.
// =============================================================================

type FakeOutcome =
  | { type: "error"; error: SSEStreamError }
  | { type: "success"; text?: string }
  | { type: "hang" }; // never settles — lets tests abort mid-flight

/**
 * Builds a fake SSE connector that fires outcomes in sequence. Outcomes are
 * delivered via microtask to approximate the real async transport. Returns the
 * connector plus a counter for asserting attempt counts.
 */
function makeFakeConnect(outcomes: FakeOutcome[]): {
  connect: SuggestConnectFn;
  getCalls: () => number;
} {
  let calls = 0;
  const connect: SuggestConnectFn = (options) => {
    const outcome = outcomes[Math.min(calls, outcomes.length - 1)];
    calls++;
    queueMicrotask(() => {
      switch (outcome.type) {
        case "error":
          options.onError(outcome.error);
          break;
        case "success":
          if (outcome.text) options.onChunk({ text: outcome.text, is_final: true });
          options.onComplete();
          break;
        case "hang":
          // Intentionally never settles — the caller controls resolution via abort.
          break;
      }
    });
  };
  return { connect, getCalls: () => calls };
}

describe("createSseSuggestionFetcher — bounded network retry", () => {
  const CHAPTER_ID = "chapter-42";
  const NETWORK_ERROR = new SSEStreamError("connection lost", "network");
  const HTTP_500_ERROR = new SSEStreamError("HTTP 500", "http", 500);

  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  // (a) network error then success → resolves, exactly 2 attempts
  it("retries once after a network error and resolves when the retry succeeds", async () => {
    const { connect, getCalls } = makeFakeConnect([
      { type: "error", error: NETWORK_ERROR },
      { type: "success", text: "The old house" },
    ]);
    const fetcher = createSseSuggestionFetcher(CHAPTER_ID, "en", connect);

    const promise = fetcher({
      textBefore: "x",
      textAfter: "",
      signal: new AbortController().signal,
    });

    // Advance past the abortable backoff so the single retry attempt runs.
    await vi.advanceTimersByTimeAsync(NETWORK_RETRY_BACKOFF_MS + 10);
    const result = await promise;

    expect(result).toBe("The old house");
    expect(getCalls()).toBe(2);
  });

  // (b) non-network error → rejects immediately, exactly 1 attempt
  it("does not retry on an HTTP error and rejects immediately", async () => {
    const { connect, getCalls } = makeFakeConnect([{ type: "error", error: HTTP_500_ERROR }]);
    const fetcher = createSseSuggestionFetcher(CHAPTER_ID, "en", connect);

    await expect(
      fetcher({
        textBefore: "x",
        textAfter: "",
        signal: new AbortController().signal,
      }),
    ).rejects.toThrow("HTTP 500");

    expect(getCalls()).toBe(1);
  });

  // (c) abort is not retried → rejects with AbortError, no extra attempt
  it("does not retry when the caller aborts mid-flight and rejects with AbortError", async () => {
    const { connect, getCalls } = makeFakeConnect([{ type: "hang" }]);
    const fetcher = createSseSuggestionFetcher(CHAPTER_ID, "en", connect);
    const controller = new AbortController();

    const promise = fetcher({
      textBefore: "x",
      textAfter: "",
      signal: controller.signal,
    });

    // Let attempt 0 start (flush the connect microtask), then abort.
    await vi.advanceTimersByTimeAsync(0);
    controller.abort();

    await expect(promise).rejects.toThrow("Aborted");
    expect(getCalls()).toBe(1);
  });

  // (d) both attempts fail with a network error → rejects, exactly 2 attempts
  it("does not retry more than once when both attempts fail with a network error", async () => {
    const { connect, getCalls } = makeFakeConnect([
      { type: "error", error: NETWORK_ERROR },
      { type: "error", error: NETWORK_ERROR },
    ]);
    const fetcher = createSseSuggestionFetcher(CHAPTER_ID, "en", connect);

    const promise = fetcher({
      textBefore: "x",
      textAfter: "",
      signal: new AbortController().signal,
    });
    // Attach the rejection handler BEFORE flushing timers: the promise rejects
    // while timers advance, and attaching the handler first avoids an
    // unhandled-rejection race (the promise is never left without a handler).
    const assertion = expect(promise).rejects.toThrow("connection lost");

    await vi.advanceTimersByTimeAsync(NETWORK_RETRY_BACKOFF_MS + 10);
    await assertion;

    expect(getCalls()).toBe(2);
  });

  // (e) abort during backoff stops the retry → rejects with AbortError
  it("stops the retry and rejects with AbortError when the signal aborts during backoff", async () => {
    const { connect, getCalls } = makeFakeConnect([
      { type: "error", error: NETWORK_ERROR },
      { type: "success", text: "should-not-happen" },
    ]);
    const fetcher = createSseSuggestionFetcher(CHAPTER_ID, "en", connect);
    const controller = new AbortController();

    const promise = fetcher({
      textBefore: "x",
      textAfter: "",
      signal: controller.signal,
    });

    // Flush attempt 0 (network error) so the fetcher enters the backoff wait,
    // then abort before the backoff elapses.
    await vi.advanceTimersByTimeAsync(0);
    controller.abort();

    await expect(promise).rejects.toThrow("Aborted");
    expect(getCalls()).toBe(1);
  });
});
